from __future__ import annotations

from http import HTTPStatus
from typing import Any

from app_error import AppError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app_layer_base.base.exceptions.base import CustomException
from app_layer_base.base.exceptions.db import database_exception_handler
from app_layer_base.core.log import logger
from app_layer_base.core.traceback import get_exception_traceback_str

__all__ = [
    "format_custom_exception",
    "format_mcp_error",
    "set_exception_handler",
]


# Helper to get request_id, returns None if not available
def _get_request_id(request: Request) -> str | None:
    try:
        return request.state.request_id
    except AttributeError:
        return None


def _should_include_advisory(request: Request) -> bool:
    """Determine whether structured agent advisory metadata should be included in HTTP response."""
    # 1. Explicit request header override (useful for AI agent tool invocations or test suites)
    agent_header = request.headers.get("x-agent-context", "").strip().lower()
    if agent_header in ("1", "true", "yes"):
        return True
    if agent_header in ("0", "false", "no"):
        return False

    # 2. Configured mode in AppSettings
    try:
        from app_layer_base.config import get_app_settings

        settings = get_app_settings()
        mode = settings.ERROR_ADVISORY_MODE.strip().lower()
        if mode in ("always", "development", "mcp"):
            return True
        if mode in ("never", "production"):
            return False
        # 'auto': show in non-production environments
        return not settings.is_production
    except Exception:
        return False


def format_custom_exception(
    exc: CustomException,
    include_advisory: bool = False,
    instance: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Format a CustomException into RFC 7807 problem details dictionary."""
    content: dict[str, Any] = {
        "type": "about:blank",
        "title": exc.title,
        "status": exc.status_code,
        "code": exc.code,
        "detail": exc.message,
        "instance": instance,
        "request_id": request_id,
    }
    if include_advisory:
        content["advisory"] = exc.advisory.to_dict()
    return content


def format_mcp_error(exc: AppError) -> str:
    """Format an exception into a prompt-friendly text block for Model Context Protocol tools."""
    return exc.render_mcp()


def _process_custom_exception(request: Request, exc: CustomException):
    advisory_lines = exc.lines()
    formatted_advisory = "\n".join(advisory_lines) if advisory_lines else f"Error: {exc.log_message}"

    if exc.trace:
        tb_log = get_exception_traceback_str(exc)
        logger.error(f"{formatted_advisory}\n{tb_log}")
    else:
        logger.error(formatted_advisory)

    include_advisory = _should_include_advisory(request)
    content = format_custom_exception(
        exc,
        include_advisory=include_advisory,
        instance=str(request.url.path),
        request_id=_get_request_id(request),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
    )


def _process_general_exception(request: Request, exc: Exception):
    tb_log = get_exception_traceback_str(exc)
    logger.error(f"Unknown Error: {exc}\n{tb_log}")
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    title = status_code.phrase
    detail = "An unexpected internal server error occurred."
    return JSONResponse(
        status_code=status_code,
        content={
            "type": "about:blank",
            "title": title,
            "status": status_code,
            "code": "INTERNAL_SERVER_ERROR",
            "detail": detail,
            "instance": str(request.url.path),
            "request_id": _get_request_id(request),
        },
    )


def set_exception_handler(app: FastAPI):
    @app.exception_handler(CustomException)
    async def custom_exception_handler(request: Request, exc: CustomException):
        return _process_custom_exception(request, exc)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        tb_log = get_exception_traceback_str(exc)
        logger.error(f"Error: {exc.detail}\n{tb_log}")
        try:
            # Get the standard title for the HTTP status code
            title = HTTPStatus(exc.status_code).phrase
        except ValueError:
            title = "HTTP Exception"

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": "about:blank",
                "title": title,
                "status": exc.status_code,
                "code": "HTTP_EXCEPTION",
                "detail": exc.detail,
                "instance": str(request.url.path),
                "request_id": _get_request_id(request),
            },
        )

    @app.exception_handler(NotImplementedError)
    async def not_implemented_exception_handler(request: Request, exc: NotImplementedError):
        status_code = HTTPStatus.NOT_IMPLEMENTED
        title = status_code.phrase
        detail = "The requested functionality is not implemented."
        logger.error(f"{title}: {detail} at {request.url.path}")
        return JSONResponse(
            status_code=status_code,
            content={
                "type": "about:blank",
                "title": title,
                "status": status_code,
                "code": "NOT_IMPLEMENTED",
                "detail": detail,
                "instance": str(request.url.path),
                "request_id": _get_request_id(request),
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        try:
            async with database_exception_handler():
                raise exc
        except CustomException as e:
            return _process_custom_exception(request, e)
        except Exception as e:
            return _process_general_exception(request, e)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return _process_general_exception(request, exc)

    return app
