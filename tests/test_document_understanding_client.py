from types import SimpleNamespace

import pytest

from src.document_understanding_client import DocumentUnderstandingClient
from src.models import ExtractionResult


class NestedCell:
    def __init__(self, text: str):
        self.text = text


class TableLike:
    def to_dict(self):
        return {"cells": [NestedCell("Invoice"), NestedCell("Amount")]}


def test_extract_tables_returns_json_safe_values():
    result = SimpleNamespace(pages=[SimpleNamespace(tables=[TableLike()])])

    tables = DocumentUnderstandingClient._extract_tables(result)

    assert tables == [{"cells": [{"text": "Invoice"}, {"text": "Amount"}]}]


def test_extract_key_values_returns_plain_fallback_value():
    field = SimpleNamespace(
        field_name=SimpleNamespace(text="Total"),
        field_value=SimpleNamespace(amount=125.5, currency="GBP"),
    )
    result = SimpleNamespace(pages=[SimpleNamespace(document_fields=[field])])

    values = DocumentUnderstandingClient._extract_key_values(result)

    assert values == {"Total": {"amount": 125.5, "currency": "GBP"}}


def test_extract_document_retries_inline_extraction(monkeypatch):
    client = object.__new__(DocumentUnderstandingClient)
    client.config = SimpleNamespace(document_ai_retry_attempts=2)
    calls = 0

    def fake_extract(object_name):
        nonlocal calls
        calls += 1
        assert object_name == "documents/doc-1/receipt.pdf"
        if calls == 1:
            raise RuntimeError("temporary DU failure")
        return ExtractionResult(text="Receipt text")

    monkeypatch.setattr(client, "_extract_document_inline", fake_extract)
    monkeypatch.setattr(
        "src.document_understanding_client.time.sleep", lambda seconds: None
    )

    result = client.extract_document("documents/doc-1/receipt.pdf")

    assert result.text == "Receipt text"
    assert calls == 2


def test_extract_document_reports_final_inline_error(monkeypatch):
    client = object.__new__(DocumentUnderstandingClient)
    client.config = SimpleNamespace(document_ai_retry_attempts=1)
    monkeypatch.setattr(
        client,
        "_extract_document_inline",
        lambda object_name: (_ for _ in ()).throw(RuntimeError("service denied")),
    )

    with pytest.raises(
        RuntimeError, match="OCI Document Understanding failed: service denied"
    ):
        client.extract_document("documents/doc-1/receipt.pdf")
