from unittest.mock import patch

from app_layer_base.core.middlewares.query_counter import (
    QueryCounterMiddleware,
    _before_cursor_execute,
    add_middleware,
    query_count_ctx,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_add_middleware():
    app = FastAPI()
    add_middleware(app)

    middleware_classes = [m.cls for m in app.user_middleware]
    assert QueryCounterMiddleware in middleware_classes


def test_before_cursor_execute_increments_count():
    token = query_count_ctx.set(0)
    try:
        _before_cursor_execute(None, None, None, None, None, False)
        assert query_count_ctx.get() == 1

        _before_cursor_execute(None, None, None, None, None, False)
        assert query_count_ctx.get() == 2
    finally:
        query_count_ctx.reset(token)


def test_response_contains_x_query_count_header():
    app = FastAPI()
    add_middleware(app)

    @app.get("/test")
    async def test_route():
        return {"message": "ok"}

    client = TestClient(app)
    response = client.get("/test")
    assert "x-query-count" in response.headers


def test_query_count_header_is_zero_without_db():
    app = FastAPI()
    add_middleware(app)

    @app.get("/test")
    async def test_route():
        return {"message": "ok"}

    client = TestClient(app)
    response = client.get("/test")
    assert response.headers["x-query-count"] == "0"


def test_query_count_resets_between_requests():
    app = FastAPI()
    add_middleware(app)

    @app.get("/test")
    async def test_route():
        # Directly increment the query counter to simulate DB queries
        current = query_count_ctx.get()
        query_count_ctx.set(current + 3)
        return {"message": "ok"}

    client = TestClient(app)
    r1 = client.get("/test")
    r2 = client.get("/test")

    # Each request should be counted independently
    assert r1.headers["x-query-count"] == r2.headers["x-query-count"]


def test_warning_logged_when_too_many_queries():
    app = FastAPI()
    add_middleware(app)

    @app.get("/heavy")
    async def heavy_route():
        query_count_ctx.set(21)
        return {"message": "ok"}

    client = TestClient(app)
    with patch("app_layer_base.core.middlewares.query_counter.logger") as mock_logger:
        client.get("/heavy")
        mock_logger.warning.assert_called_once()
        assert "Too many queries" in mock_logger.warning.call_args.args[0]


def test_no_warning_below_threshold(caplog):
    import logging

    app = FastAPI()
    add_middleware(app)

    @app.get("/light")
    async def light_route():
        return {"message": "ok"}

    client = TestClient(app)
    with caplog.at_level(logging.WARNING):
        client.get("/light")

    assert "Too many queries" not in caplog.text
