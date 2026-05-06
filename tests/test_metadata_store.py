from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.metadata_store import MetadataStore
from src.models import DocumentRecord, DocumentType, ProcessingStatus


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
    assert "Retry the upload" in updated.error_message


def test_fail_stale_processing_skips_live_queued_records(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    store = MetadataStore(config)
    record = DocumentRecord(
        document_id="doc-3",
        document_name="queued.pdf",
        document_type=DocumentType.GENERAL,
        status=ProcessingStatus.UPLOADED,
        uploaded_at=datetime.now(timezone.utc) - timedelta(minutes=20),
    )
    store.save(record)

    assert store.fail_stale_processing(
        max_age_minutes=10,
        protected_document_ids={"doc-3"},
    ) == 0
    updated = store.load("doc-3")
    assert updated.status == ProcessingStatus.UPLOADED
