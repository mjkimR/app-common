from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .local import LocalStorageProvider
    from .s3 import S3StorageProvider

__all__ = ["LocalStorageProvider", "S3StorageProvider"]

_lazy_imports: dict[str, str] = {
    "LocalStorageProvider": ".local",
    "S3StorageProvider": ".s3",
}


def __getattr__(name: str):
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name], package=__name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
