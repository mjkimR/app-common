from http import HTTPStatus

from app_error import ActionMode, Actor, AppError, Retry
from app_layer_base.base.exceptions.base import CustomException
from app_layer_base.base.exceptions.basic import BadRequestException, NotFoundException
from app_layer_base.base.exceptions.handler import (
    format_custom_exception,
    format_mcp_error,
    set_exception_handler,
)
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient


def test_custom_exception_inherits_app_error():
    exc = CustomException(
        message="Resource not accessible",
        code="ACCESS_DENIED",
        actor=Actor.USER,
        retry=Retry.AFTER_FIX,
        fix="request permissions",
        target_files=["/etc/app/config.yaml"],
    )
    assert isinstance(exc, AppError)
    assert exc.code == "ACCESS_DENIED"
    assert exc.actor == Actor.USER
    assert exc.mode == ActionMode.INTERACTION
    assert exc.target_files == ["/etc/app/config.yaml"]
    assert exc.fix == "request permissions"

    mcp_text = exc.render_mcp()
    assert "[ERROR]  (ACCESS_DENIED) Resource not accessible" in mcp_text
    assert "[ACTION] INTERACTION" in mcp_text
    assert "[TARGET] /etc/app/config.yaml" in mcp_text
    assert "[FIX]    request permissions" in mcp_text


def test_format_custom_exception_presentation():
    exc = BadRequestException(
        message="Invalid payload",
        actor=Actor.TOOL,
        retry=Retry.SAFE,
        fix="run linter",
        target_files=["schema.json"],
    )

    # In production (include_advisory = False): advisory is hidden
    prod_data = format_custom_exception(exc, include_advisory=False)
    assert prod_data["code"] == "BAD_REQUEST"
    assert prod_data["status"] == HTTPStatus.BAD_REQUEST
    assert prod_data["detail"] == "Invalid payload"
    assert "advisory" not in prod_data

    # In development/agent (include_advisory = True): advisory is present
    dev_data = format_custom_exception(exc, include_advisory=True)
    assert dev_data["code"] == "BAD_REQUEST"
    assert "advisory" in dev_data
    assert dev_data["advisory"]["actor"] == "TOOL"
    assert dev_data["advisory"]["mode"] == "AUTO"
    assert dev_data["advisory"]["fix"] == "run linter"
    assert dev_data["advisory"]["target_files"] == ["schema.json"]


def test_format_mcp_error():
    exc = NotFoundException(
        message="Entity not found",
        code="USER_NOT_FOUND",
        actor=Actor.USER,
        retry=Retry.AFTER_FIX,
        what_to_report="User ID 123 does not exist",
    )
    mcp_output = format_mcp_error(exc)
    assert "[ERROR]  (USER_NOT_FOUND) Entity not found" in mcp_output
    assert "[ACTION] INTERACTION" in mcp_output
    assert "[REPORT] User ID 123 does not exist" in mcp_output


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
