from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class SpecState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    spec_markdown: str
    style_examples: str
