from app_layer_base.core.database.engine import get_session_maker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_api_key_session_maker() -> async_sessionmaker[AsyncSession]:
    """Override this dependency when the host owns its database engine."""
    return get_session_maker()
