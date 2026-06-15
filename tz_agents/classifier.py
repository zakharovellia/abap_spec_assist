import json
from typing import Any

from core.base_agent import BaseAgent
from core.llm_client import get_client

MODIFICATION_TRIGGERS = (
    "доработ",
    "изменить",
    "добавить поле",
    "исправить",
    "расширить",
    "модифиц",
)

RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "classifier_result",
        "schema": {
            "type": "object",
            "properties": {
                "tz_type": {"type": "string"},
                "scenario": {"type": "string", "enum": ["new", "modification"]},
                "confidence": {"type": "number"},
                "parent_object_hint": {"type": ["string", "null"]},
            },
            "required": ["tz_type", "scenario", "confidence"],
        },
    },
}


class ClassifierAgent(BaseAgent):
    name = "classifier"
    tier = "small"
    temperature = 0.0
    prompt_file = "classifier.md"

    def _heuristic(self, state: dict[str, Any]) -> dict[str, Any]:
        text = (state.get("user_change_request") or "").lower()
        forced_modification = bool(state.get("parent_object_ref")) or bool(
            (state.get("legacy_tz") or {}).get("provided")
        )
        has_trigger = any(t in text for t in MODIFICATION_TRIGGERS)
        scenario = "modification" if forced_modification or has_trigger else "new"
        return {
            "tz_type": state.get("tz_type") or "alv_report",
            "scenario": scenario,
            "confidence": 0.9 if forced_modification else (0.6 if has_trigger else 0.5),
            "parent_object_hint": state.get("parent_object_ref"),
        }

    async def classify(self, state: dict[str, Any]) -> dict[str, Any]:
        client = get_client()
        if not client.api_key or client.api_key == "not-needed":
            return self._heuristic(state)
        try:
            messages = self.build_messages(state.get("user_change_request") or "")
            resp = await self.complete(messages, response_format=RESPONSE_SCHEMA)
            return json.loads(resp.choices[0].message.content)
        except Exception:  # noqa: BLE001
            return self._heuristic(state)

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        result = await self.classify(state)
        if state.get("parent_object_ref"):
            result["scenario"] = "modification"
        return {
            "classifier": result,
            "tz_type": result["tz_type"],
            "scenario": result["scenario"],
            "parent_object_ref": result.get("parent_object_hint")
            or state.get("parent_object_ref"),
        }
