from http import HTTPStatus

from app_error import Actor, Retry
from app_layer_base.base.exceptions.base import CustomException
from app_layer_base.base.exceptions.basic import BadRequestException
from app_layer_base.base.exceptions.handler import (
    set_exception_handler,
)
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient


def test_fastapi_advisory_exposure_uses_server_configuration(monkeypatch):
    app = FastAPI()
    set_exception_handler(app)
    router = APIRouter()

    @router.get("/error")
    async def trigger():
        raise CustomException(
            message="Database connection dropped",
            code="DB_DISCONNECTED",
            actor=Actor.TOOL,
            retry=Retry.SAFE,
            fix="restart db container",
            target_files=["docker-compose.yml"],
        )

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ERROR_ADVISORY_MODE", "auto")
    from app_layer_base.config import get_app_settings

    get_app_settings.cache_clear()
    try:
        # Request headers cannot expose operational details in production.
        response = client.get("/error", headers={"X-Agent-Context": "true"})
        assert response.status_code == 500
        assert "advisory" not in response.json()

        monkeypatch.setenv("ERROR_ADVISORY_MODE", "always")
        get_app_settings.cache_clear()
        response = client.get("/error")
        assert response.json()["advisory"]["mode"] == "AUTO"
    finally:
        get_app_settings.cache_clear()


def test_an_error_that_says_how_many_seconds_to_wait_sends_retry_after():
    app = FastAPI()
    set_exception_handler(app)

    @app.get("/locked")
    async def locked():
        raise CustomException(message="Too many attempts", status_code=HTTPStatus.TOO_MANY_REQUESTS, retry_after="240")

    @app.get("/later")
    async def later():
        raise CustomException(message="Quota resets later", retry_after="2026-09-22T00:00:00Z")

    @app.get("/plain")
    async def plain():
        raise BadRequestException()

    client = TestClient(app, raise_server_exceptions=False)

    assert client.get("/locked").headers["Retry-After"] == "240"
    # Only whole seconds make a valid header here; other forms stay in the advisory.
    assert "Retry-After" not in client.get("/later").headers
    assert "Retry-After" not in client.get("/plain").headers
