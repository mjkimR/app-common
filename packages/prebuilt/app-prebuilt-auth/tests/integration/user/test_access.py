import asyncio

import pytest
from app_layer_base.core.database.transaction import AsyncTransaction
from app_prebuilt_auth.user.access import AccessUseCase
from app_prebuilt_auth.user.access_repo import AccessRepository
from app_prebuilt_auth.user.access_service import AccessService
from app_prebuilt_auth.user.config import AuthSettings
from app_prebuilt_auth.user.exceptions import PermissionDeniedException
from app_prebuilt_auth.user.models import User
from app_prebuilt_auth.user.schemas import UserAccessChange

pytestmark = pytest.mark.real_commit


async def test_administrators_cannot_concurrently_remove_each_other(session, is_postgres):
    if not is_postgres:
        pytest.skip("PostgreSQL row locking contract")
    first = User(firstname="First", email="first@example.com", is_superadmin=True)
    second = User(firstname="Second", email="second@example.com", is_superadmin=True)
    session.add_all([first, second])
    await session.commit()
    settings = AuthSettings(
        FIRST_USER_EMAIL="bootstrap@example.com",
        FIRST_USER_PASSWORD="password",
        SECRET_KEY="test-key-for-administrator-race",
    )
    case = AccessUseCase(AccessService(AccessRepository(), settings), AsyncTransaction)
    change = UserAccessChange(action="demote", expected_version=0)
    results = await asyncio.gather(
        case.change(first.id, change, second.id), case.change(second.id, change, first.id), return_exceptions=True
    )
    assert sum(isinstance(result, PermissionDeniedException) for result in results) == 1
    assert sum(not isinstance(result, Exception) for result in results) == 1
