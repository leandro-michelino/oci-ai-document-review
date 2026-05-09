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


def test_prompt_includes_document_understanding_key_values():
    prompt = build_prompt(
        DocumentType.INVOICE,
        "Invoice body",
        max_chars=1000,
        key_values={"Total": "$42.00"},
        table_count=1,
    )

    assert "Key values detected by OCI Document Understanding" in prompt
    assert "Total: $42.00" in prompt
    assert "Tables detected by OCI Document Understanding: 1" in prompt


def test_invoice_prompt_does_not_treat_vat_as_public_sector_evidence():
    prompt = build_prompt(
        DocumentType.INVOICE,
        "Invoice with VAT 21% for Spain.",
        max_chars=1000,
    )

    assert "Do not treat VAT" in prompt
    assert "ordinary invoice tax fields" in prompt
    assert "Never create a" in prompt
    assert "risk note based only on VAT" in prompt


def test_invoice_prompt_requests_receipt_line_items():
    prompt = build_prompt(
        DocumentType.INVOICE,
        "Receipt with pasta, water, and coffee.",
        max_chars=1000,
    )

    assert "extracted_fields.line_items" in prompt
    assert "what was consumed or purchased" in prompt
    assert "Do not invent consumed items" in prompt
