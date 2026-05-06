from src.models import DocumentAnalysis, DocumentRecord, DocumentType, ProcessingStatus
from src.report_generator import generate_markdown_report


def test_generate_markdown_report_contains_summary_and_model():
    record = DocumentRecord(
        document_id="doc-1",
        document_name="contract.pdf",
        document_type=DocumentType.CONTRACT,
        status=ProcessingStatus.REVIEW_REQUIRED,
        analysis=DocumentAnalysis(
            document_class="CONTRACT",
            executive_summary="A short summary.",
            key_points=["Point one"],
            recommendations=["Review terms"],
            confidence_score=0.8,
            human_review_required=True,
        ),
    )

    report = generate_markdown_report(record, model_id="cohere.command-r-plus-08-2024")

    assert "# Document Intelligence Report" in report
    assert "A short summary." in report
    assert "cohere.command-r-plus-08-2024" in report
