import logging

from app.config import settings
from app.rag import embeddings, store

logger = logging.getLogger(__name__)


def retrieve_style_examples(query: str) -> list[dict]:
    """Ищет фрагменты реальных ТЗ, похожие на запрос.

    RAG — вспомогательный механизм: при недоступности Qdrant/эмбеддингов
    ассистент продолжает работать без примеров.
    """
    if not query.strip():
        return []
    try:
        vector = embeddings.embed_query(query[:2000])
        hits = store.search(vector, top_k=settings.rag_top_k)
        logger.info("RAG: найдено %d фрагментов примеров ТЗ", len(hits))
        return hits
    except Exception:
        logger.warning("RAG недоступен, продолжаем без примеров", exc_info=True)
        return []


def format_examples(hits: list[dict]) -> str:
    if not hits:
        return ""
    blocks = []
    for i, hit in enumerate(hits, 1):
        header = f"### Пример {i} — «{hit.get('doc_name', '?')}»"
        if hit.get("section"):
            header += f", раздел «{hit['section']}»"
        blocks.append(f"{header}\n\n{hit.get('text', '')}")
    return "\n\n---\n\n".join(blocks)
