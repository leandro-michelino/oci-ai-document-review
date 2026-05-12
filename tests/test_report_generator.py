# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from src.models import (
    DocumentAnalysis,
    DocumentRecord,
    DocumentType,
    ExtractedFields,
    ProcessingStatus,
    RiskNote,
    WorkflowStatus,
)
from src.report_generator import generate_markdown_report
from src.safety_messages import GENAI_SAFETY_REVIEW_MESSAGE


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
    assert "## Workflow" in report
    assert "- Workflow Status: New" in report


def test_generate_markdown_report_escapes_table_values():
    record = DocumentRecord(
        document_id="doc-2",
        document_name="invoice.pdf",
        document_type=DocumentType.INVOICE,
        status=ProcessingStatus.REVIEW_REQUIRED,
        analysis=DocumentAnalysis(
            document_class="INVOICE",
            executive_summary="A short summary.",
            key_points=["Contains pipe | value"],
            extracted_fields=ExtractedFields(payment_terms="Net 30 | urgent"),
            risk_notes=[
                RiskNote(
                    risk="Mismatch | amount",
                    severity="HIGH",
                    evidence="Line one\nLine two",
                )
            ],
            confidence_score=0.7,
        ),
    )

    report = generate_markdown_report(record, model_id="cohere.command-r-plus-08-2024")

    assert "Net 30 \\| urgent" in report
    assert "Mismatch \\| amount" in report
    assert "Line one<br>Line two" in report


def test_generate_markdown_report_sanitizes_provider_safety_json():
    raw = '{ "code" : "InvalidParameter", "message" : "Inappropriate content detected!!!" }'
    record = DocumentRecord(
        document_id="doc-safety",
        document_name="scan.pdf",
        document_type=DocumentType.GENERAL,
        status=ProcessingStatus.REVIEW_REQUIRED,
        analysis=DocumentAnalysis(
            document_class="GENERAL",
            executive_summary="Manual review.",
            risk_notes=[
                RiskNote(
                    risk="Provider block",
                    severity="HIGH",
                    evidence=raw,
                )
            ],
            confidence_score=0.0,
        ),
    )

    report = generate_markdown_report(record, model_id="cohere.command-r-plus-08-2024")

    assert raw not in report
    assert GENAI_SAFETY_REVIEW_MESSAGE in report


def test_generate_markdown_report_contains_workflow_metadata():
    record = DocumentRecord(
        document_id="doc-3",
        document_name="contract.pdf",
        document_type=DocumentType.CONTRACT,
        status=ProcessingStatus.REVIEW_REQUIRED,
        workflow_status=WorkflowStatus.ESCALATED,
        assignee="Legal",
        retry_count=2,
        analysis=DocumentAnalysis(
            document_class="CONTRACT",
            executive_summary="A short summary.",
            confidence_score=0.8,
        ),
    )

    report = generate_markdown_report(record, model_id="cohere.command-r-plus-08-2024")

    assert "- Workflow Status: Escalated" in report
    assert "- Assignee: Legal" in report
    assert "- Retry Count: 2" in report
