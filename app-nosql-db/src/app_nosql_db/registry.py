import importlib
from typing import ClassVar

from app_nosql_db.config import NoSQLDBProviderType
from app_nosql_db.interface import NoSQLDBProvider


class NoSQLDBRegistry:
    """Registry for NoSQL database providers."""

    _PROVIDER_MODULES: ClassVar[dict[NoSQLDBProviderType, str]] = {
        NoSQLDBProviderType.FIRESTORE: "app_nosql_db.providers.firestore",
        NoSQLDBProviderType.MONGODB: "app_nosql_db.providers.mongodb",
    }

    _PROVIDER_CLASSES: ClassVar[dict[NoSQLDBProviderType, str]] = {
        NoSQLDBProviderType.FIRESTORE: "FirestoreProvider",
        NoSQLDBProviderType.MONGODB: "MongoDBProvider",
    }

    @classmethod
    def get_provider_cls(cls, provider: NoSQLDBProviderType | str) -> type[NoSQLDBProvider]:
        try:
            provider_enum = NoSQLDBProviderType(provider)
        except ValueError as exc:
            raise ValueError(f"Unsupported NoSQL DB provider: {provider}") from exc

        if provider_enum not in cls._PROVIDER_MODULES:
            raise ValueError(f"NoSQL DB provider for kind '{provider_enum}' is not registered.")

        module_path = cls._PROVIDER_MODULES[provider_enum]
        class_name = cls._PROVIDER_CLASSES[provider_enum]

        module = importlib.import_module(module_path)
        return getattr(module, class_name)
