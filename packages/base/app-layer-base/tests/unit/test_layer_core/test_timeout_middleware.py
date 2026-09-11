import asyncio

from app_layer_base.core.middlewares.timeout_middleware import TimeoutMiddleware, add_middleware
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_add_middleware_default_timeout():
    app = FastAPI()
    add_middleware(app)

    middleware_classes = [m.cls for m in app.user_middleware]
    assert TimeoutMiddleware in middleware_classes


def test_add_middleware_custom_timeout():
    app = FastAPI()
    add_middleware(app, timeout=30)

    timeout_mw = next((m for m in app.user_middleware if m.cls == TimeoutMiddleware), None)
    assert timeout_mw is not None
    assert timeout_mw.kwargs["timeout"] == 30


def test_request_completes_within_timeout():
    app = FastAPI()
    add_middleware(app, timeout=30)

    @app.get("/fast")
    async def fast_route():
        return {"message": "ok"}

    client = TestClient(app)
    response = client.get("/fast")
    assert response.status_code == 200


def test_request_timeout_returns_504():
    app = FastAPI()
    add_middleware(app, timeout=0.001)

    @app.get("/slow")
    async def slow_route():
        await asyncio.sleep(0.01)
        return {"message": "ok"}

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/slow")
    assert response.status_code == 504


def test_timeout_response_body():
    app = FastAPI()
    add_middleware(app, timeout=0.001)

    @app.get("/slow")
    async def slow_route():
        await asyncio.sleep(0.01)
        return {"message": "ok"}

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/slow")
    assert "exceeded limit" in response.text


def test_timeout_logs_error_on_timeout():
    from unittest.mock import patch

    app = FastAPI()
    add_middleware(app, timeout=0.001)

    @app.get("/slow")
    async def slow_route():
        await asyncio.sleep(0.01)
        return {"message": "ok"}

    client = TestClient(app, raise_server_exceptions=False)
    with patch("app_layer_base.core.middlewares.timeout_middleware.logger") as mock_logger:
        client.get("/slow")
        mock_logger.error.assert_called_once()
        assert "timeout" in mock_logger.error.call_args.args[0].lower()
