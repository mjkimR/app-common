import asyncio

from fastapi import FastAPI
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app_layer_base.core.log import logger


class TimeoutMiddleware:
    """Pure ASGI Middleware to enforce request timeout"""

    def __init__(self, app: ASGIApp, timeout: float = 60.0):
        self.app = app
        self.timeout = timeout

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            await asyncio.wait_for(self.app(scope, receive, send), timeout=self.timeout)
        except TimeoutError:
            path = scope.get("path", "")
            logger.error(f"Request timeout: {path}")
            response = PlainTextResponse("Request processing time exceeded limit", status_code=504)
            await response(scope, receive, send)


def add_middleware(app: FastAPI, timeout: float = 60.0):
    """Add timeout middleware to FastAPI app"""
    app.add_middleware(TimeoutMiddleware, timeout=timeout)
