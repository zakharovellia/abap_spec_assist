from datetime import datetime
from typing import Any

from core.time_utils import to_iso_z


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return to_iso_z(value)
    return value


def serialize_document(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "author_id": row["author_id"],
        "tz_type": row["tz_type"],
        "scenario": row["scenario"],
        "title": row.get("title"),
        "parent_object_ref": row.get("parent_object_ref"),
        "status": row["status"],
        "current_revision": row.get("current_revision"),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def serialize_revision(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tz_id": row["tz_id"],
        "payload": row["payload"],
        "research_log": row.get("research_log") or [],
        "critic_report": row.get("critic_report"),
        "docx_object_key": row.get("docx_object_key"),
        "created_at": _iso(row["created_at"]),
        "created_by": row["created_by"],
    }


def serialize_turn(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tz_id": row["tz_id"],
        "role": row["role"],
        "content": row.get("content"),
        "agent_name": row.get("agent_name"),
        "model_used": row.get("model_used"),
        "created_at": _iso(row["created_at"]),
    }


def serialize_feedback(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tz_id": row["tz_id"],
        "revision_id": row["revision_id"],
        "developer_id": row["developer_id"],
        "rating": row.get("rating"),
        "category": row.get("category"),
        "comment": row.get("comment"),
        "created_at": _iso(row["created_at"]),
    }
