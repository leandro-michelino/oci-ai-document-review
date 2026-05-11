from types import SimpleNamespace

from src.job_queue import (
    _process_document,
    retry_document_processing,
    submit_document_processing,
)
from src.metadata_store import MetadataStore
from src.models import DocumentRecord, DocumentType, ProcessingStatus, WorkflowStatus


def test_background_worker_marks_startup_failure_failed(tmp_path, monkeypatch):
    class BrokenProcessor:
        def __init__(self, config):
            raise RuntimeError("missing runtime config")

    monkeypatch.setattr("src.job_queue.DocumentProcessor", BrokenProcessor)
    config = SimpleNamespace(local_metadata_dir=tmp_path / "metadata")
    store = MetadataStore(config)
    store.save(
        DocumentRecord(
            document_id="doc-failed",
            document_name="contract.pdf",
            document_type=DocumentType.CONTRACT,
        )
    )
    source = tmp_path / "queued-contract.pdf"
    source.write_text("source", encoding="utf-8")

    _process_document(
        config=config,
        source_path=source,
        document_id="doc-failed",
        document_name="contract.pdf",
        document_type=DocumentType.CONTRACT,
        business_reference=None,
        notes=None,
        job_description=None,
        source_file_size_bytes=None,
        source_file_mime_type=None,
    )

    updated = store.load("doc-failed")
    assert updated.status == ProcessingStatus.FAILED
    assert updated.error_message == "missing runtime config"
    assert updated.audit_events[-1].action == "PROCESSING_FAILED"
    assert not source.exists()


def test_submit_document_processing_uses_configured_parallel_jobs(
    tmp_path, monkeypatch
):
    config = SimpleNamespace(max_parallel_jobs=5)
    captured = {}

    class FakeFuture:
        def add_done_callback(self, callback):
            callback(self)

    class FakeExecutor:
        def submit(self, fn, *args):
            captured["submitted_fn"] = fn
            captured["submitted_args"] = args
            return FakeFuture()

    def fake_get_executor(max_workers):
        captured["max_workers"] = max_workers
        return FakeExecutor()

    monkeypatch.setattr("src.job_queue.get_executor", fake_get_executor)

    assert submit_document_processing(
        config=config,
        source_path=tmp_path / "contract.pdf",
        document_id="doc-parallel",
        document_name="contract.pdf",
        document_type=DocumentType.CONTRACT,
        business_reference=None,
        notes=None,
        job_description=None,
        source_file_size_bytes=None,
        source_file_mime_type=None,
    )

    assert captured["max_workers"] == 5
    assert captured["submitted_args"][0] is config


def test_retry_document_processing_creates_child_record_and_history(
    tmp_path, monkeypatch
):
    config = SimpleNamespace(
        local_metadata_dir=tmp_path / "metadata",
        local_uploads_dir=tmp_path / "uploads",
        max_parallel_jobs=1,
    )
    config.local_metadata_dir.mkdir()
    config.local_uploads_dir.mkdir()
    store = MetadataStore(config)
    store.save(
        DocumentRecord(
            document_id="doc-failed",
            document_name="contract.pdf",
            document_type=DocumentType.CONTRACT,
            status=ProcessingStatus.FAILED,
            job_description="Quarter-end vendor review",
            assignee="Legal",
        )
    )
    (config.local_uploads_dir / "doc-failed-contract.pdf").write_text(
        "contract source",
        encoding="utf-8",
    )
    submitted = {}

    def fake_submit_document_processing(**kwargs):
        submitted.update(kwargs)
        return True

    monkeypatch.setattr("src.job_queue.create_document_id", lambda: "doc-retry")
    monkeypatch.setattr(
        "src.job_queue.submit_document_processing",
        fake_submit_document_processing,
    )

    retry_id = retry_document_processing(
        config,
        "doc-failed",
        actor="Reviewer",
        reason="Transient OCR issue",
    )

    assert retry_id == "doc-retry"
    original = store.load("doc-failed")
    assert original.retry_count == 1
    assert original.retry_history[-1].new_document_id == "doc-retry"
    assert original.workflow_status == WorkflowStatus.RETRY_PLANNED
    retry = store.load("doc-retry")
    assert retry.parent_document_id == "doc-failed"
    assert retry.job_description == "Quarter-end vendor review"
    assert retry.assignee == "Legal"
    assert retry.workflow_status == WorkflowStatus.ASSIGNED
    assert submitted["document_id"] == "doc-retry"
    assert submitted["job_description"] == "Quarter-end vendor review"
    assert submitted["source_path"].name == "retry-doc-retry-contract.pdf"
