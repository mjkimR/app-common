from app_base.adapter.nosql_db.interface import NoSQLDBProvider

_NOSQL_DB_REGISTRY: dict[str, type[NoSQLDBProvider]] = {}


def register_nosql_db[T: NoSQLDBProvider](kind: str):
    def decorator(cls: type[T]) -> type[T]:
        _NOSQL_DB_REGISTRY[kind] = cls
        return cls

    return decorator


def get_provider_cls(kind: str) -> type[NoSQLDBProvider]:
    provider_cls = _NOSQL_DB_REGISTRY.get(kind)
    if not provider_cls:
        raise ValueError(f"NoSQL DB provider for kind '{kind}' is not registered.")
    return provider_cls
