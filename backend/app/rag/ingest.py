"""Чанкинг примеров ТЗ и загрузка в Qdrant.

Единица индексации — раздел документа (по заголовкам H1/H2): стиль ТЗ
(структура таблиц полей, нумерация шагов алгоритма, глубина детализации)
живёт на уровне раздела, обрывки в пару абзацев его не передают. Поэтому
в промпт попадает раздел целиком (до MAX_CHUNK_CHARS), а эмбеддится только
заголовок + начало раздела: у retrieval-моделей (FRIDA, e5) предел 512
токенов (~1200 символов русского), всё сверх этого модель эмбеддингов молча
отбросила бы — тот же приём, что в rag/doc_retriever.py для рабочего документа.
"""

import re

from app.rag import embeddings, store

# Потолок текста одного примера (показывается в промпте целиком); разделы
# длиннее режутся на части по абзацам
MAX_CHUNK_CHARS = 8000
# Эмбеддится заголовок + это начало текста (лимит FRIDA/e5 — 512 токенов)
EMBED_PREVIEW_CHARS = 1000

_HEADING_RE = re.compile(r"^(#{1,2})\s+(.*)$", re.MULTILINE)


def split_into_chunks(markdown: str) -> list[dict]:
    """Режет документ на разделы по заголовкам H1/H2; слишком длинные разделы —
    на части по абзацам."""
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


def _embed_text(chunk: dict) -> str:
    preview = chunk["text"][:EMBED_PREVIEW_CHARS]
    return f"{chunk['section']}\n{preview}" if chunk["section"] else preview


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
    vectors = embeddings.embed_passages([_embed_text(c) for c in chunks])
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
