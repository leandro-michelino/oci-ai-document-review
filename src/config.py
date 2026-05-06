from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    oci_config_file: str = Field(default="~/.oci/config", alias="OCI_CONFIG_FILE")
    oci_profile: str = Field(default="DEFAULT", alias="OCI_PROFILE")
    oci_auth: str = Field(default="config_file", alias="OCI_AUTH")
    oci_region: str = Field(alias="OCI_REGION")
    genai_region: str = Field(alias="GENAI_REGION")
    oci_compartment_id: str = Field(alias="OCI_COMPARTMENT_ID")
    oci_namespace: str = Field(alias="OCI_NAMESPACE")
    oci_bucket_name: str = Field(alias="OCI_BUCKET_NAME")

    genai_model_id: str = Field(alias="GENAI_MODEL_ID")
    genai_temperature: float = Field(default=0.2, alias="GENAI_TEMPERATURE")
    genai_max_tokens: int = Field(default=3000, alias="GENAI_MAX_TOKENS")

    document_ai_timeout_seconds: int = Field(default=30, alias="DOCUMENT_AI_TIMEOUT_SECONDS")
    document_ai_retry_attempts: int = Field(default=1, alias="DOCUMENT_AI_RETRY_ATTEMPTS")
    stale_processing_minutes: int = Field(default=3, alias="STALE_PROCESSING_MINUTES")
    max_document_chars: int = Field(default=50000, alias="MAX_DOCUMENT_CHARS")
    max_upload_mb: int = Field(default=10, alias="MAX_UPLOAD_MB")
    local_metadata_dir: Path = Field(default=Path("data/metadata"), alias="LOCAL_METADATA_DIR")
    local_reports_dir: Path = Field(default=Path("data/reports"), alias="LOCAL_REPORTS_DIR")
    local_uploads_dir: Path = Field(default=Path("data/uploads"), alias="LOCAL_UPLOADS_DIR")
    app_title: str = Field(default="OCI AI Document Review Portal", alias="APP_TITLE")

    @property
    def expanded_oci_config_file(self) -> str:
        return str(Path(self.oci_config_file).expanduser())

    @property
    def genai_endpoint(self) -> str:
        return f"https://inference.generativeai.{self.genai_region}.oci.oraclecloud.com"


@lru_cache
def get_config() -> AppConfig:
    config = AppConfig()
    config.local_metadata_dir.mkdir(parents=True, exist_ok=True)
    config.local_reports_dir.mkdir(parents=True, exist_ok=True)
    config.local_uploads_dir.mkdir(parents=True, exist_ok=True)
    return config
