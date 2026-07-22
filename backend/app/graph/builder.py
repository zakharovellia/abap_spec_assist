from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app import spec_doc
from app.config import settings
from app.graph.prompts import NO_EXAMPLES_PLACEHOLDER, SYSTEM_PROMPT
from app.graph.state import SpecState
from app.rag.doc_retriever import relevant_section_ids
from app.rag.retriever import format_examples, retrieve_style_examples


class list_sections(BaseModel):
    """Показать оглавление документа ТЗ целиком: id, заголовок и объём каждого раздела."""


class get_section(BaseModel):
    """Получить полный текст одного раздела документа ТЗ по его id из оглавления."""

    section_id: str = Field(description="id раздела из <toc> или из list_sections")


class update_section(BaseModel):
    """Заменить один раздел документа ТЗ новой версией целиком (включая строку заголовка).

    Используй только для ОДНОГО раздела за вызов — никогда не пытайся передать так
    весь документ.
    """

    section_id: str = Field(description="id заменяемого раздела")
    new_text: str = Field(
        description="Полный новый текст раздела в Markdown, включая строку заголовка (#/##/...)"
    )


class insert_section(BaseModel):
    """Добавить новый раздел в документ ТЗ."""

    after_section_id: str | None = Field(
        default=None,
        description="id раздела, после которого вставить новый; не указывай, чтобы вставить в начало",
    )
    level: int = Field(description="Уровень заголовка нового раздела, 1-6")
    title: str = Field(description="Заголовок нового раздела, без решёток")
    body: str = Field(default="", description="Текст раздела в Markdown, без строки заголовка")


class delete_section(BaseModel):
    """Удалить раздел документа ТЗ по id."""

    section_id: str = Field(description="id удаляемого раздела")


DOC_TOOLS = [list_sections, get_section, update_section, insert_section, delete_section]
DOC_WRITE_TOOLS = {update_section.__name__, insert_section.__name__, delete_section.__name__}


def _make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
    )


def build_graph(checkpointer: BaseCheckpointSaver, sap_tools: list | None = None):
    sap_tools = sap_tools or []
    sap_by_name = {t.name: t for t in sap_tools}
    llm_with_tools = _make_llm().bind_tools([*DOC_TOOLS, *sap_tools])

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
        ids, index = relevant_section_ids(
            state.get("sections") or [],
            query,
            state.get("section_index") or {},
            top_k=settings.spec_rag_top_k,
        )
        return {
            "style_examples": format_examples(hits),
            "relevant_section_ids": ids,
            "section_index": index,
        }

    async def assistant(state: SpecState) -> dict:
        sections = state.get("sections") or []
        toc = spec_doc.render_toc(sections)
        relevant = spec_doc.render_relevant(sections, state.get("relevant_section_ids") or [])
        examples = state.get("style_examples") or NO_EXAMPLES_PLACEHOLDER
        system = SystemMessage(
            content=SYSTEM_PROMPT.format(examples=examples, toc=toc, relevant_sections=relevant)
        )
        response = await llm_with_tools.ainvoke([system, *state["messages"]])
        return {"messages": [response]}

    async def tools(state: SpecState) -> dict:
        last = state["messages"][-1]
        assert isinstance(last, AIMessage)
        sections = list(state.get("sections") or [])
        changed = False
        tool_messages: list[ToolMessage] = []
        for call in last.tool_calls:
            name, args = call["name"], call["args"]
            if name == list_sections.__name__:
                result = spec_doc.render_toc(sections)
            elif name == get_section.__name__:
                section = spec_doc.find_section(sections, args["section_id"])
                result = (
                    spec_doc.render_section(section)
                    if section
                    else f"Раздел {args['section_id']} не найден."
                )
            elif name == update_section.__name__:
                sections, ok = spec_doc.update_section(
                    sections, args["section_id"], args["new_text"]
                )
                changed = changed or ok
                result = "Раздел обновлён." if ok else f"Раздел {args['section_id']} не найден."
            elif name == insert_section.__name__:
                sections, new_id = spec_doc.insert_section(
                    sections,
                    args.get("after_section_id"),
                    args["level"],
                    args["title"],
                    args.get("body", ""),
                )
                changed = True
                result = f"Добавлен раздел [{new_id}]."
            elif name == delete_section.__name__:
                sections, ok = spec_doc.delete_section(sections, args["section_id"])
                changed = changed or ok
                result = "Раздел удалён." if ok else f"Раздел {args['section_id']} не найден."
            elif name in sap_by_name:
                try:
                    result = str(await sap_by_name[name].ainvoke(args))
                except Exception as exc:  # noqa: BLE001 — сбой MCP не должен ронять ход
                    result = f"Инструмент {name} недоступен: {exc}"
            else:
                result = f"Неизвестный инструмент: {name}"
            tool_messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
        update: dict = {"messages": tool_messages}
        if changed:
            update["sections"] = sections
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
    return graph.compile(checkpointer=checkpointer)
