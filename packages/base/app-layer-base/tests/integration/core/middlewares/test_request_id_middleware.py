from unittest.mock import patch

from app_layer_base.core.middlewares.request_id_middleware import RequestIDMiddleware, add_middleware
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


def _make_app() -> TestClient:
    app = FastAPI()
    add_middleware(app)

    @app.get("/test")
    async def test_route():
        return {"message": "ok"}

    return TestClient(app)


def test_add_middleware():
    app = FastAPI()
    add_middleware(app)

    middleware_classes = [m.cls for m in app.user_middleware]
    assert RequestIDMiddleware in middleware_classes


def test_response_contains_x_request_id_header():
    client = _make_app()
    response = client.get("/test")
    assert "x-request-id" in response.headers


def test_request_id_is_8_chars():
    client = _make_app()
    response = client.get("/test")
    request_id = response.headers.get("x-request-id")
    assert len(request_id) == 8


def test_request_id_is_unique_per_request():
    client = _make_app()
    ids = {client.get("/test").headers.get("x-request-id") for _ in range(10)}
    # Most requests out of 10 should generate unique IDs
    assert len(ids) > 1


def test_request_id_stored_in_scope_state():
    app = FastAPI()
    add_middleware(app)

    captured_request_id = {}

    @app.get("/test")
    async def test_route(request: Request):
        captured_request_id["value"] = request.state.request_id
        return {"message": "ok"}

    client = TestClient(app)
    response = client.get("/test")

    response_id = response.headers.get("x-request-id")
    assert captured_request_id["value"] == response_id


def test_request_id_logged_on_start_and_end():
    with patch("app_layer_base.core.middlewares.request_id_middleware.logger") as mock_logger:
        client = _make_app()
        client.get("/test")

        debug_messages = [call.args[0] for call in mock_logger.debug.call_args_list]
        assert any("Request started" in msg for msg in debug_messages)
        assert any("Request completed" in msg for msg in debug_messages)
