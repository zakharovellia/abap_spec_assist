from typing import Any

from core.base_agent import BaseAgent


class TzIngestorAgent(BaseAgent):
    name = "tz_ingestor"
    tier = "medium"
    prompt_file = "tz_ingestor.md"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        legacy = dict(state.get("legacy_tz") or {})
        if not legacy.get("chain"):
            legacy.setdefault("provided", False)
            legacy.setdefault("chain", [])
        else:
            legacy["provided"] = True
            legacy["chain"] = sorted(
                legacy["chain"], key=lambda item: item.get("legacy_date") or ""
            )
        return {"legacy_tz": legacy}
