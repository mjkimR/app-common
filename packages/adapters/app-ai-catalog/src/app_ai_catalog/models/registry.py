from threading import RLock
from typing import Any

from app_ai_catalog.models.schemas import (
    AIAliasItem,
    AICatalogItem,
    AICollectionItem,
    AIModelItem,
    AIModelType,
    AIRouteItem,
    AIRouterSettings,
)


class AIModelRegistry:
    def __init__(self, raw_config: dict[str, Any]):
        self.router_settings = AIRouterSettings(**raw_config.get("router", {}))
        self.models = self._load_items(raw_config.get("models", []), AIModelItem, "models")
        self.routes = self._load_items(raw_config.get("routes", []), AIRouteItem, "routes")
        self.aliases = self._load_items(raw_config.get("aliases", []), AIAliasItem, "aliases")
        self.collections = self._load_items(raw_config.get("collections", []), AICollectionItem, "collections")
        self._dimension_lock = RLock()
        self._dynamic_dimensions: dict[str, int] = {}
        self._validate()

    @staticmethod
    def _load_items(items: list[dict[str, Any]], item_type: type, section: str) -> dict[str, Any]:
        loaded = {}
        for item in items:
            if "name" not in item:
                raise ValueError(f"Each {section} item must have a 'name' field.")
            name = item["name"]
            if name in loaded:
                raise ValueError(f"Duplicate item name in {section}: '{name}'.")
            try:
                loaded[name] = item_type(**item)
            except Exception as e:
                raise ValueError(f"Error in {section} item '{name}': {e!s}") from e
        return loaded

    def _validate(self) -> None:
        all_names = set()
        for section_name, section in (
            ("models", self.models),
            ("routes", self.routes),
            ("aliases", self.aliases),
            ("collections", self.collections),
        ):
            conflicts = all_names.intersection(section.keys())
            if conflicts:
                raise ValueError(f"Catalog names must be unique. Conflicts in {section_name}: {sorted(conflicts)}")
        all_names.update(section.keys())

        for name, alias in self.aliases.items():
            self._validate_alias_chain(name)
            target = self._resolve_target(alias.target)
            if alias.type != target.type:
                raise ValueError(
                    f"Configuration Error: Alias '{name}' type ({alias.type.value}) does not match target "
                    f"'{alias.target}' type ({target.type.value})."
                )

        for name, collection in self.collections.items():
            if collection.default is not None and collection.default not in collection.members:
                raise ValueError(
                    f"Configuration Error: Collection '{name}' default '{collection.default}' is not in members."
                )
            for member_name in collection.members:
                member = self._resolve_target(member_name)
                if member.type != collection.type:
                    raise ValueError(
                        f"Configuration Error: Collection '{name}' member '{member_name}' type "
                        f"({member.type.value}) does not match collection type ({collection.type.value})."
                    )

    def _validate_alias_chain(self, alias_name: str) -> None:
        visited = set()
        chain = []
        current = alias_name
        while current in self.aliases:
            if current in visited:
                chain.append(current)
                raise ValueError(
                    f"Configuration Error: Circular reference detected in alias chain: {' -> '.join(chain)}"
                )
            visited.add(current)
            chain.append(current)
            current = self.aliases[current].target

    def _resolve_target(self, name: str) -> AIModelItem | AIRouteItem:
        resolved_name = name
        visited = set()
        while resolved_name in self.aliases:
            if resolved_name in visited:
                raise ValueError(f"Configuration Error: Circular reference detected for alias '{name}'.")
            visited.add(resolved_name)
            resolved_name = self.aliases[resolved_name].target

        if resolved_name in self.models:
            return self.models[resolved_name]
        if resolved_name in self.routes:
            return self.routes[resolved_name]
        raise ValueError(f"Model, route, or alias '{name}' not found.")

    def resolve_name(self, name: str, expected_type: AIModelType | str | None = None) -> str:
        target = self._resolve_target(name)
        req_type = AIModelType(expected_type) if isinstance(expected_type, str) else expected_type
        if req_type is not None and target.type != req_type:
            raise ValueError(
                f"Type mismatch: Requested item '{name}' is '{target.type.value}', "
                f"but operation expects '{req_type.value}'."
            )
        return target.name

    def get_dimension(self, name: str) -> int | None:
        target = self._resolve_target(name)
        if target.type != AIModelType.EMBEDDING:
            raise ValueError(
                f"Type mismatch: Requested item '{name}' is '{target.type.value}', "
                f"but operation expects '{AIModelType.EMBEDDING.value}'."
            )
        configured_dimension = target.dimension
        if configured_dimension is not None:
            return configured_dimension
        with self._dimension_lock:
            return self._dynamic_dimensions.get(target.name)

    def cache_dimension(self, name: str, dimension: int) -> None:
        target = self._resolve_target(name)
        if target.type != AIModelType.EMBEDDING:
            raise ValueError(
                f"Type mismatch: Requested item '{name}' is '{target.type.value}', "
                f"but operation expects '{AIModelType.EMBEDDING.value}'."
            )
        if dimension <= 0:
            raise ValueError(f"Embedding dimension must be positive, got {dimension}.")
        with self._dimension_lock:
            self._dynamic_dimensions[target.name] = dimension

    def get_router_model_list(self) -> list[dict[str, Any]]:
        model_list = []
        seen = set()

        def add_model(item: dict[str, Any]) -> None:
            key = self._router_model_key(item)
            if key in seen:
                return
            seen.add(key)
            model_list.append(item)

        for model in self.models.values():
            add_model(model.to_router_model())
        for route in self.routes.values():
            for item in route.to_router_models():
                add_model(item)
        return model_list

    @classmethod
    def _router_model_key(cls, item: dict[str, Any]) -> tuple[Any, ...]:
        return (
            item.get("model_name"),
            cls._freeze(item.get("litellm_params", {})),
            cls._freeze(item.get("model_info", {})),
            item.get("tpm"),
            item.get("rpm"),
        )

    @classmethod
    def _freeze(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return tuple(sorted((key, cls._freeze(item)) for key, item in value.items()))
        if isinstance(value, list):
            return tuple(cls._freeze(item) for item in value)
        return value

    def get_catalog(self, model_type: AIModelType | str) -> list[AICatalogItem]:
        target_type = AIModelType(model_type) if isinstance(model_type, str) else model_type
        results: list[AICatalogItem] = []
        for section in (self.models, self.routes, self.aliases):
            for item in section.values():
                if item.type == target_type:
                    results.append(item.to_catalog_item())
        return sorted(results, key=lambda item: (item.kind, item.name))

    def get_collection(self, name: str) -> AICollectionItem:
        if name not in self.collections:
            raise ValueError(f"Collection '{name}' not found.")
        return self.collections[name]

    def get_collections(self, model_type: AIModelType | str | None = None) -> list[AICollectionItem]:
        if model_type is None:
            return sorted(self.collections.values(), key=lambda item: item.name)
        target_type = AIModelType(model_type) if isinstance(model_type, str) else model_type
        return sorted(
            [collection for collection in self.collections.values() if collection.type == target_type],
            key=lambda item: item.name,
        )
