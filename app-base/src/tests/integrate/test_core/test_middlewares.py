"""
Integration tests for core middlewares.
"""

import asyncio

import pytest
from app_base.core.middlewares import (
    cors_middleware,
    query_counter,
    request_id_middleware,
    security_header,
    timeout_middleware,
)
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


def create_test_app():
    app = FastAPI()

    # Order matters: Last added is the outermost in Starlette
    timeout_middleware.add_middleware(app, timeout=0.1)
    security_header.add_middleware(app)
    cors_middleware.add_middleware(app)
    query_counter.add_middleware(app)
    # RequestIDMiddleware is added LAST to be the OUTERMOST
    request_id_middleware.add_middleware(app)

    @app.get("/ok")
    async def ok_route():
        return {"status": "ok"}

    @app.get("/slow")
    async def slow_route():
        await asyncio.sleep(0.2)
        return {"status": "slow"}

    @app.get("/request-id")
    async def get_req_id(request: Request):
        return {"request_id": request.state.request_id}

    @app.get("/db-simulate")
    async def db_simulate():
        from app_base.core.middlewares.query_counter import query_count_ctx

        # Manually increment since we are not using a real Engine event in this test
        query_count_ctx.set(query_count_ctx.get() + 5)
        return {"status": "queried"}

    return app


@pytest.fixture
def client():
    return TestClient(create_test_app(), raise_server_exceptions=False)


async def test_request_id_is_outermost(client):
    """
    Verify RequestIDMiddleware is outermost by checking if it captures
    all internal middleware and handler request IDs.
    """
    from app_base.core.log import get_request_id
    from starlette.types import ASGIApp, Receive, Scope, Send

    app = FastAPI()

    inner_request_id = {"value": None}

    class CheckIDMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            # Capture the request ID set by the outer middleware
            inner_request_id["value"] = get_request_id()
            await self.app(scope, receive, send)

    # Add CheckIDMiddleware FIRST (innermost)
    app.add_middleware(CheckIDMiddleware)
    # Add RequestIDMiddleware LAST (outermost)
    request_id_middleware.add_middleware(app)

    @app.get("/")
    async def root():
        return {"id": get_request_id()}

    test_client = TestClient(app)
    response = test_client.get("/")

    # 1. Check if ID was available in the inner middleware
    assert inner_request_id["value"] is not None
    assert inner_request_id["value"] != "N/A"

    # 2. Check if the same ID reached the handler
    assert response.json()["id"] == inner_request_id["value"]

    # 3. Check if the same ID is in the header
    assert response.headers["x-request-id"] == inner_request_id["value"]


async def test_request_id_and_security_headers(client):
    response = client.get("/ok")
    assert response.status_code == 200

    # Request ID
    assert "x-request-id" in response.headers
    req_id = response.headers["x-request-id"]
    assert len(req_id) == 8

    # Verify request-id in response body from state
    id_resp = client.get("/request-id")
    assert id_resp.json()["request_id"] == id_resp.headers["x-request-id"]

    # Security Headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


async def test_timeout_middleware_integration(client):
    # This should trigger timeout (504)
    response = client.get("/slow")
    assert response.status_code == 504
    assert "exceeded limit" in response.text


async def test_cors_middleware_integration(client):
    from unittest.mock import patch

    from app_base.config.config import AppSettings

    # Create settings that allow the test origin
    mock_settings = AppSettings(CORS_ALLOWED_ORIGINS=["http://localhost"])

    with patch("app_base.core.middlewares.cors_middleware.get_app_settings", return_value=mock_settings):
        # We need to re-add the middleware or use a fresh app since it captures settings at init
        app = FastAPI()
        cors_middleware.add_middleware(app)

        @app.get("/ok")
        async def ok_route():
            return {"status": "ok"}

        test_client = TestClient(app)

        # Test preflight
        headers = {
            "Origin": "http://localhost",
            "Access-Control-Request-Method": "GET",
        }
        response = test_client.options("/ok", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost"


async def test_query_counter_middleware_integration(client):
    response = client.get("/db-simulate")
    assert response.status_code == 200
    assert response.headers["x-query-count"] == "5"

    # Next request should be zero
    response_ok = client.get("/ok")
    assert response_ok.headers["x-query-count"] == "0"
