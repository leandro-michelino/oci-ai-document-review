from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import AppConfig
from src.oci_auth import get_oci_client_config


class ObjectStorageClient:
    def __init__(self, config: AppConfig):
        import oci

        self.config = config
        oci_config, signer = get_oci_client_config(config, config.oci_region)
        client_kwargs = {"signer": signer} if signer else {}
        self.client = oci.object_storage.ObjectStorageClient(oci_config, **client_kwargs)

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

    def delete_object(self, object_name: str) -> None:
        self.client.delete_object(
            namespace_name=self.config.oci_namespace,
            bucket_name=self.config.oci_bucket_name,
            object_name=object_name,
        )

    def object_uri(self, object_name: str) -> str:
        return f"oci://{self.config.oci_bucket_name}@{self.config.oci_namespace}/{object_name}"
