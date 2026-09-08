import json
from types import SimpleNamespace

import pytest

from src.document_deletion import discard_failed_document, portal_object_name
from src.metadata_store import MetadataStore
from src.models import DocumentRecord, DocumentType, ProcessingStatus


class FakeObjectStorage:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.deleted_objects: list[str] = []

    def delete_object(self, object_name: str) -> None:
        self.deleted_objects.append(object_name)
        if self.error:
            raise self.error


def configured_store(tmp_path):
    config = SimpleNamespace(
        local_metadata_dir=tmp_path / "metadata",
        local_reports_dir=tmp_path / "reports",
        local_uploads_dir=tmp_path / "uploads",
    )
    for path in (
        config.local_metadata_dir,
        config.local_reports_dir,
        config.local_uploads_dir,
    ):
        path.mkdir(parents=True)
    return config, MetadataStore(config)


def failed_record() -> DocumentRecord:
    return DocumentRecord(
        document_id="failed-123",
        document_name="receipt 2026.pdf",
        document_type=DocumentType.INVOICE,
        status=ProcessingStatus.FAILED,
        object_storage_path="oci://review@namespace/documents/failed-123/receipt_2026.pdf",
    )


def test_discard_failed_document_deletes_portal_copy_and_local_artifacts(tmp_path):
    config, store = configured_store(tmp_path)
    record = failed_record()
    store.save(record)
    report = config.local_reports_dir / "failed-123.md"
    upload = config.local_uploads_dir / "failed-123-receipt_2026.pdf"
    report.write_text("report", encoding="utf-8")
    upload.write_bytes(b"source")
    object_storage = FakeObjectStorage()

    result = discard_failed_document(
        config,
        store,
        record.document_id,
        actor="Operations",
        reason="Unsupported source file",
        object_storage=object_storage,
    )

    assert object_storage.deleted_objects == [
        "documents/failed-123/receipt_2026.pdf"
    ]
    assert result.cloud_object_deleted is True
    assert not store.path_for(record.document_id).exists()
    assert not report.exists()
    assert not upload.exists()
    tombstone = json.loads(result.local_result.tombstone_path.read_text(encoding="utf-8"))
    assert tombstone["action"] == "FAILED_DOCUMENT_DISCARDED"
    assert tombstone["actor"] == "Operations"
    assert tombstone["reason"] == "Unsupported source file"
    assert tombstone["cloud_object_deleted"] is True


def test_discard_rejects_active_document_without_deleting_anything(tmp_path):
    config, store = configured_store(tmp_path)
    record = failed_record()
    record.status = ProcessingStatus.PROCESSING
    store.save(record)
    object_storage = FakeObjectStorage()

    with pytest.raises(ValueError, match="Only failed"):
        discard_failed_document(
            config, store, record.document_id, actor="Operations", object_storage=object_storage
        )

    assert object_storage.deleted_objects == []
    assert store.path_for(record.document_id).exists()
    assert not store.deleted_root.exists()


def test_cloud_deletion_error_preserves_local_recovery_artifacts(tmp_path):
    config, store = configured_store(tmp_path)
    record = failed_record()
    store.save(record)
    report = config.local_reports_dir / "failed-123.md"
    report.write_text("report", encoding="utf-8")
    object_storage = FakeObjectStorage(error=RuntimeError("OCI unavailable"))

    with pytest.raises(RuntimeError, match="Local data has been kept"):
        discard_failed_document(
            config, store, record.document_id, actor="Operations", object_storage=object_storage
        )

    assert store.path_for(record.document_id).exists()
    assert report.exists()
    assert not store.deleted_root.exists()


def test_missing_portal_object_allows_discard(tmp_path):
    config, store = configured_store(tmp_path)
    record = failed_record()
    store.save(record)
    missing = RuntimeError("not found")
    missing.status = 404

    result = discard_failed_document(
        config,
        store,
        record.document_id,
        actor="Operations",
        object_storage=FakeObjectStorage(error=missing),
    )

    assert result.cloud_object_deleted is False
    assert not store.path_for(record.document_id).exists()


def test_portal_object_name_is_restricted_to_the_document_prefix():
    assert portal_object_name("abc", "../../incoming/source.pdf") == "documents/abc/source.pdf"
