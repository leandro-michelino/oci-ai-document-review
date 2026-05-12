# Implementation Guide

This project is deployed from a local laptop. It does not use GitHub Actions or Git-based deployment automation.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.5.1`

## Local Preparation

Recommended end-to-end path:

```bash
./setup.sh
```

The root setup script creates or refreshes `.venv`, installs dependencies, runs the guided OCI setup wizard, validates the repository, runs Terraform, deploys with Ansible, waits for the Streamlit port, and prints the portal URL. Use `./setup.sh --configure-only` to stop after configuration, or `./setup.sh --deploy-only` to deploy from existing `.env` and `terraform/terraform.tfvars`.

Manual preparation:

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

The wizard prompts for customer-specific values, validates the OCI profile and API key, discovers subscribed regions, reads the Object Storage namespace, probes supported OCI Generative AI chat models, asks for the runtime retention period, and writes both `.env` and `terraform/terraform.tfvars`. It does not create OCI resources. Retention defaults to 30 days.

For repeatable automation, provide the required values explicitly:

```bash
python scripts/setup.py \
  --compartment-id ocid1.compartment.oc1..exampleproject \
  --parent-compartment-id ocid1.compartment.oc1..exampleparent \
  --home-region your-home-region \
  --runtime-region your-runtime-region \
  --allowed-ingress-cidr 203.0.113.10/32 \
  --retention-days 30
```

Before showing GenAI choices, setup reads your OCI subscriptions and probes OCI Generative AI for active supported chat models. The app currently uses OCI SDK `CohereChatRequest`, so setup writes a Cohere chat model id.

The wizard keeps runtime and GenAI region selection separate. Runtime region hosts compute, networking, Object Storage, and Document Understanding. GenAI region is selected only from discovered supported chat-model regions. In non-interactive mode, setup validates the supplied OCIDs and subscribed regions; if `--runtime-region` is omitted, it uses the OCI profile region. The wizard also writes a narrow `allowed_ingress_cidr`; host IPs are normalized to `/32`, and setup rejects explicit open ingress instead of falling back to it.

The same retention value is written to `.env` as `RETENTION_DAYS` and to Terraform as `retention_days`. The app uses it for VM-local metadata, Markdown reports, and preserved upload copies. Ansible also installs `oci-ai-document-review-retention.timer` so the VM runs local cleanup daily even when nobody opens the Streamlit page. Terraform uses the value for the Object Storage lifecycle policy that deletes uploaded document objects under `documents/`.

Optional automatic intake is configured by the same setup and Terraform path. Use `--enable-automatic-processing` only after the `functions/object_intake` image has been built and pushed to OCIR, then provide `--automatic-processing-function-image`. The setup script normalizes incoming and queue prefixes as relative Object Storage prefixes, then writes the Function image, incoming prefix, queue prefix, polling interval, and tenancy OCID into `terraform/terraform.tfvars`.

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
./setup.sh --deploy-only
```

`setup.sh --deploy-only` runs validation and then calls `scripts/deploy.sh`. The deploy script packages the app, runs Terraform, waits for SSH on the Terraform-created VM, runs Ansible, starts the systemd service, verifies the public portal URL from the laptop, and prints an end-to-end summary of what Terraform deployed and what Ansible configured. If you have already validated locally and want the lower-level deploy command, run `./scripts/deploy.sh` directly.

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
  -> one to five files
  -> mandatory expense name or reference when more than one file is selected
  -> local working copies
  -> one metadata record per file, with shared expense name or reference when supplied
  -> metadata status UPLOADED
  -> background worker pool
  -> Object Storage put_object
  -> local extraction for text files and PDFs with selectable text
  -> Document Understanding OCR for images, scanned PDFs, and image-only PDFs
  -> temporary limit-safe OCR chunks for scanned PDFs above OCI's synchronous limits
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

Optional automatic intake adds an Object Storage event path without replacing the Streamlit upload path:

```text
External upload to incoming/<expense-name-or-reference>/<file>
  -> Object Storage object-created event
  -> OCI Events rule
  -> OCI Function functions/object_intake
  -> JSON queue marker under event-queue/
  -> VM systemd timer runs scripts/poll_event_queue.py
  -> marker importer downloads the incoming object
  -> one metadata record with document type Auto-detect
  -> same background worker pool and review workflow as portal uploads
```

This keeps Dashboard and Actions consistent while avoiding direct writes from a Function to VM-local metadata.

The app records progress only after each service step completes. If local extraction and Document Understanding OCR return no extractable text, processing fails with a clear error instead of sending empty content to GenAI.

Document Understanding calls use a bounded timeout and retry configuration:

```text
DOCUMENT_AI_TIMEOUT_SECONDS=180
DOCUMENT_AI_RETRY_ATTEMPTS=2
STALE_PROCESSING_MINUTES=12
MAX_PARALLEL_JOBS=5
```

The app validates runtime configuration before startup. Invalid OCI auth modes, zero or negative processing limits, out-of-range GenAI temperature, and unsafe compliance knowledge-base object names fail fast.

Scanned PDFs and PDFs that contain page images use OCR. The app first tries rich Document Understanding extraction for OCR, tables, and key-values. If a scanned PDF has more than 5 pages or a chunk is above the synchronous file-size limit, the processor writes smaller temporary PDF chunks, uploads each chunk to Object Storage, runs Document Understanding on each chunk, merges text/tables/key-values, and deletes the temporary chunk objects. Chunk Object Storage names are based on the original file stem plus a sequence number, such as `Receipt_21Apr2026_112647_1.pdf` and `Receipt_21Apr2026_112647_2.pdf`, instead of opaque chunk names. If rich extraction fails but text-only OCR succeeds, the app still sends the OCR text to GenAI and records the source as `OCI Document Understanding text-only OCR fallback`. Scanned files need more time than text-based PDFs and can fail if the scan is low quality, rotated, password-protected, too large, or above the upload limit.

Uploads are queued into a background worker pool. The browser returns immediately after submission, and workers process up to `MAX_PARALLEL_JOBS` documents at the same time. If a browser session is interrupted or a processing run remains in an active stage beyond the stale window, the app marks it as `FAILED` so the reviewer can retry instead of waiting indefinitely.

The Dashboard route is synchronized to `?page=Dashboard`, so browser refresh stays on the Dashboard instead of returning to Upload. The Dashboard body runs inside a Streamlit fragment and refreshes every 10 seconds while the session is active. That updates metrics, queue table rows, active elapsed-time labels, stale processing cleanup, and tabbed queue sections without using a full browser reload. Dashboard metric cards are emitted as one compact HTML block through `dashboard_metrics_html()` so Streamlit Markdown does not treat later cards as escaped code text.

The Upload page validates basic requirements before queueing: up to five files, mandatory expense name or reference when more than one file is selected, supported extension, non-empty file, and `MAX_UPLOAD_MB`. Ansible starts Streamlit with `--server.maxUploadSize` set to the same value, so the browser uploader and app validation show the same per-file limit. It also blocks image OCR uploads above the current OCI synchronous file-size limit. For PDFs, it attempts to read the local page count. PDFs above the OCI synchronous OCR page or file-size limit are allowed and the user is informed that scanned pages will be processed in chunks. If the page count cannot be read locally, the user sees a warning that encrypted, damaged, or password-protected PDFs may fail during extraction.

The Dashboard, Actions, and Reviewed pages display the stored expense name or reference so reviewers can keep related files from the same multi-file upload together end to end. Dashboard shows individual files and multi-file expense/reference groups in the same compact selectable queue tables. A group row shows file count, stage summary, target action, highest risk, confidence range, SLA, owner, and the first target file; `Review selected` opens the best next actionable file, preferring compliance review and approval work before retry, active, or reviewed records. Actions keeps linked files for the same expense/reference inside an expander beside the selected document context. The Actions selector is labeled `Selected file for review`, and each option includes the exact file name, document ID, expense/reference, stage, and upload time so duplicate or similar file names are easier to distinguish. The selected record summary repeats the file name, document ID, linked-file count, workflow, SLA, current action, and risk. For multi-file expense/reference groups, Actions shows group aggregation inside the linked-files expander: total files, files needing decision, files needing fix, total extracted items/services, total risk notes, and an Items / Services by file table when line items are present. The Actions page shows the AI review summary before the Decision panel, then keeps Workflow, notes, retry, audit, source document, analysis details, lifecycle, extracted text, and downloads in expanders so reviewers expand only what they need. The Reviewed page is a closed-work archive for approved and rejected documents, with summary metrics, search, and Approved/Rejected filtering; its table uses `Open selected` to revisit the stored decision context. It uses the preserved local working copy in `data/uploads` and shows a `Download Doc for Review` button so the reviewer can open the original file locally. If the working copy is missing, the reviewer still sees metadata, lifecycle details, extracted text, and generated analysis.

After GenAI returns structured analysis, the app applies a deterministic compliance overlay. It checks extracted text, file name, business reference, notes, and selected AI fields against the curated entity catalog configured by `COMPLIANCE_ENTITIES_OBJECT_NAME`, defaulting to `compliance/public_sector_entities.csv` in Object Storage. If the object is missing, the app seeds it from the bundled `data/compliance/public_sector_entities.csv` file and falls back locally if Object Storage cannot be reached.

Expense-like documents that match public-sector entries such as `gov`, ministries, municipalities, state agencies, public officials, or named entities such as ZIMSEC are flagged with a `Public-sector expense compliance review` note. The evidence records the knowledge-base source, matched term, entity type, country, source, and source date. The catalog supports `LOW`, `MEDIUM`, and `HIGH` values so lower-signal entries show as `Risk Small`, broader public-sector cues show as `Risk Medium`, and stronger cues such as public officials, facilitation payments, political contributions, sanctions, conflicts of interest, or sole-source exceptions show as `Risk High`. These documents show as `Compliance review` in the Actions queue. This is a reviewer-routing control for the MVP, not a final compliance determination.

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

## Retention

The default retention period is 30 days. `RETENTION_DAYS` controls local cleanup on the VM for `data/metadata`, `data/reports`, and `data/uploads`. Active records in `UPLOADED`, `PROCESSING`, `EXTRACTED`, or `AI_ANALYZED` are protected from local cleanup so in-flight work is not removed mid-processing. Closed, failed, approved, rejected, and review-required records expire from their `processed_at` timestamp when available, otherwise from `uploaded_at`. Cleanup runs when the app starts/renders and through the daily `oci-ai-document-review-retention.timer` systemd timer.

Terraform configures `oci_objectstorage_object_lifecycle_policy.documents_retention` for the private bucket. It deletes only objects with the `documents/` prefix after `retention_days`, so the curated compliance knowledge base at `compliance/public_sector_entities.csv` remains available.

## Automatic Object Intake

Set `enable_automatic_processing = true` in `terraform/terraform.tfvars` only after building and pushing the `functions/object_intake` image to OCIR, setting `automatic_processing_function_image`, and keeping `tenancy_id` populated with the tenancy OCID discovered by setup. Terraform then enables Object Storage object events on the private bucket, validates the intake prefixes, creates the Functions application and function in the private subnet, creates an Events rule for Object Storage create events in the bucket, and creates a resource-principal IAM dynamic group scoped to the deployed intake function plus a bucket-scoped policy.

The Function normalizes incoming and queue prefixes, filters for objects under `incoming/`, and writes queue markers under `event-queue/`. Ansible enables `oci-ai-document-review-event-intake.timer` on the VM when Terraform reports automatic processing as enabled. The timer imports queue markers every `event_intake_poll_seconds` seconds. Objects outside `incoming/` are ignored by the Function, and generated queue markers are not processed as documents.

The Function is deliberately small: it writes queue markers only. It does not write VM-local metadata, call Document Understanding, call Generative AI, approve documents, or bypass the normal Dashboard and Actions review workflow.

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
5. Select an individual Dashboard row and open it with Review selected. For multi-file submissions, confirm the group row opens the best next actionable file from the same table.
6. Confirm the Actions page shows the Decision panel near the top, before the source download and full AI analysis.
7. Confirm multi-file Actions pages show group aggregation and Items / Services by file when line items were extracted.
8. Confirm the Actions page shows the `Download Doc for Review` button when the local working copy exists.
9. Confirm the Actions page shows AI summary, key points, and recommendations.
10. Confirm the Workflow panel can assign an owner, set an SLA, add a comment, and show an audit event.
11. For a failed document, confirm Retry Processing creates a child record and the original shows retry history.
12. Confirm the reviewer can correct the document type if needed.
13. Confirm JSON and Markdown downloads are available and include workflow metadata.
14. Confirm approve or reject updates the review state, closes the workflow, and moves to the next action item when one exists.
15. After approval or rejection, open Reviewed and confirm the closed document appears with the correct decision filter.
16. Upload or simulate a public-sector expense and confirm the correct small, medium, or high compliance attention risk is added.
```

## Local App Run

For local development only:

```bash
streamlit run app.py --server.maxUploadSize=10
```

Use your configured `MAX_UPLOAD_MB` value if you changed the default.
