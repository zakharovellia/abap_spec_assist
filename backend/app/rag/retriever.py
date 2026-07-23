import logging

from app.config import settings
from app.rag import embeddings, store

logger = logging.getLogger(__name__)


def retrieve_style_examples(query: str) -> list[dict]:
    """Ищет разделы реальных ТЗ, похожие на запрос.

    Кандидаты берутся с запасом, затем: порог по score (нетематический запрос
    не должен тащить случайные примеры) и дедуп по документу (примеры из
    разных ТЗ передают стиль лучше, чем несколько кусков одного).

    RAG — вспомогательный механизм: при недоступности Qdrant/эмбеддингов
    ассистент продолжает работать без примеров.
    """
    if not query.strip():
        return []
    try:
        vector = embeddings.embed_query(query[:2000])
        candidates = store.search(vector, top_k=settings.rag_top_k * 3)
    except Exception:
        logger.warning("RAG недоступен, продолжаем без примеров", exc_info=True)
        return []
    picked: list[dict] = []
    per_doc: dict[str, int] = {}
    for hit in candidates:  # кандидаты уже отсортированы по убыванию score
        if hit.get("score", 0.0) < settings.rag_min_score:
            continue
        doc = hit.get("source_path") or hit.get("doc_name") or ""
        if per_doc.get(doc, 0) >= settings.rag_max_per_doc:
            continue
        per_doc[doc] = per_doc.get(doc, 0) + 1
        picked.append(hit)
        if len(picked) >= settings.rag_top_k:
            break
    # score кандидатов — в лог: по ним калибруется RAG_MIN_SCORE под модель
    logger.info(
        "RAG: %d кандидатов (score %s) → %d примеров из %d документов",
        len(candidates),
        [round(h.get("score", 0.0), 3) for h in candidates[:6]],
        len(picked),
        len(per_doc),
    )
    return picked


def format_examples(hits: list[dict]) -> str:
    """Собирает блок примеров с общим потолком examples_max_chars: примеры —
    целые разделы, без бюджета они вытеснили бы из контекста документ и историю."""
    if not hits:
        return ""
    limit = settings.examples_max_chars
    blocks: list[str] = []
    used = 0
    for i, hit in enumerate(hits, 1):
        header = f"### Пример {i} — «{hit.get('doc_name', '?')}»"
        if hit.get("section"):
            header += f", раздел «{hit['section']}»"
        block = f"{header}\n\n{hit.get('text', '')}"
        remaining = limit - used
        if remaining <= 0:
            break
        if len(block) > remaining:
            block = block[:remaining] + "\n…(пример обрезан)"
        blocks.append(block)
        used += len(block)
    return "\n\n---\n\n".join(blocks)
