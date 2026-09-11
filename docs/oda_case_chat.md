# ODA Case Chat, grounded and document-scoped

This integration lets an authenticated user ask questions about a document they
are permitted to access. It is deliberately read-only. It cannot upload a file,
approve or reject a review, update workflow fields, download a source document,
or search across cases.

## What is available now, and what remains optional

The Streamlit portal has a floating **Case assistant** button in its
bottom-right corner. It is a local, document-scoped RAG demonstration: the
user selects a portal record, asks a question, and receives an answer from
retrieved evidence for that record only. It is useful for demonstrations and
for validating answer quality with the existing reviewer workflow.

This embedded panel is not an ODA instance and it does not add portal sign-in
or per-user authorisation to Streamlit. Deploy it only where portal access is
already restricted to the intended reviewers. The optional ODA path below is
the customer-facing integration: it adds authenticated end-user identity,
default-deny case access, and a private API boundary.

## Trust boundary

```text
Authenticated ODA user
  -> ODA skill with OAuth account linking
  -> OCI API Gateway, JWT validation and private route
  -> case-chat API on the review VM
  -> metadata store and OCI Generative AI
```

The API validates the OIDC access token itself and uses its `sub` claim. API
Gateway should validate the same issuer and audience before forwarding the
request. The API must not be exposed through the public Streamlit listener.
For a private Gateway route, set `CASE_CHAT_API_HOST` to the VM private address
or `0.0.0.0`, restrict the VM security list/NSG to the Gateway subnet, and do
not open port 8081 to the internet. `127.0.0.1` is the safe default and needs a
local reverse proxy only for development.

## Retrieval and GenAI controls

For each request, the service:

1. validates the bearer JWT issuer, audience, signature, and `sub`;
2. checks `data/case_chat_access.json` for exactly that `document_id` and
   subject. Missing, malformed, or empty ACLs deny access;
3. creates retrieval chunks only from the selected record's status, workflow,
   human-review comments, generated analysis, and extracted fields;
4. ranks those chunks against the question and sends at most six to OCI
   Generative AI;
5. requires evidence citations (`[E1]`, `[E2]`, etc.). Answers without valid
   citations are replaced with a safe refusal.

For records marked `RESTRICTED`, the raw extracted-text preview is excluded
from retrieval. The chat response always says that human review is required.

The API ACL is fail-closed. Missing files, malformed JSON, unreadable files,
and unknown subjects all produce no access. The API returns `404` for an
unauthorised case so it does not disclose whether a document exists.

## Configure the protected service

Set these values in the VM `.env`, or pass their corresponding deployment
variables. Do not enable the service until all OIDC values are real.

```dotenv
CASE_CHAT_API_ENABLED=true
CASE_CHAT_API_HOST=10.0.2.15
CASE_CHAT_API_PORT=8081
CASE_CHAT_OIDC_ISSUER=https://identity.example.com/
CASE_CHAT_OIDC_AUDIENCE=oci-document-review-case-chat
CASE_CHAT_OIDC_JWKS_URL=https://identity.example.com/.well-known/jwks.json
CASE_CHAT_ACCESS_FILE=data/case_chat_access.json
```

Create the ACL file with the VM app-user permissions (`0640` is appropriate).
Subjects are exact OIDC `sub` values, not display names or email addresses.

```json
{
  "document-uuid-1": ["00u123example", "00u456reviewer"],
  "document-uuid-2": ["00u789customer"]
}
```

Changing this file changes access immediately. Maintain it through the future
identity/workflow integration, not through the chatbot. Do not put access
tokens, client secrets, or documents in the ACL file.

## Deployment behaviour

The default configuration is safe for customers that do not choose ODA:
`CASE_CHAT_API_ENABLED=false`. In that mode no FastAPI case-chat systemd
service is installed or started. The existing Streamlit portal, including the
embedded demonstrator, continues to run normally.

When the flag is `true`, Ansible writes the OIDC settings, installs
`oci-ai-document-review-case-chat.service`, starts it, and checks
`/healthz` locally. It does not create an ODA instance, a Gateway deployment,
an identity application, an ACL file, or network rules. Those customer-specific
resources require the tenancy's approved identity and network design.

## Configure ODA and API Gateway

1. In ODA, create a `Case Review` skill and enable OAuth account linking to the
   same OIDC identity domain used by the API. The REST call must forward the
   end-user bearer token, not a shared service token, because authorization is
   per document.
2. In API Gateway, create a private deployment whose backend is the private
   case-chat endpoint. Require JWT authentication with the configured issuer
   and audience, preserve the `Authorization` header, and allow only `POST
   /v1/cases/{document_id}/chat`.
3. Register the REST service in ODA using the Gateway base URL and the OpenAPI
   contract in [`oda/case-review-openapi.yaml`](../oda/case-review-openapi.yaml).
4. Implement a short dialog flow: collect a document ID, collect a question,
   invoke `askAboutCase`, show `answer`, and offer escalation to the assignee.
   Treat `401` as sign-in required and `404` as "case unavailable" without
   stating whether the document exists.
5. Test with two users and two records: a permitted user gets only their case;
   the other user gets `404`. Test a restricted document and an unsupported
   question, which must receive the safe refusal.

ODA supports REST-service calls and OAuth backend authentication, but its
console settings and identity-domain options vary by tenancy. This repository
therefore supplies the deployable API and contract, rather than pretending to
provision your ODA instance or its identity application without tenancy access.
