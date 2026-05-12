# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import PurePosixPath
from urllib.parse import unquote

from src.config import AppConfig
from src.file_names import safe_document_name
from src.job_queue import submit_document_processing
from src.logger import get_logger
from src.metadata_store import MetadataStore
from src.models import DocumentRecord, DocumentType, ProcessingStatus
from src.object_storage_client import ObjectStorageClient

logger = get_logger(__name__)


@dataclass
class EventIntakeResult:
    imported: int = 0
    skipped: int = 0
    failed: int = 0
    messages: list[str] = field(default_factory=list)


def marker_document_id(marker: dict) -> str:
    identity = "\n".join(
        str(marker.get(key) or "")
        for key in ("namespace", "bucket", "object_name", "etag", "event_id")
    )
    return f"event-{sha256(identity.encode('utf-8')).hexdigest()[:20]}"


def document_name_from_object(object_name: str, incoming_prefix: str) -> str | None:
    relative = object_name.removeprefix(incoming_prefix).strip("/")
    if not relative:
        return None
    name = unquote(PurePosixPath(relative).name).strip()
    return name or None


def job_description_from_object(
    object_name: str, incoming_prefix: str
) -> str | None:
    relative = object_name.removeprefix(incoming_prefix).strip("/")
    parts = [unquote(part).strip() for part in PurePosixPath(relative).parts]
    if len(parts) < 2:
        return None
    return parts[0] or None


def load_marker(object_storage, marker_name: str) -> dict:
    raw = object_storage.get_object_text(marker_name)
    marker = json.loads(raw)
    if not isinstance(marker, dict):
        raise ValueError("Event queue marker must be a JSON object.")
    return marker


def import_event_queue(
    config: AppConfig,
    *,
    object_storage=None,
    store: MetadataStore | None = None,
    limit: int = 20,
) -> EventIntakeResult:
    result = EventIntakeResult()
    if not config.event_intake_enabled:
        result.messages.append("Event intake is disabled.")
        return result

    object_storage = object_storage or ObjectStorageClient(config)
    store = store or MetadataStore(config)
    marker_names = object_storage.list_objects(
        config.event_intake_queue_prefix, limit=limit
    )
    for marker_name in marker_names:
        try:
            marker = load_marker(object_storage, marker_name)
            if import_marker(config, object_storage, store, marker, marker_name):
                result.imported += 1
            else:
                result.skipped += 1
        except Exception as exc:
            result.failed += 1
            result.messages.append(f"{marker_name}: {exc}")
            logger.exception("Could not import Object Storage event marker %s", marker_name)
    return result


def import_marker(
    config: AppConfig,
    object_storage,
    store: MetadataStore,
    marker: dict,
    marker_name: str,
) -> bool:
    bucket = marker.get("bucket")
    namespace = marker.get("namespace")
    object_name = str(marker.get("object_name") or "")
    if bucket and bucket != config.oci_bucket_name:
        object_storage.delete_object(marker_name)
        return False
    if namespace and namespace != config.oci_namespace:
        object_storage.delete_object(marker_name)
        return False
    if not object_name.startswith(config.event_intake_incoming_prefix):
        object_storage.delete_object(marker_name)
        return False

    document_name = document_name_from_object(
        object_name, config.event_intake_incoming_prefix
    )
    if not document_name:
        object_storage.delete_object(marker_name)
        return False

    document_id = marker_document_id(marker)
    if store.path_for(document_id).exists():
        object_storage.delete_object(marker_name)
        return False

    storage_name = safe_document_name(document_name)
    source_path = config.local_uploads_dir / f"incoming-{document_id}-{storage_name}"
    object_storage.download_file(object_name, source_path)
    file_size = source_path.stat().st_size
    mime_type = marker.get("content_type") or mimetypes.guess_type(document_name)[0]
    job_description = marker.get("job_description") or job_description_from_object(
        object_name, config.event_intake_incoming_prefix
    )
    notes = (
        "Imported automatically from Object Storage event "
        f"{marker.get('event_id') or marker_name}. Source object: {object_name}."
    )
    record = DocumentRecord(
        document_id=document_id,
        document_name=document_name,
        document_type=DocumentType.AUTO_DETECT,
        source_file_size_bytes=file_size,
        source_file_mime_type=mime_type,
        object_storage_path=object_storage.object_uri(object_name),
        status=ProcessingStatus.UPLOADED,
        job_description=job_description,
        notes=notes,
    )
    store.save(record)
    submit_document_processing(
        config=config,
        source_path=source_path,
        document_id=document_id,
        document_name=document_name,
        document_type=DocumentType.AUTO_DETECT,
        business_reference=None,
        notes=notes,
        job_description=job_description,
        source_file_size_bytes=file_size,
        source_file_mime_type=mime_type,
    )
    object_storage.delete_object(marker_name)
    return True
