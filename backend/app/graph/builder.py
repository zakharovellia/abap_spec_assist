from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.config import settings
from app.graph.prompts import (
    EMPTY_SPEC_PLACEHOLDER,
    NO_EXAMPLES_PLACEHOLDER,
    SYSTEM_PROMPT,
)
from app.graph.state import SpecState
from app.rag.retriever import format_examples, retrieve_style_examples


class update_spec(BaseModel):
    """Полностью заменить текущий документ ТЗ новой версией.

    Всегда передавай ПОЛНЫЙ текст документа в Markdown, а не фрагмент или diff.
    """

    spec_markdown: str = Field(
        description="Полный новый текст документа ТЗ в формате Markdown"
    )


def _make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
    )


def build_graph(sap_tools: list | None = None):
    sap_tools = sap_tools or []
    sap_by_name = {t.name: t for t in sap_tools}
    llm_with_tools = _make_llm().bind_tools([update_spec, *sap_tools])

    def retrieve(state: SpecState) -> dict:
        query = next(
            (
                m.content
                for m in reversed(state["messages"])
                if isinstance(m, HumanMessage) and isinstance(m.content, str)
            ),
            "",
        )
        hits = retrieve_style_examples(query)
        return {"style_examples": format_examples(hits)}

    async def assistant(state: SpecState) -> dict:
        spec = state.get("spec_markdown") or EMPTY_SPEC_PLACEHOLDER
        examples = state.get("style_examples") or NO_EXAMPLES_PLACEHOLDER
        system = SystemMessage(content=SYSTEM_PROMPT.format(spec=spec, examples=examples))
        response = await llm_with_tools.ainvoke([system, *state["messages"]])
        return {"messages": [response]}

    async def tools(state: SpecState) -> dict:
        last = state["messages"][-1]
        assert isinstance(last, AIMessage)
        spec_changed = False
        spec = state.get("spec_markdown", "")
        tool_messages: list[ToolMessage] = []
        for call in last.tool_calls:
            if call["name"] == update_spec.__name__:
                spec = call["args"]["spec_markdown"]
                spec_changed = True
                result = "Документ ТЗ обновлён."
            elif call["name"] in sap_by_name:
                try:
                    result = str(await sap_by_name[call["name"]].ainvoke(call["args"]))
                except Exception as exc:  # noqa: BLE001 — сбой MCP не должен ронять ход
                    result = f"Инструмент {call['name']} недоступен: {exc}"
            else:
                result = f"Неизвестный инструмент: {call['name']}"
            tool_messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
        update: dict = {"messages": tool_messages}
        if spec_changed:
            update["spec_markdown"] = spec
        return update

    def route(state: SpecState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(SpecState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("assistant", assistant)
    graph.add_node("tools", tools)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "assistant")
    graph.add_conditional_edges("assistant", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "assistant")
    return graph.compile(checkpointer=MemorySaver())
