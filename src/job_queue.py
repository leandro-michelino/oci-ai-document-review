# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from src.config import AppConfig
from src.logger import get_logger
from src.metadata_store import MetadataStore
from src.models import DocumentRecord, DocumentType, ProcessingStatus, WorkflowStatus
from src.processor import (
    DocumentProcessor,
    create_document_id,
    error_message,
    safe_document_name,
)

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
    job_description: str | None,
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
            job_description,
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


def retry_document_processing(
    config: AppConfig,
    document_id: str,
    actor: str = "Reviewer",
    reason: str | None = None,
) -> str:
    store = MetadataStore(config)
    original = store.load(document_id)
    if original.status != ProcessingStatus.FAILED:
        raise ValueError("Only failed documents can be retried.")

    storage_name = safe_document_name(original.document_name)
    original_copy = config.local_uploads_dir / f"{document_id}-{storage_name}"
    if not original_copy.exists():
        raise FileNotFoundError(
            "The local working copy for this failed document is not available. "
            "Upload the source file again."
        )

    retry_document_id = create_document_id()
    retry_source = (
        config.local_uploads_dir / f"retry-{retry_document_id}-{storage_name}"
    )
    shutil.copyfile(original_copy, retry_source)

    retry_record = DocumentRecord(
        document_id=retry_document_id,
        document_name=original.document_name,
        document_type=original.document_type,
        source_file_size_bytes=original.source_file_size_bytes,
        source_file_mime_type=original.source_file_mime_type,
        status=ProcessingStatus.UPLOADED,
        business_reference=original.business_reference,
        notes=original.notes,
        job_description=original.job_description,
        parent_document_id=document_id,
        assignee=original.assignee,
        due_at=original.due_at,
        workflow_status=(
            WorkflowStatus.ASSIGNED if original.assignee else WorkflowStatus.NEW
        ),
    )
    store.save(retry_record)
    store.record_retry(
        document_id, actor=actor, reason=reason, new_document_id=retry_document_id
    )
    submit_document_processing(
        config=config,
        source_path=retry_source,
        document_id=retry_document_id,
        document_name=original.document_name,
        document_type=original.document_type,
        business_reference=original.business_reference,
        notes=original.notes,
        job_description=original.job_description,
        source_file_size_bytes=original.source_file_size_bytes,
        source_file_mime_type=original.source_file_mime_type,
    )
    return retry_document_id


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
    job_description: str | None,
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
            job_description=job_description,
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
        MetadataStore(config).mark_failed(document_id, error_message(exc))
    except Exception:
        logger.exception(
            "Could not mark background processing failed for %s", document_id
        )
