from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app_base.base.exceptions.base import CustomException
from app_base.base.exceptions.db import database_exception_handler
from app_base.core.log import logger


# Helper to get request_id, returns None if not available
def _get_request_id(request: Request) -> str | None:
    try:
        return request.state.request_id
    except AttributeError:
        return None


def _process_custom_exception(request: Request, exc: CustomException):
    if exc.trace:
        logger.exception(f"Error: {exc.log_message}")
    else:
        logger.error(f"Error: {exc.log_message}")

    # RFC 7807
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "about:blank",
            "title": exc.title,
            "status": exc.status_code,
            "detail": exc.message,
            "instance": str(request.url.path),
            "request_id": _get_request_id(request),
        },
    )


def _process_general_exception(request: Request, exc: Exception):
    logger.exception(f"Unknown Error: {exc}")
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    title = status_code.phrase
    detail = "An unexpected internal server error occurred."
    return JSONResponse(
        status_code=status_code,
        content={
            "type": "about:blank",
            "title": title,
            "status": status_code,
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
        logger.exception(f"Error: {exc.detail}")
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
                "detail": detail,
                "instance": str(request.url.path),
                "request_id": _get_request_id(request),
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.exception(f"ValueError: {exc}")
        status_code = HTTPStatus.BAD_REQUEST
        title = status_code.phrase
        detail = "Invalid input provided."
        return JSONResponse(
            status_code=status_code,
            content={
                "type": "about:blank",
                "title": title,
                "status": status_code,
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
