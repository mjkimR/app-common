import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app_base.core.log import logger, set_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to each request"""

    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]

        # Set request ID in context
        set_request_id(request_id)

        # Add request ID to request state for access in endpoints
        request.state.request_id = request_id

        # Log request start
        logger.debug(
            f"Request started: {request.method} {request.url.path}",
            extra={"request_id": request_id},
        )

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        # Log request completion
        logger.debug(
            f"Request completed: {request.method} {request.url.path} - Status: {response.status_code}",
            extra={"request_id": request_id},
        )

        return response


def add_middleware(app: FastAPI):
    """Add request ID middleware to FastAPI app"""
    app.add_middleware(RequestIDMiddleware)
