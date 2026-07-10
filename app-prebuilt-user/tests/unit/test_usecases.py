import pytest
from app_layer_base.core.database.transaction import AsyncTransaction
from app_layer_base.testing import random_email
from app_prebuilt_user.config.auth import AuthSettings
from app_prebuilt_user.exceptions import PermissionDeniedException
from app_prebuilt_user.repos import UserRepository
from app_prebuilt_user.schemas import UserCreate, UserUpdate
from app_prebuilt_user.services import UserService
from app_prebuilt_user.usecases.crud import GetUserUseCase, UpdateUserUseCase


@pytest.fixture
def service() -> UserService:
    settings = AuthSettings(
        FIRST_USER_EMAIL="admin@example.com",
        FIRST_USER_PASSWORD="changeme123",
        SECRET_KEY="test-secret-key-not-for-production",
    )
    return UserService(settings=settings, repo=UserRepository())


async def _seed_user(session, service: UserService, *, superadmin: bool = False):
    payload = UserCreate(
        firstname="First",
        lastname="Last",
        email=random_email(),
        password="password123",
    )
    if superadmin:
        user = await service.create_admin(session, payload)
    else:
        user = await service.create_user(session, payload)
    await session.commit()
    return user


class TestUpdateUserUseCase:
    async def test_self_update_applies_changes(self, session, service):
        """Regression: updating your own record must persist obj_data, not no-op."""
        user = await _seed_user(session, service)
        user_id = user.id
        use_case = UpdateUserUseCase(service)

        result = await use_case.execute(
            obj_data=UserUpdate(firstname="Updated"),
            user_id=user_id,
            current_user=user,
        )

        assert result is not None
        assert result.firstname == "Updated"

        # And the change is actually persisted (read back in a fresh transaction).
        async with AsyncTransaction() as verify_session:
            persisted = await service.repo.get_by_pk(verify_session, user_id)
        assert persisted is not None
        assert persisted.firstname == "Updated"

    async def test_superadmin_updates_other_user(self, session, service):
        admin = await _seed_user(session, service, superadmin=True)
        target = await _seed_user(session, service)
        use_case = UpdateUserUseCase(service)

        result = await use_case.execute(
            obj_data=UserUpdate(firstname="ByAdmin"),
            user_id=target.id,
            current_user=admin,
        )

        assert result is not None
        assert result.firstname == "ByAdmin"

    async def test_non_superadmin_updating_other_user_is_denied(self, session, service):
        actor = await _seed_user(session, service)
        target = await _seed_user(session, service)
        use_case = UpdateUserUseCase(service)

        with pytest.raises(PermissionDeniedException):
            await use_case.execute(
                obj_data=UserUpdate(firstname="Nope"),
                user_id=target.id,
                current_user=actor,
            )


class TestGetUserUseCase:
    async def test_self_get_returns_current_user(self, session, service):
        user = await _seed_user(session, service)
        use_case = GetUserUseCase(service)

        result = await use_case.execute(user_id=user.id, current_user=user)

        assert result is user

    async def test_superadmin_gets_other_user(self, session, service):
        admin = await _seed_user(session, service, superadmin=True)
        target = await _seed_user(session, service)
        use_case = GetUserUseCase(service)

        result = await use_case.execute(user_id=target.id, current_user=admin)

        assert result is not None
        assert result.id == target.id

    async def test_non_superadmin_getting_other_user_is_denied(self, session, service):
        actor = await _seed_user(session, service)
        target = await _seed_user(session, service)
        use_case = GetUserUseCase(service)

        with pytest.raises(PermissionDeniedException):
            await use_case.execute(user_id=target.id, current_user=actor)
