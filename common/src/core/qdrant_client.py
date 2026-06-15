from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    Range,
    VectorParams,
)

from config import settings

_client: AsyncQdrantClient | None = None


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=settings.qdrant.url,
            api_key=settings.qdrant.api_key or None,
        )
    return _client


async def ensure_collection(dim: int | None = None) -> None:
    client = get_client()
    name = settings.qdrant.collection
    exists = await client.collection_exists(name)
    if exists:
        return
    await client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=dim or settings.embeddings.dim,
            distance=Distance.COSINE,
        ),
    )
    for field in ("tz_type", "scenario", "section_type", "source_tz_id"):
        await client.create_payload_index(name, field, PayloadSchemaType.KEYWORD)
    await client.create_payload_index(name, "quality_score", PayloadSchemaType.FLOAT)


async def upsert_example(
    point_id: str,
    vector: list[float],
    payload: dict[str, Any],
) -> None:
    client = get_client()
    await client.upsert(
        collection_name=settings.qdrant.collection,
        points=[PointStruct(id=point_id, vector=vector, payload=payload)],
    )


async def search_examples(
    query_vector: list[float],
    *,
    tz_type: str,
    scenario: str,
    section_type: str,
    min_quality: float = 0.0,
    limit: int = 5,
) -> list[Any]:
    client = get_client()
    must = [
        FieldCondition(key="tz_type", match=MatchValue(value=tz_type)),
        FieldCondition(key="scenario", match=MatchValue(value=scenario)),
        FieldCondition(key="section_type", match=MatchValue(value=section_type)),
    ]
    query_filter = Filter(
        must=must,
        should=[FieldCondition(key="quality_score", range=Range(gte=min_quality))]
        if min_quality
        else None,
    )
    hits = await client.search(
        collection_name=settings.qdrant.collection,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )
    return sorted(
        hits,
        key=lambda h: h.score * float((h.payload or {}).get("quality_score", 1.0)),
        reverse=True,
    )


async def set_quality_score(point_id: str, quality_score: float) -> None:
    client = get_client()
    await client.set_payload(
        collection_name=settings.qdrant.collection,
        payload={"quality_score": quality_score},
        points=[point_id],
    )
