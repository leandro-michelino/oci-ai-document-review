from src.processor import error_message, safe_document_name


def test_safe_document_name_removes_path_parts_and_unsafe_chars():
    assert safe_document_name("../../contract final|v1.pdf") == "contract_final_v1.pdf"


def test_safe_document_name_has_fallback():
    assert safe_document_name("...") == "document"


def test_error_message_unwraps_retry_error_like_exception():
    class Attempt:
        @staticmethod
        def exception():
            return AttributeError("missing signer")

    class RetryLikeError(Exception):
        last_attempt = Attempt()

    assert error_message(RetryLikeError("wrapped")) == "missing signer"
