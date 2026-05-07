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
from src.models import (
    DocumentRecord,
    DocumentType,
    ExtractionResult,
    ProcessingStatus,
    RiskNote,
)
from src.object_storage_client import ObjectStorageClient
from src.prompts import build_prompt
from src.report_generator import generate_markdown_report
from src.text_extraction import extract_text_locally

logger = get_logger(__name__)

PUBLIC_SECTOR_TERMS = (
    "public sector",
    "government",
    "ministry",
    "municipality",
    "municipal",
    "state-owned",
    "state owned",
    "public authority",
    "public official",
    "civil servant",
    "department of",
    "embassy",
    "police",
    "military",
    "army",
    "council",
)
EXPENSE_TERMS = (
    "invoice",
    "receipt",
    "expense",
    "reimbursement",
    "payment due",
    "total",
    "vat",
    "tax",
    "gratuity",
    "meal",
    "lunch",
    "dinner",
    "restaurant",
    "hotel",
    "travel",
    "beverage",
    "food",
)
PUBLIC_SECTOR_EXPENSE_RISK = "Public-sector expense compliance review"


def create_document_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{uuid4().hex[:8]}"


def safe_document_name(document_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(document_name).name).strip("._")
    return cleaned or "document"


def detected_document_type(document_class: str | None) -> DocumentType:
    if not document_class:
        return DocumentType.GENERAL
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", document_class.upper()).strip("_")
    aliases = {
        "TECHNICAL": DocumentType.TECHNICAL_REPORT,
        "TECHNICAL_REPORT": DocumentType.TECHNICAL_REPORT,
        "REPORT": DocumentType.TECHNICAL_REPORT,
        "RECEIPT": DocumentType.INVOICE,
        "PURCHASE_ORDER": DocumentType.INVOICE,
        "PO": DocumentType.INVOICE,
        "UNKNOWN": DocumentType.GENERAL,
    }
    if normalized in aliases:
        return aliases[normalized]
    try:
        detected = DocumentType(normalized)
    except ValueError:
        return DocumentType.GENERAL
    if detected == DocumentType.AUTO_DETECT:
        return DocumentType.GENERAL
    return detected


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


def matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    normalized = text.lower()
    return [term for term in terms if term in normalized]


def apply_compliance_attention(
    record: DocumentRecord, extracted_text: str
) -> DocumentRecord:
    if record.analysis is None:
        return record
    public_matches = matched_terms(extracted_text, PUBLIC_SECTOR_TERMS)
    if not public_matches:
        return record

    detected_type = detected_document_type(record.analysis.document_class)
    expense_matches = matched_terms(extracted_text, EXPENSE_TERMS)
    is_expense = (
        record.document_type == DocumentType.INVOICE
        or detected_type == DocumentType.INVOICE
        or bool(expense_matches)
    )
    if not is_expense:
        return record

    if not any(
        note.risk == PUBLIC_SECTOR_EXPENSE_RISK for note in record.analysis.risk_notes
    ):
        evidence_parts = [f"public-sector cue: {', '.join(public_matches[:3])}"]
        if expense_matches:
            evidence_parts.append(f"expense cue: {', '.join(expense_matches[:3])}")
        record.analysis.risk_notes.append(
            RiskNote(
                risk=PUBLIC_SECTOR_EXPENSE_RISK,
                severity="HIGH",
                evidence=(
                    "Potential public-sector related expense. "
                    + "; ".join(evidence_parts)
                    + "."
                ),
            )
        )
    recommendation = (
        "Route to compliance review before approval because the expense appears "
        "connected to a public-sector entity or official."
    )
    if recommendation not in record.analysis.recommendations:
        record.analysis.recommendations.append(recommendation)
    record.analysis.human_review_required = True
    return record


class DocumentProcessor:
    def __init__(self, config: AppConfig):
        self.config = config
        self.store = MetadataStore(config)
        self.object_storage = ObjectStorageClient(config)
        self._document_ai = None
        self.genai = GenAIClient(config)

    @property
    def document_ai(self) -> DocumentUnderstandingClient:
        if self._document_ai is None:
            self._document_ai = DocumentUnderstandingClient(self.config)
        return self._document_ai

    def process(
        self,
        source_path: Path,
        document_name: str,
        document_type: DocumentType,
        business_reference: str | None = None,
        notes: str | None = None,
        source_file_size_bytes: int | None = None,
        source_file_mime_type: str | None = None,
        document_id: str | None = None,
        progress_callback=None,
    ) -> DocumentRecord:
        def progress(message: str) -> None:
            if progress_callback:
                progress_callback(message)

        document_id = document_id or create_document_id()
        storage_name = safe_document_name(document_name)
        local_path = self.config.local_uploads_dir / f"{document_id}-{storage_name}"
        if source_path.resolve() != local_path.resolve():
            shutil.copyfile(source_path, local_path)
        progress("Stored local working copy")

        if self.store.path_for(document_id).exists():
            record = self.store.load(document_id)
            record.document_name = document_name
            record.document_type = document_type
            record.source_file_size_bytes = source_file_size_bytes
            record.source_file_mime_type = source_file_mime_type
            record.business_reference = business_reference
            record.notes = notes
            record.error_message = None
        else:
            record = DocumentRecord(
                document_id=document_id,
                document_name=document_name,
                document_type=document_type,
                source_file_size_bytes=source_file_size_bytes,
                source_file_mime_type=source_file_mime_type,
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
            progress("Uploaded original file to OCI Object Storage")

            local_extraction = extract_text_locally(local_path, document_name)
            if local_extraction:
                extraction = ExtractionResult(text=local_extraction.text)
                record.extraction_source = local_extraction.source
                progress(f"Extracted text locally from {local_extraction.source}")
            else:
                progress(
                    "Starting OCI Document Understanding extraction "
                    f"(timeout {self.config.document_ai_timeout_seconds}s, "
                    f"attempts {self.config.document_ai_retry_attempts})"
                )
                extraction = self.document_ai.extract_document(object_name)
                record.extraction_source = (
                    extraction.source or "OCI Document Understanding"
                )
            if not extraction.text.strip():
                raise ValueError(
                    "No extractable text was found. Try a text-based file or a clearer PDF/image."
                )
            record.status = ProcessingStatus.EXTRACTED
            record.extracted_text_preview = extraction.text[:2000]
            self.store.save(record)
            progress("Prepared extracted text for OCI Generative AI")

            prompt = build_prompt(
                document_type=document_type,
                extracted_text=extraction.text,
                max_chars=self.config.max_document_chars,
                key_values=extraction.key_values,
                table_count=len(extraction.tables),
            )
            analysis = self.genai.analyze_document(prompt)
            if record.document_type == DocumentType.AUTO_DETECT:
                record.document_type = detected_document_type(analysis.document_class)
            record.analysis = analysis
            apply_compliance_attention(record, extraction.text)
            record.status = ProcessingStatus.AI_ANALYZED
            self.store.save(record)
            progress("Generated structured analysis with OCI Generative AI")

            record.status = ProcessingStatus.REVIEW_REQUIRED
            record.processed_at = datetime.now(timezone.utc)
            report = generate_markdown_report(record, self.config.genai_model_id)
            report_path = self.config.local_reports_dir / f"{document_id}.md"
            report_path.write_text(report, encoding="utf-8")
            record.report_path = str(report_path)
            self.store.save(record)
            progress("Saved review metadata and Markdown report")
            return record
        except Exception as exc:
            logger.exception("Document processing failed for %s", document_id)
            self.store.mark_failed(document_id, error_message(exc), actor="Worker")
            raise
