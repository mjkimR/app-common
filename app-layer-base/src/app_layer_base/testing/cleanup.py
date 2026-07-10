"""Table cleanup between tests, for suites that let their code really commit."""

from collections.abc import Iterable

from sqlalchemy import Table, text
from sqlalchemy.ext.asyncio import AsyncConnection


async def clean_db_after_test(driver_name: str, tables: Iterable[Table], conn: AsyncConnection) -> None:
    """Empty ``tables`` on the connection, skipping any that were never created.

    Mock models declared in unit-test conftests are registered on ``Base.metadata``
    but have no table in the database, so filtering by what actually exists keeps
    cleanup from blowing up on them.
    """
    is_sqlite = "sqlite" in driver_name

    if is_sqlite:
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    else:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
    existing_names = {row[0] for row in result}
    existing = [table for table in tables if table.name in existing_names]
    if not existing:
        return

    if is_sqlite:
        await conn.execute(text("PRAGMA foreign_keys = OFF;"))
        for table in existing:
            await conn.execute(text(f"DELETE FROM {table.name}"))
        await conn.execute(text("PRAGMA foreign_keys = ON;"))
    else:
        names = ", ".join(f'"{table.name}"' for table in existing)
        await conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE;"))

    await conn.commit()
