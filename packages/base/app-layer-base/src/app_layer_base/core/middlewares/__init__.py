from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import cors_middleware, query_counter, request_id_middleware, security_header, timeout_middleware

__all__ = [
    "cors_middleware",
    "query_counter",
    "request_id_middleware",
    "security_header",
    "timeout_middleware",
]

_lazy_imports: dict[str, str] = {
    "cors_middleware": f"{__name__}.cors_middleware",
    "query_counter": f"{__name__}.query_counter",
    "request_id_middleware": f"{__name__}.request_id_middleware",
    "security_header": f"{__name__}.security_header",
    "timeout_middleware": f"{__name__}.timeout_middleware",
}


def __getattr__(name: str):
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
