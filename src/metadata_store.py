from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.logger import get_logger
from src.models import (
    AuditEvent,
    DocumentRecord,
    ProcessingStatus,
    RetryEvent,
    ReviewStatus,
    WorkflowComment,
    WorkflowStatus,
)

logger = get_logger(__name__)
ACTIVE_PROCESSING_STATUSES = {
    ProcessingStatus.UPLOADED,
    ProcessingStatus.PROCESSING,
    ProcessingStatus.EXTRACTED,
    ProcessingStatus.AI_ANALYZED,
}


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
                records.append(
                    DocumentRecord.model_validate_json(path.read_text(encoding="utf-8"))
                )
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

    def _append_audit(
        self, record: DocumentRecord, action: str, actor: str, detail: str | None = None
    ) -> None:
        record.audit_events.append(
            AuditEvent(actor=actor or "System", action=action, detail=detail)
        )

    def set_workflow(
        self,
        document_id: str,
        workflow_status: WorkflowStatus,
        assignee: str | None,
        due_at: datetime | None,
        actor: str = "Reviewer",
    ) -> DocumentRecord:
        record = self.load(document_id)
        previous = (
            record.workflow_status,
            record.assignee,
            record.due_at,
        )
        record.workflow_status = workflow_status
        record.assignee = assignee.strip() if assignee and assignee.strip() else None
        record.due_at = due_at
        current = (
            record.workflow_status,
            record.assignee,
            record.due_at,
        )
        if current != previous:
            self._append_audit(
                record,
                "WORKFLOW_UPDATED",
                actor,
                (
                    f"Status={record.workflow_status.value}; "
                    f"Assignee={record.assignee or 'Unassigned'}; "
                    f"Due={record.due_at.date().isoformat() if record.due_at else 'No SLA'}"
                ),
            )
        self.save(record)
        return record

    def add_comment(
        self,
        document_id: str,
        author: str,
        comment: str,
    ) -> DocumentRecord:
        record = self.load(document_id)
        comment_text = comment.strip()
        if not comment_text:
            return record
        record.workflow_comments.append(
            WorkflowComment(author=author.strip() or "Reviewer", comment=comment_text)
        )
        self._append_audit(
            record,
            "COMMENT_ADDED",
            author.strip() or "Reviewer",
            comment_text[:160],
        )
        self.save(record)
        return record

    def record_retry(
        self,
        document_id: str,
        actor: str,
        reason: str | None,
        new_document_id: str | None,
    ) -> DocumentRecord:
        record = self.load(document_id)
        record.retry_count += 1
        record.retry_history.append(
            RetryEvent(
                actor=actor.strip() or "Reviewer",
                reason=reason.strip() if reason else None,
                new_document_id=new_document_id,
            )
        )
        record.workflow_status = WorkflowStatus.RETRY_PLANNED
        self._append_audit(
            record,
            "RETRY_QUEUED",
            actor.strip() or "Reviewer",
            f"New document: {new_document_id or 'not created'}",
        )
        self.save(record)
        return record

    def mark_failed(
        self,
        document_id: str,
        message: str,
        actor: str = "Worker",
        action: str = "PROCESSING_FAILED",
    ) -> DocumentRecord:
        record = self.load(document_id)
        record.status = ProcessingStatus.FAILED
        record.error_message = message
        record.processed_at = datetime.now(timezone.utc)
        last_event = record.audit_events[-1] if record.audit_events else None
        if not (
            last_event and last_event.action == action and last_event.detail == message
        ):
            self._append_audit(record, action, actor, message)
        self.save(record)
        return record

    def set_review(
        self, document_id: str, approved: bool, comments: str | None
    ) -> DocumentRecord:
        record = self.load(document_id)
        record.status = (
            ProcessingStatus.APPROVED if approved else ProcessingStatus.REJECTED
        )
        record.review_status = (
            ReviewStatus.APPROVED if approved else ReviewStatus.REJECTED
        )
        record.workflow_status = WorkflowStatus.CLOSED
        record.review_comments = comments
        record.processed_at = datetime.now(timezone.utc)
        self._append_audit(
            record,
            "REVIEW_APPROVED" if approved else "REVIEW_REJECTED",
            "Reviewer",
            comments,
        )
        self.save(record)
        return record

    def fail_stale_processing(
        self,
        max_age_minutes: int,
        protected_document_ids: set[str] | None = None,
    ) -> int:
        protected_document_ids = protected_document_ids or set()
        now = datetime.now(timezone.utc)
        failed_count = 0
        for record in self.list_records():
            if record.status not in ACTIVE_PROCESSING_STATUSES:
                continue
            age_seconds = (now - record.uploaded_at).total_seconds()
            if age_seconds < max_age_minutes * 60:
                continue
            if record.document_id in protected_document_ids:
                logger.warning(
                    "Marking submitted document %s as stale after %.1f minutes in %s",
                    record.document_id,
                    age_seconds / 60,
                    record.status.value,
                )
            record.status = ProcessingStatus.FAILED
            record.error_message = (
                "Processing did not complete before the configured timeout window. "
                "Retry the upload or check the service logs for the extraction or GenAI step."
            )
            record.processed_at = now
            self._append_audit(
                record,
                "STALE_PROCESSING_FAILED",
                "System",
                record.error_message,
            )
            self.save(record)
            failed_count += 1
        return failed_count
