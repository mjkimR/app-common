from typing import Annotated

from app_base.core.database.deps import get_session
from app_base.prebuilt.user.exceptions import IncorrectEmailOrPasswordException
from app_base.prebuilt.user.services import UserService
from app_base.prebuilt.user.token_schemas import Token
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

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
