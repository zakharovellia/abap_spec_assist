from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

Scenario = Literal["new", "modification"]


def _merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    merged.update(right)
    return merged


def _extend_list(left: list[Any], right: list[Any]) -> list[Any]:
    return [*left, *right]


class ResearchStep(BaseModel):
    step: int
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    result_summary: str = ""


class ConversationTurn(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    agent_name: str | None = None


class ClassifierResult(BaseModel):
    tz_type: str
    scenario: Scenario
    confidence: float = 0.0
    parent_object_hint: str | None = None


class TzState(BaseModel):
    tz_id: str
    author_id: str

    tz_type: str | None = None
    scenario: Scenario = "new"
    parent_object_ref: str | None = None

    classifier: ClassifierResult | None = None

    conversation: Annotated[list[ConversationTurn], _extend_list] = Field(default_factory=list)
    user_change_request: str | None = None

    payload: Annotated[dict[str, Any], _merge_dicts] = Field(default_factory=dict)
    legacy_tz: dict[str, Any] = Field(default_factory=dict)
    current_state_analysis: dict[str, Any] = Field(default_factory=dict)
    diff_analysis: dict[str, Any] = Field(default_factory=dict)

    research_log: Annotated[list[ResearchStep], _extend_list] = Field(default_factory=list)
    critic_report: dict[str, Any] = Field(default_factory=dict)
    critic_iterations: int = 0

    docx_object_key: str | None = None

    status: str = "draft"
    error: str | None = None
