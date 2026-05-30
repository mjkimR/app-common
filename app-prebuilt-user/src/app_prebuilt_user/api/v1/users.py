from typing import Annotated
from uuid import UUID

from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends

from app_prebuilt_user.deps import get_current_user, on_superuser
from app_prebuilt_user.exceptions import UserNotFoundException
from app_prebuilt_user.models import User
from app_prebuilt_user.schemas import UserRead, UserUpdate
from app_prebuilt_user.usecases.crud import GetUserUseCase, UpdateUserUseCase

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/{user_id}", response_model=PaginatedList[UserRead])
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
