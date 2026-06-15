from functools import lru_cache

from config import settings


class Embedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    async def embed_one(self, text: str) -> list[float]:
        result = await self.embed([text])
        return result[0]


class APIEmbedder(Embedder):
    def __init__(self) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            base_url=settings.embeddings.base_url,
            api_key=settings.embeddings.api_key or "not-needed",
        )
        self._model = settings.embeddings.model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in resp.data]


class LocalEmbedder(Embedder):
    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(settings.embeddings.local_model)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    if settings.embeddings.provider == "local":
        return LocalEmbedder()
    return APIEmbedder()
