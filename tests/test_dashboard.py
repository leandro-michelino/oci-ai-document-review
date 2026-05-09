import inspect
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from streamlit.testing.v1 import AppTest

from app import (
    DASHBOARD_STATUS_FILTERS,
    action_badge,
    action_group_for_document,
    action_group_options,
    action_item_label,
    action_workload_metrics_html,
    action_tone,
    actions_summary_html,
    backfill_compliance_attention,
    dashboard_metrics_html,
    detail_page,
    display_error_message,
    document_type_label,
    expense_group_badges_html,
    expense_group_aggregation,
    expense_group_file_list,
    expense_group_item_rows,
    expense_reference_file_card_html,
    expense_row_group_target,
    expense_row_file_table,
    expense_reference_groups,
    expense_row_groups,
    file_size_label,
    filter_dashboard_status,
    filter_queue_rows,
    format_compliance_evidence,
    next_action,
    next_action_document_id,
    processing_stage_rows,
    queue_view_frames,
    record_to_row,
    reviewer_action_count,
    render_howto_panel,
    risk_detail_label,
    selected_file_notice,
    source_download_mime,
    source_download_name,
    sort_action_records,
    upload_document_type_options,
    validate_upload_batch_requirements,
    validate_upload_requirements,
    workflow_status_label,
    workflow_status_options,
)
from src.models import (
    DocumentAnalysis,
    DocumentRecord,
    DocumentType,
    ProcessingStatus,
    RiskNote,
    ReviewStatus,
    WorkflowStatus,
)


def query_value(params: dict, key: str) -> str | None:
    value = params.get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


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


def configure_streamlit_test_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OCI_REGION", "uk-london-1")
    monkeypatch.setenv("GENAI_REGION", "uk-london-1")
    monkeypatch.setenv("OCI_COMPARTMENT_ID", "ocid1.compartment.oc1..exampleproject")
    monkeypatch.setenv("OCI_NAMESPACE", "example")
    monkeypatch.setenv("OCI_BUCKET_NAME", "example")
    monkeypatch.setenv("GENAI_MODEL_ID", "cohere.command-r-plus-08-2024")
    monkeypatch.setenv("LOCAL_METADATA_DIR", str(tmp_path / "metadata"))
    monkeypatch.setenv("LOCAL_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("LOCAL_UPLOADS_DIR", str(tmp_path / "uploads"))


def test_record_to_row_adds_dashboard_fields():
    record = make_record(
        "doc-1",
        "contract.pdf",
        risks=[RiskNote(risk="Bad clause", severity="HIGH")],
        confidence=0.76,
    )
    record.job_description = "Q1 vendor onboarding"

    row = record_to_row(record)

    assert row["Risk Level"] == "HIGH"
    assert row["Risks"] == 1
    assert row["Risk Detail"] == "1 risk note: 1 High."
    assert row["Stage"] == "Ready"
    assert row["Workflow"] == "New"
    assert row["Assignee"] == "Unassigned"
    assert row["SLA"] == "No SLA"
    assert row["Retries"] == 0
    assert row["Expense Name or Reference"] == "Q1 vendor onboarding"
    assert row["Confidence"] == 76
    assert row["Action"] == "Approve or reject"
    assert "contract.pdf" in row["Search Text"]
    assert "q1 vendor onboarding" in row["Search Text"]
    assert "new" in row["Search Text"]


def test_expense_reference_groups_keep_multi_file_uploads_together():
    first = make_record("doc-1", "receipt-a.pdf")
    first.job_description = "Client dinner May"
    second = make_record("doc-2", "receipt-b.pdf", status=ProcessingStatus.PROCESSING)
    second.job_description = "Client dinner May"
    third = make_record("doc-3", "unrelated.pdf")

    groups = expense_reference_groups([third, second, first])

    assert groups == [("Client dinner May", [first, second])]


def test_action_group_options_expose_document_groups_for_actions():
    first = make_record("doc-1", "receipt-a.pdf")
    first.job_description = "Client dinner May"
    second = make_record("doc-2", "receipt-b.pdf", status=ProcessingStatus.PROCESSING)
    second.job_description = "Client dinner May"
    third = make_record("doc-3", "unrelated.pdf")

    options = action_group_options([third, second, first])
    keys = [key for key, _, _ in options]
    labels = [label for _, label, _ in options]

    assert keys == ["all", "group::Client dinner May"]
    assert labels[0] == "All documents (3 files)"
    assert labels[1] == "Client dinner May (2 files, 1 need action)"
    assert action_group_for_document([third, second, first], "doc-1") == (
        "group::Client dinner May"
    )
    assert action_group_for_document([third, second, first], "doc-3") == "all"


def test_expense_row_groups_groups_dashboard_rows_by_reference():
    first = make_record("doc-1", "receipt-a.pdf")
    first.job_description = "Client dinner May"
    second = make_record("doc-2", "receipt-b.pdf")
    second.job_description = "Client dinner May"
    loose = make_record("doc-3", "single.pdf")
    rows = pd.DataFrame([record_to_row(record) for record in [first, loose, second]])

    groups = expense_row_groups(rows)

    assert groups[0][0] == "Client dinner May"
    assert groups[0][1]["Document ID"].tolist() == ["doc-1", "doc-2"]
    assert groups[1][0] is None
    assert groups[1][1]["Document ID"].tolist() == ["doc-3"]


def test_expense_group_visual_helpers_summarize_files_and_statuses():
    ready = make_record("doc-ready", "ready.pdf")
    processing = make_record(
        "doc-processing", "processing.pdf", status=ProcessingStatus.PROCESSING
    )
    failed = make_record("doc-failed", "failed.pdf", status=ProcessingStatus.FAILED)

    assert expense_group_file_list([ready, processing, failed], limit=2) == (
        "ready.pdf, processing.pdf, +1 more"
    )
    badges = expense_group_badges_html([ready, processing, failed])
    assert "1 Failed" in badges
    assert "1 Processing" in badges
    assert "1 Ready" in badges


def test_expense_row_file_table_keeps_dashboard_group_details_compact():
    ready = make_record("doc-ready", "ready.pdf")
    ready.job_description = "Client dinner May"
    ready.analysis.risk_notes = [RiskNote(risk="Check policy", severity="LOW")]
    failed = make_record(
        "doc-failed", "failed.pdf", status=ProcessingStatus.FAILED
    )
    failed.job_description = "Client dinner May"
    failed.assignee = "Finance"
    rows = pd.DataFrame([record_to_row(record) for record in [ready, failed]])

    table = expense_row_file_table(rows)

    assert table.columns.tolist() == ["File", "Stage", "Action", "Risk", "Details"]
    assert table["File"].tolist() == ["ready.pdf", "failed.pdf"]
    assert table["Risk"].tolist() == ["Risk Small", "Risk None"]
    assert "Owner: Finance" in table.loc[1, "Details"]


def test_expense_row_group_target_prefers_reviewable_file():
    reviewed = make_record("doc-reviewed", "reviewed.pdf")
    reviewed.review_status = ReviewStatus.APPROVED
    reviewed.status = ProcessingStatus.APPROVED
    failed = make_record("doc-failed", "failed.pdf", status=ProcessingStatus.FAILED)
    ready = make_record("doc-ready", "ready.pdf")
    rows = pd.DataFrame(
        [record_to_row(record) for record in [reviewed, failed, ready]]
    )

    target = expense_row_group_target(rows)

    assert target["Document ID"] == "doc-ready"


def test_action_item_label_and_selected_notice_identify_exact_file():
    record = make_record("doc-abc123", "Receipt_21Apr2026_112647.pdf")
    record.job_description = "Client dinner April"

    label = action_item_label(record)
    notice = selected_file_notice(record, linked_count=3)
    summary = actions_summary_html(record, linked_count=3)

    assert "Receipt_21Apr2026_112647.pdf" in label
    assert "ID: doc-abc123" in label
    assert "Expense: Client dinner April" in label
    assert "Selected file: Receipt_21Apr2026_112647.pdf" in notice
    assert "Document ID: doc-abc123" in notice
    assert "Linked files in expense/reference: 3" in notice
    assert "Selected file for review" in summary
    assert "Workflow: New" in summary
    assert "Linked files: 3" in summary


def test_actions_page_shows_ai_summary_before_decision_panel():
    source = inspect.getsource(detail_page)

    assert source.index('"AI review summary"') < source.index('st.subheader("Decision")')


def test_action_workload_metrics_html_summarizes_actions():
    html = action_workload_metrics_html(
        ready_actions=2,
        failed_actions=1,
        active_actions=3,
        reviewed_actions=4,
    )

    assert "Needs decision" in html
    assert "Needs fix" in html
    assert ">2<" in html
    assert ">1<" in html


def test_expense_group_aggregation_includes_items_and_risks():
    first = make_record(
        "doc-1",
        "receipt-a.pdf",
        risks=[RiskNote(risk="Missing receipt detail", severity="LOW")],
    )
    first.analysis.extracted_fields.line_items = ["Coffee EUR 4", "Lunch EUR 18"]
    second = make_record("doc-2", "receipt-b.pdf", status=ProcessingStatus.FAILED)

    aggregation = expense_group_aggregation([first, second])
    rows = expense_group_item_rows([first, second])

    assert aggregation == {
        "files": 2,
        "needs_decision": 1,
        "needs_fix": 1,
        "items": 2,
        "risks": 1,
    }
    assert rows == [
        {
            "File": "receipt-a.pdf",
            "Stage": "Ready",
            "Items / Services": "Coffee EUR 4; Lunch EUR 18",
        }
    ]


def test_expense_reference_file_card_html_highlights_selected_file():
    record = make_record("doc-1", "receipt.pdf")

    selected = expense_reference_file_card_html(record, is_current=True)
    normal = expense_reference_file_card_html(record, is_current=False)

    assert "expense-file-card selected" in selected
    assert "Selected now" in selected
    assert "expense-file-card selected" not in normal


def test_risk_detail_label_explains_missing_and_multiple_risks():
    no_analysis = DocumentRecord(
        document_id="doc-empty",
        document_name="empty.pdf",
        document_type=DocumentType.GENERAL,
    )
    no_risks = make_record("doc-safe", "safe.pdf")
    mixed = make_record(
        "doc-mixed",
        "mixed.pdf",
        risks=[
            RiskNote(risk="Missing signature", severity="HIGH"),
            RiskNote(risk="Unclear payment terms", severity="MEDIUM"),
            RiskNote(risk="Minor formatting issue", severity="LOW"),
        ],
    )

    assert risk_detail_label(no_analysis) == "Risk not analyzed yet."
    assert risk_detail_label(no_risks) == "No AI risk notes returned."
    assert risk_detail_label(mixed) == "3 risk notes: 1 High, 1 Medium, 1 Small."


def test_format_compliance_evidence_summarizes_catalog_details():
    evidence = (
        "Curated compliance knowledge base matched a public-sector entity or cue "
        "in an expense context. knowledge-base: Object Storage: "
        "compliance/public_sector_entities.csv; public-sector match: "
        "entity: Government keyword; matched term: gov; type: keyword; "
        "country: global; source: curated; source date: 2026-05-07 | "
        "entity: Ministry keyword; matched term: department of; type: keyword; "
        "country: global; source: curated; source date: 2026-05-07; "
        "expense cue: receipt, expense, reimbursement."
    )

    summary = format_compliance_evidence(evidence)

    assert summary == (
        "Compliance knowledge base matched public-sector context: "
        "government or public-sector reference; ministry or department reference. "
        "Expense cues found: receipt, expense, reimbursement. "
        "Review before approval."
    )


def test_dashboard_metrics_html_stays_in_one_html_block():
    html = dashboard_metrics_html(
        [
            ("Needs <action>", 13, "Ready & waiting", "warning"),
            ("Compliance", 3, "Knowledge-base matches", "danger"),
        ]
    )

    assert "\n" not in html
    assert html.count('class="dashboard-card') == 2
    assert "&lt;action&gt;" in html
    assert "Ready &amp; waiting" in html


def test_action_badges_use_decision_colors():
    assert action_tone("Approved") == "state-good"
    assert action_tone("Rejected") == "state-bad"
    assert action_tone("Fix and retry") == "state-bad"
    assert action_tone("Retry planned") == "state-warn"
    assert 'class="badge state-good"' in action_badge("Approved")


def test_dropdown_options_are_alphabetized_with_defaults_first():
    assert DASHBOARD_STATUS_FILTERS == [
        "All",
        "Approved",
        "Compliance review",
        "Failed",
        "Fix and retry",
        "Needs decision",
        "Processing",
        "Rejected",
        "Retry planned",
        "Reviewed",
    ]
    document_labels = [
        document_type_label(item) for item in upload_document_type_options()
    ]
    assert document_labels[0] == "Auto-detect"
    assert document_labels[1:] == sorted(document_labels[1:])
    workflow_labels = [workflow_status_label(item) for item in workflow_status_options()]
    assert workflow_labels == sorted(workflow_labels)


def test_howto_panel_html_is_not_indented_as_markdown_code():
    html = render_howto_panel(
        "For approvers",
        "Use this path for decisions.",
        [("Open Actions", "Review the next item.")],
    )

    assert "\n" not in html
    assert '<div class="howto-panel">' in html
    assert "<pre" not in html


def test_display_error_message_hides_raw_genai_safety_json():
    raw = '{ "code" : "InvalidParameter", "message" : "Inappropriate content detected!!!" }'

    assert "Inappropriate content detected" not in display_error_message(raw)
    assert "content safety filter" in display_error_message(raw)


def test_display_error_message_hides_raw_document_ai_page_limit_json():
    raw = (
        "OCI Document Understanding failed: {'target_service': 'ai_service_document', "
        "'status': 413, 'message': 'Input file has too many pages, maximum number "
        "of pages allowed is: 5'}"
    )

    message = display_error_message(raw)

    assert "target_service" not in message
    assert "too many pages" not in message
    assert "5-page synchronous limit" in message
    assert "automatically splits" in message


def test_upload_requirement_validation_alerts_for_invalid_file(tmp_path):
    source = tmp_path / "document.exe"
    source.write_bytes(b"binary")
    uploaded = SimpleNamespace(name="document.exe", size=12 * 1024 * 1024)
    config = SimpleNamespace(max_upload_mb=10)

    errors, notices = validate_upload_requirements(uploaded, source, config)

    assert notices == []
    assert any("Unsupported file type" in message for message in errors)
    assert any("above the configured 10 MB limit" in message for message in errors)


def test_upload_requirement_validation_blocks_large_images_for_ocr(tmp_path):
    source = tmp_path / "receipt.png"
    source.write_bytes(b"not a real image")
    uploaded = SimpleNamespace(name="receipt.png", size=9 * 1024 * 1024)
    config = SimpleNamespace(max_upload_mb=10)

    errors, notices = validate_upload_requirements(uploaded, source, config)

    assert notices == []
    assert any("Image OCR files must be 8 MB or smaller" in message for message in errors)


def test_upload_batch_requires_description_only_for_multiple_files():
    one_file = [SimpleNamespace(name="one.pdf")]
    two_files = [SimpleNamespace(name="one.pdf"), SimpleNamespace(name="two.pdf")]
    six_files = [SimpleNamespace(name=f"{index}.pdf") for index in range(6)]

    assert validate_upload_batch_requirements(one_file, "") == []
    assert validate_upload_batch_requirements(two_files, "Quarter-end invoices") == []
    assert validate_upload_batch_requirements(two_files, "") == [
        "Expense name or reference is required when uploading more than one file."
    ]
    assert validate_upload_batch_requirements(six_files, "Too many") == [
        "Select up to 5 files per upload."
    ]


def test_source_download_metadata_uses_safe_name_and_mime_type():
    record = make_record("doc-pdf", "../../Receipt 21.pdf")
    record.source_file_mime_type = "application/pdf; charset=binary"
    no_mime = make_record("doc-bin", "archive.zip")

    assert source_download_name(record) == "Receipt_21.pdf"
    assert source_download_mime(record) == "application/pdf"
    assert source_download_mime(no_mime) == "application/octet-stream"


def test_compliance_backfill_updates_existing_metadata(tmp_path):
    from src.metadata_store import MetadataStore

    config = type(
        "Config",
        (),
        {
            "local_metadata_dir": tmp_path / "metadata",
            "genai_model_id": "cohere.command-r-plus",
        },
    )()
    store = MetadataStore(config)
    report_path = tmp_path / "report.md"
    record = DocumentRecord(
        document_id="doc-existing-gov",
        document_name="receipt.pdf",
        document_type=DocumentType.INVOICE,
        business_reference="lunch with gov customer",
        extracted_text_preview="Restaurant receipt total GBP 42.",
        report_path=str(report_path),
        analysis=DocumentAnalysis(
            document_class="INVOICE",
            executive_summary="Lunch receipt.",
            confidence_score=0.9,
            human_review_required=False,
        ),
    )
    report_path.write_text("old report", encoding="utf-8")
    store.save(record)

    assert backfill_compliance_attention(config, store) == 1
    updated = store.load("doc-existing-gov")

    assert updated.analysis.human_review_required is True
    assert updated.analysis.risk_notes[-1].severity == "MEDIUM"
    assert "knowledge-base" in updated.analysis.risk_notes[-1].evidence
    assert "matched term: gov" in updated.analysis.risk_notes[-1].evidence
    assert "Public-sector expense compliance review" in report_path.read_text(
        encoding="utf-8"
    )


def test_next_action_for_failed_and_reviewed_records():
    failed = make_record("doc-3", "bad.pdf", status=ProcessingStatus.FAILED)
    approved = make_record("doc-4", "approved.pdf", status=ProcessingStatus.APPROVED)
    approved.review_status = ReviewStatus.APPROVED

    assert next_action(failed) == "Fix and retry"
    assert next_action(approved) == "Approved"


def test_next_action_routes_compliance_risk_to_actions_queue():
    record = make_record(
        "doc-compliance",
        "receipt.pdf",
        risks=[
            RiskNote(
                risk="Public-sector expense compliance review",
                severity="HIGH",
                evidence="knowledge-base match",
            )
        ],
    )

    assert next_action(record) == "Compliance review"


def test_next_action_surfaces_workflow_states():
    escalated = make_record("doc-6", "escalated.pdf")
    escalated.workflow_status = WorkflowStatus.ESCALATED
    waiting = make_record("doc-7", "waiting.pdf")
    waiting.workflow_status = WorkflowStatus.WAITING_FOR_INFO
    retry_planned = make_record(
        "doc-8",
        "retry.pdf",
        status=ProcessingStatus.FAILED,
    )
    retry_planned.workflow_status = WorkflowStatus.RETRY_PLANNED

    assert next_action(escalated) == "Escalated review"
    assert next_action(waiting) == "Waiting for info"
    assert next_action(retry_planned) == "Retry planned"


def test_processing_stage_rows_show_backend_lifecycle():
    record = make_record("doc-5", "lifecycle.pdf")
    record.object_storage_path = "oci://bucket/documents/doc-5/lifecycle.pdf"
    record.extracted_text_preview = "Important contract text"
    record.assignee = "Legal"
    record.workflow_status = WorkflowStatus.ASSIGNED

    rows = processing_stage_rows(record)

    assert [row["Stage"] for row in rows] == [
        "Upload",
        "Object Storage",
        "Extraction",
        "GenAI analysis",
        "Review report",
        "Human decision",
        "Workflow",
    ]
    assert rows[1]["State"] == "Complete"
    assert rows[2]["Evidence"] == "Extraction source not recorded; text preview saved"
    assert rows[-2]["Evidence"] == "Approve or reject"
    assert rows[-1]["State"] == "Assigned"
    assert "Legal" in rows[-1]["Evidence"]


def test_file_size_label_formats_known_and_missing_sizes():
    assert file_size_label(None) == "Not captured"
    assert file_size_label(512) == "512 B"
    assert file_size_label(2048) == "2.0 KB"
    assert file_size_label(2 * 1024 * 1024) == "2.00 MB"


def test_filter_queue_rows_uses_simple_review_views():
    ready = make_record("doc-1", "ready.pdf")
    processing = make_record(
        "doc-2", "processing.pdf", status=ProcessingStatus.PROCESSING
    )
    failed = make_record("doc-3", "failed.pdf", status=ProcessingStatus.FAILED)
    approved = make_record("doc-4", "approved.pdf", status=ProcessingStatus.APPROVED)
    approved.review_status = ReviewStatus.APPROVED
    df = pd.DataFrame(
        [record_to_row(record) for record in [ready, processing, failed, approved]]
    )

    assert filter_queue_rows(df, view="Ready", query="")["Document ID"].tolist() == [
        "doc-1"
    ]
    assert filter_queue_rows(df, view="Processing", query="")[
        "Document ID"
    ].tolist() == ["doc-2"]
    assert filter_queue_rows(df, view="Failed", query="")["Document ID"].tolist() == [
        "doc-3"
    ]
    assert filter_queue_rows(df, view="Reviewed", query="")["Document ID"].tolist() == [
        "doc-4"
    ]
    assert filter_queue_rows(df, view="All", query="approved")[
        "Document ID"
    ].tolist() == ["doc-4"]


def test_dashboard_status_filter_targets_decisions_and_actions():
    approved = make_record(
        "doc-approved", "approved.pdf", status=ProcessingStatus.APPROVED
    )
    approved.review_status = ReviewStatus.APPROVED
    rejected = make_record(
        "doc-rejected", "rejected.pdf", status=ProcessingStatus.REJECTED
    )
    rejected.review_status = ReviewStatus.REJECTED
    failed = make_record("doc-failed", "failed.pdf", status=ProcessingStatus.FAILED)
    retry_planned = make_record(
        "doc-retry", "retry.pdf", status=ProcessingStatus.FAILED
    )
    retry_planned.workflow_status = WorkflowStatus.RETRY_PLANNED
    compliance = make_record(
        "doc-compliance",
        "receipt.pdf",
        risks=[
            RiskNote(
                risk="Public-sector expense compliance review",
                severity="HIGH",
                evidence="knowledge-base match",
            )
        ],
    )
    df = pd.DataFrame(
        [
            record_to_row(record)
            for record in [approved, rejected, failed, retry_planned, compliance]
        ]
    )

    assert filter_dashboard_status(df, "Reviewed")["Document ID"].tolist() == [
        "doc-approved",
        "doc-rejected",
    ]
    assert filter_queue_rows(df, view="All", query="", status_filter="Approved")[
        "Document ID"
    ].tolist() == ["doc-approved"]
    assert filter_queue_rows(df, view="All", query="", status_filter="Rejected")[
        "Document ID"
    ].tolist() == ["doc-rejected"]
    assert filter_queue_rows(df, view="All", query="", status_filter="Fix and retry")[
        "Document ID"
    ].tolist() == ["doc-failed"]
    assert filter_queue_rows(df, view="All", query="", status_filter="Retry planned")[
        "Document ID"
    ].tolist() == ["doc-retry"]
    assert filter_queue_rows(
        df, view="All", query="", status_filter="Compliance review"
    )["Document ID"].tolist() == ["doc-compliance"]


def test_queue_view_frames_splits_dashboard_sections():
    ready = make_record("doc-1", "ready.pdf")
    processing = make_record(
        "doc-2", "processing.pdf", status=ProcessingStatus.PROCESSING
    )
    failed = make_record("doc-3", "failed.pdf", status=ProcessingStatus.FAILED)
    approved = make_record("doc-4", "approved.pdf", status=ProcessingStatus.APPROVED)
    approved.review_status = ReviewStatus.APPROVED
    df = pd.DataFrame(
        [record_to_row(record) for record in [ready, processing, failed, approved]]
    )

    sections = queue_view_frames(df, query="")

    assert sections["Processing"]["Document ID"].tolist() == ["doc-2"]
    assert sections["Ready"]["Document ID"].tolist() == ["doc-1"]
    assert sections["Failed"]["Document ID"].tolist() == ["doc-3"]
    assert sections["Reviewed"]["Document ID"].tolist() == ["doc-4"]

    approved_sections = queue_view_frames(df, query="", status_filter="Approved")
    assert approved_sections["Reviewed"]["Document ID"].tolist() == ["doc-4"]
    assert approved_sections["Ready"].empty


def test_actions_prioritize_user_work():
    ready = make_record("doc-1", "ready.pdf")
    failed = make_record("doc-2", "failed.pdf", status=ProcessingStatus.FAILED)
    processing = make_record(
        "doc-3", "processing.pdf", status=ProcessingStatus.PROCESSING
    )
    approved = make_record("doc-4", "approved.pdf", status=ProcessingStatus.APPROVED)
    approved.review_status = ReviewStatus.APPROVED
    escalated = make_record("doc-5", "escalated.pdf")
    escalated.workflow_status = WorkflowStatus.ESCALATED

    ordered = sort_action_records([approved, processing, failed, ready, escalated])

    assert [record.document_id for record in ordered] == [
        "doc-5",
        "doc-1",
        "doc-2",
        "doc-3",
        "doc-4",
    ]
    assert reviewer_action_count([ready, failed, processing, approved, escalated]) == 3


def test_next_action_document_id_skips_current_and_reviewed_records():
    current = make_record("doc-current", "current.pdf")
    next_ready = make_record("doc-ready", "ready.pdf")
    failed = make_record("doc-failed", "failed.pdf", status=ProcessingStatus.FAILED)
    approved = make_record(
        "doc-approved", "approved.pdf", status=ProcessingStatus.APPROVED
    )
    approved.review_status = ReviewStatus.APPROVED

    assert (
        next_action_document_id([approved, current, failed, next_ready], "doc-current")
        == "doc-ready"
    )
    assert next_action_document_id([approved, current], "doc-current") is None


def test_sidebar_navigation_buttons_change_page(monkeypatch, tmp_path):
    configure_streamlit_test_env(monkeypatch, tmp_path)

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
        assert query_value(app.query_params, "page") == "Dashboard"
        app = app.run()
        assert app.session_state["page"] == "Dashboard"

        for button in app.button:
            if button.label in {"↗", "Open", "Review"}:
                app = button.click().run()
                break
        assert app.session_state["page"] == "Actions"
        assert app.session_state["selected_document_id"] == "test-doc"
        assert all(
            "Calling st.rerun() within a callback" not in warning.value
            for warning in app.warning
        )
    finally:
        get_config.cache_clear()


def test_sidebar_upload_settings_and_query_navigation(monkeypatch, tmp_path):
    configure_streamlit_test_env(monkeypatch, tmp_path)

    from src.config import get_config

    get_config.cache_clear()
    try:
        app = AppTest.from_file("app.py", default_timeout=5).run()
        assert app.session_state["page"] == "Upload"

        for button in app.sidebar.button:
            if button.label == "Dashboard":
                app = button.click().run()
                break
        assert app.session_state["page"] == "Dashboard"
        assert query_value(app.query_params, "page") == "Dashboard"

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
        assert query_value(app.query_params, "page") == "Settings"

        refreshed = AppTest.from_file("app.py", default_timeout=5)
        refreshed.query_params["page"] = "Dashboard"
        refreshed = refreshed.run()
        assert refreshed.session_state["page"] == "Dashboard"
    finally:
        get_config.cache_clear()


def test_upload_how_to_use_button_opens_guide(monkeypatch, tmp_path):
    configure_streamlit_test_env(monkeypatch, tmp_path)

    from src.config import get_config

    get_config.cache_clear()
    try:
        app = AppTest.from_file("app.py", default_timeout=5).run()
        assert app.session_state["page"] == "Upload"

        for button in app.button:
            if button.label == "How to Use":
                app = button.click().run()
                break

        assert app.session_state["page"] == "How to Use"
        assert query_value(app.query_params, "page") == "How to Use"
    finally:
        get_config.cache_clear()


def test_upload_page_uses_single_expense_reference_field(monkeypatch, tmp_path):
    configure_streamlit_test_env(monkeypatch, tmp_path)

    from src.config import get_config

    get_config.cache_clear()
    try:
        app = AppTest.from_file("app.py", default_timeout=5).run()

        assert [item.label for item in app.text_input] == []
        assert [item.label for item in app.text_area] == [
            "Expense name or reference",
            "Notes",
        ]
    finally:
        get_config.cache_clear()


def test_actions_document_type_editor_updates_metadata(monkeypatch, tmp_path):
    configure_streamlit_test_env(monkeypatch, tmp_path)

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

        app = AppTest.from_file("app.py", default_timeout=5)
        app.query_params["page"] = "Actions"
        app = app.run()
        assert app.session_state["page"] == "Actions"

        for selectbox in app.selectbox:
            if selectbox.label == "Document type":
                app = selectbox.set_value(DocumentType.INVOICE).run()
                break
        for button in app.button:
            if button.label == "Save Type":
                app = button.click().run()
                break
        updated = MetadataStore(config).load("test-doc")
        assert updated.document_type == DocumentType.INVOICE
        assert "- Document Type: INVOICE" in report_path.read_text(encoding="utf-8")
    finally:
        get_config.cache_clear()


def test_approve_advances_actions_picker_to_next_item(monkeypatch, tmp_path):
    configure_streamlit_test_env(monkeypatch, tmp_path)

    from src.config import get_config
    from src.metadata_store import MetadataStore

    get_config.cache_clear()
    try:
        config = get_config()
        store = MetadataStore(config)
        current = make_record("doc-current", "current-contract.pdf")
        current.uploaded_at = datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc)
        next_record = make_record("doc-next", "next-contract.pdf")
        next_record.uploaded_at = datetime(2026, 5, 7, 11, 0, tzinfo=timezone.utc)
        store.save(next_record)
        store.save(current)

        app = AppTest.from_file("app.py", default_timeout=5)
        app.query_params["page"] = "Actions"
        app = app.run()
        assert app.session_state["selected_document_id"] == "doc-current"

        for button in app.button:
            if button.label == "Approve":
                app = button.click().run()
                break

        assert store.load("doc-current").review_status == ReviewStatus.APPROVED
        assert app.session_state["selected_document_id"] == "doc-next"
        assert app.session_state["detail_action_item"] == "doc-next"
    finally:
        get_config.cache_clear()
