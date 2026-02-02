from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_base.core.database.engine import get_session_maker


class AsyncTransaction:
    """Async context manager for SQLAlchemy session and transaction.

    This context manager opens an ``AsyncSession``, yields it, and on exit
    commits when no exception occurred or rolls back otherwise. The session is
    always closed at the end.

    Example:

        async with AsyncTransaction() as session:
            await session.execute(...)
    """

    def __init__(self, session_maker: Optional[async_sessionmaker] = None) -> None:
        """Initialize AsyncTransaction with an async session maker.

        Args:
            session_maker: Optional async_sessionmaker to create sessions. If not
                provided, uses ``app_base.core.database.async_session``.
        """
        self._session_maker: async_sessionmaker = session_maker or get_session_maker()
        self._session: Optional[AsyncSession] = None

    async def __aenter__(self) -> AsyncSession:
        """Create and return a new AsyncSession instance."""
        self._session = self._session_maker()
        if self._session is None:
            raise RuntimeError("Failed to create AsyncSession")
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Commit or rollback based on exception, then close the session."""
        if self._session is None:
            return

        try:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
        finally:
            await self._session.close()
