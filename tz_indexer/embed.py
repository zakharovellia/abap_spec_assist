from core.embeddings import get_embedder


async def embed_sections(texts: list[str]) -> list[list[float]]:
    embedder = get_embedder()
    return await embedder.embed(texts)
