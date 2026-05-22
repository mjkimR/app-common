from contextvars import ContextVar

from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.engine import Engine
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app_base.core.log import logger

query_count_ctx: ContextVar[int] = ContextVar("query_count", default=0)


def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """SQLAlchemy event listener: called right before a query is executed."""
    # Increment the query count for the current context by 1
    try:
        current_count = query_count_ctx.get()
        query_count_ctx.set(current_count + 1)
    except LookupError:
        pass


class QueryCounterMiddleware:
    """Pure ASGI Middleware to count SQL queries per request"""

    QUERY_COUNT_WARNING_THRESHOLD: int = 20

    def __init__(self, app: ASGIApp):
        self.app = app
        event.listen(Engine, "before_cursor_execute", _before_cursor_execute)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1. Initialize counter (starts at 0)
        token = query_count_ctx.set(0)

        method = scope.get("method", "")
        path = scope.get("path", "")
        query_count = 0

        async def send_wrapper(message: Message):
            nonlocal query_count

            if message["type"] == "http.response.start":
                # 3. Get the result
                query_count = query_count_ctx.get()

                # 4. Add to response headers
                headers = list(message.get("headers", []))
                headers.append((b"x-query-count", str(query_count).encode()))
                message = {**message, "headers": headers}

            await send(message)

            if (
                message["type"] == "http.response.body"
                and not message.get("more_body", False)
                and query_count > self.QUERY_COUNT_WARNING_THRESHOLD
            ):
                logger.warning(f"Too many queries ({query_count}) in request: {method} {path}")

        try:
            # 2. Process request (DB queries that occur here are counted)
            await self.app(scope, receive, send_wrapper)
        finally:
            # 5. Clean up context
            query_count_ctx.reset(token)


def add_middleware(app: FastAPI):
    """Add query counter middleware to FastAPI app"""
    app.add_middleware(QueryCounterMiddleware)
