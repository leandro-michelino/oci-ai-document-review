import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from src.compliance import (
    ComplianceCatalog,
    load_compliance_catalog,
    load_local_compliance_catalog,
    term_matches,
)
from src.config import AppConfig
from src.document_understanding_client import DocumentUnderstandingClient
from src.genai_client import GenAIClient
from src.logger import get_logger
from src.metadata_store import MetadataStore
from src.models import (
    DocumentAnalysis,
    DocumentRecord,
    DocumentType,
    ExtractionResult,
    ProcessingStatus,
    RiskNote,
)
from src.object_storage_client import ObjectStorageClient
from src.prompts import build_prompt
from src.report_generator import generate_markdown_report
from src.safety_messages import (
    GENAI_SAFETY_REVIEW_MESSAGE,
    GENAI_SAFETY_REVIEW_RISK,
    is_genai_content_filter_text,
    sanitize_provider_message,
)
from src.text_extraction import (
    DOCUMENT_UNDERSTANDING_SYNC_FILE_SIZE_LIMIT_BYTES,
    DOCUMENT_UNDERSTANDING_SYNC_PAGE_LIMIT,
    PdfPageChunk,
    extract_text_locally,
    pdf_page_count,
    write_pdf_page_chunks,
)

logger = get_logger(__name__)

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
EXPENSE_DOCUMENT_TERMS = (
    "invoice",
    "receipt",
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


def chunk_document_name(storage_name: str, index: int) -> str:
    path = Path(storage_name)
    suffix = path.suffix or ".pdf"
    stem = path.stem if path.suffix else path.name
    stem = stem.strip("._") or "document"
    return f"{stem}_{index}{suffix}"


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
    if is_genai_content_filter_error(root):
        return GENAI_SAFETY_REVIEW_MESSAGE
    message = str(root).strip()
    return sanitize_provider_message(message) or message or root.__class__.__name__


def is_genai_content_filter_error(exc: Exception) -> bool:
    code = str(getattr(exc, "code", "") or "")
    message = str(getattr(exc, "message", "") or exc)
    return is_genai_content_filter_text(f"{code} {message}")


def fallback_safety_analysis(extraction: ExtractionResult) -> DocumentAnalysis:
    preview = re.sub(r"\s+", " ", extraction.text).strip()[:240]
    summary = (
        "Automatic AI analysis was blocked by the OCI Generative AI content safety "
        "filter. Manual review is required."
    )
    if preview:
        summary = f"{summary} Extracted text preview: {preview}"
    return DocumentAnalysis(
        document_class="GENERAL",
        executive_summary=summary,
        risk_notes=[
            RiskNote(
                risk=GENAI_SAFETY_REVIEW_RISK,
                severity="HIGH",
                evidence=GENAI_SAFETY_REVIEW_MESSAGE,
            )
        ],
        recommendations=[
            "Review the extracted text manually and retry processing only if the "
            "source document is appropriate for automated AI analysis."
        ],
        confidence_score=0.0,
        human_review_required=True,
    )


def merge_extraction_results(
    chunk_results: list[tuple[PdfPageChunk, ExtractionResult]],
) -> ExtractionResult:
    text_parts = []
    tables = []
    key_values = {}
    for chunk, extraction in chunk_results:
        chunk_label = f"pages {chunk.start_page}-{chunk.end_page}"
        if extraction.text.strip():
            text_parts.append(f"[OCR {chunk_label}]\n{extraction.text.strip()}")
        tables.extend(extraction.tables)
        for key, value in extraction.key_values.items():
            if key not in key_values:
                key_values[key] = value
            elif key_values[key] != value:
                key_values[f"{chunk_label} - {key}"] = value
    page_total = chunk_results[-1][0].end_page if chunk_results else 0
    return ExtractionResult(
        text="\n\n".join(text_parts),
        tables=tables,
        key_values=key_values,
        source=(
            "OCI Document Understanding chunked OCR "
            f"({len(chunk_results)} chunks, {page_total} pages)"
        ),
    )


def matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if term_matches(text, term)]


def compliance_context(record: DocumentRecord, extracted_text: str) -> str:
    analysis = record.analysis
    parts = [
        extracted_text,
        record.document_name,
        record.job_description or "",
        record.business_reference or "",
        record.notes or "",
    ]
    if analysis:
        parts.extend(
            [
                analysis.document_class,
                analysis.executive_summary,
                " ".join(analysis.key_points),
                " ".join(analysis.recommendations),
            ]
        )
    return "\n".join(part for part in parts if part)


def apply_compliance_attention(
    record: DocumentRecord,
    extracted_text: str,
    catalog: ComplianceCatalog | None = None,
) -> DocumentRecord:
    if record.analysis is None:
        return record
    catalog = catalog or load_local_compliance_catalog()
    context = compliance_context(record, extracted_text)
    public_matches = catalog.find_public_sector_matches(context)
    if not public_matches:
        return record

    detected_type = detected_document_type(record.analysis.document_class)
    expense_matches = matched_terms(context, EXPENSE_TERMS)
    expense_document_matches = matched_terms(context, EXPENSE_DOCUMENT_TERMS)
    is_expense = (
        record.document_type == DocumentType.INVOICE
        or detected_type == DocumentType.INVOICE
        or bool(expense_document_matches)
    )
    if not is_expense:
        return record

    if not any(
        note.risk == PUBLIC_SECTOR_EXPENSE_RISK for note in record.analysis.risk_notes
    ):
        highest_severity = max(
            (match.entity.risk_level for match in public_matches),
            key=lambda severity: {"LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(severity, 0),
        )
        evidence_parts = [
            f"knowledge-base: {catalog.source_name}",
            "public-sector match: "
            + " | ".join(match.evidence for match in public_matches[:3]),
        ]
        if expense_matches:
            evidence_parts.append(f"expense cue: {', '.join(expense_matches[:3])}")
        record.analysis.risk_notes.append(
            RiskNote(
                risk=PUBLIC_SECTOR_EXPENSE_RISK,
                severity=highest_severity,
                evidence=(
                    "Curated compliance knowledge base matched a public-sector entity "
                    "or cue in an expense context. " + "; ".join(evidence_parts) + "."
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
        self.compliance_catalog = load_compliance_catalog(
            config, object_storage=self.object_storage
        )
        self._document_ai = None
        self.genai = GenAIClient(config)

    @property
    def document_ai(self) -> DocumentUnderstandingClient:
        if self._document_ai is None:
            self._document_ai = DocumentUnderstandingClient(self.config)
        return self._document_ai

    def extract_with_document_understanding(
        self,
        local_path: Path,
        document_name: str,
        document_id: str,
        object_name: str,
        storage_name: str,
        progress,
    ) -> ExtractionResult:
        page_count = pdf_page_count(local_path, document_name)
        if page_count and (
            page_count > DOCUMENT_UNDERSTANDING_SYNC_PAGE_LIMIT
            or local_path.stat().st_size
            > DOCUMENT_UNDERSTANDING_SYNC_FILE_SIZE_LIMIT_BYTES
        ):
            return self._extract_pdf_chunks(
                local_path=local_path,
                document_id=document_id,
                storage_name=storage_name,
                page_count=page_count,
                progress=progress,
            )
        progress(
            "Starting OCI Document Understanding extraction "
            f"(timeout {self.config.document_ai_timeout_seconds}s, "
            f"attempts {self.config.document_ai_retry_attempts})"
        )
        return self.document_ai.extract_document(object_name)

    def _extract_pdf_chunks(
        self,
        local_path: Path,
        document_id: str,
        storage_name: str,
        page_count: int,
        progress,
    ) -> ExtractionResult:
        with TemporaryDirectory(prefix=f"ocr-{document_id}-") as tmp_dir:
            chunks = write_pdf_page_chunks(
                local_path,
                Path(tmp_dir),
                pages_per_chunk=DOCUMENT_UNDERSTANDING_SYNC_PAGE_LIMIT,
                max_chunk_bytes=DOCUMENT_UNDERSTANDING_SYNC_FILE_SIZE_LIMIT_BYTES,
            )
            progress(
                "Split scanned PDF for OCI Document Understanding "
                f"({page_count} pages across {len(chunks)} OCR chunks)"
            )
            chunk_results = []
            for index, chunk in enumerate(chunks, start=1):
                chunk_object_name = (
                    f"documents/{document_id}/ocr-chunks/"
                    f"{chunk_document_name(storage_name, index)}"
                )
                self.object_storage.upload_file(chunk.path, chunk_object_name)
                try:
                    progress(
                        "Running OCI Document Understanding OCR "
                        f"chunk {index}/{len(chunks)} "
                        f"(pages {chunk.start_page}-{chunk.end_page})"
                    )
                    chunk_results.append(
                        (chunk, self.document_ai.extract_document(chunk_object_name))
                    )
                finally:
                    try:
                        self.object_storage.delete_object(chunk_object_name)
                    except Exception:
                        logger.warning(
                            "Failed to delete temporary OCR chunk object %s",
                            chunk_object_name,
                            exc_info=True,
                        )
            return merge_extraction_results(chunk_results)

    def process(
        self,
        source_path: Path,
        document_name: str,
        document_type: DocumentType,
        business_reference: str | None = None,
        notes: str | None = None,
        job_description: str | None = None,
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
            record.job_description = job_description
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
                job_description=job_description,
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
                extraction = self.extract_with_document_understanding(
                    local_path=local_path,
                    document_name=document_name,
                    document_id=document_id,
                    object_name=object_name,
                    storage_name=storage_name,
                    progress=progress,
                )
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
            try:
                analysis = self.genai.analyze_document(prompt)
            except Exception as exc:
                if not is_genai_content_filter_error(root_exception(exc)):
                    raise
                logger.warning(
                    "OCI Generative AI content safety filter blocked %s; "
                    "routing to manual review",
                    document_id,
                )
                analysis = fallback_safety_analysis(extraction)
            if record.document_type == DocumentType.AUTO_DETECT:
                record.document_type = detected_document_type(analysis.document_class)
            record.analysis = analysis
            apply_compliance_attention(
                record, extraction.text, catalog=self.compliance_catalog
            )
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
