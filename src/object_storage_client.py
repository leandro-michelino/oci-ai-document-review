# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from pathlib import Path
import os
import tempfile
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import AppConfig
from src.oci_auth import get_oci_client_config


class ObjectStorageClient:
    def __init__(self, config: AppConfig):
        import oci

        self.config = config
        oci_config, signer = get_oci_client_config(config, config.oci_region)
        client_kwargs = {"signer": signer} if signer else {}
        self.client = oci.object_storage.ObjectStorageClient(
            oci_config, **client_kwargs
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def upload_file(self, file_path: Path, object_name: str) -> str:
        with file_path.open("rb") as file_body:
            self.client.put_object(
                namespace_name=self.config.oci_namespace,
                bucket_name=self.config.oci_bucket_name,
                object_name=object_name,
                put_object_body=file_body,
            )
        return object_name

    def get_bucket(self):
        return self.client.get_bucket(
            namespace_name=self.config.oci_namespace,
            bucket_name=self.config.oci_bucket_name,
        ).data

    def get_object_text(self, object_name: str) -> str:
        response = self.client.get_object(
            namespace_name=self.config.oci_namespace,
            bucket_name=self.config.oci_bucket_name,
            object_name=object_name,
        )
        return response.data.content.decode("utf-8")

    def get_object_bytes(self, object_name: str) -> bytes:
        response = self.client.get_object(
            namespace_name=self.config.oci_namespace,
            bucket_name=self.config.oci_bucket_name,
            object_name=object_name,
        )
        return response.data.content

    def download_file(
        self,
        object_name: str,
        file_path: Path,
        *,
        max_bytes: int | None = None,
        if_match: str | None = None,
    ) -> Path:
        if max_bytes is not None and max_bytes < 1:
            raise ValueError("The download size limit must be positive.")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        kwargs = {"if_match": if_match} if if_match else {}
        response = self.client.get_object(
            namespace_name=self.config.oci_namespace,
            bucket_name=self.config.oci_bucket_name,
            object_name=object_name,
            **kwargs,
        )
        temporary_path = None
        try:
            content_length = response.headers.get("content-length")
            if (
                max_bytes is not None
                and content_length is not None
                and int(content_length) > max_bytes
            ):
                raise ValueError(
                    "The intake object exceeds the configured upload size limit."
                )
            with tempfile.NamedTemporaryFile(
                dir=file_path.parent, delete=False
            ) as target:
                temporary_path = Path(target.name)
                size = 0
                for chunk in response.data.iter_content(chunk_size=1024 * 1024):
                    size += len(chunk)
                    if max_bytes is not None and size > max_bytes:
                        raise ValueError(
                            "The intake object exceeds the configured upload size limit."
                        )
                    target.write(chunk)
            os.replace(temporary_path, file_path)
        finally:
            response.data.close()
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return file_path

    def list_objects(self, prefix: str, limit: int = 100) -> list[str]:
        response = self.client.list_objects(
            namespace_name=self.config.oci_namespace,
            bucket_name=self.config.oci_bucket_name,
            prefix=prefix,
            limit=limit,
        )
        objects: list[Any] = getattr(response.data, "objects", []) or []
        return [item.name for item in objects if getattr(item, "name", None)]

    def put_text(self, object_name: str, content: str) -> str:
        self.client.put_object(
            namespace_name=self.config.oci_namespace,
            bucket_name=self.config.oci_bucket_name,
            object_name=object_name,
            put_object_body=content.encode("utf-8"),
        )
        return object_name

    def delete_object(self, object_name: str) -> None:
        self.client.delete_object(
            namespace_name=self.config.oci_namespace,
            bucket_name=self.config.oci_bucket_name,
            object_name=object_name,
        )

    def object_uri(self, object_name: str) -> str:
        return f"oci://{self.config.oci_bucket_name}@{self.config.oci_namespace}/{object_name}"
