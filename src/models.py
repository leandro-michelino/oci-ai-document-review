from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DocumentType(str, Enum):
    AUTO_DETECT = "AUTO_DETECT"
    CONTRACT = "CONTRACT"
    INVOICE = "INVOICE"
    COMPLIANCE = "COMPLIANCE"
    TECHNICAL_REPORT = "TECHNICAL_REPORT"
    GENERAL = "GENERAL"


class ProcessingStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    AI_ANALYZED = "AI_ANALYZED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RiskNote(BaseModel):
    risk: str
    severity: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")
    evidence: str | None = None


class ExtractedFields(BaseModel):
    parties: list[str] = Field(default_factory=list)
    document_date: str | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    total_amount: str | None = None
    currency: str | None = None
    payment_terms: str | None = None

    @field_validator("parties", mode="before")
    @classmethod
    def none_to_empty_list(cls, value):
        return [] if value is None else value


class DocumentAnalysis(BaseModel):
    document_class: str
    executive_summary: str
    key_points: list[str] = Field(default_factory=list)
    extracted_fields: ExtractedFields = Field(default_factory=ExtractedFields)
    risk_notes: list[RiskNote] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    human_review_required: bool = True

    @field_validator(
        "key_points",
        "risk_notes",
        "recommendations",
        "missing_information",
        mode="before",
    )
    @classmethod
    def none_to_empty_list(cls, value):
        return [] if value is None else value

    @field_validator("extracted_fields", mode="before")
    @classmethod
    def none_to_empty_fields(cls, value):
        return {} if value is None else value


class ExtractionResult(BaseModel):
    text: str
    tables: list[Any] = Field(default_factory=list)
    key_values: dict[str, Any] = Field(default_factory=dict)


class DocumentRecord(BaseModel):
    document_id: str
    document_name: str
    document_type: DocumentType
    source_file_size_bytes: int | None = None
    source_file_mime_type: str | None = None
    object_storage_path: str | None = None
    status: ProcessingStatus = ProcessingStatus.UPLOADED
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING
    review_comments: str | None = None
    business_reference: str | None = None
    notes: str | None = None
    analysis: DocumentAnalysis | None = None
    extracted_text_preview: str | None = None
    report_path: str | None = None
    error_message: str | None = None
