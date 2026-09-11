# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
"""Private API consumed by ODA through API Gateway. It has no mutation routes."""
from __future__ import annotations

from functools import lru_cache

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from src.case_chat import (
    NO_ANSWER, CaseAccessPolicy, CaseEvidenceRetriever, answer_has_valid_citations,
    build_case_answer_prompt,
)
from src.config import AppConfig, get_config
from src.genai_client import GenAIClient
from src.metadata_store import MetadataStore

bearer = HTTPBearer(auto_error=False)
app = FastAPI(title="OCI AI Document Review Case Chat API", docs_url=None, redoc_url=None)


class CaseQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=1200)


class CaseAnswer(BaseModel):
    answer: str
    evidence_ids: list[str]
    human_review_required: bool = True


@lru_cache
def _jwks_client(url: str):
    return jwt.PyJWKClient(url, cache_keys=True)


def authenticated_subject(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    config: AppConfig = Depends(get_config),
) -> str:
    if not config.case_chat_api_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer token required")
    try:
        key = _jwks_client(str(config.case_chat_oidc_jwks_url)).get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(
            credentials.credentials, key.key, algorithms=[key.algorithm_name],
            audience=config.case_chat_oidc_audience, issuer=config.case_chat_oidc_issuer,
        )
        subject = claims.get("sub")
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token") from exc
    if not isinstance(subject, str) or not subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token subject is missing")
    return subject


def get_store(config: AppConfig = Depends(get_config)) -> MetadataStore:
    return MetadataStore(config)


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/cases/{document_id}/chat", response_model=CaseAnswer)
def chat_about_case(
    document_id: str,
    payload: CaseQuestion,
    subject: str = Depends(authenticated_subject),
    config: AppConfig = Depends(get_config),
    store: MetadataStore = Depends(get_store),
) -> CaseAnswer:
    if not CaseAccessPolicy(config.case_chat_access_file).permits(document_id, subject):
        # Do not reveal whether an unauthorised document exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    try:
        record = store.load(document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found") from exc
    evidence = CaseEvidenceRetriever(config.case_chat_max_context_chunks).retrieve(record, payload.question)
    if not evidence:
        return CaseAnswer(answer=NO_ANSWER, evidence_ids=[])
    answer = GenAIClient(config).answer_case_question(build_case_answer_prompt(payload.question, evidence)).strip()
    if not answer_has_valid_citations(answer, evidence):
        answer = NO_ANSWER
    return CaseAnswer(answer=answer, evidence_ids=[item.evidence_id for item in evidence])
