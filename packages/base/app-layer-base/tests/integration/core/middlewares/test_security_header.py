from unittest.mock import patch

import pytest
from app_layer_base.core.middlewares.security_header import SecurityHeaderMiddleware, add_middleware
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _Settings:
    def __init__(self, app_env: str):
        self.APP_ENV = app_env

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


def _make_app(is_production: bool | None = True) -> TestClient:
    app = FastAPI()
    add_middleware(app, is_production=is_production)

    @app.get("/test")
    async def test_route():
        return {"message": "ok"}

    return TestClient(app)


def test_add_middleware():
    app = FastAPI()
    add_middleware(app)

    middleware_classes = [m.cls for m in app.user_middleware]
    assert SecurityHeaderMiddleware in middleware_classes


def test_x_content_type_options_header():
    client = _make_app()
    response = client.get("/test")
    assert response.headers.get("x-content-type-options") == "nosniff"


def test_x_frame_options_header():
    client = _make_app()
    response = client.get("/test")
    assert response.headers.get("x-frame-options") == "DENY"


def test_strict_transport_security_header():
    client = _make_app()
    response = client.get("/test")
    assert response.headers.get("strict-transport-security") == "max-age=31536000; includeSubDomains"


def test_content_security_policy_header():
    client = _make_app()
    response = client.get("/test")
    assert response.headers.get("content-security-policy") == "default-src 'self'"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/docs/oauth2-redirect"])
def test_docs_paths_use_docs_content_security_policy(path: str):
    client = _make_app()
    response = client.get(path)

    assert response.headers.get("content-security-policy") == SecurityHeaderMiddleware.DOCS_CSP.decode()
    assert response.headers.get("strict-transport-security") == "max-age=31536000; includeSubDomains"


def test_referrer_policy_header():
    client = _make_app()
    response = client.get("/test")
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_all_security_headers_present():
    client = _make_app()
    response = client.get("/test")

    expected_headers = [
        *SecurityHeaderMiddleware.BASE_HEADERS,
        (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
        (b"content-security-policy", b"default-src 'self'"),
    ]

    for header_name, expected_value in expected_headers:
        name = header_name.decode()
        value = expected_value.decode()
        assert response.headers.get(name) == value, f"Header '{name}' mismatch"


def test_add_middleware_uses_app_env_settings_by_default():
    with patch(
        "app_layer_base.core.middlewares.security_header.get_app_settings",
        return_value=_Settings("production"),
    ):
        client = _make_app(is_production=None)
        response = client.get("/test")

    assert response.headers.get("strict-transport-security") == "max-age=31536000; includeSubDomains"
    assert response.headers.get("content-security-policy") == "default-src 'self'"


def test_development_mode_omits_hsts_relaxes_csp_and_logs():
    with (
        patch(
            "app_layer_base.core.middlewares.security_header.get_app_settings",
            return_value=_Settings("development"),
        ),
        patch("app_layer_base.core.middlewares.security_header.logger") as mock_logger,
    ):
        client = _make_app(is_production=None)
        response = client.get("/test")

    assert response.headers.get("strict-transport-security") is None
    assert response.headers.get("content-security-policy") == "default-src 'self' 'unsafe-inline' 'unsafe-eval' ws:;"
    mock_logger.info.assert_called_once()


def test_non_http_scope_not_affected():
    """Non-HTTP requests (e.g. websocket) should pass through without modification"""
    app = FastAPI()
    add_middleware(app, is_production=True)

    @app.get("/test")
    async def test_route():
        return {"message": "ok"}

    client = TestClient(app)
    # Verify that a regular HTTP request works correctly
    response = client.get("/test")
    assert response.status_code == 200
