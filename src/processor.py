import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.config import AppConfig
from src.document_understanding_client import DocumentUnderstandingClient
from src.genai_client import GenAIClient
from src.logger import get_logger
from src.metadata_store import MetadataStore
from src.models import DocumentRecord, DocumentType, ProcessingStatus
from src.object_storage_client import ObjectStorageClient
from src.prompts import build_prompt
from src.report_generator import generate_markdown_report


logger = get_logger(__name__)


def create_document_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{uuid4().hex[:8]}"


def safe_document_name(document_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(document_name).name).strip("._")
    return cleaned or "document"


def root_exception(exc: Exception) -> Exception:
    last_attempt = getattr(exc, "last_attempt", None)
    if last_attempt:
        try:
            root = last_attempt.exception()
            if root:
                return root_exception(root)
        except Exception:
            return exc
    cause = getattr(exc, "__cause__", None)
    if cause:
        return root_exception(cause)
    return exc


def error_message(exc: Exception) -> str:
    root = root_exception(exc)
    message = str(root).strip()
    return message or root.__class__.__name__


class DocumentProcessor:
    def __init__(self, config: AppConfig):
        self.config = config
        self.store = MetadataStore(config)
        self.object_storage = ObjectStorageClient(config)
        self.document_ai = DocumentUnderstandingClient(config)
        self.genai = GenAIClient(config)

    def process(
        self,
        source_path: Path,
        document_name: str,
        document_type: DocumentType,
        business_reference: str | None = None,
        notes: str | None = None,
    ) -> DocumentRecord:
        document_id = create_document_id()
        storage_name = safe_document_name(document_name)
        local_path = self.config.local_uploads_dir / f"{document_id}-{storage_name}"
        shutil.copyfile(source_path, local_path)

        record = DocumentRecord(
            document_id=document_id,
            document_name=document_name,
            document_type=document_type,
            business_reference=business_reference,
            notes=notes,
        )
        self.store.save(record)

        try:
            object_name = f"documents/{document_id}/{storage_name}"
            self.object_storage.upload_file(local_path, object_name)
            record.object_storage_path = self.object_storage.object_uri(object_name)
            record.status = ProcessingStatus.PROCESSING
            self.store.save(record)

            extraction = self.document_ai.extract_document(object_name)
            record.status = ProcessingStatus.EXTRACTED
            record.extracted_text_preview = extraction.text[:2000]
            self.store.save(record)

            prompt = build_prompt(
                document_type=document_type,
                extracted_text=extraction.text,
                max_chars=self.config.max_document_chars,
            )
            analysis = self.genai.analyze_document(prompt)
            record.status = ProcessingStatus.AI_ANALYZED
            record.analysis = analysis
            self.store.save(record)

            record.status = ProcessingStatus.REVIEW_REQUIRED
            record.processed_at = datetime.now(timezone.utc)
            report = generate_markdown_report(record, self.config.genai_model_id)
            report_path = self.config.local_reports_dir / f"{document_id}.md"
            report_path.write_text(report, encoding="utf-8")
            record.report_path = str(report_path)
            self.store.save(record)
            return record
        except Exception as exc:
            logger.exception("Document processing failed for %s", document_id)
            record.status = ProcessingStatus.FAILED
            record.error_message = error_message(exc)
            record.processed_at = datetime.now(timezone.utc)
            self.store.save(record)
            raise
