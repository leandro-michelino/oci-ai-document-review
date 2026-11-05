# Security Notes

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.8.0`

## MVP Controls

- Keep Object Storage buckets private.
- Do not commit `.env`, `terraform.tfvars`, Terraform state, `.deploy/`, OCI config files, API keys, private keys, or downloaded reports.
- Use a narrow `allowed_ingress_cidr`, ideally your current public IP with `/32`.
- Pass `--allowed-ingress-cidr` explicitly if setup cannot discover your current public IP. The setup script must not fall back to open ingress.
- Keep the Streamlit VM behind security lists only. No NSGs are created in this MVP version.
- Use existing least-privilege OCI policies for Object Storage, Document Understanding, and Generative AI.
- Avoid logging full document text.
- Keep human review before business approval.
- Treat local JSON metadata, Markdown reports, and uploaded working copies as sensitive runtime data.
- Retain uploaded document data for 30 days by default, unless `scripts/setup.py` is run with a customer-approved `--retention-days` value.

## Credential Model

Deployment uses the local OCI profile for Terraform. The VM defaults to `OCI_AUTH=instance_principal`: its Dynamic Group matches the exact instance OCID, Object Storage access is restricted to the application bucket, and Document Understanding/Generative AI grants are scoped to the selected compartment. The default deployment writes `.env` and does not copy the user's API key.

The optional legacy `--vm-api-key-auth` setup flag selects config-file authentication and copies the referenced API key into the VM's private `.oci` directory. Use it only when explicitly approved. Remove obsolete credential files when migrating an existing deployment to instance principals.

The lifecycle service needs a separate root IAM policy for the regional Object Storage service, restricted to the application bucket and required read/delete permissions. Terraform waits 60 seconds for initial propagation by default. Existing centrally managed policies can be used with `create_lifecycle_service_policy=false`; creation requires an appropriately authorized administrator.

The app release package excludes local `.git`, `.env`, `.oci`, `.venv`, Python caches, macOS metadata files, Terraform tfvars, Terraform state, private keys, metadata, reports, and uploaded documents. The Ansible playbook also removes sensitive and runtime-unneeded file patterns after unpacking the app release, before writing the intended runtime files.

Do not keep these local-only files in the deployed app tree:

```text
terraform/terraform.tfvars
terraform/*.tfvars
terraform/terraform.tfstate*
data/metadata/*.json
data/reports/*.md
data/uploads/*
data/deleted/*.json
local laptop .env files
local private keys (all keys in the default instance-principal mode)
```

Workflow assignment, SLA dates, comments, audit events, retry history, extracted text previews, and AI review output are stored in local JSON metadata on the VM for this MVP. Uploaded working copies are also retained locally under `/opt/oci-ai-document-review/data/uploads` so reviewers can download source documents from Actions and failed documents can be retried. A successful failed-document discard writes a limited audit tombstone under `/opt/oci-ai-document-review/data/deleted`; it contains the document ID, name, type, prior status, actor, reason, timestamp, Object Storage URI, and cloud-deletion outcome. `RETENTION_DAYS` defaults to 30 and controls local expiry for metadata, reports, and uploads; active in-flight processing records are protected. It does not currently expire deletion tombstones, so the owner must set a separate tombstone-retention control. Local cleanup runs in the app and through the daily `oci-ai-document-review-retention.timer`. Do not move those files into Git, public buckets, public screenshots, or external posts unless they are synthetic and scrubbed.

Terraform configures Object Storage lifecycle deletion for uploaded document objects under `documents/` after `retention_days`, also defaulting to 30. The compliance knowledge-base object under `compliance/` is intentionally outside that lifecycle rule.

The public-sector expense risk overlay is a deterministic reviewer-routing control for the MVP. It checks document text and metadata against the curated compliance knowledge base configured by `COMPLIANCE_ENTITIES_OBJECT_NAME`, defaulting to `compliance/public_sector_entities.csv` in Object Storage. Catalog entries use `LOW`, `MEDIUM`, and `HIGH` severity values that map to reviewer-facing small, medium, and high risk badges. Matches are auditable in the risk evidence, but they are not legal or compliance determinations. Human review remains mandatory for approval and rejection.

OCI Generative AI content-safety provider JSON is treated as operational noise, not reviewer-facing evidence. The app replaces those raw provider messages with a short manual-review explanation when displaying errors, loading old metadata, generating downloads, or regenerating reports.

For production, retain workload identity, store application secrets in OCI Vault, and add OCI Logging, audit review, budgets, and an approved retention policy.

## AI Quality And Privacy Controls

Each completed record stores the OCI model ID and prompt version. Reviewers can flag an incorrect AI field with a correction note; the feedback is retained in metadata, report output, and the audit trail for later evaluation. The bundled synthetic golden cases cover a passport, an invoice containing contact data, and a non-sensitive contract.

The portal classifies identity-document, government-identifier, email, phone, and invoice-with-personal-data signals. Restricted records show redacted text/analysis previews and block source and result downloads in this unauthenticated MVP. This is a conservative portal-wide block, not user-specific authorization. `SENSITIVE_RETENTION_DAYS` defaults to 7 and overrides local metadata/report/upload retention for restricted records; set it through setup or `.env` according to the approved retention policy.

## Runtime Validation

Use `Settings -> OCI Preflight` to validate live service access before processing documents. It checks Object Storage write/read/delete, Document Understanding API access, and Generative AI response with the same credentials used by processing.

When optional OCI Events and Functions automatic intake is enabled, keep `incoming/` uploads restricted to trusted systems and users. The Function uses resource principals; Terraform scopes the dynamic group to the deployed intake function and scopes the object policy to the configured project bucket. Queue markers under `event-queue/` contain object names and event identifiers, so treat them as operational metadata and keep the bucket private. The Function does not write VM-local metadata directly; the VM timer imports markers and applies the normal metadata, retention, review, and audit workflow.
