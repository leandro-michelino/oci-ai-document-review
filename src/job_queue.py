from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from src.config import AppConfig
from src.logger import get_logger
from src.metadata_store import MetadataStore
from src.models import DocumentType, ProcessingStatus
from src.processor import DocumentProcessor, error_message


logger = get_logger(__name__)
_executors: dict[int, ThreadPoolExecutor] = {}
_submitted: set[str] = set()
_lock = Lock()


def submitted_document_ids() -> set[str]:
    with _lock:
        return set(_submitted)


def get_executor(max_workers: int) -> ThreadPoolExecutor:
    workers = max(1, max_workers)
    with _lock:
        executor = _executors.get(workers)
        if executor is None:
            executor = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="doc-review-worker",
            )
            _executors[workers] = executor
        return executor


def submit_document_processing(
    config: AppConfig,
    source_path: Path,
    document_id: str,
    document_name: str,
    document_type: DocumentType,
    business_reference: str | None,
    notes: str | None,
    source_file_size_bytes: int | None,
    source_file_mime_type: str | None,
) -> bool:
    with _lock:
        if document_id in _submitted:
            return False
        _submitted.add(document_id)

    try:
        future = get_executor(config.max_parallel_jobs).submit(
            _process_document,
            config,
            source_path,
            document_id,
            document_name,
            document_type,
            business_reference,
            notes,
            source_file_size_bytes,
            source_file_mime_type,
        )
    except Exception as exc:
        _remove_submitted(document_id)
        _mark_failed(config, document_id, exc)
        source_path.unlink(missing_ok=True)
        raise
    future.add_done_callback(lambda completed: _remove_submitted(document_id))
    return True


def _remove_submitted(document_id: str) -> None:
    with _lock:
        _submitted.discard(document_id)


def _process_document(
    config: AppConfig,
    source_path: Path,
    document_id: str,
    document_name: str,
    document_type: DocumentType,
    business_reference: str | None,
    notes: str | None,
    source_file_size_bytes: int | None,
    source_file_mime_type: str | None,
) -> None:
    try:
        DocumentProcessor(config).process(
            source_path=source_path,
            document_name=document_name,
            document_type=document_type,
            business_reference=business_reference,
            notes=notes,
            source_file_size_bytes=source_file_size_bytes,
            source_file_mime_type=source_file_mime_type,
            document_id=document_id,
        )
    except Exception as exc:
        logger.exception("Background document processing failed for %s", document_id)
        _mark_failed(config, document_id, exc)
    finally:
        source_path.unlink(missing_ok=True)


def _mark_failed(config: AppConfig, document_id: str, exc: Exception) -> None:
    try:
        MetadataStore(config).update(
            document_id,
            status=ProcessingStatus.FAILED,
            error_message=error_message(exc),
            processed_at=datetime.now(timezone.utc),
        )
    except Exception:
        logger.exception("Could not mark background processing failed for %s", document_id)
