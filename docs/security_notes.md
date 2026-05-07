# Security Notes

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

## MVP Controls

- Keep Object Storage buckets private.
- Do not commit `.env`, `terraform.tfvars`, Terraform state, `.deploy/`, OCI config files, API keys, private keys, or downloaded reports.
- Use a narrow `allowed_ingress_cidr`, ideally your current public IP with `/32`.
- Pass `--allowed-ingress-cidr` explicitly if setup cannot discover your current public IP. The setup script must not fall back to open ingress.
- Keep the Streamlit VM behind security lists only. No NSGs are created in this version.
- Use existing least-privilege OCI policies for Object Storage, Document Understanding, and Generative AI.
- Avoid logging full document text.
- Keep human review before business approval.
- Treat local JSON metadata, Markdown reports, and uploaded working copies as sensitive runtime data.

## Credential Model

The MVP deploys from your laptop and copies the existing OCI API key referenced by your local OCI profile to the VM. This keeps Git clean, but it is still a first-version credential model.

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

Workflow assignment, SLA dates, comments, audit events, retry history, extracted text previews, and AI review output are stored in local JSON metadata on the VM for this MVP. Do not move those files into Git, public buckets, public screenshots, or external posts unless they are synthetic and scrubbed.

For production, replace the copied API key with instance principals or another approved workload identity pattern, store secrets in OCI Vault, and add OCI Logging, audit review, budgets, and lifecycle policies.

## Runtime Validation

Use `Settings -> OCI Preflight` to validate live service access before processing documents. It checks Object Storage write/read/delete, Document Understanding API access, and Generative AI response with the same credentials used by processing.
