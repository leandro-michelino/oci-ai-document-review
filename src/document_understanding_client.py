from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import AppConfig
from src.models import ExtractionResult
from src.oci_auth import get_oci_client_config


class DocumentUnderstandingClient:
    def __init__(self, config: AppConfig):
        import oci

        self.config = config
        self.oci = oci
        oci_config, signer = get_oci_client_config(config, config.oci_region)
        client_kwargs = {"signer": signer} if signer else {}
        self.client = oci.ai_document.AIServiceDocumentClient(oci_config, **client_kwargs)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def extract_document(self, object_name: str) -> ExtractionResult:
        models = self.oci.ai_document.models
        details = models.AnalyzeDocumentDetails(
            compartment_id=self.config.oci_compartment_id,
            document=models.ObjectLocation(
                namespace_name=self.config.oci_namespace,
                bucket_name=self.config.oci_bucket_name,
                object_name=object_name,
            ),
            features=[
                models.DocumentTextExtractionFeature(),
                models.DocumentTableExtractionFeature(),
                models.DocumentKeyValueExtractionFeature(),
            ],
        )
        response = self.client.analyze_document(analyze_document_details=details)
        result = response.data
        return ExtractionResult(
            text=self._extract_text(result),
            tables=self._extract_tables(result),
            key_values=self._extract_key_values(result),
        )

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
    def _extract_tables(result) -> list:
        tables = []
        for page in getattr(result, "pages", []) or []:
            for table in getattr(page, "tables", []) or []:
                tables.append(table.to_dict() if hasattr(table, "to_dict") else table)
        return tables

    @staticmethod
    def _extract_key_values(result) -> dict:
        values = {}
        for page in getattr(result, "pages", []) or []:
            for field in getattr(page, "document_fields", []) or []:
                name = getattr(getattr(field, "field_name", None), "text", None)
                value = getattr(getattr(field, "field_value", None), "text", None)
                if name:
                    values[name] = value
        return values
