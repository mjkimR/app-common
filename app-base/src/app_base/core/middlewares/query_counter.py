from contextvars import ContextVar
from typing import Callable

from fastapi import FastAPI, Request, Response
from sqlalchemy import event
from sqlalchemy.engine import Engine
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

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


class QueryCounterMiddleware(BaseHTTPMiddleware):
    QUERY_COUNT_WARNING_THRESHOLD: int = 20

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        event.listen(Engine, "before_cursor_execute", _before_cursor_execute)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Initialize counter (starts at 0)
        token = query_count_ctx.set(0)

        # 2. Process request (DB queries that occur here are counted)
        response = await call_next(request)

        # 3. Get the result
        query_count = query_count_ctx.get()

        # 4. Add to response headers (can be checked by frontend or client)
        response.headers["X-Query-Count"] = str(query_count)

        # (Optional) If there are too many queries, print a warning log (for detecting N+1 problems)
        if query_count > self.QUERY_COUNT_WARNING_THRESHOLD:
            logger.warning(f"Too many queries ({query_count}) in request: {request.method} {request.url.path}")

        # 5. Clean up context
        query_count_ctx.reset(token)

        return response


def add_middleware(app: FastAPI):
    """Add query counter middleware to FastAPI app"""
    app.add_middleware(QueryCounterMiddleware)
