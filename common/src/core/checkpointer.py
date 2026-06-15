from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from config import settings


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _sqlite_path(url: str) -> str:
    return url.split("///", 1)[-1] if "///" in url else "./data/tz_checkpoints.db"


@asynccontextmanager
async def get_checkpointer() -> AsyncIterator[Any]:
    url = settings.db.url
    if _is_sqlite(url):
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        path = _sqlite_path(url)
        async with AsyncSqliteSaver.from_conn_string(path) as saver:
            yield saver
    else:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(url) as saver:
            await saver.setup()
            yield saver
