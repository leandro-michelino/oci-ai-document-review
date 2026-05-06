from datetime import datetime, timezone

import pandas as pd

from app import filter_dashboard_rows, next_action, processing_stage_rows, record_to_row
from src.models import (
    DocumentAnalysis,
    DocumentRecord,
    DocumentType,
    ProcessingStatus,
    RiskNote,
    ReviewStatus,
)


def make_record(
    document_id: str,
    name: str,
    status: ProcessingStatus = ProcessingStatus.REVIEW_REQUIRED,
    risks: list[RiskNote] | None = None,
    confidence: float = 0.8,
) -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id,
        document_name=name,
        document_type=DocumentType.CONTRACT,
        status=status,
        business_reference="REF-001",
        uploaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        analysis=DocumentAnalysis(
            document_class="CONTRACT",
            executive_summary=f"Summary for {name}",
            risk_notes=risks or [],
            confidence_score=confidence,
        ),
    )


def test_record_to_row_adds_dashboard_fields():
    record = make_record(
        "doc-1",
        "contract.pdf",
        risks=[RiskNote(risk="Bad clause", severity="HIGH")],
        confidence=0.76,
    )

    row = record_to_row(record)

    assert row["Risk Level"] == "HIGH"
    assert row["Confidence"] == 76
    assert row["Action"] == "Approve or reject"
    assert "contract.pdf" in row["Search Text"]


def test_next_action_for_failed_and_reviewed_records():
    failed = make_record("doc-3", "bad.pdf", status=ProcessingStatus.FAILED)
    approved = make_record("doc-4", "approved.pdf", status=ProcessingStatus.APPROVED)
    approved.review_status = ReviewStatus.APPROVED

    assert next_action(failed) == "Fix and retry"
    assert next_action(approved) == "Approved"


def test_processing_stage_rows_show_backend_lifecycle():
    record = make_record("doc-5", "lifecycle.pdf")
    record.object_storage_path = "oci://bucket/documents/doc-5/lifecycle.pdf"
    record.extracted_text_preview = "Important contract text"

    rows = processing_stage_rows(record)

    assert [row["Stage"] for row in rows] == [
        "Upload",
        "Object Storage",
        "Document Understanding",
        "GenAI analysis",
        "Review report",
        "Human decision",
    ]
    assert rows[1]["State"] == "Complete"
    assert rows[-1]["Evidence"] == "Approve or reject"


def test_filter_dashboard_rows_searches_and_filters():
    records = [
        make_record("doc-1", "contract.pdf", risks=[RiskNote(risk="Risk", severity="HIGH")]),
        make_record("doc-2", "invoice.pdf", status=ProcessingStatus.APPROVED, confidence=0.5),
    ]
    df = pd.DataFrame([record_to_row(record) for record in records])

    filtered = filter_dashboard_rows(
        df=df,
        query="contract REF-001",
        statuses=["REVIEW_REQUIRED"],
        document_types=["CONTRACT"],
        review_states=["PENDING"],
        risk_levels=["HIGH"],
        minimum_confidence=75,
        needs_attention_only=True,
    )

    assert filtered["Document ID"].tolist() == ["doc-1"]
