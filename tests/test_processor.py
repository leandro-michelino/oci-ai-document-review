from types import SimpleNamespace

from src.models import (
    DocumentAnalysis,
    DocumentType,
    ExtractionResult,
    ProcessingStatus,
)
from src.processor import (
    DocumentProcessor,
    detected_document_type,
    error_message,
    safe_document_name,
)


def test_safe_document_name_removes_path_parts_and_unsafe_chars():
    assert safe_document_name("../../contract final|v1.pdf") == "contract_final_v1.pdf"


def test_safe_document_name_has_fallback():
    assert safe_document_name("...") == "document"


def test_error_message_unwraps_retry_error_like_exception():
    class Attempt:
        @staticmethod
        def exception():
            return AttributeError("missing signer")

    class RetryLikeError(Exception):
        last_attempt = Attempt()

    assert error_message(RetryLikeError("wrapped")) == "missing signer"


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
        document_id="doc-fixed",
    )

    assert record.document_id == "doc-fixed"
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
    assert "public-sector cue: ministry" in record.analysis.risk_notes[-1].evidence


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
            "extracted_fields": {"parties": None},
            "confidence_score": 0.7,
        }
    )

    assert analysis.key_points == []
    assert analysis.risk_notes == []
    assert analysis.recommendations == []
    assert analysis.missing_information == []
    assert analysis.extracted_fields.parties == []
