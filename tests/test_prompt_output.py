from src.models import DocumentType
from src.prompts import build_prompt


def test_prompt_requests_json_only():
    prompt = build_prompt(DocumentType.CONTRACT, "Contract body", max_chars=1000)

    assert "Return JSON only" in prompt
    assert "Contract body" in prompt
    assert "human_review_required" in prompt


def test_prompt_truncates_document_text():
    prompt = build_prompt(DocumentType.GENERAL, "x" * 100, max_chars=10)

    assert "x" * 10 in prompt
    assert "x" * 11 not in prompt
