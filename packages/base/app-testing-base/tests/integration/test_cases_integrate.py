"""Integration and E2E tests verifying base class inheritance and helpers."""

from typing import Annotated

import pytest
from app_layer_base.base.models.mixin import Base
from app_testing_base import E2ETest, IntegrationTest, assert_status_code
from fastapi import Depends, FastAPI
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession


class BaseCaseItem(Base):
    __tablename__ = "test_base_case_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(50), nullable=False)


class DummyRepo:
    def __init__(self, session: Annotated[AsyncSession, Depends()]):
        self.session = session

    async def create(self, title: str) -> BaseCaseItem:
        item = BaseCaseItem(title=title)
        self.session.add(item)
        await self.session.commit()
        return item


class DummyUseCase:
    def __init__(self, repo: Annotated[DummyRepo, Depends()]):
        self.repo = repo

    async def execute(self, title: str) -> BaseCaseItem:
        return await self.repo.create(title)


# -----------------------------------------------------------------------------
# IntegrationTest Verification
# -----------------------------------------------------------------------------


class TestIntegrationBaseClass(IntegrationTest):
    async def test_resolve_and_refresh_helpers(self):
        # 1. Use self.resolve to resolve UseCase with pre-bound session
        use_case = self.resolve(DummyUseCase)
        assert isinstance(use_case, DummyUseCase)
        assert use_case.repo.session is self.session

        # 2. Execute
        item = await use_case.execute("initial_title")
        assert item.id is not None

        # 3. Simulate in-memory mutation
        item.title = "cached_mutation"

        # 4. Use self.refresh to reload DB state
        fresh = await self.refresh(BaseCaseItem, item.id)
        assert fresh is not None
        assert fresh.title == "initial_title"


# -----------------------------------------------------------------------------
# E2ETest Verification
# -----------------------------------------------------------------------------

api_app = FastAPI()


@api_app.get("/api/v1/ping")
async def ping():
    return {"message": "pong"}


@pytest.fixture
def app():
    return api_app


class TestE2EBaseClass(E2ETest):
    base_url = "/api/v1"

    async def test_url_and_client_helpers(self):
        assert self.url("/ping") == "/api/v1/ping"

        response = await self.client.get(self.url("/ping"))
        assert_status_code(response, 200)
        assert response.json()["message"] == "pong"
