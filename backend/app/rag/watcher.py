"""Фоновая синхронизация базы примеров ТЗ с папкой settings.examples_dir.

Периодически сканирует папку (рекурсивно): новые и изменённые файлы
(.docx/.md/.txt) индексируются в Qdrant, удалённые из папки — удаляются
из базы. Отслеживание изменений — по sha256 содержимого, хэш хранится
в payload чанков, поэтому состояние переживает перезапуск.
"""

import asyncio
import hashlib
import logging
from pathlib import Path

from app.config import settings
from app.docx_parse import file_to_markdown
from app.rag import store
from app.rag.ingest import ingest_example

logger = logging.getLogger(__name__)

EXTENSIONS = {".docx", ".md", ".markdown", ".txt"}


def scan_once() -> None:
    folder = Path(settings.examples_dir)
    if not folder.is_dir():
        logger.debug("Папка примеров %s не существует, пропускаем скан", folder)
        return

    seen: set[str] = set()
    added = updated = 0
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() not in EXTENSIONS or path.name.startswith("~$"):
            continue
        source_path = str(path.resolve())
        seen.add(source_path)
        try:
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            known = store.get_doc_hash(source_path)
            if known == digest:
                continue
            chunks = ingest_example(
                path.name,
                file_to_markdown(path.name, data),
                source_path=source_path,
                content_hash=digest,
            )
        except Exception:
            logger.warning("Не удалось проиндексировать %s", path, exc_info=True)
            continue
        if known is None:
            added += 1
        else:
            updated += 1
        logger.info("Примеры ТЗ: %s → %d чанков", path.name, chunks)

    removed = 0
    for stale in store.list_source_paths() - seen:
        store.delete_doc(stale)
        removed += 1
        logger.info("Примеры ТЗ: %s удалён из базы (файла больше нет)", stale)

    if added or updated or removed:
        logger.info(
            "Синхронизация примеров ТЗ: +%d новых, ~%d обновлено, -%d удалено",
            added,
            updated,
            removed,
        )


async def watch_examples_dir() -> None:
    while True:
        try:
            await asyncio.to_thread(scan_once)
        except Exception:
            logger.warning("Скан папки примеров не удался", exc_info=True)
        await asyncio.sleep(settings.examples_scan_interval_seconds)
