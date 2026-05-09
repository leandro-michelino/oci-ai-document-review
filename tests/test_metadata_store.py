from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.metadata_store import MetadataStore
from src.models import (
    DocumentRecord,
    DocumentType,
    ProcessingStatus,
    ReviewStatus,
    WorkflowStatus,
)
from src.safety_messages import GENAI_SAFETY_REVIEW_MESSAGE
from src.safety_messages import DOCUMENT_UNDERSTANDING_PAGE_LIMIT_MESSAGE


def test_list_records_skips_invalid_metadata(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    valid = DocumentRecord(
        document_id="doc-1",
        document_name="contract.pdf",
        document_type=DocumentType.CONTRACT,
    )
    (tmp_path / "doc-1.json").write_text(valid.model_dump_json(), encoding="utf-8")
    (tmp_path / "broken.json").write_text("{not-json", encoding="utf-8")

    records = MetadataStore(config).list_records()

    assert [record.document_id for record in records] == ["doc-1"]


def test_fail_stale_processing_marks_old_processing_records_failed(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    store = MetadataStore(config)
    record = DocumentRecord(
        document_id="doc-2",
        document_name="receipt.pdf",
        document_type=DocumentType.GENERAL,
        status=ProcessingStatus.PROCESSING,
        uploaded_at=datetime.now(timezone.utc) - timedelta(minutes=20),
    )
    store.save(record)

    assert store.fail_stale_processing(max_age_minutes=10) == 1
    updated = store.load("doc-2")
    assert updated.status == ProcessingStatus.FAILED
    assert "timeout window" in updated.error_message
    assert updated.audit_events[-1].action == "STALE_PROCESSING_FAILED"


def test_fail_stale_processing_marks_submitted_records_failed_after_timeout(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    store = MetadataStore(config)
    record = DocumentRecord(
        document_id="doc-3",
        document_name="queued.pdf",
        document_type=DocumentType.GENERAL,
        status=ProcessingStatus.EXTRACTED,
        uploaded_at=datetime.now(timezone.utc) - timedelta(minutes=20),
    )
    store.save(record)

    assert (
        store.fail_stale_processing(
            max_age_minutes=10,
            protected_document_ids={"doc-3"},
        )
        == 1
    )
    updated = store.load("doc-3")
    assert updated.status == ProcessingStatus.FAILED


def test_fail_stale_processing_keeps_recent_submitted_records_active(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    store = MetadataStore(config)
    record = DocumentRecord(
        document_id="doc-4",
        document_name="queued.pdf",
        document_type=DocumentType.GENERAL,
        status=ProcessingStatus.UPLOADED,
        uploaded_at=datetime.now(timezone.utc) - timedelta(minutes=2),
    )
    store.save(record)

    assert (
        store.fail_stale_processing(
            max_age_minutes=10,
            protected_document_ids={"doc-4"},
        )
        == 0
    )
    updated = store.load("doc-4")
    assert updated.status == ProcessingStatus.UPLOADED


def test_set_workflow_updates_assignment_sla_and_audit(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    store = MetadataStore(config)
    due_at = datetime(2026, 5, 8, tzinfo=timezone.utc)
    store.save(
        DocumentRecord(
            document_id="doc-workflow",
            document_name="contract.pdf",
            document_type=DocumentType.CONTRACT,
        )
    )

    updated = store.set_workflow(
        "doc-workflow",
        workflow_status=WorkflowStatus.ASSIGNED,
        assignee=" Legal Team ",
        due_at=due_at,
        actor="Manager",
    )

    assert updated.workflow_status == WorkflowStatus.ASSIGNED
    assert updated.assignee == "Legal Team"
    assert updated.due_at == due_at
    assert updated.audit_events[-1].action == "WORKFLOW_UPDATED"
    assert updated.audit_events[-1].actor == "Manager"


def test_add_comment_appends_comment_and_audit(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    store = MetadataStore(config)
    store.save(
        DocumentRecord(
            document_id="doc-comment",
            document_name="invoice.pdf",
            document_type=DocumentType.INVOICE,
        )
    )

    updated = store.add_comment(
        "doc-comment",
        author=" Finance ",
        comment=" Please confirm the supplier bank details. ",
    )

    assert updated.workflow_comments[-1].author == "Finance"
    assert updated.workflow_comments[-1].comment == (
        "Please confirm the supplier bank details."
    )
    assert updated.audit_events[-1].action == "COMMENT_ADDED"


def test_set_review_closes_workflow_and_records_audit(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    store = MetadataStore(config)
    store.save(
        DocumentRecord(
            document_id="doc-review",
            document_name="contract.pdf",
            document_type=DocumentType.CONTRACT,
            status=ProcessingStatus.REVIEW_REQUIRED,
            workflow_status=WorkflowStatus.IN_REVIEW,
        )
    )

    updated = store.set_review("doc-review", approved=True, comments="Looks good.")

    assert updated.status == ProcessingStatus.APPROVED
    assert updated.review_status == ReviewStatus.APPROVED
    assert updated.workflow_status == WorkflowStatus.CLOSED
    assert updated.audit_events[-1].action == "REVIEW_APPROVED"


def test_record_retry_tracks_retry_history_and_status(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    store = MetadataStore(config)
    store.save(
        DocumentRecord(
            document_id="doc-failed",
            document_name="scan.pdf",
            document_type=DocumentType.GENERAL,
            status=ProcessingStatus.FAILED,
        )
    )

    updated = store.record_retry(
        "doc-failed",
        actor="Reviewer",
        reason="Better scan uploaded",
        new_document_id="doc-retry",
    )

    assert updated.retry_count == 1
    assert updated.retry_history[-1].new_document_id == "doc-retry"
    assert updated.workflow_status == WorkflowStatus.RETRY_PLANNED
    assert updated.audit_events[-1].action == "RETRY_QUEUED"


def test_mark_failed_records_audit_once_for_same_failure(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    store = MetadataStore(config)
    store.save(
        DocumentRecord(
            document_id="doc-error",
            document_name="scan.pdf",
            document_type=DocumentType.GENERAL,
            status=ProcessingStatus.PROCESSING,
        )
    )

    first = store.mark_failed("doc-error", "OCR timeout", actor="Worker")
    second = store.mark_failed("doc-error", "OCR timeout", actor="Worker")

    assert second.status == ProcessingStatus.FAILED
    assert second.error_message == "OCR timeout"
    assert [event.action for event in first.audit_events] == ["PROCESSING_FAILED"]
    assert [event.action for event in second.audit_events] == ["PROCESSING_FAILED"]


def test_load_sanitizes_stored_genai_content_filter_json(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    store = MetadataStore(config)
    raw = '{ "code" : "InvalidParameter", "message" : "Inappropriate content detected!!!" }'
    store.save(
        DocumentRecord(
            document_id="doc-safety",
            document_name="scan.pdf",
            document_type=DocumentType.GENERAL,
            status=ProcessingStatus.FAILED,
            error_message=raw,
        )
    )

    updated = store.mark_failed("doc-safety", raw, actor="Worker")

    assert updated.error_message == GENAI_SAFETY_REVIEW_MESSAGE
    assert updated.audit_events[-1].detail == GENAI_SAFETY_REVIEW_MESSAGE


def test_load_sanitizes_stored_document_ai_page_limit_json(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    store = MetadataStore(config)
    raw = (
        "OCI Document Understanding failed: {'target_service': 'ai_service_document', "
        "'status': 413, 'message': 'Input file has too many pages, maximum number "
        "of pages allowed is: 5'}"
    )
    store.save(
        DocumentRecord(
            document_id="doc-page-limit",
            document_name="scan.pdf",
            document_type=DocumentType.GENERAL,
            status=ProcessingStatus.FAILED,
            error_message=raw,
        )
    )

    loaded = store.load("doc-page-limit")

    assert loaded.error_message == DOCUMENT_UNDERSTANDING_PAGE_LIMIT_MESSAGE
