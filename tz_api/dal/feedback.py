import uuid
from typing import Any

from sqlalchemy import insert, select

from core.db import connection
from core.tables import tz_feedback
from core.time_utils import utcnow


async def add_feedback(
    *,
    tz_id: str,
    revision_id: str,
    developer_id: str,
    rating: int | None = None,
    category: str | None = None,
    comment: str | None = None,
) -> dict[str, Any]:
    values = {
        "id": str(uuid.uuid4()),
        "tz_id": tz_id,
        "revision_id": revision_id,
        "developer_id": developer_id,
        "rating": rating,
        "category": category,
        "comment": comment,
        "created_at": utcnow(),
    }
    async with connection() as conn:
        await conn.execute(insert(tz_feedback).values(**values))
    return values


async def list_feedback(tz_id: str) -> list[dict[str, Any]]:
    async with connection() as conn:
        result = await conn.execute(
            select(tz_feedback)
            .where(tz_feedback.c.tz_id == tz_id)
            .order_by(tz_feedback.c.created_at.asc())
        )
        rows = result.fetchall()
    return [dict(r._mapping) for r in rows]
