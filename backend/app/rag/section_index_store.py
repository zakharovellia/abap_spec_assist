"""Кэш эмбеддингов разделов рабочего документа — во внешнем SQLite.

Раньше индекс жил в состоянии графа (SpecState.section_index), но LangGraph
сериализует полное состояние в каждый чекпоинт каждого супершага: для
документа в сотни разделов это мегабайты векторов, копируемые по несколько
раз за ход. Здесь же пишутся только реально изменившиеся разделы.

Файл отдельный от чекпоинтов (settings.section_index_db_path), чтобы не
конкурировать за блокировки с асинхронным чекпоинтером. Все функции
синхронные — вызываются из узла retrieve, который LangGraph исполняет в
пуле потоков.
"""

import sqlite3
from array import array
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import settings


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    Path(settings.section_index_db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.section_index_db_path, timeout=10)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS section_index (
                session_id TEXT NOT NULL,
                section_id TEXT NOT NULL,
                hash TEXT NOT NULL,
                vector BLOB NOT NULL,
                PRIMARY KEY (session_id, section_id)
            )
            """
        )
        yield conn
        conn.commit()
    finally:
        conn.close()


def load(session_id: str) -> dict[str, dict]:
    """Индекс сессии в формате doc_retriever: {section_id: {"hash", "vector"}}."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT section_id, hash, vector FROM section_index WHERE session_id = ?",
            (session_id,),
        ).fetchall()
    return {
        r[0]: {"hash": r[1], "vector": array("f", r[2]).tolist()} for r in rows
    }


def save(session_id: str, old_index: dict[str, dict], new_index: dict[str, dict]) -> None:
    """Пишет только дельту относительно old_index: новые/изменившиеся разделы
    (по хэшу превью) и удаляет исчезнувшие. Векторы храним как float32-BLOB —
    в 5 раз компактнее JSON, потеря точности для косинусной близости не важна."""
    changed = [
        (sid, v)
        for sid, v in new_index.items()
        if sid not in old_index or old_index[sid]["hash"] != v["hash"]
    ]
    removed = [sid for sid in old_index if sid not in new_index]
    if not changed and not removed:
        return
    with _db() as conn:
        if changed:
            conn.executemany(
                "INSERT OR REPLACE INTO section_index (session_id, section_id, hash, vector) "
                "VALUES (?, ?, ?, ?)",
                [
                    (session_id, sid, v["hash"], array("f", v["vector"]).tobytes())
                    for sid, v in changed
                ],
            )
        if removed:
            conn.executemany(
                "DELETE FROM section_index WHERE session_id = ? AND section_id = ?",
                [(session_id, sid) for sid in removed],
            )


def clear(session_id: str) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM section_index WHERE session_id = ?", (session_id,))
