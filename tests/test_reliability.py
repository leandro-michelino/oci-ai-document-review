"""Processing recovery and bounded IO regression tests. No live OCI calls."""

from datetime import datetime, timedelta, timezone
import multiprocessing
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from scripts.package_release import build_release
from scripts.setup import validate_intake_prefixes
from src.config import AppConfig
from src.document_deletion import discard_failed_document
from src.event_intake import import_event_queue, marker_document_id
from src.health_checks import check_object_storage
from src.job_queue import _process_document, retry_document_processing
from src.metadata_store import DocumentBusyError, MetadataStore
from src.models import DocumentRecord, DocumentType, ProcessingStatus
from src.object_storage_client import ObjectStorageClient
from tests.test_event_intake import FakeObjectStorage, make_config


def _hold_lease(root, ready, release):
    with MetadataStore(SimpleNamespace(local_metadata_dir=root)).document_lease(
        "leased-case"
    ):
        ready.set()
        release.wait(15)


def test_document_lease_protects_work_across_processes(tmp_path, monkeypatch):
    config = make_config(tmp_path)
    store = MetadataStore(config)
    old = datetime.now(timezone.utc) - timedelta(days=40)
    store.save(
        DocumentRecord(
            document_id="leased-case",
            document_name="source.txt",
            document_type=DocumentType.GENERAL,
            uploaded_at=old,
            status=ProcessingStatus.PROCESSING,
        )
    )
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    process = context.Process(target=_hold_lease, args=(store.root, ready, release))
    process.start()
    try:
        assert ready.wait(10)
        assert store.worker_active("leased-case")
        assert store.fail_stale_processing(1) == 0
        store.update("leased-case", status=ProcessingStatus.FAILED, processed_at=old)
        assert store.cleanup_expired_local_data(30).total == 0
        with pytest.raises(DocumentBusyError):
            retry_document_processing(config, "leased-case")
        with pytest.raises(DocumentBusyError):
            discard_failed_document(config, store, "leased-case", "Reviewer")
        source = tmp_path / "queued-source.txt"
        source.write_text("source")

        def forbidden_processor(config):
            pytest.fail("A duplicate worker must not initialize the processor")

        monkeypatch.setattr("src.job_queue.DocumentProcessor", forbidden_processor)
        _process_document(
            config,
            source,
            "leased-case",
            "source.txt",
            DocumentType.GENERAL,
            None,
            None,
            None,
            None,
            None,
        )
        assert source.read_text() == "source"
        assert store.load("leased-case").status == ProcessingStatus.FAILED
    finally:
        release.set()
        process.join(10)
        if process.is_alive():
            process.terminate()
            process.join()
    assert process.exitcode == 0
    assert not store.worker_active("leased-case")


def test_abandoned_queue_record_is_resubmitted(tmp_path, monkeypatch):
    marker = {
        "event_id": "evt",
        "namespace": "example",
        "bucket": "doc-review-input",
        "object_name": "incoming/ref/doc.txt",
        "etag": "current-etag",
    }
    storage = FakeObjectStorage(
        {"event-queue/evt.json": marker}, {marker["object_name"]: b"content"}
    )
    config = make_config(tmp_path)
    store = MetadataStore(config)
    store.save(
        DocumentRecord(
            document_id=marker_document_id(marker),
            document_name="doc.txt",
            document_type=DocumentType.AUTO_DETECT,
        )
    )
    submitted = []
    monkeypatch.setattr(
        "src.event_intake.submit_document_processing",
        lambda **kwargs: submitted.append(kwargs) or True,
    )
    result = import_event_queue(config, object_storage=storage, store=store)
    assert result.imported == 1
    assert submitted[0]["document_id"] == marker_document_id(marker)
    assert not storage.markers


def test_intake_passes_size_limit_and_event_etag(tmp_path, monkeypatch):
    marker = {"event_id": "evt", "object_name": "incoming/doc.txt", "etag": "etag-1"}
    config = make_config(tmp_path)
    config.max_upload_mb = 3
    storage = FakeObjectStorage(
        {"event-queue/evt.json": marker}, {"incoming/doc.txt": b"content"}
    )
    original = storage.download_file
    captured = {}

    def download(name, path, **kwargs):
        captured.update(kwargs)
        return original(name, path)

    storage.download_file = download
    monkeypatch.setattr(
        "src.event_intake.submit_document_processing", lambda **kwargs: True
    )
    assert (
        import_event_queue(
            config, object_storage=storage, store=MetadataStore(config)
        ).imported
        == 1
    )
    assert captured == {"max_bytes": 3 * 1024 * 1024, "if_match": "etag-1"}


class Body:
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False
        self.read = False

    def iter_content(self, chunk_size):
        self.read = True
        yield from self.chunks

    def close(self):
        self.closed = True


def download_client(body, headers=None):
    client = object.__new__(ObjectStorageClient)
    client.config = SimpleNamespace(oci_namespace="namespace", oci_bucket_name="bucket")
    captured = {}

    def get_object(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(data=body, headers=headers or {})

    client.client = SimpleNamespace(get_object=get_object)
    return client, captured


@pytest.mark.parametrize("headers", [{}, {"content-length": "20"}])
def test_oversized_download_keeps_previous_copy_and_closes_response(tmp_path, headers):
    body = Body([b"123", b"456"])
    client, _ = download_client(body, headers)
    target = tmp_path / "source.txt"
    target.write_bytes(b"previous")
    with pytest.raises(ValueError, match="size limit"):
        client.download_file("incoming/source.txt", target, max_bytes=5)
    assert target.read_bytes() == b"previous"
    assert body.closed
    assert list(tmp_path.iterdir()) == [target]


def test_streamed_download_enforces_etag_and_replaces_atomically(tmp_path):
    body = Body([b"abc", b"def"])
    client, captured = download_client(body)
    target = tmp_path / "source.txt"
    assert (
        client.download_file(
            "incoming/source.txt", target, max_bytes=6, if_match="etag"
        )
        == target
    )
    assert captured["if_match"] == "etag"
    assert target.read_bytes() == b"abcdef"
    assert body.closed


@pytest.mark.parametrize(
    "incoming,queue",
    [
        ("incoming/", "incoming/queue/"),
        ("incoming/a/", "incoming/"),
        ("same/", "same/"),
        ("documents/", "queue/"),
        ("incoming/", "documents/queue/"),
    ],
)
def test_recursive_intake_prefixes_are_rejected(incoming, queue):
    with pytest.raises(SystemExit, match="overlap"):
        validate_intake_prefixes(incoming, queue)
    with pytest.raises(ValidationError, match="overlap"):
        AppConfig(
            _env_file=None,
            OCI_REGION="example",
            GENAI_REGION="example",
            OCI_COMPARTMENT_ID="example",
            OCI_NAMESPACE="example",
            OCI_BUCKET_NAME="example",
            GENAI_MODEL_ID="cohere.test",
            EVENT_INTAKE_INCOMING_PREFIX=incoming,
            EVENT_INTAKE_QUEUE_PREFIX=queue,
        )


def test_preflight_reports_client_initialization_error(monkeypatch):
    def fail_client(config):
        raise RuntimeError("Invalid OCI configuration")

    monkeypatch.setattr("src.health_checks.ObjectStorageClient", fail_client)
    result = check_object_storage(SimpleNamespace())
    assert not result.ok
    assert result.detail == "Invalid OCI configuration"


def test_release_excludes_nested_secret_directories_and_ssh_keys(tmp_path):
    import tarfile

    for name in (
        "src/.env.d/token.txt",
        "src/.aws/credentials",
        "docs/id_ed25519",
        "src/KEY.PEM",
        "src/.streamlit/secrets.toml",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic secret")
    build_release(tmp_path, tmp_path / "release.tar.gz")
    with tarfile.open(tmp_path / "release.tar.gz") as archive:
        assert archive.getnames() == []
