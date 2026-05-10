# Security Notes

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.5.1`

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

The MVP deploys from your laptop and copies the existing OCI API key referenced by your local OCI profile to the VM. This keeps Git clean, but it is still an early-version credential model.

Expected runtime credential files on the VM:

```text
/opt/oci-ai-document-review/.env
/opt/oci-ai-document-review/.oci/config
/opt/oci-ai-document-review/.oci/oci_api_key.pem
```

These files are created by Ansible during deployment. They are not committed to Git.

The app release package excludes local `.git`, `.env`, `.oci`, `.venv`, Python caches, macOS metadata files, Terraform tfvars, Terraform state, private keys, metadata, reports, and uploaded documents. The Ansible playbook also removes sensitive and runtime-unneeded file patterns after unpacking the app release, before writing the intended runtime files.

Do not keep these local-only files in the deployed app tree:

```text
terraform/terraform.tfvars
terraform/*.tfvars
terraform/terraform.tfstate*
data/metadata/*.json
data/reports/*.md
data/uploads/*
local laptop .env files
local private keys outside /opt/oci-ai-document-review/.oci/oci_api_key.pem
```

Workflow assignment, SLA dates, comments, audit events, retry history, extracted text previews, and AI review output are stored in local JSON metadata on the VM for this MVP. Uploaded working copies are also retained locally under `/opt/oci-ai-document-review/data/uploads` so reviewers can download source documents from Actions and failed documents can be retried. `RETENTION_DAYS` defaults to 30 and controls local expiry for metadata, reports, and uploads; active in-flight processing records are protected. Local cleanup runs in the app and through the daily `oci-ai-document-review-retention.timer`. Do not move those files into Git, public buckets, public screenshots, or external posts unless they are synthetic and scrubbed.

Terraform configures Object Storage lifecycle deletion for uploaded document objects under `documents/` after `retention_days`, also defaulting to 30. The compliance knowledge-base object under `compliance/` is intentionally outside that lifecycle rule.

The public-sector expense risk overlay is a deterministic reviewer-routing control for the MVP. It checks document text and metadata against the curated compliance knowledge base configured by `COMPLIANCE_ENTITIES_OBJECT_NAME`, defaulting to `compliance/public_sector_entities.csv` in Object Storage. Catalog entries use `LOW`, `MEDIUM`, and `HIGH` severity values that map to reviewer-facing small, medium, and high risk badges. Matches are auditable in the risk evidence, but they are not legal or compliance determinations. Human review remains mandatory for approval and rejection.

OCI Generative AI content-safety provider JSON is treated as operational noise, not reviewer-facing evidence. The app replaces those raw provider messages with a short manual-review explanation when displaying errors, loading old metadata, generating downloads, or regenerating reports.

For production, replace the copied API key with instance principals or another approved workload identity pattern, store secrets in OCI Vault, and add OCI Logging, audit review, budgets, and lifecycle policies.

## Runtime Validation

Use `Settings -> OCI Preflight` to validate live service access before processing documents. It checks Object Storage write/read/delete, Document Understanding API access, and Generative AI response with the same credentials used by processing.

When optional OCI Events and Functions automatic intake is enabled, keep `incoming/` uploads restricted to trusted systems and users. The Function uses resource principals; Terraform scopes the dynamic group to the deployed intake function and scopes the object policy to the configured project bucket. Queue markers under `event-queue/` contain object names and event identifiers, so treat them as operational metadata and keep the bucket private. The Function does not write VM-local metadata directly; the VM timer imports markers and applies the normal metadata, retention, review, and audit workflow.
