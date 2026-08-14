"""Validated AI provider request and result contracts."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Severity = Literal["info", "warning", "error"]
CategoryCode = Literal["ORDER", "INVENTORY", "SHIPPING", "OTHER", "UNKNOWN"]


class AnalysisWarning(BaseModel):
    code: str
    severity: Severity = "warning"
    message: str


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: int
    file_name: str
    file_type: str
    extracted_text: str = ""
    table_preview: list[dict[str, Any]] = Field(default_factory=list)
    parser_metadata: dict[str, Any] = Field(default_factory=dict)
    parse_warnings: list[AnalysisWarning] = Field(default_factory=list)
    ocr_text: str = ""
    requires_ocr: bool = False
    previous_examples: list[dict[str, Any]] = Field(default_factory=list)


class DocumentCategory(BaseModel):
    code: CategoryCode
    label: str
    confidence: float = Field(ge=0, le=1)
    reason: str


class ConfidenceValue(BaseModel):
    value: str | None = None
    confidence: float = Field(ge=0, le=1)


class DocumentType(BaseModel):
    name: str
    confidence: float = Field(ge=0, le=1)


class ExtractedField(BaseModel):
    source_name: str
    normalized_name: str
    value: str | None = None
    data_type: str
    confidence: float = Field(ge=0, le=1)
    needs_review: bool = False
    review_reason: str | None = None


class AIAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_category: DocumentCategory
    document_type: DocumentType
    provider_name: ConfidenceValue
    target_date: ConfidenceValue
    fields: list[ExtractedField] = Field(default_factory=list)
    summary: str
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    needs_review: bool = False
