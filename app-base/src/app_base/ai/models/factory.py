import os
import re
from functools import lru_cache
from threading import Lock
from typing import TYPE_CHECKING, Any

import yaml

from app_base.ai.models.factory_embedding import EmbeddingFactory
from app_base.ai.models.factory_llm import LLMFactory
from app_base.ai.models.schemas import (
    AICatalogItem,
    AIModelAliasItem,
    AIModelGroupItem,
    AIModelItem,
    AIModelType,
)
from app_base.config import get_app_path
from app_base.core.log import logger

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from langchain_core.language_models import BaseChatModel


class ConfigLoader:
    @staticmethod
    def load_yaml_with_env(path: str) -> dict[str, Any]:
        pattern = re.compile(r"\$\{(\w+)}")

        def replace_env(match):
            env_var = match.group(1)
            value = os.environ.get(env_var)
            if value is None:
                logger.warning(f"Environment variable '{env_var}' is not set but required in config.")
            return value

        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            content = pattern.sub(replace_env, content)
            return yaml.safe_load(content)


class AIModelFactory:
    _instance = None
    _lock = Lock()
    DEFAULT_PATH = os.path.join(get_app_path(), "catalog.yml")

    def __new__(cls, config_path: str = DEFAULT_PATH):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(AIModelFactory, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: str = DEFAULT_PATH):
        if getattr(self, "_initialized", False):
            return

        logger.info(f"[System] Loading Catalog from {config_path}...")
        raw_config = ConfigLoader.load_yaml_with_env(config_path)

        self.models: dict[str, AIModelItem] = {}
        self.aliases: dict[str, AIModelAliasItem] = {}
        self.groups: dict[str, AIModelGroupItem] = {}

        self._initial_dictionaries(raw_config)

        self._validate_config()

        self.llm_factory = LLMFactory()
        self.embedding_factory = EmbeddingFactory()

        self._config_path = config_path  # Save path for reload
        self._initialized = True

    def _initial_dictionaries(self, raw_config: dict[str, Any]):
        for item in raw_config.get("models", []):
            if "name" not in item:
                raise ValueError("Each models item must have a 'name' field.")
            name = item["name"]
            try:
                self.models[name] = AIModelItem(**item)
            except Exception as e:
                raise ValueError(f"Error in models item '{name}': {str(e)}") from e
        for item in raw_config.get("aliases", []):
            if "name" not in item:
                raise ValueError("Each alias item must have a 'name' field.")
            name = item["name"]
            try:
                self.aliases[name] = AIModelAliasItem(**item)
            except Exception as e:
                raise ValueError(f"Error in alias item '{name}': {str(e)}") from e
        catalogs = {
            **{name: model.to_catalog_item() for name, model in self.models.items()},
            **{name: alias.to_catalog_item() for name, alias in self.aliases.items()},
        }
        for item in raw_config.get("groups", []):
            if "name" not in item:
                raise ValueError("Each group item must have a 'name' field.")
            name = item["name"]
            try:
                self.groups[name] = AIModelGroupItem.from_data(item, catalogs)
            except Exception as e:
                raise ValueError(f"Error in group item '{name}': {str(e)}") from e

    def _validate_config(self):
        """Validate the integrity and type correctness of the configuration file."""
        # 1. Alias Item Validation
        for name, alias in self.aliases.items():
            target_name = alias.target

            # (1) Target Existence Check
            if target_name not in self.models and target_name not in self.aliases:
                raise ValueError(f"Configuration Error: Alias '{name}' refers to non-existent target '{target_name}'.")
            target = self.models[target_name] if target_name in self.models else self.aliases[target_name]

            # (2) Type Consistency Check (Alias Type vs Target Type)
            if alias.type != target.type:
                raise ValueError(
                    f"Configuration Error: Alias '{name}' type ({alias.type.value}) does not match final target '{target_name}' type ({target.type.value})."
                )

            # (3) Fallback Validation
            for fb_name in alias.fallbacks:
                if fb_name in self.models:
                    fb_type = self.models[fb_name].type
                elif fb_name in self.aliases:
                    fb_type = self.aliases[fb_name].type
                else:
                    raise ValueError(
                        f"Configuration Error: Alias '{name}' has fallback to non-existent model/alias '{fb_name}'."
                    )
                if alias.type != fb_type:
                    raise ValueError(
                        f"Configuration Error: Alias '{name}' fallback '{fb_name}' type ({fb_type.value}) does not match alias type ({alias.type.value})."
                    )

            # (4) Self-referential Fallback Check
            if name in alias.fallbacks:
                raise ValueError(f"Configuration Error: Alias '{name}' cannot have itself as a fallback.")

            # (5) Circular Target Check
            visited = set()
            current = name
            chain = []
            while current in self.aliases:
                if current in visited:
                    chain.append(current)
                    raise ValueError(
                        f"Configuration Error: Circular reference detected in alias target chain: {' -> '.join(chain)}"
                    )
                visited.add(current)
                chain.append(current)
                current = self.aliases[current].target

        # 2. Name Conflict Check
        model_names = set(self.models.keys())
        alias_names = set(self.aliases.keys())
        conflicts = model_names.intersection(alias_names)
        if conflicts:
            raise ValueError(f"Configuration Error: Model names must be unique. Conflicts found: {conflicts}")

    @lru_cache(maxsize=32)
    def _get_llm(self, name: str) -> "BaseChatModel":
        config = self._resolve_config(name, AIModelType.LLM)
        return self.llm_factory.create_model(config)

    def get_llm(self, name: str, **kwargs) -> "BaseChatModel":
        """
        LRU Cache applied:
        If the same 'name' is requested, returns the cached object instead of executing the function
        Returns the LLM model instance for the given name, with optional parameter binding.

        Example:
            llm = model_factory.get_llm("gpt-4", temperature=0.5)

        [Note]
        - Fallback models are NOT included here. Use `get_fallback_llms` to get them if needed. (model.with_fallbacks() is not a BaseChatModel)
        """
        model = self._get_llm(name)
        if kwargs:
            model = model.bind(**kwargs)
        return model  # type: ignore

    def get_fallback_llms(self, name: str) -> list["BaseChatModel"]:
        """
        [Helper] Returns the list of fallback models configured for this model.

        [Note]
        - Only one-level fallback is supported; multi-level fallback chains are not supported.
        """
        if name in self.aliases:
            config = self.aliases[name]
            # Verify the alias is an LLM alias
            if config.type != AIModelType.LLM:
                raise ValueError(
                    f"Type mismatch: Alias '{name}' is type '{config.type.value}', but LLM fallbacks were requested."
                )
        elif name in self.models:
            # A base model can also have fallbacks defined.
            config = self.models[name]
            if config.type != AIModelType.LLM:
                raise ValueError(
                    f"Type mismatch: Model '{name}' is type '{config.type.value}', but LLM fallbacks were requested."
                )
        else:
            raise ValueError(f"Model or Alias '{name}' not found in models or aliases.")

        fallback_models = []
        for fb_name in config.fallbacks:
            fallback_models.append(self.get_llm(fb_name))

        return fallback_models

    @lru_cache(maxsize=8)
    def _get_embedding(self, name: str) -> "Embeddings":
        config = self._resolve_config(name, AIModelType.EMBEDDING)
        return self.embedding_factory.create_model(config)

    def get_embedding(self, name: str) -> "Embeddings":
        model = self._get_embedding(name)
        return model

    def get_embedding_dimension(self, name: str) -> int:
        """
        Returns the dimension of the embedding model.
        """
        config = self._resolve_config(name, AIModelType.EMBEDDING)
        if config.dimension:
            return config.dimension
        return self.embedding_factory.get_dimension(config)

    def _resolve_config(self, name: str, expected_type: AIModelType | str | None = None) -> AIModelItem:
        """Name resolution"""
        # 1. Alias Resolution (If name is an alias, resolve to target model)
        while name in self.aliases:
            alias = self.aliases[name]
            name = alias.target

        # 2. Existence Check
        if name not in self.models:
            raise ValueError(f"Model '{name}' not found in models.")

        config = self.models[name]

        # 3. Usage Check
        if expected_type:
            req_type = AIModelType(expected_type) if isinstance(expected_type, str) else expected_type
            actual_type = config.type
            if actual_type != req_type:
                raise ValueError(
                    f"Type mismatch: Requested model '{name}' is '{actual_type.value}', "
                    f"but operation expects '{req_type.value}'."
                )

        return config

    def reload(self):
        """When the config file changes, clear the cache and reload"""
        logger.info("[System] Reloading Catalog...")
        self._get_llm.cache_clear()
        self._get_embedding.cache_clear()
        self._initialized = False
        self.__init__(self._config_path)

    def get_catalog(self, model_type: AIModelType | str) -> list[AICatalogItem]:
        target_type = AIModelType(model_type) if isinstance(model_type, str) else model_type
        results: list[AICatalogItem] = []

        # 1. Models
        for info in self.models.values():
            if info.type == target_type:
                results.append(info.to_catalog_item())

        # 2. Aliases
        for info in self.aliases.values():
            if info.type == target_type:
                results.append(info.to_catalog_item())

        return sorted(results, key=lambda x: (x.kind == "alias", x.provider, x.name))

    def get_group(self, name: str) -> AIModelGroupItem:
        if name not in self.groups:
            raise ValueError(f"Model group '{name}' not found.")
        return self.groups[name]
