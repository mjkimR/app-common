import functools
from collections.abc import Awaitable, Callable
from typing import Annotated

import jwt
from app_layer_base.core.database.deps import get_session
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_auth_settings
from .exceptions import (
    InvalidCredentialsException,
    PermissionDeniedException,
    UserNotFoundException,
)
from .models import User
from .services import UserService
from .throttle import FailedLoginThrottle
from .token_schemas import TokenPayload

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login/")


@functools.lru_cache
def get_login_throttle() -> FailedLoginThrottle:
    """One throttle per process, sized from the auth settings."""
    settings = get_auth_settings()
    return FailedLoginThrottle(
        max_failures=settings.LOGIN_MAX_FAILURES,
        window_seconds=settings.LOGIN_FAILURE_WINDOW_SECONDS,
        lockout_seconds=settings.LOGIN_LOCKOUT_SECONDS,
    )


def get_login_caller(request: Request) -> str:
    """Who is logging in, for the failed-login lockout.

    The default is the peer address. Behind a proxy that is the proxy, and a forwarded header is only trustworthy
    in the part the platform itself wrote, which differs per platform: override this dependency
    (`app.dependency_overrides[get_login_caller]`) with what is right for the deployment.
    """
    return request.client.host if request.client else "unknown"


LoginLockoutListener = Callable[[str], Awaitable[None]]


async def _ignore_lockout(caller: str) -> None:
    return None


def get_login_lockout_listener() -> LoginLockoutListener:
    """Called once when a caller is locked out. Override to tell an operator; the default does nothing."""
    return _ignore_lockout


def get_token_data(
    token: Annotated[str, Depends(oauth2)],
    user_service: Annotated[UserService, Depends()],
) -> TokenPayload:
    try:
        secret_key = user_service.settings.SECRET_KEY.get_secret_value()
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[user_service.jwt_algorithm],
            issuer=user_service.settings.JWT_ISSUER,
            audience=user_service.settings.JWT_AUDIENCE,
            leeway=user_service.settings.JWT_LEEWAY_SECONDS,
            options={
                "require": ["exp", "iat", "nbf", "iss", "aud", "sub", "typ"],
            },
        )
        token_data = TokenPayload(**payload)
        if token_data.typ != "access":
            raise InvalidCredentialsException()
    except Exception:
        raise InvalidCredentialsException() from None
    return token_data


async def get_current_user(
    token: Annotated[TokenPayload, Depends(get_token_data)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_service: Annotated[UserService, Depends()],
) -> User:
    if token.user_id is None:
        raise InvalidCredentialsException()
    user = await user_service.get(session, obj_pk=token.user_id)
    if user is None:
        raise UserNotFoundException()
    if not user.is_active or user.approval_status != "approved" or token.ver != user.auth_version:
        raise InvalidCredentialsException()
    return user


def get_current_superuser(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_superadmin:
        raise PermissionDeniedException()
    return user


on_superuser = get_current_superuser
