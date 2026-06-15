import asyncio

from sqlalchemy import select

from core.db import connection
from core.qdrant_client import ensure_collection, upsert_example
from core.tables import tz_examples_registry
from tz_indexer.embed import embed_sections


async def reindex() -> int:
    await ensure_collection()
    async with connection() as conn:
        result = await conn.execute(select(tz_examples_registry))
        rows = [dict(r._mapping) for r in result.fetchall()]

    if not rows:
        return 0

    vectors = await embed_sections([r["content"] for r in rows])
    for row, vector in zip(rows, vectors, strict=True):
        await upsert_example(
            point_id=row["id"],
            vector=vector,
            payload={
                "tz_type": row["tz_type"],
                "scenario": row["scenario"],
                "section_type": row["section_type"],
                "content": row["content"],
                "source_tz_id": row.get("source_tz_id"),
                "quality_score": row.get("quality_score", 1.0),
                "embedding_model": row.get("embedding_model"),
                "metadata": row.get("metadata", {}),
            },
        )
    return len(rows)


if __name__ == "__main__":
    print(asyncio.run(reindex()))
