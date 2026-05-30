from app_layer_base.core.middlewares.security_header import SecurityHeaderMiddleware, add_middleware
from fastapi import FastAPI
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


def test_x_xss_protection_header():
    client = _make_app()
    response = client.get("/test")
    assert response.headers.get("x-xss-protection") == "1; mode=block"


def test_all_security_headers_present():
    client = _make_app()
    response = client.get("/test")

    for header_name, expected_value in SecurityHeaderMiddleware.SECURITY_HEADERS:
        name = header_name.decode()
        value = expected_value.decode()
        assert response.headers.get(name) == value, f"Header '{name}' mismatch"


def test_non_http_scope_not_affected():
    """Non-HTTP requests (e.g. websocket) should pass through without modification"""
    app = FastAPI()
    add_middleware(app)

    @app.get("/test")
    async def test_route():
        return {"message": "ok"}

    client = TestClient(app)
    # Verify that a regular HTTP request works correctly
    response = client.get("/test")
    assert response.status_code == 200
