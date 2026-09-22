"""Register the complete auth API while preserving host-owned policy and lifecycle."""

from fastapi import APIRouter, FastAPI

from .api_key.api import api_keys_router
from .api_key.config import ApiKeySettings, get_api_key_settings
from .google.api import router as google_router
from .google.config import GoogleAuthSettings, get_google_auth_settings
from .user.api import v1_users_router
from .user.config import AuthSettings, get_auth_settings
from .user.deps import get_login_throttle
from .user.throttle import FailedLoginThrottle


def create_auth_router() -> APIRouter:
    """Return all auth routes. Google endpoints enforce their enabled setting."""
    router = APIRouter()
    router.include_router(v1_users_router)
    router.include_router(google_router)
    router.include_router(api_keys_router)
    return router


def install_auth(
    app: FastAPI,
    *,
    prefix: str = "/api/v1",
    user_settings: AuthSettings | None = None,
    google_settings: GoogleAuthSettings | None = None,
    api_key_settings: ApiKeySettings | None = None,
) -> None:
    """Mount all auth routes and optionally supply settings for this app instance.

    Settings not supplied here keep their environment-backed dependencies. This
    performs no I/O, bootstrapping, schema creation or HTTP-client initialization.
    Hosts own startup/shutdown, transactions, business scopes and administrator UI.
    The default prefix matches the password token URL and Google cookie path;
    configure both explicitly when mounting at another prefix.
    """
    if getattr(app.state, "app_prebuilt_auth_installed", False):
        raise ValueError("Authentication is already installed on this application")
    if user_settings is not None:
        app.dependency_overrides[get_auth_settings] = lambda: user_settings
        throttle = FailedLoginThrottle(
            user_settings.LOGIN_MAX_FAILURES,
            user_settings.LOGIN_FAILURE_WINDOW_SECONDS,
            user_settings.LOGIN_LOCKOUT_SECONDS,
        )
        app.dependency_overrides[get_login_throttle] = lambda: throttle
    if google_settings is not None:
        app.dependency_overrides[get_google_auth_settings] = lambda: google_settings
    if api_key_settings is not None:
        app.dependency_overrides[get_api_key_settings] = lambda: api_key_settings
    app.include_router(create_auth_router(), prefix=prefix)
    app.state.app_prebuilt_auth_installed = True
