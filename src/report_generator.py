from datetime import datetime, timezone

from src.models import DocumentAnalysis, DocumentRecord
from src.safety_messages import sanitize_provider_text


def _normalize_markdown(value: object) -> str:
    text = sanitize_provider_text(value) or ""
    return text.replace("\n", "<br>").replace("|", "\\|")


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- None found"
    return "\n".join(f"- {_normalize_markdown(item)}" for item in items)


def _fields_table(analysis: DocumentAnalysis) -> str:
    fields = analysis.extracted_fields.model_dump()
    lines = ["| Field | Value |", "| --- | --- |"]
    for key, value in fields.items():
        if isinstance(value, list):
            rendered = ", ".join(value) if value else "None found"
        else:
            rendered = value or "Not found"
        lines.append(
            f"| {key.replace('_', ' ').title()} | {_normalize_markdown(rendered)} |"
        )
    return "\n".join(lines)


def _risks_table(analysis: DocumentAnalysis) -> str:
    if not analysis.risk_notes:
        return "| Severity | Risk | Evidence |\n| --- | --- | --- |\n| - | None found | - |"
    lines = ["| Severity | Risk | Evidence |", "| --- | --- | --- |"]
    for risk in analysis.risk_notes:
        lines.append(
            f"| {risk.severity} | {_normalize_markdown(risk.risk)} | "
            f"{_normalize_markdown(risk.evidence or '-')} |"
        )
    return "\n".join(lines)


def _label(value: object) -> str:
    text = str(value)
    return text.replace("_", " ").title()


def generate_markdown_report(record: DocumentRecord, model_id: str) -> str:
    analysis = record.analysis
    if analysis is None:
        raise ValueError("Cannot generate a report without analysis")

    generated_at = datetime.now(timezone.utc).isoformat()
    due_at = record.due_at.date().isoformat() if record.due_at else "No SLA"
    return f"""# Document Intelligence Report

## Document Metadata

- Document Name: {record.document_name}
- Document Type: {record.document_type.value}
- Uploaded At: {record.uploaded_at.isoformat()}
- Processed At: {record.processed_at.isoformat() if record.processed_at else generated_at}
- Processing Status: {record.status.value}
- Business Reference: {record.business_reference or "Not provided"}

## Executive Summary

{analysis.executive_summary}

## Key Points

{_bullet_list(analysis.key_points)}

## Extracted Fields

{_fields_table(analysis)}

## Risk Notes

{_risks_table(analysis)}

## Recommendations

{_bullet_list(analysis.recommendations)}

## Missing Information

{_bullet_list(analysis.missing_information)}

## Human Review

- Human Review Required: {analysis.human_review_required}
- Review Status: {record.review_status.value}
- Review Comments: {record.review_comments or "None"}

## Workflow

- Workflow Status: {_label(record.workflow_status.value)}
- Assignee: {record.assignee or "Unassigned"}
- SLA Due Date: {due_at}
- Parent Document ID: {record.parent_document_id or "None"}
- Retry Count: {record.retry_count}
- Workflow Comments: {len(record.workflow_comments)}
- Audit Events: {len(record.audit_events)}

## Processing Metadata

- Model ID: {model_id}
- Confidence Score: {analysis.confidence_score}
- Generated At: {generated_at}
"""
