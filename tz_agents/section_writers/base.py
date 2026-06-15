from typing import Any

from core.base_agent import BaseAgent
from core.llm_client import ModelTier


class SectionWriter(BaseAgent):
    section_type: str = "generic"

    def __init__(
        self,
        section_type: str,
        *,
        tier: ModelTier = "medium",
        prompt_new: str | None = None,
        prompt_modification: str | None = None,
    ) -> None:
        self.section_type = section_type
        self.tier = tier
        self._prompt_new = prompt_new
        self._prompt_modification = prompt_modification

    def prompt_file_for(self, scenario: str) -> str | None:
        return self._prompt_modification if scenario == "modification" else self._prompt_new

    async def write(self, state: dict[str, Any]) -> Any:
        scenario = state.get("scenario", "new")
        self.prompt_file = self.prompt_file_for(scenario)
        payload = state.get("payload") or {}
        existing = payload.get(self.section_type)
        if existing:
            return existing
        return {"generated": True, "section": self.section_type, "scenario": scenario}
