from datetime import datetime, timezone

import pandas as pd

from app import filter_dashboard_rows, record_to_row
from src.models import (
    DocumentAnalysis,
    DocumentRecord,
    DocumentType,
    ProcessingStatus,
    RiskNote,
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
    assert "contract.pdf" in row["Search Text"]


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
