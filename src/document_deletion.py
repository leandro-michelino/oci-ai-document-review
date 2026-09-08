# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
"""Guarded removal of failed document records and portal-owned source objects."""

from dataclasses import dataclass

from src.config import AppConfig
from src.file_names import safe_document_name
from src.metadata_store import DiscardedDocumentResult, MetadataStore
from src.models import ProcessingStatus
from src.object_storage_client import ObjectStorageClient


@dataclass(frozen=True)
class FailedDocumentDiscardResult:
    object_name: str | None
    cloud_object_deleted: bool
    local_result: DiscardedDocumentResult


def portal_object_name(document_id: str, document_name: str) -> str:
    return f"documents/{document_id}/{safe_document_name(document_name)}"


def _object_is_missing(error: Exception) -> bool:
    return getattr(error, "status", None) == 404


def discard_failed_document(
    config: AppConfig,
    store: MetadataStore,
    document_id: str,
    actor: str,
    reason: str | None = None,
    object_storage: ObjectStorageClient | None = None,
) -> FailedDocumentDiscardResult:
    """Discard a failed document after deleting only the portal-managed OCI copy.

    Documents from an external ``incoming/`` prefix are intentionally not targeted.
    A missing portal object is acceptable because the desired final cloud state is
    absence. Any other Object Storage error leaves all local recovery artifacts intact.
    """
    record = store.load(document_id)
    if record.status != ProcessingStatus.FAILED:
        raise ValueError("Only failed documents can be discarded.")

    object_name = None
    cloud_object_deleted = False
    if record.object_storage_path:
        object_name = portal_object_name(record.document_id, record.document_name)
        client = object_storage or ObjectStorageClient(config)
        try:
            client.delete_object(object_name)
        except Exception as exc:
            if not _object_is_missing(exc):
                raise RuntimeError(
                    "The portal-managed Object Storage copy could not be deleted. "
                    "Local data has been kept so the document can still be retried."
                ) from exc
        else:
            cloud_object_deleted = True

    local_result = store.discard_failed_document(
        document_id=document_id,
        actor=actor,
        reason=reason,
        cloud_object_deleted=cloud_object_deleted,
    )
    return FailedDocumentDiscardResult(
        object_name=object_name,
        cloud_object_deleted=cloud_object_deleted,
        local_result=local_result,
    )
