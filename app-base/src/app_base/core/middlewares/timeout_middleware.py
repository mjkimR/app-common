import asyncio

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app_base.core.log import logger


class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout: int = 60):
        super().__init__(app)
        self.timeout = timeout

    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.error(f"Request timeout: {request.url.path}")
            return Response("Request processing time exceeded limit", status_code=504)


def add_middleware(app: FastAPI):
    """Add timeout middleware to FastAPI app"""
    app.add_middleware(TimeoutMiddleware)
