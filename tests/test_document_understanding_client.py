from types import SimpleNamespace

from src.document_understanding_client import DocumentUnderstandingClient


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
