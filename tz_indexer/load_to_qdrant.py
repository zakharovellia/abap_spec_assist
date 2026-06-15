from typing import Any

from core.qdrant_client import ensure_collection, upsert_example


async def load_examples(examples: list[dict[str, Any]]) -> int:
    await ensure_collection()
    count = 0
    for ex in examples:
        await upsert_example(
            point_id=ex["id"],
            vector=ex["vector"],
            payload={
                "tz_type": ex["tz_type"],
                "scenario": ex["scenario"],
                "section_type": ex["section_type"],
                "content": ex["content"],
                "source_tz_id": ex.get("source_tz_id"),
                "quality_score": ex.get("quality_score", 1.0),
                "embedding_model": ex.get("embedding_model"),
                "metadata": ex.get("metadata", {}),
            },
        )
        count += 1
    return count
