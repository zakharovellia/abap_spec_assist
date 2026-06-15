from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    create_async_engine,
)

from config import settings

_engine: AsyncEngine | None = None


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def create_engine(url: str | None = None) -> AsyncEngine:
    db_url = url or settings.db.url
    engine = create_async_engine(db_url, future=True)
    if _is_sqlite(db_url):

        from sqlalchemy import event

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


@asynccontextmanager
async def connection() -> AsyncIterator[AsyncConnection]:
    engine = get_engine()
    async with engine.begin() as conn:
        yield conn
