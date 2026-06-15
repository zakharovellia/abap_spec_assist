from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph import END, START, StateGraph

from schemas.tz_state import TzState
from tz_orchestrator.conditions import (
    route_after_classifier,
    route_after_critic,
    route_after_explorer,
)
from tz_orchestrator.nodes import (
    classifier_node,
    critic_node,
    diff_analyst_node,
    interviewer_node,
    renderer_node,
    sap_explorer_node,
    section_writers_node,
    tz_ingestor_node,
)


def build_graph() -> StateGraph:
    graph = StateGraph(TzState)

    graph.add_node("classifier", classifier_node)
    graph.add_node("tz_ingestor", tz_ingestor_node)
    graph.add_node("interviewer", interviewer_node)
    graph.add_node("sap_explorer", sap_explorer_node)
    graph.add_node("diff_analyst", diff_analyst_node)
    graph.add_node("section_writers", section_writers_node)
    graph.add_node("critic", critic_node)
    graph.add_node("renderer", renderer_node)

    graph.add_edge(START, "classifier")
    graph.add_conditional_edges(
        "classifier",
        route_after_classifier,
        {"tz_ingestor": "tz_ingestor", "interviewer": "interviewer"},
    )
    graph.add_edge("tz_ingestor", "interviewer")
    graph.add_edge("interviewer", "sap_explorer")
    graph.add_conditional_edges(
        "sap_explorer",
        route_after_explorer,
        {"diff_analyst": "diff_analyst", "section_writers": "section_writers"},
    )
    graph.add_edge("diff_analyst", "section_writers")
    graph.add_edge("section_writers", "critic")
    graph.add_conditional_edges(
        "critic",
        route_after_critic,
        {"section_writers": "section_writers", "renderer": "renderer"},
    )
    graph.add_edge("renderer", END)

    return graph


def initial_state(doc_id: str, document: dict[str, Any], message: str | None = None) -> TzState:
    return TzState(
        tz_id=doc_id,
        author_id=document.get("author_id", "unknown"),
        tz_type=document.get("tz_type"),
        scenario=document.get("scenario", "new"),
        parent_object_ref=document.get("parent_object_ref"),
        user_change_request=message or document.get("title"),
    )


async def run_generation_stream(
    *,
    doc_id: str,
    document: dict[str, Any],
    message: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    from core.checkpointer import get_checkpointer

    graph = build_graph()
    config = {"configurable": {"thread_id": doc_id}}
    state = initial_state(doc_id, document, message)

    async with get_checkpointer() as checkpointer:
        compiled = graph.compile(checkpointer=checkpointer)
        async for chunk in compiled.astream(state, config=config, stream_mode="updates"):
            for node_name, update in chunk.items():
                yield {"event": "node", "node": node_name, "update": update}


async def run_generation(
    *,
    doc_id: str,
    document: dict[str, Any],
    message: str | None = None,
) -> dict[str, Any]:
    from core.checkpointer import get_checkpointer

    graph = build_graph()
    config = {"configurable": {"thread_id": doc_id}}
    state = initial_state(doc_id, document, message)

    async with get_checkpointer() as checkpointer:
        compiled = graph.compile(checkpointer=checkpointer)
        result = await compiled.ainvoke(state, config=config)
    return result if isinstance(result, dict) else result.model_dump()
