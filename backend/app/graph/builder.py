import asyncio
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app import spec_doc
from app.config import settings
from app.graph.history import prepare_for_llm
from app.graph.prompts import NO_EXAMPLES_PLACEHOLDER, SYSTEM_PROMPT
from app.graph.state import SpecState
from app.rag import section_index_store
from app.rag.doc_retriever import relevant_section_ids
from app.rag.retriever import format_examples, retrieve_style_examples

logger = logging.getLogger(__name__)


class list_sections(BaseModel):
    """Показать оглавление документа ТЗ целиком: id, заголовок и объём каждого раздела."""


class get_sections(BaseModel):
    """Получить полный текст разделов документа ТЗ по их id из оглавления.

    Передавай сразу ВСЕ нужные id одним вызовом — число раундов инструментов
    на один ход ограничено, чтение по одному разделу быстро исчерпает его.
    """

    section_ids: list[str] = Field(
        description="id разделов из <toc> или из list_sections; можно сразу несколько"
    )


class update_section(BaseModel):
    """Заменить один раздел документа ТЗ новой версией целиком (включая строку заголовка).

    Используй только для ОДНОГО раздела за вызов — никогда не пытайся передать так
    весь документ.
    """

    section_id: str = Field(description="id заменяемого раздела")
    new_text: str = Field(
        description="Полный новый текст раздела в Markdown, включая строку заголовка (#/##/...)"
    )


class patch_section(BaseModel):
    """Точечно заменить фрагмент текста внутри раздела, не переписывая раздел целиком.

    Для небольших правок (число, формулировка, ячейка таблицы, пара предложений)
    используй этот инструмент, а НЕ update_section: он быстрее и не рискует
    случайно изменить соседний текст. old_string должен встречаться в разделе
    ровно один раз — включи в него достаточно контекста.
    """

    section_id: str = Field(description="id раздела, в котором делается правка")
    old_string: str = Field(
        description="Точный существующий фрагмент текста раздела (буквально: регистр, пробелы, переносы строк)"
    )
    new_string: str = Field(description="Текст, которым заменить фрагмент")


class find_in_document(BaseModel):
    """Точный текстовый поиск по всему документу ТЗ (без учёта регистра).

    Используй для конкретных терминов и идентификаторов: имена таблиц/полей
    (VBAK, MATNR), коды транзакций, имена Z-объектов, номера сообщений.
    Возвращает id разделов и фрагменты текста вокруг совпадений.
    """

    query: str = Field(description="Искомая подстрока, минимум 2 символа")


class find_style_examples(BaseModel):
    """Найти в базе примеров реальных ТЗ разделы по заданной теме — образцы стиля.

    Вызывай ПЕРЕД написанием или крупной переработкой раздела: запроси примеры
    под его тему («селекционный экран параметры», «алгоритм обработки выборка»,
    «критерии приёмки») — это даст более точные образцы, чем автоматическая
    подборка по сообщению пользователя.
    """

    query: str = Field(
        description="Тема/название раздела и ключевые слова для поиска примеров"
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


DOC_TOOLS = [
    list_sections,
    get_sections,
    find_in_document,
    find_style_examples,
    update_section,
    patch_section,
    insert_section,
    delete_section,
]
DOC_WRITE_TOOLS = {
    update_section.__name__,
    patch_section.__name__,
    insert_section.__name__,
    delete_section.__name__,
}


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

    def retrieve(state: SpecState, config: RunnableConfig) -> dict:
        query = next(
            (
                m.content
                for m in reversed(state["messages"])
                if isinstance(m, HumanMessage) and isinstance(m.content, str)
            ),
            "",
        )
        hits = retrieve_style_examples(query)
        # Кэш эмбеддингов разделов — во внешнем хранилище по id сессии, а не в
        # состоянии графа (см. section_index_store). Его недоступность не роняет
        # ход: пересчитаем векторы заново, это только медленнее.
        session_id = config["configurable"]["thread_id"]
        try:
            stored_index = section_index_store.load(session_id)
        except Exception:
            logger.warning("Кэш эмбеддингов разделов недоступен", exc_info=True)
            stored_index = {}
        ids, new_index = relevant_section_ids(
            state.get("sections") or [],
            query,
            stored_index,
            top_k=settings.spec_rag_top_k,
        )
        try:
            section_index_store.save(session_id, stored_index, new_index)
        except Exception:
            logger.warning("Не удалось сохранить кэш эмбеддингов", exc_info=True)
        return {
            "style_examples": format_examples(hits),
            "relevant_section_ids": ids,
        }

    async def assistant(state: SpecState) -> dict:
        sections = state.get("sections") or []
        toc = spec_doc.render_toc(sections)
        relevant = spec_doc.render_relevant(
            sections,
            state.get("relevant_section_ids") or [],
            settings.spec_relevant_max_chars,
        )
        examples = state.get("style_examples") or NO_EXAMPLES_PLACEHOLDER
        system = SystemMessage(
            content=SYSTEM_PROMPT.format(examples=examples, toc=toc, relevant_sections=relevant)
        )
        messages = prepare_for_llm(
            state["messages"],
            max_chars=settings.history_max_chars,
            tool_result_keep_chars=settings.history_tool_result_keep_chars,
            tool_arg_keep_chars=settings.history_tool_arg_keep_chars,
        )
        response = await llm_with_tools.ainvoke([system, *messages])
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
            elif name == get_sections.__name__:
                result = spec_doc.render_sections(
                    sections, args["section_ids"], settings.spec_read_max_chars
                )
            elif name == find_in_document.__name__:
                result = spec_doc.search_sections(sections, args["query"])
            elif name == find_style_examples.__name__:
                # retrieve_style_examples — синхронный (эмбеддинги + Qdrant),
                # в поток, чтобы не блокировать event loop
                hits = await asyncio.to_thread(retrieve_style_examples, args["query"])
                result = (
                    format_examples(hits)
                    or "Подходящих примеров по этому запросу не найдено."
                )
            elif name == update_section.__name__:
                sections, ok = spec_doc.update_section(
                    sections, args["section_id"], args["new_text"]
                )
                changed = changed or ok
                result = "Раздел обновлён." if ok else f"Раздел {args['section_id']} не найден."
            elif name == patch_section.__name__:
                sections, err = spec_doc.patch_section(
                    sections, args["section_id"], args["old_string"], args["new_string"]
                )
                changed = changed or err is None
                result = err if err else "Правка внесена."
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
