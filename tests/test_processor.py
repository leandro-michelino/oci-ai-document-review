from types import SimpleNamespace

from src.models import DocumentAnalysis, DocumentType, ExtractionResult, ProcessingStatus
from src.processor import DocumentProcessor, error_message, safe_document_name


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
