from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from app import (
    file_size_label,
    filter_dashboard_rows,
    filter_queue_rows,
    next_action,
    processing_stage_rows,
    record_to_row,
)
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
    assert row["Stage"] == "Ready"
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


def test_file_size_label_formats_known_and_missing_sizes():
    assert file_size_label(None) == "Not captured"
    assert file_size_label(512) == "512 B"
    assert file_size_label(2048) == "2.0 KB"
    assert file_size_label(2 * 1024 * 1024) == "2.00 MB"


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


def test_filter_queue_rows_uses_simple_review_views():
    ready = make_record("doc-1", "ready.pdf")
    processing = make_record("doc-2", "processing.pdf", status=ProcessingStatus.PROCESSING)
    failed = make_record("doc-3", "failed.pdf", status=ProcessingStatus.FAILED)
    approved = make_record("doc-4", "approved.pdf", status=ProcessingStatus.APPROVED)
    approved.review_status = ReviewStatus.APPROVED
    df = pd.DataFrame([record_to_row(record) for record in [ready, processing, failed, approved]])

    assert filter_queue_rows(df, view="Ready", query="")["Document ID"].tolist() == ["doc-1"]
    assert filter_queue_rows(df, view="Processing", query="")["Document ID"].tolist() == ["doc-2"]
    assert filter_queue_rows(df, view="Failed", query="")["Document ID"].tolist() == ["doc-3"]
    assert filter_queue_rows(df, view="Reviewed", query="")["Document ID"].tolist() == ["doc-4"]
    assert filter_queue_rows(df, view="All", query="approved")["Document ID"].tolist() == ["doc-4"]


def test_sidebar_navigation_buttons_change_page(monkeypatch, tmp_path):
    monkeypatch.setenv("OCI_REGION", "uk-london-1")
    monkeypatch.setenv("GENAI_REGION", "uk-london-1")
    monkeypatch.setenv("OCI_COMPARTMENT_ID", "ocid1.compartment.oc1..exampleproject")
    monkeypatch.setenv("OCI_NAMESPACE", "example")
    monkeypatch.setenv("OCI_BUCKET_NAME", "example")
    monkeypatch.setenv("GENAI_MODEL_ID", "cohere.command-r-plus-08-2024")
    monkeypatch.setenv("LOCAL_METADATA_DIR", str(tmp_path / "metadata"))
    monkeypatch.setenv("LOCAL_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("LOCAL_UPLOADS_DIR", str(tmp_path / "uploads"))

    from src.config import get_config
    from src.metadata_store import MetadataStore

    get_config.cache_clear()
    try:
        config = get_config()
        report_path = Path(config.local_reports_dir) / "test-doc.md"
        report_path.write_text("report", encoding="utf-8")
        MetadataStore(config).save(
            DocumentRecord(
                document_id="test-doc",
                document_name="test-contract.png",
                document_type=DocumentType.CONTRACT,
                status=ProcessingStatus.REVIEW_REQUIRED,
                uploaded_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
                analysis=DocumentAnalysis(
                    document_class="CONTRACT",
                    executive_summary="Synthetic test summary.",
                    confidence_score=0.8,
                ),
                report_path=str(report_path),
            )
        )

        app = AppTest.from_file("app.py", default_timeout=5).run()
        assert app.session_state["page"] == "Upload"

        for button in app.sidebar.button:
            if button.label == "Dashboard":
                app = button.click().run()
                break
        assert app.session_state["page"] == "Dashboard"
        app = app.run()
        assert app.session_state["page"] == "Dashboard"

        for button in app.button:
            if button.label == "Open":
                app = button.click().run()
                break
        assert app.session_state["page"] == "Document"
        assert app.session_state["selected_document_id"] == "test-doc"
        app = app.run()
        assert app.session_state["page"] == "Document"

        for button in app.sidebar.button:
            if button.label == "Upload":
                app = button.click().run()
                break
        assert app.session_state["page"] == "Upload"

        for button in app.sidebar.button:
            if button.label == "Settings":
                app = button.click().run()
                break
        assert app.session_state["page"] == "Settings"
    finally:
        get_config.cache_clear()
