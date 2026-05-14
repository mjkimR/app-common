from unittest.mock import patch

from app_base.core.middlewares.cors_middleware import add_middleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def test_add_middleware_specific_origins():
    app = FastAPI()
    with patch("app_base.core.middlewares.cors_middleware.get_app_settings") as mock_settings:
        mock_settings.return_value.CORS_ALLOWED_ORIGINS = ["https://example.com"]
        mock_settings.return_value.CORS_ALLOW_ORIGIN_REGEX = None
        mock_settings.return_value.CORS_ALLOW_CREDENTIALS = True

        add_middleware(app)

        # Check if CORSMiddleware is in the app middleware stack
        # FastAPI stores middleware in app.user_middleware
        cors_middleware = next((m for m in app.user_middleware if m.cls == CORSMiddleware), None)
        assert cors_middleware is not None
        assert cors_middleware.options["allow_origins"] == ["https://example.com"]
        assert cors_middleware.options["allow_credentials"] is True


def test_add_middleware_wildcard_origin():
    app = FastAPI()
    with patch("app_base.core.middlewares.cors_middleware.get_app_settings") as mock_settings:
        mock_settings.return_value.CORS_ALLOWED_ORIGINS = ["*"]
        mock_settings.return_value.CORS_ALLOW_ORIGIN_REGEX = None
        # Even if set to True, it should be forced to False for wildcard
        mock_settings.return_value.CORS_ALLOW_CREDENTIALS = True

        add_middleware(app)

        cors_middleware = next((m for m in app.user_middleware if m.cls == CORSMiddleware), None)
        assert cors_middleware is not None
        assert cors_middleware.options["allow_origins"] == ["*"]
        assert cors_middleware.options["allow_credentials"] is False


def test_add_middleware_regex_origin():
    app = FastAPI()
    with patch("app_base.core.middlewares.cors_middleware.get_app_settings") as mock_settings:
        mock_settings.return_value.CORS_ALLOWED_ORIGINS = []
        mock_settings.return_value.CORS_ALLOW_ORIGIN_REGEX = r"https://.*\.example\.com"
        mock_settings.return_value.CORS_ALLOW_CREDENTIALS = True

        add_middleware(app)

        cors_middleware = next((m for m in app.user_middleware if m.cls == CORSMiddleware), None)
        assert cors_middleware is not None
        assert cors_middleware.options["allow_origins"] == []
        assert cors_middleware.options["allow_origin_regex"] == r"https://.*\.example\.com"
        assert cors_middleware.options["allow_credentials"] is True


def test_add_middleware_credentials_disabled():
    app = FastAPI()
    with patch("app_base.core.middlewares.cors_middleware.get_app_settings") as mock_settings:
        mock_settings.return_value.CORS_ALLOWED_ORIGINS = ["https://example.com"]
        mock_settings.return_value.CORS_ALLOW_ORIGIN_REGEX = None
        mock_settings.return_value.CORS_ALLOW_CREDENTIALS = False

        add_middleware(app)

        cors_middleware = next((m for m in app.user_middleware if m.cls == CORSMiddleware), None)
        assert cors_middleware is not None
        assert cors_middleware.options["allow_credentials"] is False
