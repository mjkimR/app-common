from typing import Annotated

from app_layer_base.core.database.deps import get_session
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app_prebuilt_user.exceptions import IncorrectEmailOrPasswordException
from app_prebuilt_user.services import UserService
from app_prebuilt_user.token_schemas import Token

router = APIRouter(tags=["Login"])


@router.post("/login/", response_model=Token)
async def login(
    data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[UserService, Depends()],
):
    user = await service.authenticate(session, email=data.username, password=data.password)
    if user is None:
        raise IncorrectEmailOrPasswordException()
    return Token(
        access_token=service.create_access_token(user),
        token_type="bearer",
    )
