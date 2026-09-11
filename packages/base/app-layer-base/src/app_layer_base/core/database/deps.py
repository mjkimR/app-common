from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app_layer_base.core.database.engine import get_session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session
