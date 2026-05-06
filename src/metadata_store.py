from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.logger import get_logger
from src.models import DocumentRecord, ProcessingStatus, ReviewStatus


logger = get_logger(__name__)


class MetadataStore:
    def __init__(self, config: AppConfig):
        self.root = config.local_metadata_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, document_id: str) -> Path:
        return self.root / f"{document_id}.json"

    def save(self, record: DocumentRecord) -> None:
        self.path_for(record.document_id).write_text(
            record.model_dump_json(indent=2), encoding="utf-8"
        )

    def load(self, document_id: str) -> DocumentRecord:
        return DocumentRecord.model_validate_json(
            self.path_for(document_id).read_text(encoding="utf-8")
        )

    def list_records(self) -> list[DocumentRecord]:
        records = []
        for path in sorted(self.root.glob("*.json"), reverse=True):
            try:
                records.append(DocumentRecord.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception as exc:
                logger.warning("Skipping invalid metadata file %s: %s", path, exc)
        return records

    def update(self, document_id: str, **changes: Any) -> DocumentRecord:
        record = self.load(document_id)
        data = record.model_dump()
        data.update(changes)
        updated = DocumentRecord.model_validate(data)
        self.save(updated)
        return updated

    def set_review(self, document_id: str, approved: bool, comments: str | None) -> DocumentRecord:
        status = ProcessingStatus.APPROVED if approved else ProcessingStatus.REJECTED
        review_status = ReviewStatus.APPROVED if approved else ReviewStatus.REJECTED
        return self.update(
            document_id,
            status=status,
            review_status=review_status,
            review_comments=comments,
            processed_at=datetime.now(timezone.utc),
        )

    def fail_stale_processing(
        self,
        max_age_minutes: int,
        protected_document_ids: set[str] | None = None,
    ) -> int:
        protected_document_ids = protected_document_ids or set()
        now = datetime.now(timezone.utc)
        failed_count = 0
        for record in self.list_records():
            if record.status not in {ProcessingStatus.UPLOADED, ProcessingStatus.PROCESSING}:
                continue
            if record.document_id in protected_document_ids:
                continue
            age_seconds = (now - record.uploaded_at).total_seconds()
            if age_seconds < max_age_minutes * 60:
                continue
            record.status = ProcessingStatus.FAILED
            record.error_message = (
                "Processing did not complete before the configured timeout window. "
                "Retry the upload or check OCI Document Understanding service health."
            )
            record.processed_at = now
            self.save(record)
            failed_count += 1
        return failed_count
