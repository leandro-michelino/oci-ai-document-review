import time
from typing import Any

from src.config import AppConfig
from src.models import ExtractionResult
from src.oci_auth import get_oci_client_config


class DocumentUnderstandingClient:
    def __init__(self, config: AppConfig):
        import oci

        self.config = config
        self.oci = oci
        oci_config, signer = get_oci_client_config(config, config.oci_region)
        client_kwargs = {"timeout": (10, config.document_ai_timeout_seconds)}
        if signer:
            client_kwargs["signer"] = signer
        self.client = oci.ai_document.AIServiceDocumentClient(
            oci_config, **client_kwargs
        )

    def extract_document(self, object_name: str) -> ExtractionResult:
        last_error = ""
        for attempt in range(1, self.config.document_ai_retry_attempts + 1):
            try:
                return self._extract_document_inline(object_name)
            except Exception as exc:
                last_error = str(exc).strip() or exc.__class__.__name__
                try:
                    return self._extract_document_inline(
                        object_name, rich_features=False
                    )
                except Exception as fallback_exc:
                    fallback_error = (
                        str(fallback_exc).strip() or fallback_exc.__class__.__name__
                    )
                    last_error = (
                        f"{last_error}; text-only OCR fallback failed: "
                        f"{fallback_error}"
                    )
                if attempt < self.config.document_ai_retry_attempts:
                    time.sleep(min(2**attempt, 10))
        raise RuntimeError(f"OCI Document Understanding failed: {last_error}")

    def _extract_document_inline(
        self, object_name: str, rich_features: bool = True
    ) -> ExtractionResult:
        models = self.oci.ai_document.models
        features = [models.DocumentTextExtractionFeature()]
        if rich_features:
            features.extend(
                [
                    models.DocumentTableExtractionFeature(),
                    models.DocumentKeyValueExtractionFeature(),
                ]
            )
        details = models.AnalyzeDocumentDetails(
            compartment_id=self.config.oci_compartment_id,
            document=models.ObjectStorageDocumentDetails(
                source="OBJECT_STORAGE",
                namespace_name=self.config.oci_namespace,
                bucket_name=self.config.oci_bucket_name,
                object_name=object_name,
            ),
            features=features,
        )
        response = self.client.analyze_document(analyze_document_details=details)
        result = response.data
        return ExtractionResult(
            text=self._extract_text(result),
            tables=self._extract_tables(result) if rich_features else [],
            key_values=self._extract_key_values(result) if rich_features else {},
            source=(
                "OCI Document Understanding"
                if rich_features
                else "OCI Document Understanding text-only OCR fallback"
            ),
        )

    def list_recent_work_requests(self) -> int:
        response = self.client.list_work_requests(
            compartment_id=self.config.oci_compartment_id,
            limit=1,
        )
        return len(getattr(response.data, "items", []) or [])

    @staticmethod
    def _extract_text(result) -> str:
        if getattr(result, "pages", None):
            page_text = []
            for page in result.pages:
                for line in getattr(page, "lines", []) or []:
                    text = getattr(line, "text", None)
                    if text:
                        page_text.append(text)
            return "\n".join(page_text)
        return getattr(result, "document_text", None) or ""

    @staticmethod
    def _to_plain(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return [DocumentUnderstandingClient._to_plain(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): DocumentUnderstandingClient._to_plain(item)
                for key, item in value.items()
            }
        if hasattr(value, "to_dict"):
            return DocumentUnderstandingClient._to_plain(value.to_dict())
        try:
            import oci

            converted = oci.util.to_dict(value)
            if converted is not value:
                return DocumentUnderstandingClient._to_plain(converted)
        except Exception:
            pass
        if hasattr(value, "__dict__"):
            return DocumentUnderstandingClient._to_plain(vars(value))
        return str(value)

    @staticmethod
    def _extract_tables(result) -> list:
        tables = []
        for page in getattr(result, "pages", []) or []:
            for table in getattr(page, "tables", []) or []:
                tables.append(DocumentUnderstandingClient._to_plain(table))
        return tables

    @staticmethod
    def _extract_key_values(result) -> dict:
        values = {}
        for page in getattr(result, "pages", []) or []:
            for field in getattr(page, "document_fields", []) or []:
                name = getattr(getattr(field, "field_name", None), "text", None)
                value = getattr(getattr(field, "field_value", None), "text", None)
                if name:
                    values[name] = (
                        value
                        if value is not None
                        else DocumentUnderstandingClient._to_plain(
                            getattr(field, "field_value", None)
                        )
                    )
        return values
