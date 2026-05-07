# Implementation Guide

This project is deployed from a local laptop. It does not use GitHub Actions or Git-based deployment automation.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

## Local Preparation

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Setup Wizard

Run setup with your own compartment values:

```bash
python scripts/setup.py \
  --compartment-id ocid1.compartment.oc1..exampleproject \
  --parent-compartment-id ocid1.compartment.oc1..exampleparent \
  --home-region your-home-region
```

The wizard writes both `.env` and `terraform/terraform.tfvars`. It does not create OCI resources.

Before showing region choices, it reads your OCI subscriptions and probes OCI Generative AI for active supported chat models. The app currently uses OCI SDK `CohereChatRequest`, so setup writes a Cohere chat model id.

The wizard also writes a narrow `allowed_ingress_cidr`. If automatic public IP discovery fails, setup stops and asks for an explicit `--allowed-ingress-cidr` instead of falling back to open ingress.

## Review And Deploy

Review local files:

```text
.env
terraform/terraform.tfvars
```

Review Terraform without applying:

```bash
cd terraform
terraform init
terraform plan
```

Deploy end to end from the repo root:

```bash
./scripts/deploy.sh
```

The deploy script runs Terraform, packages the app, runs Ansible, starts the systemd service, and prints the portal URL plus operations commands.

## Release Package Hygiene

The deployment package is built locally by `scripts/deploy.sh`. It excludes local-only and runtime-unneeded files before Ansible copies the archive to the VM:

```text
.git/
.env
.env.*
.oci/
.deploy/
.venv/
.pytest_cache/
.ruff_cache/
*/__pycache__/
*.pyc
.DS_Store
._*
terraform/terraform.tfvars
terraform/*.tfvars
terraform/*.tfvars.json
terraform/terraform.tfstate*
*.pem
*.key
id_rsa*
oci_api_key*
data/metadata/*.json
data/reports/*.md
data/uploads/*
```

After unpacking, Ansible removes the same local-only file patterns from the app directory, excluding the intended runtime `.oci` directory. Then it writes:

```text
/opt/oci-ai-document-review/.env
/opt/oci-ai-document-review/.oci/config
/opt/oci-ai-document-review/.oci/oci_api_key.pem
```

## Runtime Wiring

The MVP uses real OCI services in sequence:

```text
Streamlit upload
  -> local working copy
  -> metadata status UPLOADED
  -> background worker pool
  -> Object Storage put_object
  -> local extraction for text files and text PDFs OR Document Understanding for images and image-only PDFs
  -> JSON-safe extraction result conversion when Document Understanding is used
  -> GenAI CohereChatRequest
  -> metadata JSON
  -> Markdown report
  -> Dashboard queue
  -> Actions page
  -> workflow status, assignee, SLA, comments, audit trail, retry history
```

The app records progress only after each service step completes. If local extraction or Document Understanding returns no extractable text, processing fails with a clear error.

Document Understanding calls use a bounded timeout and retry configuration:

```text
DOCUMENT_AI_TIMEOUT_SECONDS=180
DOCUMENT_AI_RETRY_ATTEMPTS=2
STALE_PROCESSING_MINUTES=12
MAX_PARALLEL_JOBS=2
```

Scanned PDFs and PDFs that contain page images use OCR. They need more time than text-based PDFs and can fail if the scan is low quality, rotated, password-protected, too large, or above the upload limit.

Uploads are queued into a background worker pool. The browser returns immediately after submission, and workers process up to `MAX_PARALLEL_JOBS` documents at the same time. If a browser session is interrupted or a processing run remains in an active stage beyond the stale window, the app marks it as `FAILED` so the reviewer can retry instead of waiting indefinitely.

## Document Lifecycle Workflow

Lifecycle data is deliberately stored in the existing local JSON metadata layer for this MVP phase. Each document record can now hold:

```text
parent_document_id
assignee
due_at
workflow_status
workflow_comments[]
audit_events[]
retry_count
retry_history[]
```

The Actions page writes these fields through `MetadataStore` methods, not by editing UI-only state:

```text
set_workflow()
  -> updates workflow status, assignee, due date
  -> appends WORKFLOW_UPDATED audit event

add_comment()
  -> appends workflow comment
  -> appends COMMENT_ADDED audit event

record_retry()
  -> increments retry_count
  -> appends retry_history item
  -> marks the original as RETRY_PLANNED
  -> appends RETRY_QUEUED audit event

set_review()
  -> approves or rejects the processing record
  -> closes workflow status
  -> appends review audit event
```

Failed-document retry creates a new child document id, copies the preserved local working file into a retry source file, saves a child metadata record with `parent_document_id`, and submits that child record back to the background worker pool. The original failed record keeps its retry history and audit trail.

Markdown reports are refreshed from the latest metadata when workflow fields, comments, retries, review status, or document type change.

## Preflight

Open `Settings` and run `OCI Preflight` after deployment. It uses the same runtime credentials as processing and verifies:

```text
Object Storage write/read/delete
Document Understanding API access
Generative AI model response
```

## Verification

Run these checks before publishing the article or showing the MVP:

```bash
terraform validate
.venv/bin/ruff check .
.venv/bin/pytest -q
ansible-playbook --syntax-check ansible/playbook.yml
./scripts/deploy.sh
```

Then on the portal:

```text
1. Run OCI Preflight in Settings.
2. Upload a small PDF or image.
3. Choose Auto-detect once and confirm the record receives a concrete document type.
4. Confirm Dashboard shows the record as Ready.
5. Open the record from Dashboard.
6. Confirm the Actions page shows AI summary, key points, and recommendations.
7. Confirm the Workflow panel can assign an owner, set an SLA, add a comment, and show an audit event.
8. For a failed document, confirm Retry Processing creates a child record and the original shows retry history.
9. Confirm the reviewer can correct the document type if needed.
10. Confirm JSON and Markdown downloads are available and include workflow metadata.
11. Confirm approve or reject updates the review state and closes the workflow.
```

## Local App Run

For local development only:

```bash
streamlit run app.py
```
