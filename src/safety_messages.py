# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
import re
from enum import Enum

GENAI_SAFETY_REVIEW_RISK = "Automatic AI analysis blocked by content safety filter"
GENAI_SAFETY_REVIEW_MESSAGE = (
    "OCI Generative AI blocked automatic analysis with the service content safety "
    "filter. The document was routed for manual review instead of showing the raw "
    "provider error."
)
GENAI_SAFETY_REVIEW_SHORT_MESSAGE = "OCI Generative AI content safety filter"
DOCUMENT_UNDERSTANDING_PAGE_LIMIT_MESSAGE = (
    "OCI Document Understanding rejected a previous OCR request because it exceeded "
    "the 5-page synchronous limit. The current app version automatically splits "
    "scanned PDFs into limit-safe OCR chunks before retrying."
)


def is_genai_content_filter_text(value: object) -> bool:
    combined = str(value or "").lower()
    return (
        "invalidparameter" in combined and "inappropriate content" in combined
    ) or "inappropriate content detected" in combined


def is_document_understanding_page_limit_text(value: object) -> bool:
    combined = str(value or "").lower()
    return (
        "ai_service_document" in combined
        and "too many pages" in combined
        and "maximum number of pages allowed" in combined
    )


def sanitize_provider_message(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if is_genai_content_filter_text(text):
        return GENAI_SAFETY_REVIEW_MESSAGE
    if is_document_understanding_page_limit_text(text):
        return DOCUMENT_UNDERSTANDING_PAGE_LIMIT_MESSAGE
    return text


def sanitize_provider_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if is_document_understanding_page_limit_text(text):
        return DOCUMENT_UNDERSTANDING_PAGE_LIMIT_MESSAGE
    if not is_genai_content_filter_text(text):
        return text
    sanitized = re.sub(
        r"\{[^{}]*(?:invalidparameter|inappropriate content)[^{}]*"
        r"(?:invalidparameter|inappropriate content)[^{}]*\}",
        GENAI_SAFETY_REVIEW_MESSAGE,
        text,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"inappropriate content detected!*",
        GENAI_SAFETY_REVIEW_SHORT_MESSAGE,
        sanitized,
        flags=re.IGNORECASE,
    )
    if sanitized == text:
        return GENAI_SAFETY_REVIEW_MESSAGE
    return sanitized


def sanitize_provider_payload(value):
    if isinstance(value, dict):
        return {key: sanitize_provider_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_provider_payload(item) for item in value]
    if isinstance(value, Enum):
        return value
    if isinstance(value, str):
        return sanitize_provider_text(value)
    return value
