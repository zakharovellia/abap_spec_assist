from typing import Any

from pydantic import BaseModel, Field

from schemas.tz_state import Scenario


class CreateDocumentRequest(BaseModel):
    author_id: str
    tz_type: str = "alv_report"
    scenario: Scenario = "new"
    title: str | None = None
    parent_object_ref: str | None = None


class DocumentResponse(BaseModel):
    id: str
    author_id: str
    tz_type: str
    scenario: str
    title: str | None = None
    parent_object_ref: str | None = None
    status: str
    current_revision: str | None = None
    created_at: str
    updated_at: str


class RevisionResponse(BaseModel):
    id: str
    tz_id: str
    payload: dict[str, Any]
    research_log: list[dict[str, Any]] = Field(default_factory=list)
    critic_report: dict[str, Any] | None = None
    docx_object_key: str | None = None
    created_at: str
    created_by: str


class CreateRevisionRequest(BaseModel):
    payload: dict[str, Any]
    research_log: list[dict[str, Any]] = Field(default_factory=list)
    critic_report: dict[str, Any] | None = None
    docx_object_key: str | None = None
    created_by: str = "human"


class AddMessageRequest(BaseModel):
    role: str = "user"
    content: str
    agent_name: str | None = None


class ConversationTurnResponse(BaseModel):
    id: str
    tz_id: str
    role: str
    content: str | None = None
    agent_name: str | None = None
    model_used: str | None = None
    created_at: str


class StartGenerationRequest(BaseModel):
    message: str
    legacy_attachment_ids: list[str] = Field(default_factory=list)


class GenerationStartedResponse(BaseModel):
    tz_id: str
    thread_id: str
    status: str


class FeedbackRequest(BaseModel):
    revision_id: str
    developer_id: str
    rating: int | None = None
    category: str | None = None
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    tz_id: str
    revision_id: str
    developer_id: str
    rating: int | None = None
    category: str | None = None
    comment: str | None = None
    created_at: str
