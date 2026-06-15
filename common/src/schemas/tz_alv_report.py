from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TZ_TYPE = "alv_report"


class Header(BaseModel):
    title: str
    author: str | None = None
    department: str | None = None
    priority: Literal["L", "M", "H"] = "M"
    estimated_hours: float | None = None


class BusinessContext(BaseModel):
    goal: str
    stakeholders: list[str] = Field(default_factory=list)
    current_pain: str | None = None


class DataSource(BaseModel):
    type: Literal["table", "view", "function_module", "cds", "class"]
    name: str
    fields_used: list[str] = Field(default_factory=list)
    filter_logic: str | None = None
    purpose: str | None = None


class SelectionParameter(BaseModel):
    name: str
    type: str
    mandatory: bool = False


class SelectionScreen(BaseModel):
    parameters: list[SelectionParameter] = Field(default_factory=list)
    select_options: list[dict[str, Any]] = Field(default_factory=list)


class AlgorithmStep(BaseModel):
    n: int
    description: str
    details: str | None = None


class Algorithm(BaseModel):
    steps: list[AlgorithmStep] = Field(default_factory=list)


class OutputLayout(BaseModel):
    columns: list[dict[str, Any]] = Field(default_factory=list)
    totals: list[dict[str, Any]] = Field(default_factory=list)
    sorting: str | None = None


class AlvReportPayload(BaseModel):
    tz_type: Literal["alv_report"] = "alv_report"
    scenario: Literal["new", "modification"] = "new"
    header: Header
    business_context: BusinessContext
    data_sources: list[DataSource] = Field(default_factory=list)
    selection_screen: SelectionScreen = Field(default_factory=SelectionScreen)
    algorithm: Algorithm = Field(default_factory=Algorithm)
    output_layout: OutputLayout = Field(default_factory=OutputLayout)
    authorizations: dict[str, Any] = Field(default_factory=dict)
    error_handling: dict[str, Any] = Field(default_factory=dict)
    test_cases: list[dict[str, Any]] = Field(default_factory=list)
    additions: str | None = None


REQUIRED_SECTIONS_NEW: tuple[str, ...] = (
    "header",
    "business_context",
    "data_sources",
    "selection_screen",
    "algorithm",
    "output_layout",
)

REQUIRED_SECTIONS_MODIFICATION: tuple[str, ...] = (
    *REQUIRED_SECTIONS_NEW,
    "diff_analysis",
    "current_state",
    "target_state",
    "regression_tests",
    "impact_analysis",
)
