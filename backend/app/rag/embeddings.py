from functools import lru_cache

from openai import OpenAI

from app.config import settings


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(
        base_url=settings.embeddings_base_url or settings.llm_base_url,
        api_key=settings.embeddings_api_key or settings.llm_api_key,
        timeout=settings.llm_timeout_seconds,
    )


def _prefixes() -> tuple[str, str]:
    """(префикс документа, префикс запроса) для семейства модели эмбеддингов.

    Retrieval-модели обучены с префиксами, без них качество заметно падает:
    - FRIDA (SberDevices): search_document:/search_query:
      https://habr.com/ru/companies/sberdevices/articles/909924/
    - e5 (intfloat/multilingual-e5-*): passage:/query:
    Семейство определяется по подстроке в имени модели, чтобы покрыть разные
    id у шлюзов ("frida", "ai-forever/FRIDA", "multilingual-e5-large", ...).
    """
    name = settings.embeddings_model.lower()
    if "frida" in name:
        return "search_document: ", "search_query: "
    if "e5" in name:
        return "passage: ", "query: "
    return "", ""


# Первое сообщение после загрузки большого ТЗ эмбеддит превью сотен разделов
# разом — многие embedding-серверы ограничивают размер батча, поэтому режем.
_BATCH_SIZE = 64


def _embed(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        resp = _client().embeddings.create(
            model=settings.embeddings_model, input=texts[i : i + _BATCH_SIZE]
        )
        out.extend(item.embedding for item in resp.data)
    return out


def embed_passages(texts: list[str]) -> list[list[float]]:
    prefix = _prefixes()[0]
    return _embed([prefix + t for t in texts])


def embed_query(text: str) -> list[float]:
    prefix = _prefixes()[1]
    return _embed([prefix + text])[0]
