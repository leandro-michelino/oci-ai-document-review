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
7. Confirm the reviewer can correct the document type if needed.
8. Confirm JSON and Markdown downloads are available.
9. Confirm approve or reject updates the review state.
```

## Local App Run

For local development only:

```bash
streamlit run app.py
```
