from typing import Annotated

import jwt
from app_base.core.database.deps import get_session
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .exceptions import (
    InvalidCredentialsException,
    PermissionDeniedException,
    UserNotFoundException,
)
from .models import User
from .services import UserService
from .token_schemas import TokenPayload

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


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
    user = await user_service.get(session, obj_id=token.user_id)
    if user is None:
        raise UserNotFoundException()
    return user


def get_current_superuser(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_superadmin:
        raise PermissionDeniedException()
    return user


on_superuser = get_current_superuser
