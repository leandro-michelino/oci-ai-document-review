"""Regression coverage for repository review findings, without live OCI calls."""

import json
import tarfile
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.case_chat import CaseAccessPolicy
from src.case_chat_api import authenticated_subject
from src.job_queue import _process_document, submit_document_processing
from src.metadata_store import MetadataStore
from src.models import DocumentRecord, DocumentType, ProcessingStatus
from src.text_extraction import extract_text_locally


def make_store(tmp_path):
    return MetadataStore(SimpleNamespace(local_metadata_dir=tmp_path / "metadata"))


def make_record(document_id="case-1", **changes):
    return DocumentRecord(
        document_id=document_id,
        document_name="contract.txt",
        document_type=DocumentType.CONTRACT,
        **changes,
    )


@pytest.mark.parametrize(
    "document_id", ["../outside", "/tmp/outside", "a/b", "a\\b", "*", "", ".."]
)
def test_metadata_rejects_unsafe_ids_before_read_or_write(tmp_path, document_id):
    store = make_store(tmp_path)
    with pytest.raises(ValueError):
        store.load(document_id)
    with pytest.raises(ValueError):
        store.save(make_record(document_id))


def test_metadata_rejects_external_symlink_and_mismatched_identity(tmp_path):
    store = make_store(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text(make_record().model_dump_json())
    store.path_for("linked").symlink_to(outside)
    with pytest.raises(ValueError):
        store.load("linked")
    (store.root / "wrong.json").write_text(make_record().model_dump_json())
    with pytest.raises(ValueError, match="does not match"):
        store.load("wrong")


def test_interrupted_metadata_save_preserves_previous_record(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    store.save(make_record(notes="original"))

    def fail_replace(*args):
        raise OSError("simulated failed replacement")

    monkeypatch.setattr("os.replace", fail_replace)
    with pytest.raises(OSError):
        store.save(make_record(notes="new"))
    assert store.load("case-1").notes == "original"
    assert not list(store.root.glob("*.tmp"))


def test_parallel_review_comments_are_all_preserved(tmp_path):
    store = make_store(tmp_path)
    store.save(make_record())
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(
            executor.map(
                lambda index: make_store(tmp_path).add_comment(
                    "case-1", "Reviewer", f"Comment {index}"
                ),
                range(40),
            )
        )
    updated = store.load("case-1")
    assert len(updated.workflow_comments) == len(updated.audit_events) == 40


def _append_comments_in_process(root):
    store = make_store(root)
    for index in range(10):
        store.add_comment("case-1", "Reviewer", f"Comment {index}")


def test_review_comments_are_preserved_across_processes(tmp_path):
    store = make_store(tmp_path)
    store.save(make_record())
    with ProcessPoolExecutor(
        max_workers=3, mp_context=multiprocessing.get_context("spawn")
    ) as executor:
        list(executor.map(_append_comments_in_process, [tmp_path] * 3))
    assert len(store.load("case-1").workflow_comments) == 30


def test_stale_processing_supports_legacy_naive_timestamps(tmp_path):
    store = make_store(tmp_path)
    store.save(
        make_record(
            uploaded_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(hours=1)
        )
    )
    assert store.fail_stale_processing(10) == 1


@pytest.mark.parametrize(
    "content", ["[]", "null", '"invalid"', "1", '{"case-1": "alice"}']
)
def test_access_policy_denies_malformed_shapes(tmp_path, content):
    access = tmp_path / "acl.json"
    access.write_text(content)
    assert not CaseAccessPolicy(access).permits("case-1", "alice")


def test_oidc_token_requires_expiration_and_asymmetric_signature(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(
            key=key.public_key(), algorithm_name="RS256"
        )
    )
    monkeypatch.setattr("src.case_chat_api._jwks_client", lambda url: client)
    config = SimpleNamespace(
        case_chat_api_enabled=True,
        case_chat_oidc_jwks_url="https://issuer.example/keys",
        case_chat_oidc_audience="review",
        case_chat_oidc_issuer="https://issuer.example",
    )
    claims = {"sub": "alice", "aud": "review", "iss": "https://issuer.example"}

    def authenticate(payload):
        token = jwt.encode(payload, key, algorithm="RS256")
        return authenticated_subject(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), config
        )

    with pytest.raises(HTTPException) as missing:
        authenticate(claims)
    assert missing.value.status_code == 401
    assert (
        authenticate(
            {**claims, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
        )
        == "alice"
    )
    with pytest.raises(HTTPException):
        authenticate(
            {**claims, "exp": datetime.now(timezone.utc) - timedelta(minutes=5)}
        )
    symmetric = jwt.encode({**claims, "exp": 9999999999}, "x" * 32, algorithm="HS256")
    with pytest.raises(HTTPException):
        authenticated_subject(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=symmetric), config
        )


def test_worker_constructor_failure_keeps_retryable_source(tmp_path, monkeypatch):
    config = SimpleNamespace(local_metadata_dir=tmp_path / "metadata")
    store = MetadataStore(config)
    store.save(make_record())
    source = tmp_path / "queued.txt"
    source.write_text("source content")

    def fail_processor(config):
        raise RuntimeError("startup failed")

    monkeypatch.setattr("src.job_queue.DocumentProcessor", fail_processor)
    _process_document(
        config,
        source,
        "case-1",
        "contract.txt",
        DocumentType.CONTRACT,
        None,
        None,
        None,
        None,
        None,
    )
    assert (store.uploads_root / "case-1-contract.txt").read_text() == "source content"
    assert store.load("case-1").status == ProcessingStatus.FAILED


def test_executor_submission_failure_does_not_delete_source(tmp_path, monkeypatch):
    config = SimpleNamespace(
        local_metadata_dir=tmp_path / "metadata", max_parallel_jobs=1
    )
    store = MetadataStore(config)
    store.save(make_record())
    source = tmp_path / "queued.txt"
    source.write_text("source content")

    def fail_executor(workers):
        raise RuntimeError("executor unavailable")

    monkeypatch.setattr("src.job_queue.get_executor", fail_executor)
    with pytest.raises(RuntimeError):
        submit_document_processing(
            config,
            source,
            "case-1",
            "contract.txt",
            DocumentType.CONTRACT,
            None,
            None,
            None,
            None,
            None,
        )
    assert source.read_text() == "source content"
    assert (store.uploads_root / "case-1-contract.txt").read_text() == "source content"


@pytest.mark.parametrize(
    "status",
    [ProcessingStatus.UPLOADED, ProcessingStatus.AI_ANALYZED, ProcessingStatus.FAILED],
)
def test_incomplete_or_failed_document_cannot_be_approved(tmp_path, status):
    store = make_store(tmp_path)
    store.save(make_record(status=status))
    with pytest.raises(ValueError, match="ready for review"):
        store.set_review("case-1", approved=True, comments=None)
    assert store.load("case-1").status == status


def test_failed_document_with_active_worker_cannot_be_discarded_or_retried(
    tmp_path, monkeypatch
):
    from src.document_deletion import discard_failed_document
    from src.job_queue import retry_document_processing

    config = SimpleNamespace(local_metadata_dir=tmp_path / "metadata")
    store = MetadataStore(config)
    store.save(make_record(status=ProcessingStatus.FAILED))
    monkeypatch.setattr(
        "src.document_deletion.submitted_document_ids",
        lambda: {"case-1"},
        raising=False,
    )
    monkeypatch.setattr("src.job_queue.submitted_document_ids", lambda: {"case-1"})
    with pytest.raises(ValueError, match="active worker"):
        discard_failed_document(config, store, "case-1", actor="Reviewer")
    with pytest.raises(ValueError, match="active worker"):
        retry_document_processing(config, "case-1")
    assert store.load("case-1").status == ProcessingStatus.FAILED


def test_chat_generation_error_returns_service_unavailable(tmp_path, monkeypatch):
    from src.case_chat_api import chat_about_case, CaseQuestion

    access = tmp_path / "access.json"
    access.write_text('{"case-1": ["alice"]}')
    config = SimpleNamespace(
        case_chat_access_file=access, case_chat_max_context_chunks=6
    )

    def fail_genai(config):
        raise RuntimeError("private provider error")

    monkeypatch.setattr("src.case_chat_api.GenAIClient", fail_genai)
    with pytest.raises(HTTPException) as error:
        chat_about_case(
            "case-1",
            CaseQuestion(question="What is the status?"),
            "alice",
            config,
            SimpleNamespace(load=lambda document_id: make_record()),
        )
    assert error.value.status_code == 503
    assert "private provider" not in error.value.detail


def test_worker_checkpoints_preserve_comments_added_during_ai_call(
    tmp_path, monkeypatch
):
    from src.models import DocumentAnalysis
    from src.processor import DocumentProcessor

    config = SimpleNamespace(
        local_metadata_dir=tmp_path / "metadata",
        local_reports_dir=tmp_path / "reports",
        local_uploads_dir=tmp_path / "uploads",
        max_document_chars=50000,
        genai_model_id="cohere.test",
    )
    config.local_reports_dir.mkdir()
    config.local_uploads_dir.mkdir()
    store = MetadataStore(config)
    source = tmp_path / "contract.txt"
    source.write_text("This contract describes the supply of office furniture.")

    class Storage:
        def __init__(self, config):
            pass

        def upload_file(self, *args):
            pass

        def object_uri(self, name):
            return "oci://bucket/" + name

    class GenAI:
        def __init__(self, config):
            pass

        def analyze_document(self, prompt):
            store.add_comment("case-1", "Reviewer", "Keep this comment.")
            return DocumentAnalysis(
                document_class="CONTRACT",
                executive_summary="Furniture supply.",
                confidence_score=0.8,
            )

    monkeypatch.setattr("src.processor.ObjectStorageClient", Storage)
    monkeypatch.setattr("src.processor.GenAIClient", GenAI)
    monkeypatch.setattr(
        "src.processor.load_compliance_catalog",
        lambda *args, **kwargs: SimpleNamespace(
            find_public_sector_matches=lambda context: []
        ),
    )
    result = DocumentProcessor(config).process(
        source, "contract.txt", DocumentType.CONTRACT, document_id="case-1"
    )
    assert result.status == ProcessingStatus.REVIEW_REQUIRED
    assert store.load("case-1").workflow_comments[0].comment == "Keep this comment."


def test_mixed_text_and_scanned_pdf_routes_whole_document_to_ocr(tmp_path, monkeypatch):
    text_page = SimpleNamespace(
        extract_text=lambda: "Selectable text on cover page. " * 10
    )
    scan_page = SimpleNamespace(extract_text=lambda: "")
    monkeypatch.setattr(
        "pypdf.PdfReader", lambda path: SimpleNamespace(pages=[text_page, scan_page])
    )
    assert extract_text_locally(tmp_path / "mixed.pdf", "mixed.pdf") is None


def test_release_archive_contains_sources_without_runtime_data_or_secrets(tmp_path):
    from scripts.package_release import build_release

    included = [
        "app.py",
        "src/processor.py",
        "data/compliance/entities.csv",
        "terraform/main.tf",
    ]
    excluded = [
        ".env",
        "output/export.json",
        "tmp/source.pdf",
        "data/case_chat_access.json",
        "data/deleted/case.json",
        "data/uploads/source.pdf",
        "data/metadata/case.json",
        "terraform/terraform.tfvars",
        "terraform/terraform.tfstate.backup",
        "terraform/deploy.tfplan",
        "src/private.pem",
        "docs/certificate.p12",
        "src/__pycache__/processor.pyc",
        "node_modules/private.json",
    ]
    for name in included + excluded:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fixture": name}))
    (tmp_path / "src" / "linked.txt").symlink_to(tmp_path / ".env")
    destination = tmp_path / "release.tar.gz"
    build_release(tmp_path, destination)
    with tarfile.open(destination) as archive:
        assert set(archive.getnames()) == set(included)


def test_zero_document_ai_attempts_is_rejected():
    from pydantic import ValidationError
    from src.config import AppConfig

    with pytest.raises(ValidationError, match="DOCUMENT_AI_RETRY_ATTEMPTS"):
        AppConfig(
            _env_file=None,
            OCI_REGION="example",
            GENAI_REGION="example",
            OCI_COMPARTMENT_ID="example",
            OCI_NAMESPACE="example",
            OCI_BUCKET_NAME="example",
            GENAI_MODEL_ID="cohere.test",
            DOCUMENT_AI_RETRY_ATTEMPTS=0,
        )


def test_restricted_chat_redacts_pii_in_analysis_and_comments():
    from src.case_chat import CaseEvidenceRetriever
    from src.models import DocumentAnalysis, SensitivityLevel

    record = make_record(
        sensitivity=SensitivityLevel.RESTRICTED,
        analysis=DocumentAnalysis(
            document_class="CONTRACT",
            executive_summary="Contact alice@example.com.",
            confidence_score=0.8,
        ),
        review_comments="Call +34 612 345 678 for the review.",
    )
    evidence = CaseEvidenceRetriever(12).retrieve(record, "contact")
    context = "\n".join(item.text for item in evidence)
    assert "alice@example.com" not in context
    assert "+34 612 345 678" not in context
    assert "[REDACTED EMAIL]" in context


def test_deploy_reads_case_chat_settings_from_dotenv(tmp_path):
    import os
    import subprocess
    from pathlib import Path

    deployment = (Path(__file__).resolve().parents[1] / "scripts/deploy.sh").read_text()
    # Exercise only configuration loading; never run provisioning or deployment.
    loading = deployment[
        deployment.index("env_value()") : deployment.index("export OCI_CONFIG_FILE")
    ]
    (tmp_path / ".env").write_text(
        "CASE_CHAT_API_ENABLED=true\nCASE_CHAT_API_PORT=8090\n"
        "CASE_CHAT_OIDC_AUDIENCE=review-test\n"
    )
    result = subprocess.run(
        [
            "bash",
            "-c",
            "set -eu\n"
            + loading
            + '\nprintf "%s\\n" "$CASE_CHAT_API_ENABLED" "$CASE_CHAT_API_PORT" "$CASE_CHAT_OIDC_AUDIENCE"',
        ],
        cwd=tmp_path,
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["true", "8090", "review-test"]
