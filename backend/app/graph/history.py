"""Подготовка истории диалога к передаче LLM.

История в чекпоинте LangGraph не трогается — все преобразования делаются
на копии непосредственно перед вызовом модели (см. graph/builder.py:assistant).
Без этого сессия с большим ТЗ живёт недолго: результаты get_sections
(до 60 000 символов) и аргументы update_section (до 20 000) оседают в истории
навсегда и пересылаются модели каждый ход, пока не переполнят контекст.

Три шага:
1. Компактизация прошлых ходов: длинные результаты инструментов заменяются
   заглушкой, длинные строковые аргументы tool_calls обрезаются. Текущий ход
   (от последнего сообщения пользователя) не трогается — модель прямо сейчас
   работает с этими данными.
2. Обрезка по общему бюджету символов: старые ходы отбрасываются целиком,
   граница — только по сообщению пользователя (иначе OpenAI-совместимый шлюз
   отвергнет историю, начинающуюся с ToolMessage).
3. Достройка ToolMessage-заглушек для tool_calls без ответа (остаются после
   обрыва хода, например по recursion_limit) — без них шлюз отвергает историю
   и сессия перестаёт отвечать.
"""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage

_STUB_TAIL = (
    "…\n(старый результат инструмента скрыт для экономии контекста — "
    "при необходимости вызови инструмент заново)"
)
_STUB_HEAD_CHARS = 200
_ARG_TAIL = "…(обрезано: старый ход)"


def prepare_for_llm(
    messages: list[AnyMessage],
    *,
    max_chars: int,
    tool_result_keep_chars: int,
    tool_arg_keep_chars: int,
) -> list[AnyMessage]:
    msgs = _compact_old_turns(messages, tool_result_keep_chars, tool_arg_keep_chars)
    msgs = _trim_to_budget(msgs, max_chars)
    return _close_dangling_tool_calls(msgs)


def _last_human_index(messages: list[AnyMessage]) -> int:
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return i
    return 0


def _compact_old_turns(
    messages: list[AnyMessage], result_keep: int, arg_keep: int
) -> list[AnyMessage]:
    cut = _last_human_index(messages)
    out: list[AnyMessage] = []
    for i, m in enumerate(messages):
        if i >= cut:
            out.append(m)
        elif (
            isinstance(m, ToolMessage)
            and isinstance(m.content, str)
            and len(m.content) > result_keep
        ):
            out.append(
                m.model_copy(update={"content": m.content[:_STUB_HEAD_CHARS] + _STUB_TAIL})
            )
        elif isinstance(m, AIMessage) and _has_long_args(m, arg_keep):
            calls = [
                {**c, "args": _shorten_args(c["args"], arg_keep)} for c in m.tool_calls
            ]
            # additional_kwargs["tool_calls"] — сырой ответ OpenAI; langchain_openai
            # при сериализации предпочитает его полю .tool_calls, поэтому без
            # удаления обрезка аргументов не подействует
            kwargs = {k: v for k, v in m.additional_kwargs.items() if k != "tool_calls"}
            out.append(m.model_copy(update={"tool_calls": calls, "additional_kwargs": kwargs}))
        else:
            out.append(m)
    return out


def _has_long_args(m: AIMessage, arg_keep: int) -> bool:
    return any(
        isinstance(v, str) and len(v) > arg_keep
        for c in m.tool_calls or []
        for v in c["args"].values()
    )


def _shorten_args(args: dict, arg_keep: int) -> dict:
    return {
        k: v[:arg_keep] + _ARG_TAIL if isinstance(v, str) and len(v) > arg_keep else v
        for k, v in args.items()
    }


def _msg_size(m: AnyMessage) -> int:
    size = len(m.content) if isinstance(m.content, str) else len(str(m.content))
    if isinstance(m, AIMessage):
        size += sum(len(str(c.get("args"))) for c in m.tool_calls or [])
    return size


def _trim_to_budget(messages: list[AnyMessage], max_chars: int) -> list[AnyMessage]:
    if sum(_msg_size(m) for m in messages) <= max_chars:
        return messages
    used = 0
    start = len(messages)
    for i in range(len(messages) - 1, -1, -1):
        used += _msg_size(messages[i])
        if used > max_chars:
            break
        start = i
    # граница отбрасывания — только начало хода пользователя; последний ход
    # оставляем всегда, даже если он один больше бюджета
    while start < len(messages) and not isinstance(messages[start], HumanMessage):
        start += 1
    start = min(start, _last_human_index(messages))
    return list(messages[start:])


def _close_dangling_tool_calls(messages: list[AnyMessage]) -> list[AnyMessage]:
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    out: list[AnyMessage] = []
    for m in messages:
        out.append(m)
        if isinstance(m, AIMessage):
            for call in m.tool_calls or []:
                if call["id"] not in answered:
                    out.append(
                        ToolMessage(
                            content="(вызов инструмента был прерван, результата нет)",
                            tool_call_id=call["id"],
                        )
                    )
    return out
