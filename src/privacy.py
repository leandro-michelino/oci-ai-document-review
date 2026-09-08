# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
"""Conservative PII detection and display redaction for reviewer-facing previews."""

import re
from dataclasses import dataclass

from src.models import DocumentType, SensitivityLevel

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)")
PASSPORT_PATTERN = re.compile(
    r"\b(?:passport|passaporto|national[ -]?id|identity card|dni)\b", re.I
)
IDENTIFIER_PATTERN = re.compile(
    r"\b(?:passport|passaporto|national[ -]?id|identity card|dni)\s*(?:no\.?|number|nº|#)?\s*[:#-]?\s*[A-Z0-9]{5,}\b",
    re.I,
)


@dataclass(frozen=True)
class PrivacyAssessment:
    sensitivity: SensitivityLevel
    labels: list[str]


def assess_privacy(
    document_name: str, document_type: DocumentType, extracted_text: str
) -> PrivacyAssessment:
    content = f"{document_name}\n{extracted_text}"
    labels: list[str] = []
    if PASSPORT_PATTERN.search(content):
        labels.append("IDENTITY_DOCUMENT")
    if IDENTIFIER_PATTERN.search(content):
        labels.append("GOVERNMENT_IDENTIFIER")
    if EMAIL_PATTERN.search(content):
        labels.append("EMAIL_ADDRESS")
    if PHONE_PATTERN.search(content):
        labels.append("PHONE_NUMBER")
    if document_type == DocumentType.INVOICE and labels:
        labels.append("INVOICE_WITH_PERSONAL_DATA")
    return PrivacyAssessment(
        sensitivity=SensitivityLevel.RESTRICTED if labels else SensitivityLevel.STANDARD,
        labels=labels,
    )


def redact_preview(value: str) -> str:
    redacted = EMAIL_PATTERN.sub("[REDACTED EMAIL]", value)
    redacted = PHONE_PATTERN.sub("[REDACTED PHONE]", redacted)
    return IDENTIFIER_PATTERN.sub("[REDACTED ID]", redacted)
