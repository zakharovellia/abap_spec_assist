"""Метаданные сессий (владелец/заголовок/время) — отдельная таблица в том же
SQLite-файле, что и чекпоинты LangGraph (app/config.py: checkpoint_db_path).

Чекпоинтер LangGraph хранит состояние графа по thread_id, но не знает, какому
пользователю принадлежит thread и как его назвать в списке — это отдельная
маленькая книга учёта поверх него.
"""

import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import settings

DEFAULT_TITLE = "Новое ТЗ"
TITLE_MAX_LEN = 60


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    Path(settings.checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.checkpoint_db_path, timeout=10)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username)"
        )
        yield conn
        conn.commit()
    finally:
        conn.close()


def create(username: str) -> dict:
    session_id = uuid.uuid4().hex
    now = time.time()
    with _db() as conn:
        conn.execute(
            "INSERT INTO sessions (id, username, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, username, DEFAULT_TITLE, now, now),
        )
    return {"id": session_id, "title": DEFAULT_TITLE, "created_at": now, "updated_at": now}


def list_for_user(username: str) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions "
            "WHERE username = ? ORDER BY updated_at DESC",
            (username,),
        ).fetchall()
    return [
        {"id": r[0], "title": r[1], "created_at": r[2], "updated_at": r[3]} for r in rows
    ]


def owner(session_id: str) -> str | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT username FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    return row[0] if row else None


def title(session_id: str) -> str | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT title FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    return row[0] if row else None


def touch(session_id: str) -> None:
    with _db() as conn:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (time.time(), session_id)
        )


def set_title_if_default(session_id: str, text: str) -> None:
    """Автоназвание сессии по первому сообщению/файлу — как в ChatGPT."""
    title = " ".join(text.split())[:TITLE_MAX_LEN].strip()
    if not title:
        return
    with _db() as conn:
        conn.execute(
            "UPDATE sessions SET title = ? WHERE id = ? AND title = ?",
            (title, session_id, DEFAULT_TITLE),
        )


def rename(session_id: str, username: str, title: str) -> bool:
    title = title.strip()[:TITLE_MAX_LEN]
    if not title:
        return False
    with _db() as conn:
        cur = conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ? AND username = ?",
            (title, time.time(), session_id, username),
        )
    return cur.rowcount > 0


def delete(session_id: str, username: str) -> bool:
    with _db() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE id = ? AND username = ?", (session_id, username)
        )
    return cur.rowcount > 0
