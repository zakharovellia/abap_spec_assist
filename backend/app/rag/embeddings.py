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


def _is_e5() -> bool:
    return "e5" in settings.embeddings_model.lower()


def _embed(texts: list[str]) -> list[list[float]]:
    resp = _client().embeddings.create(model=settings.embeddings_model, input=texts)
    return [item.embedding for item in resp.data]


def embed_passages(texts: list[str]) -> list[list[float]]:
    # e5-модели обучены с префиксами passage:/query: — без них качество падает
    if _is_e5():
        texts = [f"passage: {t}" for t in texts]
    return _embed(texts)


def embed_query(text: str) -> list[float]:
    if _is_e5():
        text = f"query: {text}"
    return _embed([text])[0]
