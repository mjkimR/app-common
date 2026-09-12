"""Database session query and refresh helpers."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def refresh_get[T](session: AsyncSession, model: type[T], ident: Any) -> T | None:
    """Clear session identity map cache and fetch a fresh copy of the record from the database.

    Use after API calls or UseCases that commit transactions to avoid stale reads
    caused by SQLAlchemy's in-memory identity map cache.
    """
    session.expire_all()
    return await session.get(model, ident)
