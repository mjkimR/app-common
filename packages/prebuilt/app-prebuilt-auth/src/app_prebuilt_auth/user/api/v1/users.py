from typing import Annotated
from uuid import UUID

from app_layer_base.base.exceptions.basic import NotFoundException
from fastapi import APIRouter, Depends

from app_prebuilt_auth.user.deps import get_current_user, on_superuser
from app_prebuilt_auth.user.exceptions import UserNotFoundException
from app_prebuilt_auth.user.models import User
from app_prebuilt_auth.user.schemas import UserRead, UserReadAdmin, UserUpdate
from app_prebuilt_auth.user.usecases.crud import GetUserUseCase, UpdateUserUseCase

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserReadAdmin)
async def read_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user


@router.get("/{user_id}", response_model=UserRead)
async def read_user(
    use_case: Annotated[GetUserUseCase, Depends()],
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get a specific user by id."""
    user = await use_case.execute(user_id=user_id, current_user=current_user)
    if user is None:
        raise UserNotFoundException()
    return user


@router.put("/{user_id}", response_model=UserRead, dependencies=[Depends(on_superuser)])
async def update_user(
    use_case: Annotated[UpdateUserUseCase, Depends()],
    user_id: UUID,
    user_in: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
):
    user = await use_case.execute(obj_data=user_in, user_id=user_id, current_user=current_user)
    if user is None:
        raise NotFoundException()
    return user
