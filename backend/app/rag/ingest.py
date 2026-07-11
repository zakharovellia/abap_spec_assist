"""Чанкинг примеров ТЗ и загрузка в Qdrant."""

import re

from app.rag import embeddings, store

MAX_CHUNK_CHARS = 1800

_HEADING_RE = re.compile(r"^(#{1,2})\s+(.*)$", re.MULTILINE)


def split_into_chunks(markdown: str) -> list[dict]:
    """Режет документ по заголовкам H1/H2; длинные разделы — по абзацам."""
    sections: list[tuple[str, str]] = []
    matches = list(_HEADING_RE.finditer(markdown))
    if not matches:
        sections = [("", markdown)]
    else:
        preamble = markdown[: matches[0].start()].strip()
        if preamble:
            sections.append(("", preamble))
        for m, nxt in zip(matches, [*matches[1:], None]):
            end = nxt.start() if nxt else len(markdown)
            body = markdown[m.start() : end].strip()
            if body:
                sections.append((m.group(2).strip(), body))

    chunks: list[dict] = []
    for title, body in sections:
        for part in _split_long(body):
            chunks.append({"section": title, "text": part})
    return chunks


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    parts: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        if current and len(current) + len(para) + 2 > MAX_CHUNK_CHARS:
            parts.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        parts.append(current)
    return parts


def ingest_example(
    doc_name: str,
    markdown: str,
    *,
    source_path: str,
    content_hash: str,
) -> int:
    """(Пере)индексирует один пример ТЗ: старые чанки файла удаляются.

    Возвращает число чанков.
    """
    chunks = split_into_chunks(markdown)
    store.delete_doc(source_path)
    if not chunks:
        return 0
    vectors = embeddings.embed_passages([c["text"] for c in chunks])
    payloads = [
        {
            "doc_name": doc_name,
            "source_path": source_path,
            "content_hash": content_hash,
            **c,
        }
        for c in chunks
    ]
    store.upsert_chunks(vectors, payloads)
    return len(chunks)
