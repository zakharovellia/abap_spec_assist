import uuid
from typing import Any

from sqlalchemy import insert, select

from core.db import connection
from core.tables import tz_conversations
from core.time_utils import utcnow


async def add_turn(
    *,
    tz_id: str,
    role: str,
    content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    tool_result: dict[str, Any] | None = None,
    agent_name: str | None = None,
    model_used: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
) -> dict[str, Any]:
    values = {
        "id": str(uuid.uuid4()),
        "tz_id": tz_id,
        "role": role,
        "content": content,
        "tool_calls": tool_calls,
        "tool_result": tool_result,
        "agent_name": agent_name,
        "model_used": model_used,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "created_at": utcnow(),
    }
    async with connection() as conn:
        await conn.execute(insert(tz_conversations).values(**values))
    return values


async def list_turns(tz_id: str) -> list[dict[str, Any]]:
    async with connection() as conn:
        result = await conn.execute(
            select(tz_conversations)
            .where(tz_conversations.c.tz_id == tz_id)
            .order_by(tz_conversations.c.created_at.asc())
        )
        rows = result.fetchall()
    return [dict(r._mapping) for r in rows]
