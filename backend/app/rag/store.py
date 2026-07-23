"""Обёртка над Qdrant: коллекция примеров реальных ТЗ."""

import logging
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


logger = logging.getLogger(__name__)


def ensure_collection(dim: int) -> None:
    client = get_client()
    if client.collection_exists(settings.qdrant_collection):
        current = client.get_collection(settings.qdrant_collection).config.params.vectors.size
        if current == dim:
            return
        # Размерность сменилась вместе с моделью эмбеддингов — старые векторы
        # в любом случае бесполезны, пересоздаём коллекцию. Примеры нужно
        # перезалить через панель «База примеров».
        logger.warning(
            "Размерность эмбеддингов изменилась (%d → %d) — коллекция %s пересоздана, "
            "перезалейте примеры ТЗ",
            current,
            dim,
            settings.qdrant_collection,
        )
        client.delete_collection(settings.qdrant_collection)
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


def list_docs() -> list[dict]:
    """Документы базы примеров: имя, ключ (source_path) и число чанков."""
    client = get_client()
    if not client.collection_exists(settings.qdrant_collection):
        return []
    docs: dict[str, dict] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=settings.qdrant_collection,
            limit=256,
            offset=offset,
            with_payload=["source_path", "doc_name"],
        )
        for p in points:
            payload = p.payload or {}
            source = payload.get("source_path")
            if not source:
                continue
            doc = docs.setdefault(
                source,
                {"name": payload.get("doc_name") or source, "source": source, "chunks": 0},
            )
            doc["chunks"] += 1
        if offset is None:
            break
    return sorted(docs.values(), key=lambda d: d["name"].lower())


def _source_filter(source_path: str) -> Filter:
    return Filter(
        must=[FieldCondition(key="source_path", match=MatchValue(value=source_path))]
    )


def delete_doc(source_path: str) -> None:
    client = get_client()
    if not client.collection_exists(settings.qdrant_collection):
        return
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=FilterSelector(filter=_source_filter(source_path)),
    )
