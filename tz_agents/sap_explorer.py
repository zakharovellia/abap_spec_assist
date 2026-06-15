from typing import Any

from config import settings
from core.base_agent import BaseAgent


class SapExplorerAgent(BaseAgent):
    name = "sap_explorer"
    tier = "strong"
    prompt_file = "sap_explorer_new.md"

    def limits(self, scenario: str) -> tuple[int, int]:
        if scenario == "modification":
            return (
                settings.explorer.modification_max_calls,
                settings.explorer.modification_max_tokens,
            )
        return settings.explorer.new_max_calls, settings.explorer.new_max_tokens

    def prompt_for(self, scenario: str) -> str:
        self.prompt_file = (
            "sap_explorer_modification.md" if scenario == "modification" else "sap_explorer_new.md"
        )
        return self.system_prompt()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        scenario = state.get("scenario", "new")
        max_calls, max_tokens = self.limits(scenario)
        parent = state.get("parent_object_ref")

        research_step = {
            "step": 1,
            "tool": "search_object",
            "args": {"query": parent or "n/a"},
            "reason": "Поиск упомянутых объектов SAP для сбора технического контекста",
            "result_summary": "stub: MCP не вызывался (dev)",
        }
        analysis: dict[str, Any] = {
            "code_summary": "",
            "actually_used_tables": [],
            "limits": {"max_calls": max_calls, "max_tokens": max_tokens},
        }
        if scenario == "modification":
            analysis.update(
                {
                    "documented_in_legacy": [],
                    "undocumented_drift": [],
                    "callers": [],
                }
            )
        return {
            "current_state_analysis": analysis,
            "research_log": [research_step],
        }
