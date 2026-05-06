# Implementation Guide

This project is deployed from a local laptop. It does not use GitHub Actions or Git-based deployment automation.

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

The deployment package is built locally by `scripts/deploy.sh`. It excludes local-only files before Ansible copies the archive to the VM:

```text
.env
.env.*
.oci/
.deploy/
.venv/
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
  -> Object Storage put_object
  -> Document Understanding analyze_document with ObjectStorageDocumentDetails
  -> GenAI CohereChatRequest
  -> metadata JSON
  -> Markdown report
```

The app records progress only after each service step completes. If Document Understanding returns no extractable text, processing fails with a clear error.

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
3. Confirm the progress log reaches Markdown report save.
4. Confirm the Review Dashboard shows REVIEW_REQUIRED.
5. Open details and verify JSON and Markdown downloads.
```

## Local App Run

For local development only:

```bash
streamlit run app.py
```
