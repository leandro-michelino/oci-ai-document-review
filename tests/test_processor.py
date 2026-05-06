from src.processor import safe_document_name


def test_safe_document_name_removes_path_parts_and_unsafe_chars():
    assert safe_document_name("../../contract final|v1.pdf") == "contract_final_v1.pdf"


def test_safe_document_name_has_fallback():
    assert safe_document_name("...") == "document"
