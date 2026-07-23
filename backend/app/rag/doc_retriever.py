"""Ретривал по разделам РАБОЧЕГО документа ТЗ (в отличие от rag/retriever.py,
который ищет похожие фрагменты в базе примеров).

Нужен, чтобы на каждый ход в промпт подгружались только несколько релевантных
разделов, а не весь документ — при документе на 200 000 слов оглавление
из десятков разделов иначе не помещается в контекст.

Эмбеддится не всё тело раздела, а заголовок + короткий превью — это на
порядок дешевле для больших разделов и не требует пересчёта при правках,
не задевающих начало раздела. Векторы кэшируются в состоянии сессии
(section_index) и пересчитываются только для новых/изменившихся разделов.
"""

import hashlib
import logging
import math

from app.config import settings
from app.rag import embeddings

logger = logging.getLogger(__name__)

PREVIEW_CHARS = 800


def _preview(section: dict) -> str:
    return f"{section['title']}\n{section['body'][:PREVIEW_CHARS]}"


def _hash(text: str) -> str:
    # Имя модели — часть хэша: смена модели эмбеддингов инвалидирует кэш,
    # иначе старые векторы в чужом векторном пространстве (и, возможно, другой
    # размерности) тихо ломали бы ранжирование разделов
    return hashlib.sha256(
        f"{settings.embeddings_model}\n{text}".encode("utf-8")
    ).hexdigest()


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def relevant_section_ids(
    sections: list[dict],
    query: str,
    index: dict[str, dict],
    top_k: int,
) -> tuple[list[str], dict[str, dict]]:
    """Возвращает id самых релевантных разделов и обновлённый кэш эмбеддингов
    (index: {section_id: {"hash", "vector"}}, переживает ходы в состоянии сессии).

    При недоступности эмбеддингов — как и retriever.py — не роняем ход,
    просто отдаём первые top_k разделов без ранжирования.
    """
    if not sections:
        return [], index

    live_ids = {s["id"] for s in sections}
    new_index = {sid: v for sid, v in index.items() if sid in live_ids}

    if not query.strip():
        return [s["id"] for s in sections[:top_k]], new_index

    to_embed_ids: list[str] = []
    to_embed_texts: list[str] = []
    for s in sections:
        preview = _preview(s)
        h = _hash(preview)
        cached = new_index.get(s["id"])
        if not cached or cached["hash"] != h:
            to_embed_ids.append(s["id"])
            to_embed_texts.append(preview)

    try:
        if to_embed_texts:
            vectors = embeddings.embed_passages(to_embed_texts)
            for sid, text, vec in zip(to_embed_ids, to_embed_texts, vectors):
                new_index[sid] = {"hash": _hash(text), "vector": vec}
        qvec = embeddings.embed_query(query[:2000])
        scored = sorted(
            (s["id"] for s in sections if s["id"] in new_index),
            key=lambda sid: -_cosine(qvec, new_index[sid]["vector"]),
        )
        top_ids = scored[:top_k]
        logger.info("Ретривал по документу: релевантные разделы %s", top_ids)
        return top_ids, new_index
    except Exception:
        logger.warning(
            "Ретривал по разделам документа недоступен, берём первые разделы",
            exc_info=True,
        )
        return [s["id"] for s in sections[:top_k]], new_index
