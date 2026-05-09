from types import SimpleNamespace

from src.models import (
    DocumentAnalysis,
    DocumentRecord,
    DocumentType,
    ExtractionResult,
    ProcessingStatus,
    RiskNote,
)
from src.processor import (
    DocumentProcessor,
    GENAI_SAFETY_REVIEW_MESSAGE,
    GENAI_SAFETY_REVIEW_RISK,
    PUBLIC_SECTOR_EXPENSE_RISK,
    apply_compliance_attention,
    chunk_document_name,
    detected_document_type,
    error_message,
    fallback_safety_analysis,
    safe_document_name,
)


def test_safe_document_name_removes_path_parts_and_unsafe_chars():
    assert safe_document_name("../../contract final|v1.pdf") == "contract_final_v1.pdf"


def test_safe_document_name_has_fallback():
    assert safe_document_name("...") == "document"


def test_chunk_document_name_keeps_original_stem_and_sequence():
    assert (
        chunk_document_name("Receipt_21Apr2026_112647.pdf", 2)
        == "Receipt_21Apr2026_112647_2.pdf"
    )


def test_error_message_unwraps_retry_error_like_exception():
    class Attempt:
        @staticmethod
        def exception():
            return AttributeError("missing signer")

    class RetryLikeError(Exception):
        last_attempt = Attempt()

    assert error_message(RetryLikeError("wrapped")) == "missing signer"


def test_error_message_hides_oci_genai_content_filter_json():
    class ServiceError(Exception):
        code = "InvalidParameter"
        message = "Inappropriate content detected!!!"

        def __str__(self):
            return '{ "code" : "InvalidParameter", "message" : "Inappropriate content detected!!!" }'

    assert error_message(ServiceError()) == GENAI_SAFETY_REVIEW_MESSAGE


def test_fallback_safety_analysis_routes_to_manual_review():
    analysis = fallback_safety_analysis(ExtractionResult(text="Sensitive trip text"))

    assert analysis.human_review_required is True
    assert analysis.confidence_score == 0.0
    assert analysis.risk_notes[0].risk == GENAI_SAFETY_REVIEW_RISK
    assert analysis.risk_notes[0].severity == "HIGH"
    assert "Sensitive trip text" in analysis.executive_summary


def test_processor_preserves_supplied_document_id(tmp_path, monkeypatch):
    class FakeObjectStorage:
        def __init__(self, config):
            self.config = config

        def upload_file(self, local_path, object_name):
            assert local_path.exists()
            assert object_name == "documents/doc-fixed/contract.pdf"

        @staticmethod
        def object_uri(object_name):
            return f"oci://bucket/{object_name}"

    class FakeDocumentAI:
        def __init__(self, config):
            self.config = config

        @staticmethod
        def extract_document(object_name):
            assert object_name == "documents/doc-fixed/contract.pdf"
            return ExtractionResult(text="Contract text")

    class FakeGenAI:
        def __init__(self, config):
            self.config = config

        @staticmethod
        def analyze_document(prompt):
            assert "Contract text" in prompt
            return DocumentAnalysis(
                document_class="CONTRACT",
                executive_summary="Reviewed contract.",
                confidence_score=0.82,
            )

    monkeypatch.setattr("src.processor.ObjectStorageClient", FakeObjectStorage)
    monkeypatch.setattr("src.processor.DocumentUnderstandingClient", FakeDocumentAI)
    monkeypatch.setattr("src.processor.GenAIClient", FakeGenAI)

    config = SimpleNamespace(
        local_metadata_dir=tmp_path / "metadata",
        local_reports_dir=tmp_path / "reports",
        local_uploads_dir=tmp_path / "uploads",
        max_document_chars=50000,
        genai_model_id="cohere.command-r-plus",
        document_ai_timeout_seconds=30,
        document_ai_retry_attempts=1,
    )
    config.local_metadata_dir.mkdir()
    config.local_reports_dir.mkdir()
    config.local_uploads_dir.mkdir()
    source = tmp_path / "contract.pdf"
    source.write_text("source", encoding="utf-8")

    record = DocumentProcessor(config).process(
        source_path=source,
        document_name="contract.pdf",
        document_type=DocumentType.CONTRACT,
        job_description="Vendor contract batch",
        document_id="doc-fixed",
    )

    assert record.document_id == "doc-fixed"
    assert record.job_description == "Vendor contract batch"
    assert record.status == ProcessingStatus.REVIEW_REQUIRED
    assert (config.local_metadata_dir / "doc-fixed.json").exists()


def test_processor_auto_detect_relabels_from_genai_class(tmp_path, monkeypatch):
    class FakeObjectStorage:
        def __init__(self, config):
            self.config = config

        def upload_file(self, local_path, object_name):
            assert local_path.exists()

        @staticmethod
        def object_uri(object_name):
            return f"oci://bucket/{object_name}"

    class FakeDocumentAI:
        def __init__(self, config):
            self.config = config

        @staticmethod
        def extract_document(object_name):
            return ExtractionResult(text="Invoice number INV-001 total GBP 42")

    class FakeGenAI:
        def __init__(self, config):
            self.config = config

        @staticmethod
        def analyze_document(prompt):
            assert "Invoice number" in prompt
            return DocumentAnalysis(
                document_class="INVOICE",
                executive_summary="Reviewed invoice.",
                confidence_score=0.9,
            )

    monkeypatch.setattr("src.processor.ObjectStorageClient", FakeObjectStorage)
    monkeypatch.setattr("src.processor.DocumentUnderstandingClient", FakeDocumentAI)
    monkeypatch.setattr("src.processor.GenAIClient", FakeGenAI)

    config = SimpleNamespace(
        local_metadata_dir=tmp_path / "metadata",
        local_reports_dir=tmp_path / "reports",
        local_uploads_dir=tmp_path / "uploads",
        max_document_chars=50000,
        genai_model_id="cohere.command-r-plus",
        document_ai_timeout_seconds=30,
        document_ai_retry_attempts=1,
    )
    config.local_metadata_dir.mkdir()
    config.local_reports_dir.mkdir()
    config.local_uploads_dir.mkdir()
    source = tmp_path / "invoice.png"
    source.write_text("source", encoding="utf-8")

    record = DocumentProcessor(config).process(
        source_path=source,
        document_name="invoice.png",
        document_type=DocumentType.AUTO_DETECT,
        document_id="doc-auto",
    )

    assert record.document_type == DocumentType.INVOICE
    assert "- Document Type: INVOICE" in (
        config.local_reports_dir / "doc-auto.md"
    ).read_text(encoding="utf-8")


def test_processor_chunks_scanned_pdf_over_document_understanding_limit(
    tmp_path, monkeypatch
):
    from pypdf import PdfWriter

    uploaded_objects = []
    deleted_objects = []

    class FakeObjectStorage:
        def __init__(self, config):
            self.config = config

        def upload_file(self, local_path, object_name):
            assert local_path.exists()
            uploaded_objects.append(object_name)

        def delete_object(self, object_name):
            deleted_objects.append(object_name)

        @staticmethod
        def object_uri(object_name):
            return f"oci://bucket/{object_name}"

    class FakeDocumentAI:
        def __init__(self, config):
            self.config = config

        @staticmethod
        def extract_document(object_name):
            assert "ocr-chunks" in object_name
            chunk_index = int(
                object_name.rsplit("/", 1)[-1].rsplit(".", 1)[0].rsplit("_", 1)[1]
            )
            return ExtractionResult(
                text=f"Chunk {chunk_index} OCR text",
                tables=[{"chunk": chunk_index}],
                key_values={f"Field {chunk_index}": f"Value {chunk_index}"},
            )

    class FakeGenAI:
        def __init__(self, config):
            self.config = config

        @staticmethod
        def analyze_document(prompt):
            assert "Chunk 1 OCR text" in prompt
            assert "Chunk 2 OCR text" in prompt
            assert "Chunk 3 OCR text" in prompt
            assert "Tables detected by OCI Document Understanding: 3" in prompt
            return DocumentAnalysis(
                document_class="GENERAL",
                executive_summary="Reviewed long scan.",
                confidence_score=0.83,
            )

    monkeypatch.setattr("src.processor.ObjectStorageClient", FakeObjectStorage)
    monkeypatch.setattr("src.processor.DocumentUnderstandingClient", FakeDocumentAI)
    monkeypatch.setattr("src.processor.GenAIClient", FakeGenAI)

    config = SimpleNamespace(
        local_metadata_dir=tmp_path / "metadata",
        local_reports_dir=tmp_path / "reports",
        local_uploads_dir=tmp_path / "uploads",
        max_document_chars=50000,
        genai_model_id="cohere.command-r-plus",
        document_ai_timeout_seconds=30,
        document_ai_retry_attempts=1,
    )
    config.local_metadata_dir.mkdir()
    config.local_reports_dir.mkdir()
    config.local_uploads_dir.mkdir()
    source = tmp_path / "Receipt_21Apr2026_112647.pdf"
    writer = PdfWriter()
    for _ in range(12):
        writer.add_blank_page(width=72, height=72)
    with source.open("wb") as file:
        writer.write(file)

    record = DocumentProcessor(config).process(
        source_path=source,
        document_name="Receipt_21Apr2026_112647.pdf",
        document_type=DocumentType.GENERAL,
        document_id="doc-long-scan",
    )

    assert record.status == ProcessingStatus.REVIEW_REQUIRED
    assert record.extraction_source == (
        "OCI Document Understanding chunked OCR (3 chunks, 12 pages)"
    )
    assert uploaded_objects[0] == (
        "documents/doc-long-scan/Receipt_21Apr2026_112647.pdf"
    )
    assert uploaded_objects[1:] == [
        "documents/doc-long-scan/ocr-chunks/Receipt_21Apr2026_112647_1.pdf",
        "documents/doc-long-scan/ocr-chunks/Receipt_21Apr2026_112647_2.pdf",
        "documents/doc-long-scan/ocr-chunks/Receipt_21Apr2026_112647_3.pdf",
    ]
    assert deleted_objects == uploaded_objects[1:]


def test_processor_uses_single_document_understanding_call_at_page_limit(
    tmp_path, monkeypatch
):
    from pypdf import PdfWriter

    extracted_objects = []

    class FakeObjectStorage:
        def __init__(self, config):
            self.config = config

        def upload_file(self, local_path, object_name):
            assert local_path.exists()

        @staticmethod
        def object_uri(object_name):
            return f"oci://bucket/{object_name}"

    class FakeDocumentAI:
        def __init__(self, config):
            self.config = config

        @staticmethod
        def extract_document(object_name):
            extracted_objects.append(object_name)
            return ExtractionResult(text="Five-page OCR text")

    class FakeGenAI:
        def __init__(self, config):
            self.config = config

        @staticmethod
        def analyze_document(prompt):
            assert "Five-page OCR text" in prompt
            return DocumentAnalysis(
                document_class="GENERAL",
                executive_summary="Reviewed five-page scan.",
                confidence_score=0.82,
            )

    monkeypatch.setattr("src.processor.ObjectStorageClient", FakeObjectStorage)
    monkeypatch.setattr("src.processor.DocumentUnderstandingClient", FakeDocumentAI)
    monkeypatch.setattr("src.processor.GenAIClient", FakeGenAI)

    config = SimpleNamespace(
        local_metadata_dir=tmp_path / "metadata",
        local_reports_dir=tmp_path / "reports",
        local_uploads_dir=tmp_path / "uploads",
        max_document_chars=50000,
        genai_model_id="cohere.command-r-plus",
        document_ai_timeout_seconds=30,
        document_ai_retry_attempts=1,
    )
    config.local_metadata_dir.mkdir()
    config.local_reports_dir.mkdir()
    config.local_uploads_dir.mkdir()
    source = tmp_path / "scan.pdf"
    writer = PdfWriter()
    for _ in range(5):
        writer.add_blank_page(width=72, height=72)
    with source.open("wb") as file:
        writer.write(file)

    record = DocumentProcessor(config).process(
        source_path=source,
        document_name="scan.pdf",
        document_type=DocumentType.GENERAL,
        document_id="doc-five-page-scan",
    )

    assert record.status == ProcessingStatus.REVIEW_REQUIRED
    assert extracted_objects == ["documents/doc-five-page-scan/scan.pdf"]


def test_processor_skips_document_understanding_for_text_files(tmp_path, monkeypatch):
    class FakeObjectStorage:
        def __init__(self, config):
            self.config = config

        def upload_file(self, local_path, object_name):
            assert local_path.exists()

        @staticmethod
        def object_uri(object_name):
            return f"oci://bucket/{object_name}"

    class FakeDocumentAI:
        def __init__(self, config):
            raise AssertionError(
                "Document Understanding should not initialize for text files"
            )

    class FakeGenAI:
        def __init__(self, config):
            self.config = config

        @staticmethod
        def analyze_document(prompt):
            assert "Plain text invoice total EUR 18.78" in prompt
            return DocumentAnalysis(
                document_class="INVOICE",
                executive_summary="Reviewed text invoice.",
                confidence_score=0.88,
            )

    monkeypatch.setattr("src.processor.ObjectStorageClient", FakeObjectStorage)
    monkeypatch.setattr("src.processor.DocumentUnderstandingClient", FakeDocumentAI)
    monkeypatch.setattr("src.processor.GenAIClient", FakeGenAI)

    config = SimpleNamespace(
        local_metadata_dir=tmp_path / "metadata",
        local_reports_dir=tmp_path / "reports",
        local_uploads_dir=tmp_path / "uploads",
        max_document_chars=50000,
        genai_model_id="cohere.command-r-plus",
        document_ai_timeout_seconds=30,
        document_ai_retry_attempts=1,
    )
    config.local_metadata_dir.mkdir()
    config.local_reports_dir.mkdir()
    config.local_uploads_dir.mkdir()
    source = tmp_path / "invoice.txt"
    source.write_text("Plain text invoice total EUR 18.78", encoding="utf-8")

    record = DocumentProcessor(config).process(
        source_path=source,
        document_name="invoice.txt",
        document_type=DocumentType.AUTO_DETECT,
        document_id="doc-text",
    )

    assert record.status == ProcessingStatus.REVIEW_REQUIRED
    assert record.document_type == DocumentType.INVOICE
    assert record.extraction_source == "Local text file"


def test_processor_flags_public_sector_expense_for_compliance(tmp_path, monkeypatch):
    class FakeObjectStorage:
        def __init__(self, config):
            self.config = config

        def upload_file(self, local_path, object_name):
            assert local_path.exists()

        @staticmethod
        def object_uri(object_name):
            return f"oci://bucket/{object_name}"

    class FakeDocumentAI:
        def __init__(self, config):
            raise AssertionError(
                "Document Understanding should not initialize for text files"
            )

    class FakeGenAI:
        def __init__(self, config):
            self.config = config

        @staticmethod
        def analyze_document(prompt):
            assert "Ministry of Finance" in prompt
            return DocumentAnalysis(
                document_class="INVOICE",
                executive_summary="Dinner receipt.",
                confidence_score=0.86,
                human_review_required=False,
            )

    monkeypatch.setattr("src.processor.ObjectStorageClient", FakeObjectStorage)
    monkeypatch.setattr("src.processor.DocumentUnderstandingClient", FakeDocumentAI)
    monkeypatch.setattr("src.processor.GenAIClient", FakeGenAI)

    config = SimpleNamespace(
        local_metadata_dir=tmp_path / "metadata",
        local_reports_dir=tmp_path / "reports",
        local_uploads_dir=tmp_path / "uploads",
        max_document_chars=50000,
        genai_model_id="cohere.command-r-plus",
        document_ai_timeout_seconds=30,
        document_ai_retry_attempts=1,
    )
    config.local_metadata_dir.mkdir()
    config.local_reports_dir.mkdir()
    config.local_uploads_dir.mkdir()
    source = tmp_path / "dinner-receipt.txt"
    source.write_text(
        "Receipt for dinner with Ministry of Finance officials. Total USD 120.",
        encoding="utf-8",
    )

    record = DocumentProcessor(config).process(
        source_path=source,
        document_name="dinner-receipt.txt",
        document_type=DocumentType.AUTO_DETECT,
        document_id="doc-public-sector-expense",
    )

    assert record.analysis.human_review_required is True
    assert record.analysis.risk_notes[-1].risk == (
        "Public-sector expense compliance review"
    )
    assert record.analysis.risk_notes[-1].severity == "HIGH"
    assert "knowledge-base" in record.analysis.risk_notes[-1].evidence
    assert "matched term: ministry" in record.analysis.risk_notes[-1].evidence


def test_processor_flags_public_sector_expense_from_business_reference(
    tmp_path, monkeypatch
):
    class FakeObjectStorage:
        def __init__(self, config):
            self.config = config

        def upload_file(self, local_path, object_name):
            assert local_path.exists()

        @staticmethod
        def object_uri(object_name):
            return f"oci://bucket/{object_name}"

    class FakeDocumentAI:
        def __init__(self, config):
            raise AssertionError(
                "Document Understanding should not initialize for text files"
            )

    class FakeGenAI:
        def __init__(self, config):
            self.config = config

        @staticmethod
        def analyze_document(prompt):
            assert "Restaurant receipt total GBP 42" in prompt
            return DocumentAnalysis(
                document_class="INVOICE",
                executive_summary="Lunch receipt.",
                confidence_score=0.9,
                human_review_required=False,
            )

    monkeypatch.setattr("src.processor.ObjectStorageClient", FakeObjectStorage)
    monkeypatch.setattr("src.processor.DocumentUnderstandingClient", FakeDocumentAI)
    monkeypatch.setattr("src.processor.GenAIClient", FakeGenAI)

    config = SimpleNamespace(
        local_metadata_dir=tmp_path / "metadata",
        local_reports_dir=tmp_path / "reports",
        local_uploads_dir=tmp_path / "uploads",
        max_document_chars=50000,
        genai_model_id="cohere.command-r-plus",
        document_ai_timeout_seconds=30,
        document_ai_retry_attempts=1,
    )
    config.local_metadata_dir.mkdir()
    config.local_reports_dir.mkdir()
    config.local_uploads_dir.mkdir()
    source = tmp_path / "receipt.txt"
    source.write_text("Restaurant receipt total GBP 42", encoding="utf-8")

    record = DocumentProcessor(config).process(
        source_path=source,
        document_name="receipt.txt",
        document_type=DocumentType.INVOICE,
        business_reference="lunch with gov customer",
        document_id="doc-gov-reference",
    )

    assert record.analysis.human_review_required is True
    assert record.analysis.risk_notes[-1].severity == "MEDIUM"
    assert "knowledge-base" in record.analysis.risk_notes[-1].evidence
    assert "matched term: gov" in record.analysis.risk_notes[-1].evidence
    assert "receipt" in record.analysis.risk_notes[-1].evidence


def test_compliance_attention_ignores_generic_travel_guidance():
    record = DocumentRecord(
        document_id="doc-guidance",
        document_name="travel-guidance.txt",
        document_type=DocumentType.COMPLIANCE,
        analysis=DocumentAnalysis(
            document_class="COMPLIANCE",
            executive_summary=(
                "The document mentions government websites and regulations that may "
                "require review for public-sector travel guidelines."
            ),
            confidence_score=0.82,
            risk_notes=[
                RiskNote(
                    risk="Compliance Attention",
                    severity="MEDIUM",
                    evidence=(
                        "The document mentions government websites and regulations, "
                        "which may require review."
                    ),
                )
            ],
        ),
    )

    apply_compliance_attention(
        record,
        (
            "Government travel policy and department of finance reimbursement "
            "guidelines for employees."
        ),
    )

    assert all(
        note.risk != PUBLIC_SECTOR_EXPENSE_RISK for note in record.analysis.risk_notes
    )


def test_compliance_attention_ignores_vat_without_public_sector_match():
    record = DocumentRecord(
        document_id="doc-vat",
        document_name="expense-receipt.pdf",
        document_type=DocumentType.INVOICE,
        analysis=DocumentAnalysis(
            document_class="INVOICE",
            executive_summary="Receipt with VAT 21% for Spain.",
            confidence_score=0.9,
        ),
    )

    apply_compliance_attention(
        record,
        "Restaurant receipt total EUR 42. VAT 21% ES Spain.",
    )

    assert all(
        note.risk != PUBLIC_SECTOR_EXPENSE_RISK for note in record.analysis.risk_notes
    )


def test_detected_document_type_handles_unknown_and_aliases():
    assert detected_document_type("technical report") == DocumentType.TECHNICAL_REPORT
    assert detected_document_type("receipt") == DocumentType.INVOICE
    assert detected_document_type("something else") == DocumentType.GENERAL


def test_document_analysis_accepts_null_ai_lists():
    analysis = DocumentAnalysis.model_validate(
        {
            "document_class": "INVOICE",
            "executive_summary": "Summary",
            "key_points": None,
            "risk_notes": None,
            "recommendations": None,
            "missing_information": None,
            "extracted_fields": {"parties": None, "line_items": None},
            "confidence_score": 0.7,
        }
    )

    assert analysis.key_points == []
    assert analysis.risk_notes == []
    assert analysis.recommendations == []
    assert analysis.missing_information == []
    assert analysis.extracted_fields.parties == []
    assert analysis.extracted_fields.line_items == []


def test_document_analysis_wraps_scalar_ai_list_fields():
    analysis = DocumentAnalysis.model_validate(
        {
            "document_class": "INVOICE",
            "executive_summary": "Summary",
            "key_points": "One important point",
            "extracted_fields": {
                "line_items": "Pasta, water, coffee - EUR 42",
            },
            "risk_notes": {
                "risk": "Unusual transaction",
                "severity": "MEDIUM",
                "evidence": "Single risk object returned by model",
            },
            "recommendations": "Review the transaction.",
            "missing_information": "Approver name",
            "confidence_score": 0.7,
        }
    )

    assert analysis.key_points == ["One important point"]
    assert analysis.extracted_fields.line_items == ["Pasta, water, coffee - EUR 42"]
    assert analysis.risk_notes[0].risk == "Unusual transaction"
    assert analysis.recommendations == ["Review the transaction."]
    assert analysis.missing_information == ["Approver name"]


def test_document_analysis_removes_vat_public_sector_false_positive():
    analysis = DocumentAnalysis.model_validate(
        {
            "document_class": "INVOICE",
            "executive_summary": "Receipt.",
            "risk_notes": [
                {
                    "risk": "Public Sector Reference",
                    "severity": "LOW",
                    "evidence": (
                        "The document mentions VAT and a VAT number, which could "
                        "indicate a public-sector or government-related expense."
                    ),
                },
                {
                    "risk": "Public-sector expense compliance review",
                    "severity": "MEDIUM",
                    "evidence": "Gift hospitality keyword. Expense cues found.",
                },
            ],
            "confidence_score": 0.85,
        }
    )

    assert [note.risk for note in analysis.risk_notes] == [
        "Public-sector expense compliance review"
    ]
