# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
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
    calls = []

    def fake_extract(object_name, rich_features=True):
        calls.append(rich_features)
        assert object_name == "documents/doc-1/receipt.pdf"
        if calls == [True]:
            raise RuntimeError("temporary DU failure")
        if rich_features is False:
            raise RuntimeError("temporary text fallback failure")
        return ExtractionResult(text="Receipt text")

    monkeypatch.setattr(client, "_extract_document_inline", fake_extract)
    monkeypatch.setattr(
        "src.document_understanding_client.time.sleep", lambda seconds: None
    )

    result = client.extract_document("documents/doc-1/receipt.pdf")

    assert result.text == "Receipt text"
    assert calls == [True, False, True]


def test_extract_document_falls_back_to_text_only_ocr(monkeypatch):
    client = object.__new__(DocumentUnderstandingClient)
    client.config = SimpleNamespace(document_ai_retry_attempts=1)
    calls = []

    def fake_extract(object_name, rich_features=True):
        calls.append(rich_features)
        assert object_name == "documents/doc-1/receipt.pdf"
        if rich_features:
            raise RuntimeError("table extraction failed")
        return ExtractionResult(
            text="Receipt OCR text",
            source="OCI Document Understanding text-only OCR fallback",
        )

    monkeypatch.setattr(client, "_extract_document_inline", fake_extract)

    result = client.extract_document("documents/doc-1/receipt.pdf")

    assert result.text == "Receipt OCR text"
    assert result.source == "OCI Document Understanding text-only OCR fallback"
    assert calls == [True, False]


def test_extract_document_reports_final_inline_error(monkeypatch):
    client = object.__new__(DocumentUnderstandingClient)
    client.config = SimpleNamespace(document_ai_retry_attempts=1)
    monkeypatch.setattr(
        client,
        "_extract_document_inline",
        lambda object_name, rich_features=True: (_ for _ in ()).throw(
            RuntimeError("service denied")
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "OCI Document Understanding failed: service denied; "
            "text-only OCR fallback failed: service denied"
        ),
    ):
        client.extract_document("documents/doc-1/receipt.pdf")
