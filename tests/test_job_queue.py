from types import SimpleNamespace

from src.job_queue import _process_document
from src.metadata_store import MetadataStore
from src.models import DocumentRecord, DocumentType, ProcessingStatus


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
        source_file_size_bytes=None,
        source_file_mime_type=None,
    )

    updated = store.load("doc-failed")
    assert updated.status == ProcessingStatus.FAILED
    assert updated.error_message == "missing runtime config"
    assert not source.exists()
