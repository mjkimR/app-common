import time
from typing import Annotated

from app_layer_base.core.database.deps import get_session
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app_prebuilt_user.deps import (
    LoginLockoutListener,
    get_login_caller,
    get_login_lockout_listener,
    get_login_throttle,
)
from app_prebuilt_user.exceptions import (
    IncorrectEmailOrPasswordException,
    InvalidCredentialsException,
    TooManyLoginAttemptsException,
)
from app_prebuilt_user.models import User
from app_prebuilt_user.services import UserService
from app_prebuilt_user.throttle import FailedLoginThrottle
from app_prebuilt_user.token_schemas import RefreshRequest, Token
from app_prebuilt_user.usecases.login import AuthenticateUserUseCase

router = APIRouter(tags=["Login"])


def _token_pair(service: UserService, user: User) -> Token:
    return Token(
        access_token=service.create_access_token(user),
        token_type="bearer",
        refresh_token=service.create_refresh_token(user),
        expires_in=service.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login/", response_model=Token)
async def login(
    data: Annotated[OAuth2PasswordRequestForm, Depends()],
    use_case: Annotated[AuthenticateUserUseCase, Depends()],
    service: Annotated[UserService, Depends()],
    throttle: Annotated[FailedLoginThrottle, Depends(get_login_throttle)],
    caller: Annotated[str, Depends(get_login_caller)],
    on_lockout: Annotated[LoginLockoutListener, Depends(get_login_lockout_listener)],
):
    now = time.monotonic()
    retry_after = throttle.retry_after(caller, now)
    if retry_after is not None:
        # Refused before the password is looked at: a locked-out caller learns nothing, right password or not.
        raise TooManyLoginAttemptsException(retry_after=str(retry_after))
    user = await use_case.execute(email=data.username, password=data.password)
    if user is None:
        if throttle.record_failure(caller, now):
            await on_lockout(caller)
        raise IncorrectEmailOrPasswordException()
    return _token_pair(service, user)


@router.post("/login/refresh", response_model=Token)
async def refresh(
    data: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[UserService, Depends()],
):
    """Exchange a refresh token for a new pair, extending the session by another refresh lifetime.

    The token stops working when its user is deactivated or its password changes. A refresh token is long and
    random-signed, so guessing it is not what the login lockout is for.
    """
    user = await service.refresh_user(session, data.refresh_token)
    if user is None:
        raise InvalidCredentialsException()
    return _token_pair(service, user)
