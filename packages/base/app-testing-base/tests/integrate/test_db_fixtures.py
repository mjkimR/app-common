"""Integration tests for database fixtures and isolation."""

import pytest
from app_layer_base.base.models.mixin import Base
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession


class SampleItem(Base):
    __tablename__ = "test_fixture_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)


@pytest.mark.integrate
class TestSessionFixture:
    async def test_session_can_insert_and_query(self, session: AsyncSession):
        item = SampleItem(name="item1")
        session.add(item)
        await session.flush()

        stmt = select(SampleItem).where(SampleItem.name == "item1")
        result = await session.execute(stmt)
        queried = result.scalar_one_or_none()

        assert queried is not None
        assert queried.name == "item1"

    async def test_session_isolation_from_previous_test(self, session: AsyncSession):
        """Verify that item1 from previous test does not leak into this test."""
        stmt = select(SampleItem).where(SampleItem.name == "item1")
        result = await session.execute(stmt)
        queried = result.scalar_one_or_none()

        assert queried is None
