from typing import Any

from core.base_agent import BaseAgent
from schemas.tz_alv_report import REQUIRED_SECTIONS_NEW


class InterviewerAgent(BaseAgent):
    name = "interviewer"
    tier = "medium"
    prompt_file = "interviewer.md"

    def missing_fields(self, state: dict[str, Any]) -> list[str]:
        payload = state.get("payload") or {}
        return [s for s in REQUIRED_SECTIONS_NEW if not payload.get(s)]

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        payload = dict(state.get("payload") or {})
        request = state.get("user_change_request") or ""
        if "business_context" not in payload:
            payload["business_context"] = {"goal": request, "stakeholders": []}
        if "header" not in payload:
            payload["header"] = {
                "title": request[:120] or "Без названия",
                "author": state.get("author_id"),
                "priority": "M",
            }
        return {"payload": payload}
