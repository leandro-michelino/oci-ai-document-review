# Implementation Guide

This project is deployed from a local laptop. It does not use GitHub Actions or Git-based deployment automation.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.3.0`

## Local Preparation

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Setup Wizard

Run the guided setup wizard:

```bash
python scripts/setup.py
```

The wizard prompts for customer-specific values, validates the OCI profile and API key, discovers subscribed regions, reads the Object Storage namespace, probes supported OCI Generative AI chat models, and writes both `.env` and `terraform/terraform.tfvars`. It does not create OCI resources.

For repeatable automation, provide the required values explicitly:

```bash
python scripts/setup.py \
  --compartment-id ocid1.compartment.oc1..exampleproject \
  --parent-compartment-id ocid1.compartment.oc1..exampleparent \
  --home-region your-home-region \
  --runtime-region your-runtime-region \
  --allowed-ingress-cidr 203.0.113.10/32
```

Before showing GenAI choices, setup reads your OCI subscriptions and probes OCI Generative AI for active supported chat models. The app currently uses OCI SDK `CohereChatRequest`, so setup writes a Cohere chat model id.

The wizard keeps runtime and GenAI region selection separate. Runtime region hosts compute, networking, Object Storage, and Document Understanding. GenAI region is selected only from discovered supported chat-model regions. In non-interactive mode, setup validates the supplied OCIDs and subscribed regions; if `--runtime-region` is omitted, it uses the OCI profile region. The wizard also writes a narrow `allowed_ingress_cidr`; host IPs are normalized to `/32`, and setup rejects explicit open ingress instead of falling back to it.

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
  -> local extraction for text files and PDFs with selectable text
  -> Document Understanding OCR for images, scanned PDFs, and image-only PDFs
  -> DU text-only OCR fallback when rich table/key-value extraction fails
  -> JSON-safe extraction result conversion when Document Understanding is used
  -> GenAI CohereChatRequest
  -> curated compliance knowledge-base lookup from Object Storage
  -> compliance risk overlay and Actions routing
  -> automatic document type label when Auto-detect was selected
  -> metadata JSON
  -> Markdown report
  -> Dashboard queue with URL-backed page state and fragment refresh
  -> Actions page
  -> workflow status, assignee, SLA, comments, audit trail, retry history
  -> approve or reject, then move to the next action item when available
```

The app records progress only after each service step completes. If local extraction and Document Understanding OCR return no extractable text, processing fails with a clear error instead of sending empty content to GenAI.

Document Understanding calls use a bounded timeout and retry configuration:

```text
DOCUMENT_AI_TIMEOUT_SECONDS=180
DOCUMENT_AI_RETRY_ATTEMPTS=2
STALE_PROCESSING_MINUTES=12
MAX_PARALLEL_JOBS=2
```

The app validates runtime configuration before startup. Invalid OCI auth modes, zero or negative processing limits, out-of-range GenAI temperature, and unsafe compliance knowledge-base object names fail fast.

Scanned PDFs and PDFs that contain page images use OCR. The app first tries rich Document Understanding extraction for OCR, tables, and key-values. If that rich extraction fails but text-only OCR succeeds, the app still sends the OCR text to GenAI and records the source as `OCI Document Understanding text-only OCR fallback`. Scanned files need more time than text-based PDFs and can fail if the scan is low quality, rotated, password-protected, too large, or above the upload limit.

Uploads are queued into a background worker pool. The browser returns immediately after submission, and workers process up to `MAX_PARALLEL_JOBS` documents at the same time. If a browser session is interrupted or a processing run remains in an active stage beyond the stale window, the app marks it as `FAILED` so the reviewer can retry instead of waiting indefinitely.

The Dashboard route is synchronized to `?page=Dashboard`, so browser refresh stays on the Dashboard instead of returning to Upload. The Dashboard body runs inside a Streamlit fragment and refreshes every 10 seconds while the session is active. That updates metrics and split queue tables without using a full browser reload. Dashboard metric cards are emitted as one compact HTML block through `dashboard_metrics_html()` so Streamlit Markdown does not treat later cards as escaped code text.

The Actions page includes a Source document section before the AI review area. It uses the preserved local working copy in `data/uploads` and shows a `Download Doc for Review` button so the reviewer can open the original file locally. If the working copy is missing, the reviewer still sees metadata, lifecycle details, extracted text, and generated analysis.

After GenAI returns structured analysis, the app applies a deterministic compliance overlay. It checks extracted text, file name, business reference, notes, and selected AI fields against the curated entity catalog configured by `COMPLIANCE_ENTITIES_OBJECT_NAME`, defaulting to `compliance/public_sector_entities.csv` in Object Storage. If the object is missing, the app seeds it from the bundled `data/compliance/public_sector_entities.csv` file and falls back locally if Object Storage cannot be reached.

Expense-like documents that match public-sector entries such as `gov`, ministries, municipalities, state agencies, public officials, or named entities such as ZIMSEC are flagged with a `Public-sector expense compliance review` note. The evidence records the knowledge-base source, matched term, entity type, country, source, and source date. These documents show as `Compliance review` in the Actions queue with severity-labeled risk badges such as `Risk Small`, `Risk Medium`, and `Risk High`. This is a reviewer-routing control for the MVP, not a final compliance determination.

OCI Generative AI content-safety failures are normalized through `src/safety_messages.py`. New worker failures, existing metadata loads, preflight display, JSON downloads, and regenerated Markdown reports replace raw provider JSON with a reviewer-safe explanation.

## Compliance Knowledge Base

The default seeded catalog is tracked in Git at:

```text
data/compliance/public_sector_entities.csv
```

At runtime, the app reads the catalog from the private Object Storage bucket object configured by:

```text
COMPLIANCE_ENTITIES_OBJECT_NAME=compliance/public_sector_entities.csv
```

The file can be CSV or JSON. The CSV schema is:

```text
entity_name,aliases,country,type,risk_level,source,source_date,notes
```

Aliases are separated with `|`. The matcher uses whole-word normalized matching so short aliases such as `gov` match `lunch with gov customer` but do not match unrelated words such as `governance`. If the Object Storage object is missing, the app uploads the bundled seed file and then uses the Object Storage copy as the source of truth.

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

## Next Phase: Customer Document Chatbot

A future implementation can add a read-only chatbot that lets customers ask questions about the documents they uploaded. Example questions:

```text
What is the status of my file?
Why was my receipt rejected?
Who is reviewing my contract?
When is the SLA due?
What documents failed and need retry?
What risks were found in my invoice?
```

Recommended implementation shape:

```text
Customer question
  -> authenticated customer/session context
  -> document lookup by allowed document ids, file names, or references
  -> retrieval from metadata, audit events, workflow comments, extracted summary, and report text
  -> OCI Generative AI response with strict grounding instructions
  -> answer with cited document id, status, action, reviewer decision, and next step
```

The chatbot should be grounded in application records only. It should not search the internet, expose raw provider errors, disclose another customer document, or change approval state. Actions such as approve, reject, retry, assignment, and SLA changes should remain in the reviewer workflow until explicit role-based authorization is added.

For the MVP repository, the bot can read the existing JSON metadata and Markdown reports. For the enterprise phase, move the same data into Autonomous Database and add an access-control layer keyed by customer, tenant, project, or case id.

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
6. Confirm the Actions page shows the `Download Doc for Review` button when the local working copy exists.
7. Confirm the Actions page shows AI summary, key points, and recommendations.
8. Confirm the Workflow panel can assign an owner, set an SLA, add a comment, and show an audit event.
9. For a failed document, confirm Retry Processing creates a child record and the original shows retry history.
10. Confirm the reviewer can correct the document type if needed.
11. Confirm JSON and Markdown downloads are available and include workflow metadata.
12. Confirm approve or reject updates the review state, closes the workflow, and moves to the next action item when one exists.
13. Upload or simulate a public-sector expense and confirm a high compliance attention risk is added.
```

## Local App Run

For local development only:

```bash
streamlit run app.py
```
