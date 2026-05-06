from src.models import DocumentType


GENERAL_SCHEMA = """{
  "document_class": "CONTRACT | INVOICE | COMPLIANCE | TECHNICAL_REPORT | GENERAL | UNKNOWN",
  "executive_summary": "string",
  "key_points": ["string"],
  "extracted_fields": {
    "parties": ["string"],
    "document_date": "string or null",
    "effective_date": "string or null",
    "expiration_date": "string or null",
    "total_amount": "string or null",
    "currency": "string or null",
    "payment_terms": "string or null"
  },
  "risk_notes": [
    {
      "risk": "string",
      "severity": "LOW | MEDIUM | HIGH",
      "evidence": "string"
    }
  ],
  "recommendations": ["string"],
  "missing_information": ["string"],
  "confidence_score": 0.0,
  "human_review_required": true
}"""


BASE_PROMPT = """You are an enterprise document intelligence assistant.

Analyze the extracted document text below and return a strict JSON object.

Rules:
- Do not invent information.
- If a field is not present, return null.
- Use concise business language.
- Identify risks only when supported by the document text.
- Always include a human_review_required boolean.
- Return JSON only. Do not include markdown.

Required JSON schema:
{schema}

Document text:
{text}
"""


CONTRACT_PROMPT = """You are a contract review assistant.

Analyze the contract text and return a strict JSON object matching this schema:
{schema}

Focus on parties, contract value, start date, end date, renewal, termination,
payment terms, liability, data protection, missing signatures, and business or
legal review points.

Rules:
- Do not provide legal advice.
- Highlight review points for a human legal or business reviewer.
- Do not invent fields.
- Return JSON only.

Contract text:
{text}
"""


INVOICE_PROMPT = """You are an invoice processing assistant.

Analyze the invoice text and return a strict JSON object matching this schema:
{schema}

Focus on supplier, customer, invoice number, invoice date, due date, PO number,
total amount, currency, tax, payment terms, and potential anomalies.

Rules:
- Do not invent values.
- If a field is not present, return null.
- Return JSON only.

Invoice text:
{text}
"""


def build_prompt(document_type: DocumentType, extracted_text: str, max_chars: int) -> str:
    text = extracted_text[:max_chars]
    template = BASE_PROMPT
    if document_type == DocumentType.CONTRACT:
        template = CONTRACT_PROMPT
    elif document_type == DocumentType.INVOICE:
        template = INVOICE_PROMPT
    return template.format(schema=GENERAL_SCHEMA, text=text)
