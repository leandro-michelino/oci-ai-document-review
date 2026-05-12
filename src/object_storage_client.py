# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from pathlib import Path
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

    def download_file(self, object_name: str, file_path: Path) -> Path:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(self.get_object_bytes(object_name))
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
