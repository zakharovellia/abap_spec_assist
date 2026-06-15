import uuid
from typing import Any

from sqlalchemy import insert, select, update

from core.db import connection
from core.tables import tz_documents, tz_revisions
from core.time_utils import utcnow


def new_id() -> str:
    return str(uuid.uuid4())


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


async def create_document(
    *,
    author_id: str,
    tz_type: str,
    scenario: str = "new",
    title: str | None = None,
    parent_object_ref: str | None = None,
) -> dict[str, Any]:
    doc_id = new_id()
    now = utcnow()
    values = {
        "id": doc_id,
        "author_id": author_id,
        "tz_type": tz_type,
        "scenario": scenario,
        "title": title,
        "parent_object_ref": parent_object_ref,
        "status": "draft",
        "current_revision": None,
        "created_at": now,
        "updated_at": now,
    }
    async with connection() as conn:
        await conn.execute(insert(tz_documents).values(**values))
    return values


async def get_document(doc_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        result = await conn.execute(
            select(tz_documents).where(tz_documents.c.id == doc_id)
        )
        row = result.first()
    return _row_to_dict(row) if row else None


async def list_documents(
    *,
    author_id: str | None = None,
    scenario: str | None = None,
    parent_object_ref: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    stmt = select(tz_documents)
    if author_id:
        stmt = stmt.where(tz_documents.c.author_id == author_id)
    if scenario:
        stmt = stmt.where(tz_documents.c.scenario == scenario)
    if parent_object_ref:
        stmt = stmt.where(tz_documents.c.parent_object_ref == parent_object_ref)
    stmt = stmt.order_by(tz_documents.c.updated_at.desc()).limit(limit).offset(offset)
    async with connection() as conn:
        result = await conn.execute(stmt)
        rows = result.fetchall()
    return [_row_to_dict(r) for r in rows]


async def update_document_status(doc_id: str, status: str) -> None:
    async with connection() as conn:
        await conn.execute(
            update(tz_documents)
            .where(tz_documents.c.id == doc_id)
            .values(status=status, updated_at=utcnow())
        )


async def create_revision(
    *,
    tz_id: str,
    payload: dict[str, Any],
    research_log: list[dict[str, Any]] | None = None,
    critic_report: dict[str, Any] | None = None,
    docx_object_key: str | None = None,
    created_by: str = "agent",
) -> dict[str, Any]:
    rev_id = new_id()
    now = utcnow()
    values = {
        "id": rev_id,
        "tz_id": tz_id,
        "payload": payload,
        "research_log": research_log or [],
        "critic_report": critic_report,
        "docx_object_key": docx_object_key,
        "created_at": now,
        "created_by": created_by,
    }
    async with connection() as conn:
        await conn.execute(insert(tz_revisions).values(**values))
        await conn.execute(
            update(tz_documents)
            .where(tz_documents.c.id == tz_id)
            .values(current_revision=rev_id, updated_at=now)
        )
    return values


async def list_revisions(tz_id: str) -> list[dict[str, Any]]:
    async with connection() as conn:
        result = await conn.execute(
            select(tz_revisions)
            .where(tz_revisions.c.tz_id == tz_id)
            .order_by(tz_revisions.c.created_at.asc())
        )
        rows = result.fetchall()
    return [_row_to_dict(r) for r in rows]


async def get_revision(rev_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        result = await conn.execute(
            select(tz_revisions).where(tz_revisions.c.id == rev_id)
        )
        row = result.first()
    return _row_to_dict(row) if row else None
