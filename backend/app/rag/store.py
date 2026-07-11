"""Обёртка над Qdrant: коллекция примеров реальных ТЗ."""

import uuid
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import settings


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    url = settings.qdrant_url
    if url == ":memory:":
        return QdrantClient(location=":memory:")
    if not url.startswith(("http://", "https://")):
        return QdrantClient(path=url)
    return QdrantClient(url=url, api_key=settings.qdrant_api_key or None)


def ensure_collection(dim: int) -> None:
    client = get_client()
    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def upsert_chunks(vectors: list[list[float]], payloads: list[dict]) -> None:
    ensure_collection(dim=len(vectors[0]))
    points = [
        PointStruct(id=uuid.uuid4().hex, vector=vec, payload=payload)
        for vec, payload in zip(vectors, payloads)
    ]
    get_client().upsert(collection_name=settings.qdrant_collection, points=points)


def search(query_vector: list[float], top_k: int) -> list[dict]:
    client = get_client()
    if not client.collection_exists(settings.qdrant_collection):
        return []
    hits = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=top_k,
    ).points
    return [{**(hit.payload or {}), "score": hit.score} for hit in hits]


def count_examples() -> int:
    client = get_client()
    if not client.collection_exists(settings.qdrant_collection):
        return 0
    return client.count(collection_name=settings.qdrant_collection).count


def _source_filter(source_path: str) -> Filter:
    return Filter(
        must=[FieldCondition(key="source_path", match=MatchValue(value=source_path))]
    )


def get_doc_hash(source_path: str) -> str | None:
    """Хэш содержимого, с которым файл был проиндексирован (None — файла нет в базе)."""
    client = get_client()
    if not client.collection_exists(settings.qdrant_collection):
        return None
    points, _ = client.scroll(
        collection_name=settings.qdrant_collection,
        scroll_filter=_source_filter(source_path),
        limit=1,
        with_payload=["content_hash"],
    )
    if not points:
        return None
    return (points[0].payload or {}).get("content_hash")


def delete_doc(source_path: str) -> None:
    client = get_client()
    if not client.collection_exists(settings.qdrant_collection):
        return
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=FilterSelector(filter=_source_filter(source_path)),
    )


def list_source_paths() -> set[str]:
    """Все source_path, присутствующие в коллекции."""
    client = get_client()
    if not client.collection_exists(settings.qdrant_collection):
        return set()
    paths: set[str] = set()
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=settings.qdrant_collection,
            limit=256,
            offset=offset,
            with_payload=["source_path"],
        )
        for p in points:
            if path := (p.payload or {}).get("source_path"):
                paths.add(path)
        if offset is None:
            return paths
