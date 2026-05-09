import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.file_names import safe_document_name
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
from src.safety_messages import sanitize_provider_payload

logger = get_logger(__name__)
ACTIVE_PROCESSING_STATUSES = {
    ProcessingStatus.UPLOADED,
    ProcessingStatus.PROCESSING,
    ProcessingStatus.EXTRACTED,
    ProcessingStatus.AI_ANALYZED,
}


@dataclass(frozen=True)
class RetentionCleanupResult:
    metadata_records: int = 0
    invalid_metadata_files: int = 0
    reports: int = 0
    uploads: int = 0

    @property
    def total(self) -> int:
        return (
            self.metadata_records
            + self.invalid_metadata_files
            + self.reports
            + self.uploads
        )


class MetadataStore:
    def __init__(self, config: AppConfig):
        self.root = config.local_metadata_dir
        self.reports_root = getattr(
            config, "local_reports_dir", self.root.parent / "reports"
        )
        self.uploads_root = getattr(
            config, "local_uploads_dir", self.root.parent / "uploads"
        )
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, document_id: str) -> Path:
        return self.root / f"{document_id}.json"

    def save(self, record: DocumentRecord) -> None:
        sanitized = DocumentRecord.model_validate(
            sanitize_provider_payload(record.model_dump(mode="python"))
        )
        self.path_for(record.document_id).write_text(
            sanitized.model_dump_json(indent=2), encoding="utf-8"
        )

    def load(self, document_id: str) -> DocumentRecord:
        raw = DocumentRecord.model_validate_json(
            self.path_for(document_id).read_text(encoding="utf-8")
        )
        return DocumentRecord.model_validate(
            sanitize_provider_payload(raw.model_dump(mode="python"))
        )

    def list_records(self) -> list[DocumentRecord]:
        records = []
        for path in sorted(self.root.glob("*.json"), reverse=True):
            try:
                records.append(self.load(path.stem))
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
            AuditEvent(
                actor=actor or "System",
                action=action,
                detail=sanitize_provider_payload(detail),
            )
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
        message = sanitize_provider_payload(message)
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

    def cleanup_expired_local_data(
        self,
        retention_days: int,
        protected_document_ids: set[str] | None = None,
    ) -> RetentionCleanupResult:
        protected_document_ids = protected_document_ids or set()
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        metadata_records = 0
        invalid_metadata_files = 0
        reports = 0
        uploads = 0
        protected_ids = set(protected_document_ids)

        records_by_id: dict[str, DocumentRecord] = {}
        for path in sorted(self.root.glob("*.json")):
            try:
                record = self.load(path.stem)
            except Exception as exc:
                if self._path_is_older_than(path, cutoff):
                    logger.warning(
                        "Deleting invalid metadata file %s after retention expiry: %s",
                        path,
                        exc,
                    )
                    invalid_metadata_files += self._remove_path(path)
                else:
                    logger.warning("Skipping invalid metadata file %s: %s", path, exc)
                continue

            records_by_id[record.document_id] = record
            if record.status in ACTIVE_PROCESSING_STATUSES:
                protected_ids.add(record.document_id)
                continue
            if record.document_id in protected_ids:
                continue
            if not self._record_is_older_than(record, cutoff):
                continue

            reports += self._delete_report(record)
            uploads += self._delete_uploads(record)
            metadata_records += self._remove_path(path)

        reports += self._delete_orphan_paths(
            self.reports_root,
            "*.md",
            cutoff,
            protected_ids,
            records_by_id,
            kind="report",
        )
        uploads += self._delete_orphan_paths(
            self.uploads_root,
            "*",
            cutoff,
            protected_ids,
            records_by_id,
            kind="upload",
        )

        result = RetentionCleanupResult(
            metadata_records=metadata_records,
            invalid_metadata_files=invalid_metadata_files,
            reports=reports,
            uploads=uploads,
        )
        if result.total:
            logger.info(
                "Retention cleanup deleted %s local item(s): %s metadata record(s), "
                "%s invalid metadata file(s), %s report(s), %s upload(s).",
                result.total,
                result.metadata_records,
                result.invalid_metadata_files,
                result.reports,
                result.uploads,
            )
        return result

    @staticmethod
    def _as_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _record_is_older_than(self, record: DocumentRecord, cutoff: datetime) -> bool:
        retention_anchor = record.processed_at or record.uploaded_at
        return self._as_aware(retention_anchor) < cutoff

    @staticmethod
    def _path_is_older_than(path: Path, cutoff: datetime) -> bool:
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return mtime < cutoff

    @staticmethod
    def _remove_path(path: Path) -> int:
        if not path.exists():
            return 0
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return 1

    def _delete_report(self, record: DocumentRecord) -> int:
        candidates = [self.reports_root / f"{record.document_id}.md"]
        if record.report_path:
            report_path = Path(record.report_path)
            candidates.append(report_path if report_path.is_absolute() else report_path)
        return self._remove_unique_paths(candidates)

    def _delete_uploads(self, record: DocumentRecord) -> int:
        safe_name = safe_document_name(record.document_name)
        candidates = [
            self.uploads_root / f"{record.document_id}-{safe_name}",
            self.uploads_root / f"retry-{record.document_id}-{safe_name}",
        ]
        candidates.extend(self.uploads_root.glob(f"{record.document_id}-*"))
        candidates.extend(self.uploads_root.glob(f"retry-{record.document_id}-*"))
        return self._remove_unique_paths(candidates)

    def _remove_unique_paths(self, paths: list[Path]) -> int:
        removed = 0
        seen: set[Path] = set()
        for path in paths:
            normalized = path.resolve() if path.exists() else path
            if normalized in seen:
                continue
            seen.add(normalized)
            removed += self._remove_path(path)
        return removed

    def _delete_orphan_paths(
        self,
        root: Path,
        pattern: str,
        cutoff: datetime,
        protected_ids: set[str],
        records_by_id: dict[str, DocumentRecord],
        kind: str,
    ) -> int:
        if not root.exists():
            return 0
        removed = 0
        for path in root.glob(pattern):
            if not self._path_is_older_than(path, cutoff):
                continue
            if self._artifact_belongs_to_record(path, kind, protected_ids):
                continue
            if self._artifact_belongs_to_record(
                path, kind, set(records_by_id.keys())
            ):
                continue
            removed += self._remove_path(path)
        return removed

    @staticmethod
    def _artifact_belongs_to_record(
        path: Path,
        kind: str,
        document_ids: set[str],
    ) -> bool:
        if kind == "report":
            return path.stem in document_ids
        return any(
            path.name.startswith(f"{document_id}-")
            or path.name.startswith(f"retry-{document_id}-")
            for document_id in document_ids
        )
