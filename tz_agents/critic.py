from typing import Any

from core.base_agent import BaseAgent


class CriticAgent(BaseAgent):
    name = "critic"
    tier = "strong"
    temperature = 0.0

    def prompt_for(self, scenario: str) -> str:
        self.prompt_file = (
            "critic_modification.md" if scenario == "modification" else "critic_new.md"
        )
        return self.system_prompt()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        from schemas.tz_alv_report import (
            REQUIRED_SECTIONS_MODIFICATION,
            REQUIRED_SECTIONS_NEW,
        )

        scenario = state.get("scenario", "new")
        required = (
            REQUIRED_SECTIONS_MODIFICATION
            if scenario == "modification"
            else REQUIRED_SECTIONS_NEW
        )
        payload = state.get("payload") or {}
        merged = {**payload}
        if scenario == "modification":
            merged.setdefault("diff_analysis", state.get("diff_analysis"))

        issues = [
            {"section": s, "problem": "секция не заполнена", "fix_hint": "сгенерировать секцию"}
            for s in required
            if not merged.get(s)
        ]
        iterations = int(state.get("critic_iterations", 0)) + 1
        status = "ok" if not issues else "needs_revision"
        return {
            "critic_report": {"status": status, "issues": issues},
            "critic_iterations": iterations,
        }
