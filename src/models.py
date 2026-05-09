from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


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


class WorkflowStatus(str, Enum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    IN_REVIEW = "IN_REVIEW"
    WAITING_FOR_INFO = "WAITING_FOR_INFO"
    ESCALATED = "ESCALATED"
    RETRY_PLANNED = "RETRY_PLANNED"
    CLOSED = "CLOSED"


class WorkflowComment(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    author: str = "Reviewer"
    comment: str


class AuditEvent(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str = "System"
    action: str
    detail: str | None = None


class RetryEvent(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str = "Reviewer"
    reason: str | None = None
    new_document_id: str | None = None


class RiskNote(BaseModel):
    risk: str
    severity: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")
    evidence: str | None = None


def is_tax_field_public_sector_false_positive(note: RiskNote) -> bool:
    combined = f"{note.risk} {note.evidence or ''}".lower()
    tax_field_terms = (
        "vat",
        "sales tax",
        "tax rate",
        "tax id",
        "tax number",
        "vat number",
        "tax registration",
        "tax field",
        "invoice tax",
    )
    public_sector_link_terms = (
        "public sector",
        "public-sector",
        "government",
        "government-related",
        "govt",
    )
    real_public_sector_terms = (
        "tax authority",
        "customs",
        "regulator",
        "ministry",
        "municipality",
        "municipal",
        "public official",
        "civil servant",
        "state-owned",
        "state owned",
        "state agency",
        "government official",
        "embassy",
        "consulate",
        "police",
        "military",
        "army",
        "public procurement",
        "public tender",
        "facilitation payment",
        "political contribution",
        "conflict of interest",
        "sanctioned",
        "debarred",
        "sole source",
        "zimsec",
    )
    return (
        any(term in combined for term in tax_field_terms)
        and any(term in combined for term in public_sector_link_terms)
        and not any(term in combined for term in real_public_sector_terms)
    )


class ExtractedFields(BaseModel):
    parties: list[str] = Field(default_factory=list)
    line_items: list[str] = Field(default_factory=list)
    document_date: str | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    total_amount: str | None = None
    currency: str | None = None
    payment_terms: str | None = None

    @field_validator("parties", "line_items", mode="before")
    @classmethod
    def normalize_string_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value


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

    @field_validator("key_points", "recommendations", "missing_information", mode="before")
    @classmethod
    def text_to_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("risk_notes", mode="before")
    @classmethod
    def risk_notes_to_list(cls, value):
        if value is None:
            return []
        if isinstance(value, dict):
            return [value]
        return value

    @field_validator("extracted_fields", mode="before")
    @classmethod
    def none_to_empty_fields(cls, value):
        return {} if value is None else value

    @model_validator(mode="after")
    def remove_tax_field_public_sector_false_positives(self):
        self.risk_notes = [
            note
            for note in self.risk_notes
            if not is_tax_field_public_sector_false_positive(note)
        ]
        return self


class ExtractionResult(BaseModel):
    text: str
    tables: list[Any] = Field(default_factory=list)
    key_values: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None


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
    parent_document_id: str | None = None
    assignee: str | None = None
    due_at: datetime | None = None
    workflow_status: WorkflowStatus = WorkflowStatus.NEW
    workflow_comments: list[WorkflowComment] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    retry_count: int = 0
    retry_history: list[RetryEvent] = Field(default_factory=list)
    analysis: DocumentAnalysis | None = None
    extracted_text_preview: str | None = None
    extraction_source: str | None = None
    report_path: str | None = None
    error_message: str | None = None

    @field_validator(
        "workflow_comments", "audit_events", "retry_history", mode="before"
    )
    @classmethod
    def none_to_empty_workflow_lists(cls, value):
        return [] if value is None else value
