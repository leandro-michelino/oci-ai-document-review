# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from __future__ import annotations

import io
import json
import os
from datetime import datetime, timezone
from hashlib import sha256

from fdk import response


def nested_value(data, key: str):
    if isinstance(data, dict):
        for item_key, item_value in data.items():
            if item_key == key:
                return item_value
            found = nested_value(item_value, key)
            if found is not None:
                return found
    if isinstance(data, list):
        for item in data:
            found = nested_value(item, key)
            if found is not None:
                return found
    return None


def event_value(event: dict, *keys: str) -> str | None:
    for key in keys:
        value = nested_value(event, key)
        if value:
            return str(value)
    return None


def queue_marker_name(queue_prefix: str, marker: dict) -> str:
    identity = "\n".join(
        str(marker.get(key) or "")
        for key in ("namespace", "bucket", "object_name", "etag", "event_id")
    )
    digest = sha256(identity.encode("utf-8")).hexdigest()[:32]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{queue_prefix}{timestamp}-{digest}.json"


def object_prefix(name: str, default: str) -> str:
    value = os.getenv(name, default).strip().lstrip("/")
    if not value:
        value = default
    return value if value.endswith("/") else f"{value}/"


def handler(ctx, data: io.BytesIO | None = None):
    import oci

    raw_body = data.getvalue().decode("utf-8") if data else "{}"
    event = json.loads(raw_body or "{}")
    namespace = event_value(event, "namespace") or os.environ["OCI_NAMESPACE"]
    bucket = event_value(event, "bucketName", "bucket") or os.environ["OCI_BUCKET_NAME"]
    object_name = event_value(event, "objectName", "resourceName")
    incoming_prefix = object_prefix("INCOMING_PREFIX", "incoming/")
    queue_prefix = object_prefix("QUEUE_PREFIX", "event-queue/")
    if not object_name or not object_name.startswith(incoming_prefix):
        return response.Response(
            ctx,
            response_data=json.dumps({"queued": False, "reason": "ignored object"}),
            headers={"Content-Type": "application/json"},
        )

    marker = {
        "schema_version": 1,
        "source": "oci-events-functions",
        "event_id": event.get("eventID") or event.get("id"),
        "event_type": event.get("eventType") or event.get("type"),
        "event_time": event.get("eventTime") or event.get("time"),
        "namespace": namespace,
        "bucket": bucket,
        "object_name": object_name,
        "etag": event_value(event, "eTag", "etag"),
        "content_type": event_value(event, "contentType", "content_type"),
    }
    signer = oci.auth.signers.get_resource_principals_signer()
    client = oci.object_storage.ObjectStorageClient(
        {"region": os.environ["OCI_REGION"]}, signer=signer
    )
    marker_name = queue_marker_name(queue_prefix, marker)
    client.put_object(
        namespace_name=namespace,
        bucket_name=bucket,
        object_name=marker_name,
        put_object_body=json.dumps(marker, indent=2).encode("utf-8"),
    )
    return response.Response(
        ctx,
        response_data=json.dumps({"queued": True, "marker": marker_name}),
        headers={"Content-Type": "application/json"},
    )
