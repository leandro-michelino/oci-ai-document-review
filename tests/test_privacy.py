import json
from pathlib import Path

import pytest

from src.models import DocumentType
from src.privacy import assess_privacy, redact_preview


@pytest.mark.parametrize(
    "case",
    json.loads(
        (Path(__file__).parent / "fixtures" / "golden_privacy_cases.json").read_text(
            encoding="utf-8"
        )
    ),
)
def test_golden_privacy_classification_cases(case):
    assessment = assess_privacy(
        case["name"], DocumentType(case["document_type"]), case["text"]
    )

    assert assessment.sensitivity.value == case["sensitivity"]
    assert assessment.labels == case["labels"]


def test_redact_preview_masks_detected_email_phone_and_identity_number():
    preview = redact_preview(
        "Passport No: YA1234567, email maria.rossi@example.test, phone +39 333 123 4567"
    )

    assert "YA1234567" not in preview
    assert "maria.rossi@example.test" not in preview
    assert "333 123 4567" not in preview
    assert "[REDACTED ID]" in preview
