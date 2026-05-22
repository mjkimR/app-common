import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app_base.base.deps.params.page import PaginationParam
from app_base.base.repos.query_options import ListQueryOptions
from app_base.base.schemas.delete_resp import DeleteResponse
from app_base.base.schemas.paginated import PaginatedList
from app_base.prebuilt.user.deps import get_current_user, on_superuser
from app_base.prebuilt.user.models import User
from app_base.prebuilt.user.schemas import UserCreate, UserRead
from app_base.prebuilt.user.usecases.admin import (
    CreateAdminUseCase,
    CreateUserUseCase,
    DeleteUserUseCase,
    GetMultiUserUseCase,
)

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(on_superuser)])


@router.post("/user", status_code=status.HTTP_201_CREATED, response_model=UserRead)
async def create_user(
    user_in: UserCreate,
    use_case: Annotated[CreateUserUseCase, Depends()],
):
    """Create new user."""
    user = await use_case.execute(obj_data=user_in)
    return user


@router.post("/admin", status_code=status.HTTP_201_CREATED, response_model=UserRead)
async def create_admin(
    user_in: UserCreate,
    use_case: Annotated[CreateAdminUseCase, Depends()],
):
    """Create new admin user."""
    user = await use_case.execute(obj_data=user_in)
    return user


@router.get("/", response_model=PaginatedList[UserRead])
async def read_users(
    pagination: PaginationParam,
    use_case: Annotated[GetMultiUserUseCase, Depends()],
):
    """Get user list."""
    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit)
    users = await use_case.execute(query_options=query_options)
    return users


@router.delete("/{user_id}", response_model=DeleteResponse)
async def delete_user(
    use_case: Annotated[DeleteUserUseCase, Depends()],
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await use_case.execute(user_id, current_user)
