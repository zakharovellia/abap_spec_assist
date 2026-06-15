from typing import Any

from core.base_agent import BaseAgent


class DiffAnalystAgent(BaseAgent):
    name = "diff_analyst"
    tier = "strong"
    temperature = 0.0
    prompt_file = "diff_analyst.md"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        legacy_provided = bool((state.get("legacy_tz") or {}).get("provided"))
        analysis = state.get("current_state_analysis") or {}
        diff: dict[str, Any] = {
            "current_behavior": analysis.get("code_summary", ""),
            "requested_changes": [],
            "out_of_scope_warnings": [],
            "regression_risks": [],
        }
        if legacy_provided:
            diff["documented_in_legacy"] = analysis.get("documented_in_legacy", [])
            diff["undocumented_drift"] = analysis.get("undocumented_drift", [])
        else:
            diff["inferred_behavior"] = analysis.get("code_summary", "")
        return {"diff_analysis": diff}
