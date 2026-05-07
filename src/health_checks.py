from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from src.config import AppConfig
from src.document_understanding_client import DocumentUnderstandingClient
from src.genai_client import GenAIClient
from src.object_storage_client import ObjectStorageClient
from src.processor import error_message


@dataclass
class HealthCheckResult:
    name: str
    ok: bool
    detail: str


def check_object_storage(config: AppConfig) -> HealthCheckResult:
    client = ObjectStorageClient(config)
    object_name = f"healthchecks/preflight-{uuid4().hex}.txt"
    deleted = False
    with NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"oci-ai-document-review-preflight")
        tmp_path = Path(tmp.name)
    try:
        bucket = client.get_bucket()
        client.upload_file(tmp_path, object_name)
        content = client.get_object_text(object_name)
        if content != "oci-ai-document-review-preflight":
            return HealthCheckResult(
                "Object Storage", False, "Readback content did not match."
            )
        client.delete_object(object_name)
        deleted = True
        return HealthCheckResult(
            "Object Storage",
            True,
            f"Bucket {bucket.name} is reachable and write/read/delete permissions work.",
        )
    except Exception as exc:
        return HealthCheckResult("Object Storage", False, error_message(exc))
    finally:
        tmp_path.unlink(missing_ok=True)
        if not deleted:
            try:
                client.delete_object(object_name)
            except Exception:
                pass


def check_document_understanding(config: AppConfig) -> HealthCheckResult:
    try:
        client = DocumentUnderstandingClient(config)
        client.list_recent_work_requests()
        return HealthCheckResult(
            "Document Understanding",
            True,
            "Service API is reachable with the configured compartment and credentials.",
        )
    except Exception as exc:
        return HealthCheckResult("Document Understanding", False, error_message(exc))


def check_genai(config: AppConfig) -> HealthCheckResult:
    try:
        response = GenAIClient(config).ping()
        if "OCI_GENAI_OK" not in response:
            return HealthCheckResult(
                "Generative AI", False, f"Unexpected response: {response}"
            )
        return HealthCheckResult(
            "Generative AI",
            True,
            f"Model {config.genai_model_id} responded in {config.genai_region}.",
        )
    except Exception as exc:
        return HealthCheckResult("Generative AI", False, error_message(exc))


def run_preflight(config: AppConfig) -> list[HealthCheckResult]:
    return [
        check_object_storage(config),
        check_document_understanding(config),
        check_genai(config),
    ]
