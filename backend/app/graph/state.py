from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class SpecState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # Документ ТЗ — список разделов (app/spec_doc.py), не одна строка Markdown:
    # при документах в сотни тысяч слов он не помещается в промпт целиком.
    sections: list[dict]
    # Кэш эмбеддингов разделов НЕ здесь: он в app/rag/section_index_store.py,
    # т.к. состояние целиком сериализуется в каждый чекпоинт каждого супершага
    # id разделов, отобранных ретривалом как релевантные текущему запросу —
    # их полный текст попадает в промпт (см. graph/builder.py:assistant)
    relevant_section_ids: list[str]
    style_examples: str
