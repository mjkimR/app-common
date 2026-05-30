"""Tests for NoSQLRepository (repository.py)."""

import pytest
from app_layer_base.base.schemas.paginated import PaginatedList
from app_nosql_db.query_options import NoSQLListQueryOptions
from app_nosql_db.repository import NoSQLRepository
from pydantic import BaseModel

# ----------------------------------------------------------------
# Test models
# ----------------------------------------------------------------


class UserModel(BaseModel):
    id: str
    name: str
    email: str


class UserCreateSchema(BaseModel):
    id: str
    name: str
    email: str


class UserPutSchema(BaseModel):
    name: str
    email: str


class UserPatchSchema(BaseModel):
    name: str | None = None
    email: str | None = None


# ----------------------------------------------------------------
# Repo fixture
# ----------------------------------------------------------------


class UserRepo(NoSQLRepository):
    collection_name = "users"
    model = UserModel


@pytest.fixture
def user_repo():
    return UserRepo()


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------


async def test_create_and_get_by_id(user_repo, mock_provider):
    obj_in = UserCreateSchema(id="u1", name="Alice", email="alice@example.com")
    created = await user_repo.create(mock_provider, "u1", obj_in)
    assert created.id == "u1"
    assert created.name == "Alice"

    fetched = await user_repo.get_by_id(mock_provider, "u1")
    assert fetched is not None
    assert fetched.name == "Alice"


async def test_get_by_id_not_found(user_repo, mock_provider):
    result = await user_repo.get_by_id(mock_provider, "not_exist")
    assert result is None


async def test_create_with_extra_fields(user_repo, mock_provider):
    obj_in = UserCreateSchema(id="u2", name="Bob", email="bob@example.com")
    await user_repo.create(mock_provider, "u2", obj_in, extra="extra_val")
    fetched = await user_repo.get_by_id(mock_provider, "u2")
    assert fetched is not None


async def test_put_replaces_document(user_repo, mock_provider):
    obj_in = UserCreateSchema(id="u3", name="Charlie", email="charlie@example.com")
    await user_repo.create(mock_provider, "u3", obj_in)

    put_in = UserPutSchema(name="Charlie Updated", email="charlie_new@example.com")
    updated = await user_repo.put(mock_provider, "u3", put_in)
    assert updated is not None
    assert updated.name == "Charlie Updated"
    assert updated.email == "charlie_new@example.com"


async def test_patch_updates_only_set_fields(user_repo, mock_provider):
    obj_in = UserCreateSchema(id="u4", name="Dave", email="dave@example.com")
    await user_repo.create(mock_provider, "u4", obj_in)

    patch_in = UserPatchSchema(name="Dave Patched")  # email not set
    patched = await user_repo.patch(mock_provider, "u4", patch_in)
    assert patched is not None
    assert patched.name == "Dave Patched"
    # email should remain from original (mock provider merges on update)
    assert patched.email == "dave@example.com"


async def test_delete(user_repo, mock_provider):
    obj_in = UserCreateSchema(id="u5", name="Eve", email="eve@example.com")
    await user_repo.create(mock_provider, "u5", obj_in)

    result = await user_repo.delete(mock_provider, "u5")
    assert result is True

    fetched = await user_repo.get_by_id(mock_provider, "u5")
    assert fetched is None


async def test_exists(user_repo, mock_provider):
    obj_in = UserCreateSchema(id="u6", name="Frank", email="frank@example.com")
    await user_repo.create(mock_provider, "u6", obj_in)

    assert await user_repo.exists(mock_provider, "u6") is True
    assert await user_repo.exists(mock_provider, "not_exist") is False


async def test_get_multi_no_filter(user_repo, mock_provider):
    for i in range(5):
        obj_in = UserCreateSchema(id=f"m{i}", name=f"User{i}", email=f"u{i}@example.com")
        await user_repo.create(mock_provider, f"m{i}", obj_in)

    result = await user_repo.get_multi(mock_provider)
    assert isinstance(result, PaginatedList)
    assert result.total_count == 5
    assert len(result.items) == 5


async def test_get_multi_with_offset_limit(user_repo, mock_provider):
    for i in range(10):
        obj_in = UserCreateSchema(id=f"p{i}", name=f"User{i}", email=f"u{i}@example.com")
        await user_repo.create(mock_provider, f"p{i}", obj_in)

    result = await user_repo.get_multi(mock_provider, query_options=NoSQLListQueryOptions(offset=3, limit=4))
    assert result.total_count == 10
    assert len(result.items) == 4
    assert result.offset == 3
    assert result.limit == 4


async def test_get_multi_with_filter(user_repo, mock_provider):
    await user_repo.create(mock_provider, "f1", UserCreateSchema(id="f1", name="Alice", email="a@example.com"))
    await user_repo.create(mock_provider, "f2", UserCreateSchema(id="f2", name="Bob", email="b@example.com"))
    await user_repo.create(mock_provider, "f3", UserCreateSchema(id="f3", name="Alice", email="c@example.com"))

    result = await user_repo.get_multi(
        mock_provider,
        query_options=NoSQLListQueryOptions(filters=[("name", "==", "Alice")]),
    )
    assert result.total_count == 2
    assert all(item.name == "Alice" for item in result.items)


def test_model_name(user_repo):
    assert user_repo.model_name() == "UserModel"


def test_model_repr(user_repo):
    assert user_repo.model_repr("u1") == "UserModel(id=u1)"
