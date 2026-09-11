# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    oci_config_file: str = Field(default="~/.oci/config", alias="OCI_CONFIG_FILE")
    oci_profile: str = Field(default="DEFAULT", alias="OCI_PROFILE")
    oci_auth: str = Field(default="config_file", alias="OCI_AUTH")
    oci_region: str = Field(alias="OCI_REGION", min_length=1)
    genai_region: str = Field(alias="GENAI_REGION", min_length=1)
    oci_compartment_id: str = Field(alias="OCI_COMPARTMENT_ID", min_length=1)
    oci_namespace: str = Field(alias="OCI_NAMESPACE", min_length=1)
    oci_bucket_name: str = Field(alias="OCI_BUCKET_NAME", min_length=1)

    genai_model_id: str = Field(alias="GENAI_MODEL_ID", min_length=1)
    genai_temperature: float = Field(
        default=0.2, ge=0.0, le=5.0, alias="GENAI_TEMPERATURE"
    )
    genai_max_tokens: int = Field(default=3000, ge=1, alias="GENAI_MAX_TOKENS")

    document_ai_timeout_seconds: int = Field(
        default=180, ge=1, alias="DOCUMENT_AI_TIMEOUT_SECONDS"
    )
    document_ai_retry_attempts: int = Field(
        default=2, ge=0, alias="DOCUMENT_AI_RETRY_ATTEMPTS"
    )
    stale_processing_minutes: int = Field(
        default=12, ge=1, alias="STALE_PROCESSING_MINUTES"
    )
    retention_days: int = Field(default=30, ge=1, alias="RETENTION_DAYS")
    sensitive_retention_days: int = Field(
        default=7, ge=1, alias="SENSITIVE_RETENTION_DAYS"
    )
    max_parallel_jobs: int = Field(default=5, ge=1, le=32, alias="MAX_PARALLEL_JOBS")
    max_document_chars: int = Field(default=50000, ge=1000, alias="MAX_DOCUMENT_CHARS")
    max_upload_mb: int = Field(default=10, ge=1, alias="MAX_UPLOAD_MB")
    compliance_entities_object_name: str = Field(
        default="compliance/public_sector_entities.csv",
        alias="COMPLIANCE_ENTITIES_OBJECT_NAME",
    )
    event_intake_enabled: bool = Field(default=False, alias="EVENT_INTAKE_ENABLED")
    event_intake_queue_prefix: str = Field(
        default="event-queue/", alias="EVENT_INTAKE_QUEUE_PREFIX"
    )
    event_intake_incoming_prefix: str = Field(
        default="incoming/", alias="EVENT_INTAKE_INCOMING_PREFIX"
    )
    local_metadata_dir: Path = Field(
        default=Path("data/metadata"), alias="LOCAL_METADATA_DIR"
    )
    local_reports_dir: Path = Field(
        default=Path("data/reports"), alias="LOCAL_REPORTS_DIR"
    )
    local_uploads_dir: Path = Field(
        default=Path("data/uploads"), alias="LOCAL_UPLOADS_DIR"
    )
    app_title: str = Field(default="OCI AI Document Review Portal", alias="APP_TITLE")
    case_chat_api_enabled: bool = Field(default=False, alias="CASE_CHAT_API_ENABLED")
    case_chat_api_host: str = Field(default="127.0.0.1", alias="CASE_CHAT_API_HOST")
    case_chat_api_port: int = Field(default=8081, ge=1, le=65535, alias="CASE_CHAT_API_PORT")
    case_chat_oidc_issuer: str | None = Field(default=None, alias="CASE_CHAT_OIDC_ISSUER")
    case_chat_oidc_audience: str | None = Field(default=None, alias="CASE_CHAT_OIDC_AUDIENCE")
    case_chat_oidc_jwks_url: str | None = Field(default=None, alias="CASE_CHAT_OIDC_JWKS_URL")
    case_chat_access_file: Path = Field(
        default=Path("data/case_chat_access.json"), alias="CASE_CHAT_ACCESS_FILE"
    )
    case_chat_max_context_chunks: int = Field(
        default=6, ge=1, le=12, alias="CASE_CHAT_MAX_CONTEXT_CHUNKS"
    )

    @model_validator(mode="after")
    def validate_case_chat_security(self):
        if self.case_chat_api_enabled and not all(
            value and value.strip()
            for value in (
                self.case_chat_oidc_issuer,
                self.case_chat_oidc_audience,
                self.case_chat_oidc_jwks_url,
            )
        ):
            raise ValueError(
                "CASE_CHAT_OIDC_ISSUER, CASE_CHAT_OIDC_AUDIENCE, and "
                "CASE_CHAT_OIDC_JWKS_URL are required when CASE_CHAT_API_ENABLED=true."
            )
        return self

    @field_validator("oci_auth")
    @classmethod
    def validate_oci_auth(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"config_file", "instance_principal", "instance_principals"}
        if normalized not in allowed:
            raise ValueError(
                "OCI_AUTH must be config_file, instance_principal, or instance_principals."
            )
        return normalized

    @field_validator("compliance_entities_object_name")
    @classmethod
    def validate_object_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or cleaned.startswith("/") or ".." in Path(cleaned).parts:
            raise ValueError(
                "COMPLIANCE_ENTITIES_OBJECT_NAME must be a relative Object Storage object name."
            )
        return cleaned

    @field_validator("event_intake_queue_prefix", "event_intake_incoming_prefix")
    @classmethod
    def validate_object_prefix(cls, value: str) -> str:
        cleaned = value.strip().lstrip("/")
        if not cleaned or ".." in Path(cleaned).parts:
            raise ValueError("Object Storage prefixes must be relative paths.")
        return cleaned if cleaned.endswith("/") else f"{cleaned}/"

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
