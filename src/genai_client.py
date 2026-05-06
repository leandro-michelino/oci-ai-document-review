import json
import re

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import AppConfig
from src.models import DocumentAnalysis
from src.oci_auth import get_oci_client_config


class GenAIClient:
    def __init__(self, config: AppConfig):
        import oci

        self.config = config
        if not config.genai_model_id.lower().startswith("cohere."):
            raise ValueError(
                "This app currently supports OCI Generative AI Cohere chat models. "
                "Run scripts/setup.py again and select a Cohere chat model."
            )
        self.oci = oci
        oci_config, signer = get_oci_client_config(config, config.genai_region)
        self.client = oci.generative_ai_inference.GenerativeAiInferenceClient(
            oci_config,
            signer=signer,
            service_endpoint=config.genai_endpoint,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def analyze_document(self, prompt: str) -> DocumentAnalysis:
        raw_text = self._chat(prompt)
        payload = self._extract_json(raw_text)
        return DocumentAnalysis.model_validate(payload)

    def _chat(self, prompt: str) -> str:
        models = self.oci.generative_ai_inference.models
        request = models.CohereChatRequest(
            message=prompt,
            temperature=self.config.genai_temperature,
            max_tokens=self.config.genai_max_tokens,
        )
        details = models.ChatDetails(
            compartment_id=self.config.oci_compartment_id,
            serving_mode=models.OnDemandServingMode(model_id=self.config.genai_model_id),
            chat_request=request,
        )
        response = self.client.chat(chat_details=details)
        data = response.data
        chat_response = getattr(data, "chat_response", None)
        if chat_response and getattr(chat_response, "text", None):
            return chat_response.text
        if getattr(data, "text", None):
            return data.text
        return str(data)

    @staticmethod
    def _extract_json(text: str) -> dict:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", stripped, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))
