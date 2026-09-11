from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from src.case_chat import (
    NO_ANSWER, CaseAccessPolicy, CaseEvidenceRetriever, answer_has_valid_citations,
    build_case_answer_prompt,
)
from src.case_chat_api import app, authenticated_subject, get_store
from src.models import (
    DocumentAnalysis, DocumentRecord, DocumentType, ProcessingStatus, ReviewStatus,
    SensitivityLevel,
)


def make_record(**changes):
    values = {
        "document_id": "case-1",
        "document_name": "invoice.pdf",
        "document_type": DocumentType.INVOICE,
        "status": ProcessingStatus.REVIEW_REQUIRED,
        "review_status": ReviewStatus.PENDING,
        "analysis": DocumentAnalysis(
            document_class="INVOICE", executive_summary="Invoice needs a PO check.",
            key_points=["Supplier: Example Ltd"], confidence_score=0.8,
        ),
    }
    values.update(changes)
    return DocumentRecord(**values)


def test_access_policy_is_default_deny_and_matches_exact_subject(tmp_path: Path):
    policy = CaseAccessPolicy(tmp_path / "missing.json")
    assert not policy.permits("case-1", "alice")
    access_file = tmp_path / "access.json"
    access_file.write_text('{"case-1": ["alice"]}', encoding="utf-8")
    policy = CaseAccessPolicy(access_file)
    assert policy.permits("case-1", "alice")
    assert not policy.permits("case-1", "bob")
    assert not policy.permits("case-2", "alice")
    assert not CaseAccessPolicy(tmp_path).permits("case-1", "alice")


def test_retrieval_is_limited_to_requested_record_and_citations_are_checked():
    evidence = CaseEvidenceRetriever().retrieve(make_record(), "Which supplier needs PO check?")
    prompt = build_case_answer_prompt("Which supplier needs PO check?", evidence)
    assert "Example Ltd" in prompt
    assert answer_has_valid_citations("Example Ltd needs a PO check. [E3]", evidence)
    assert not answer_has_valid_citations("Example Ltd needs a PO check.", evidence)
    assert not answer_has_valid_citations("Other case [E99]", evidence)
    assert answer_has_valid_citations(NO_ANSWER, evidence)


def test_restricted_case_never_retrieves_raw_preview():
    evidence = CaseEvidenceRetriever().retrieve(
        make_record(sensitivity=SensitivityLevel.RESTRICTED, extracted_text_preview="SECRET-RAW-TEXT"),
        "what is the secret",
    )
    assert all("SECRET-RAW-TEXT" not in item.text for item in evidence)


def test_api_returns_only_grounded_case_answer_for_authorized_subject(tmp_path: Path, monkeypatch):
    access_file = tmp_path / "access.json"
    access_file.write_text('{"case-1": ["alice"]}', encoding="utf-8")
    config = SimpleNamespace(case_chat_access_file=access_file, case_chat_max_context_chunks=6)

    class Store:
        def load(self, document_id):
            assert document_id == "case-1"
            return make_record()

    class FakeGenAI:
        def __init__(self, _config):
            pass

        def answer_case_question(self, prompt):
            assert "case-1" not in prompt  # IDs are not needed by the model.
            return "Example Ltd needs a PO check. [E3]"

    monkeypatch.setattr("src.case_chat_api.GenAIClient", FakeGenAI)
    app.dependency_overrides[authenticated_subject] = lambda: "alice"
    app.dependency_overrides[get_store] = lambda: Store()
    # The config dependency is imported by the module, so override it by route resolution.
    from src.case_chat_api import get_config
    app.dependency_overrides[get_config] = lambda: config
    try:
        response = TestClient(app).post("/v1/cases/case-1/chat", json={"question": "Who needs a PO check?"})
        assert response.status_code == 200
        assert response.json()["answer"] == "Example Ltd needs a PO check. [E3]"
        app.dependency_overrides[authenticated_subject] = lambda: "bob"
        denied = TestClient(app).post("/v1/cases/case-1/chat", json={"question": "Who needs a PO check?"})
        assert denied.status_code == 404
    finally:
        app.dependency_overrides.clear()
