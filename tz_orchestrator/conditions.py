from typing import Any

from config import settings


def _as_dict(state: Any) -> dict[str, Any]:
    if isinstance(state, dict):
        return state
    return state.model_dump()


def route_after_classifier(state: Any) -> str:
    data = _as_dict(state)
    if data.get("scenario") == "modification":
        legacy = data.get("legacy_tz") or {}
        if legacy.get("chain"):
            return "tz_ingestor"
    return "interviewer"


def route_after_explorer(state: Any) -> str:
    data = _as_dict(state)
    return "diff_analyst" if data.get("scenario") == "modification" else "section_writers"


def route_after_critic(state: Any) -> str:
    data = _as_dict(state)
    report = data.get("critic_report") or {}
    iterations = int(data.get("critic_iterations", 0))
    if report.get("status") == "ok":
        return "renderer"
    if iterations >= settings.critic_max_iterations:
        return "renderer"
    return "section_writers"
