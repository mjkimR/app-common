import uuid

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app_base.core.log import logger, set_request_id


class RequestIDMiddleware:
    """Pure ASGI Middleware to add request ID to each request"""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # Only process HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]

        # Set request ID in context
        set_request_id(request_id)

        # Store request ID in scope state for access in endpoints
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        # Extract request info from scope
        method = scope.get("method", "")
        path = scope.get("path", "")

        # Log request start
        logger.debug(
            f"Request started: {method} {path}",
            extra={"request_id": request_id},
        )

        status_code: int | None = None

        async def send_wrapper(message: Message):
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = message.get("status")
                # Add request ID to response headers
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}

            await send(message)

            # Log request completion when response body is sent
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                logger.debug(
                    f"Request completed: {method} {path} - Status: {status_code}",
                    extra={"request_id": request_id},
                )

        await self.app(scope, receive, send_wrapper)


def add_middleware(app: FastAPI):
    """Add request ID middleware to FastAPI app"""
    app.add_middleware(RequestIDMiddleware)
