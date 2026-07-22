from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class SpecState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # Документ ТЗ — список разделов (app/spec_doc.py), не одна строка Markdown:
    # при документах в сотни тысяч слов он не помещается в промпт целиком.
    sections: list[dict]
    # Кэш эмбеддингов разделов для ретривала (app/rag/doc_retriever.py):
    # {section_id: {"hash": str, "vector": list[float]}}
    section_index: dict[str, dict]
    # id разделов, отобранных ретривалом как релевантные текущему запросу —
    # их полный текст попадает в промпт (см. graph/builder.py:assistant)
    relevant_section_ids: list[str]
    style_examples: str
