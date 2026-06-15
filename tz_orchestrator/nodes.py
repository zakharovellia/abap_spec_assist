import asyncio
from typing import Any

from tz_agents.classifier import ClassifierAgent
from tz_agents.critic import CriticAgent
from tz_agents.diff_analyst import DiffAnalystAgent
from tz_agents.interviewer import InterviewerAgent
from tz_agents.renderer import RendererAgent
from tz_agents.sap_explorer import SapExplorerAgent
from tz_agents.section_writers import (
    DEPENDENT_SECTIONS,
    INDEPENDENT_SECTIONS,
    SECTION_WRITERS,
)
from tz_agents.tz_ingestor import TzIngestorAgent


def _as_dict(state: Any) -> dict[str, Any]:
    if isinstance(state, dict):
        return state
    return state.model_dump()


async def classifier_node(state: Any) -> dict[str, Any]:
    return await ClassifierAgent().run(_as_dict(state))


async def tz_ingestor_node(state: Any) -> dict[str, Any]:
    return await TzIngestorAgent().run(_as_dict(state))


async def interviewer_node(state: Any) -> dict[str, Any]:
    return await InterviewerAgent().run(_as_dict(state))


async def sap_explorer_node(state: Any) -> dict[str, Any]:
    return await SapExplorerAgent().run(_as_dict(state))


async def diff_analyst_node(state: Any) -> dict[str, Any]:
    return await DiffAnalystAgent().run(_as_dict(state))


async def section_writers_node(state: Any) -> dict[str, Any]:
    data = _as_dict(state)
    payload = dict(data.get("payload") or {})

    independent = await asyncio.gather(
        *(SECTION_WRITERS[s].write(data) for s in INDEPENDENT_SECTIONS)
    )
    for name, result in zip(INDEPENDENT_SECTIONS, independent, strict=True):
        payload.setdefault(name, result)

    enriched = {**data, "payload": payload}
    for name in DEPENDENT_SECTIONS:
        payload.setdefault(name, await SECTION_WRITERS[name].write(enriched))

    return {"payload": payload}


async def critic_node(state: Any) -> dict[str, Any]:
    return await CriticAgent().run(_as_dict(state))


async def renderer_node(state: Any) -> dict[str, Any]:
    return await RendererAgent().run(_as_dict(state))
