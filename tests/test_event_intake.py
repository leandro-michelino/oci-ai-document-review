# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from types import SimpleNamespace

from src.event_intake import (
    document_name_from_object,
    import_event_queue,
    job_description_from_object,
    marker_document_id,
)
from src.metadata_store import MetadataStore
from src.models import DocumentType, ProcessingStatus


class FakeObjectStorage:
    def __init__(self, markers: dict[str, dict], objects: dict[str, bytes]):
        self.markers = markers
        self.objects = objects
        self.deleted = []

    def list_objects(self, prefix: str, limit: int = 100) -> list[str]:
        return [name for name in self.markers if name.startswith(prefix)][:limit]

    def get_object_text(self, object_name: str) -> str:
        import json

        return json.dumps(self.markers[object_name])

    def download_file(self, object_name: str, file_path):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(self.objects[object_name])
        return file_path

    def delete_object(self, object_name: str) -> None:
        self.deleted.append(object_name)
        self.markers.pop(object_name, None)

    def object_uri(self, object_name: str) -> str:
        return f"oci://doc-review-input@example/{object_name}"


def make_config(tmp_path, enabled=True):
    return SimpleNamespace(
        event_intake_enabled=enabled,
        event_intake_queue_prefix="event-queue/",
        event_intake_incoming_prefix="incoming/",
        oci_bucket_name="doc-review-input",
        oci_namespace="example",
        local_metadata_dir=tmp_path / "metadata",
        local_reports_dir=tmp_path / "reports",
        local_uploads_dir=tmp_path / "uploads",
        max_parallel_jobs=1,
    )


def test_object_event_helpers_extract_file_and_reference():
    object_name = "incoming/Client%20Dinner/receipt.pdf"

    assert document_name_from_object(object_name, "incoming/") == "receipt.pdf"
    assert job_description_from_object(object_name, "incoming/") == "Client Dinner"


def test_import_event_queue_creates_record_and_submits_processing(monkeypatch, tmp_path):
    marker = {
        "event_id": "event-1",
        "namespace": "example",
        "bucket": "doc-review-input",
        "object_name": "incoming/Client Dinner/receipt.pdf",
        "etag": "abc123",
        "content_type": "application/pdf",
    }
    object_storage = FakeObjectStorage(
        markers={"event-queue/event-1.json": marker},
        objects={"incoming/Client Dinner/receipt.pdf": b"receipt bytes"},
    )
    submitted = {}

    def fake_submit_document_processing(**kwargs):
        submitted.update(kwargs)
        return True

    monkeypatch.setattr(
        "src.event_intake.submit_document_processing",
        fake_submit_document_processing,
    )
    config = make_config(tmp_path)
    store = MetadataStore(config)

    result = import_event_queue(
        config, object_storage=object_storage, store=store, limit=10
    )

    document_id = marker_document_id(marker)
    record = store.load(document_id)
    assert result.imported == 1
    assert record.status == ProcessingStatus.UPLOADED
    assert record.document_type == DocumentType.AUTO_DETECT
    assert record.document_name == "receipt.pdf"
    assert record.job_description == "Client Dinner"
    assert record.object_storage_path.endswith("incoming/Client Dinner/receipt.pdf")
    assert submitted["document_id"] == document_id
    assert submitted["source_path"].exists()
    assert object_storage.deleted == ["event-queue/event-1.json"]


def test_import_event_queue_noops_when_disabled(tmp_path):
    config = make_config(tmp_path, enabled=False)
    object_storage = FakeObjectStorage(
        markers={"event-queue/event-1.json": {}},
        objects={},
    )

    result = import_event_queue(
        config, object_storage=object_storage, store=MetadataStore(config)
    )

    assert result.imported == 0
    assert result.messages == ["Event intake is disabled."]
