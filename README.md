# OCI AI Document Review Portal

A deployed Oracle Cloud Infrastructure MVP that turns uploaded business documents into structured AI review reports using Streamlit, OCI Object Storage, OCI Document Understanding, and OCI Generative AI.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

## What This Project Does

This project is a working document review portal for OCI. It is designed for business documents such as receipts, invoices, contracts, compliance files, reports, and general PDFs or images.

Users upload a document in the web portal. The platform then:

```text
1. Saves the upload locally and creates an UPLOADED metadata record.
2. Queues the document in a background worker pool so the browser does not wait on OCI processing.
3. Stores the original file in a private OCI Object Storage bucket.
4. Extracts text locally for text-native files or with OCI Document Understanding for images and image-only PDFs.
5. Normalizes extraction output into text and JSON-safe plain data.
6. Sends the extracted content to OCI Generative AI for structured review.
7. Auto-detects the document type when `Auto-detect` was selected during upload.
8. Creates a JSON metadata record and a Markdown report.
9. Shows the document in a clean Dashboard queue.
10. Opens the Actions page for AI review, human decision, lifecycle details, and downloads.
11. Lets a reviewer assign ownership, set an SLA, add workflow comments, and inspect the audit trail.
12. Lets failed documents be retried from the preserved local working copy.
13. Lets a reviewer correct the document type, then approve or reject the document.
```

The goal is not to replace human approval. The goal is to give reviewers a real, end-to-end AI-assisted workflow that reduces manual reading, highlights risks, and keeps the final decision with a person.

## What Happens After Upload

After the user clicks Queue Document, the portal accepts the file, creates a metadata record, and queues the live backend workflow. The Dashboard shows the queue while workers process documents in parallel.

```text
User uploads file
  |
  v
Local working copy saved
  |
  v
Metadata status is set to UPLOADED
  |
  v
Background worker pool accepts the job
  |
  +--> Worker 1 processes a document
  |
  +--> Worker 2 processes another document
  |
  v
Original file uploaded to OCI Object Storage
  |
  v
Text is extracted locally or with OCI Document Understanding
  |
  v
OCI Generative AI creates structured review
  |
  v
Auto-detected document type is applied when requested
  |
  v
Metadata and Markdown report are saved
  |
  v
Dashboard shows the document as Ready
  |
  v
Reviewer opens the Actions page
  |
  v
Reviewer assigns owner, SLA, workflow status, or comments
  |
  v
Reviewer approves or rejects the document
```

The Dashboard is intentionally action-oriented. It shows queue metrics, a next-action panel, global search, Upload and Actions shortcuts, split tables for Processing, Ready, Failed, and Reviewed documents, and an `Open` action directly in front of each file. The Actions page is where review work happens. It prioritizes documents that need approval, rejection, escalation, waiting-for-information follow-up, or a failed-processing fix. Documents that are ready for review show `Approve or reject`. Failed documents show `Fix and retry` until a retry is queued. Reviewed documents show `Approved` or `Rejected`. Workflow fields track status, assignee, SLA due date, comments, audit events, and retry history in the local JSON metadata. Text-native files and PDFs with selectable text go directly to GenAI after local text extraction. Image files and PDFs without usable embedded text use OCI Document Understanding first. If the upload type was `Auto-detect`, GenAI classifies the document and the reviewer can still correct the type before approval.

## Field Reference

The portal shows a `?` marker beside the main review and file fields. Hover over it in the app to see the same definitions below.

| Field | Meaning |
| --- | --- |
| Status | Processing state for the document lifecycle, from upload through approval or failure. |
| Stage | Simplified queue state shown in the Dashboard: `Queued`, `Processing`, `Ready`, `Reviewed`, or `Failed`. |
| Review | Human review decision state: `PENDING`, `APPROVED`, or `REJECTED`. |
| Risk | Highest severity found in AI risk notes. `NONE` means no risk note was returned. |
| Confidence | AI confidence score returned by the review analysis, shown as 0 to 100 percent. It is not a guarantee of correctness. |
| Action | The next human or operational step for the selected document. |
| Workflow | Human workflow state for assignment, SLA tracking, escalation, retry planning, and closure. |
| Assignee | Person, team, or queue responsible for the next action. |
| SLA | Due date for the current review workflow. |
| Retries | Number of retry attempts recorded for this document. |
| Document type | Review category chosen during upload or detected by GenAI. Reviewers can correct it before approval. |
| File name | Original uploaded file name. |
| Extension | File extension from the uploaded file name. |
| File size | Original upload size captured by the portal for new uploads. |
| MIME type | Browser-reported file content type captured during upload. |
| Business reference | Optional user-provided reference, such as invoice number, case ID, or contract ID. |
| Document ID | Internal portal identifier created for this processing run. |
| Report | Whether a Markdown review report exists on the VM. |
| Text preview | Number of extracted characters stored for quick inspection in the portal. |
| Storage | Whether the original file has an OCI Object Storage path recorded. |
| Parallel jobs | Number of background worker threads allowed to process documents at the same time. |

Confidence, extracted fields, recommendations, missing information, and risk notes are AI-assisted signals. A human reviewer must still verify the document and make the final approval or rejection decision.

## Description

This project implements an end-to-end AI document review portal on Oracle Cloud Infrastructure. Users upload PDFs, images, or text-native files through a Streamlit web interface, the app stores the originals in a private Object Storage bucket, extracts text locally or with OCI Document Understanding, analyzes the content with OCI Generative AI, and presents a queue dashboard plus a focused Actions page with summaries, risks, recommendations, approval actions, and downloadable Markdown or JSON reports.

The repository includes the application code, Terraform infrastructure, Ansible deployment automation, ASCII architecture flows, and documentation for evolving the MVP into an enterprise version with Autonomous Database, APEX or Visual Builder, Vault, Logging, Events, and Functions.

## OCI Deployment

The project is intended to be deployed from your local laptop into your own OCI compartment.

```text
Name: oci-ai-document-review
OCID: ocid1.compartment.oc1..exampleproject
Parent: ocid1.compartment.oc1..exampleparent
```

Use your own compartment OCIDs, Object Storage namespace, region, SSH key, and ingress CIDR in local files only.

## Architecture

![OCI AI Document Review architecture](docs/assets/oci-ai-document-review-architecture.png)

```text
+---------------+
| Business User |
+-------+-------+
        |
        v
+----------------------+
| Python Web Portal    |
+-------+--------------+
        |
        v
+----------------------+
| Background Worker    |
| Queue                |
+-------+--------------+
        |
        v
+----------------------+
| OCI Object Storage   |
+-------+--------------+
        |
        +----------------------+----------------------+
        |                                             |
        | text files / PDFs with text                 | images / image-only PDFs
        v                                             v
+----------------------+                 +----------------------------+
| Local Text Extract   |                 | OCI Document Understanding |
| Direct to GenAI      |                 | OCR, Tables, Key Values    |
+----------+-----------+                 +----------+-----------------+
           |                                        |
           +--------------------+-------------------+
                                |
                                v
              +-----------------------------+
              | OCI Generative AI           |
              +-------------+---------------+
                            |
                            v
              +-----------------------------+
              | Local JSON Metadata         |
              | Reports, Workflow, Audit    |
              +-------------+---------------+
                            |
                            v
              +-----------------------------+
              | Dashboard Queue             |
              | Split Tables + Next Action  |
              +-------------+---------------+
                            |
                            v
              +-----------------------------+
              | Actions Review              |
              | Decision + Workflow         |
              +-----------------------------+
```

More ASCII flows are in `docs/architecture_flows.md`.

## Platform Usage

Detailed Terraform outputs, Ansible output, deployment flow, operations commands, and portal usage instructions are in `docs/platform_usage.md`.

## Real MVP Verification

The app is wired to real OCI services. It does not use simulated processing in the runtime path.

Before processing customer documents, open `Settings` and run `OCI Preflight`. It performs live checks with the same credentials used by processing:

- Object Storage bucket reachability plus write, read, and delete.
- Document Understanding API access in the configured compartment.
- Generative AI model response in the selected GenAI region.

The processing path is:

```text
Uploaded file
  -> background worker queue
  -> private Object Storage bucket
  -> local text extraction OR OCI Document Understanding using ObjectStorageDocumentDetails
  -> JSON-safe extraction result conversion when Document Understanding is used
  -> OCI Generative AI Cohere chat model
  -> automatic document type label when Auto-detect was selected
  -> local metadata JSON
  -> Markdown report
  -> Dashboard queue
  -> Actions page
  -> workflow assignment, comments, audit, retry, approval/rejection
```

If local extraction or Document Understanding returns no text, the app fails clearly instead of sending empty content to GenAI.

PDFs that contain scanned pages or embedded images are handled through OCI Document Understanding OCR. They can take much longer than PDFs with selectable text because OCI must read the pixels on each page. Very large, low-quality, rotated, password-protected, or image-heavy PDFs may still fail or return little text. For best results, use clear scans, normal page orientation, and files below the configured upload limit.

Document Understanding calls are bounded by runtime settings:

```text
DOCUMENT_AI_TIMEOUT_SECONDS=180
DOCUMENT_AI_RETRY_ATTEMPTS=2
STALE_PROCESSING_MINUTES=12
MAX_PARALLEL_JOBS=2
```

Uploads are queued into a background worker pool. The browser returns immediately after submission, and workers process up to `MAX_PARALLEL_JOBS` documents at the same time. If a browser session is interrupted or a processing run stays in an active stage beyond the stale window, the portal marks it as `FAILED` with a retry message instead of leaving it stuck.

## Cost Estimate

An illustrative cost estimate and pricing worksheet is available in `docs/cost_estimate.md`.

This estimate is not an official Oracle quote and may not be realistic for your tenancy, usage, region, discount terms, or free tier eligibility. Use the Oracle Cost Estimator and request a formal quote from your Oracle representative before using it for budgeting or production planning.

## Setup

Create and activate a Python 3.11+ virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the setup wizard with your own local values:

```bash
python scripts/setup.py \
  --compartment-id ocid1.compartment.oc1..exampleproject \
  --parent-compartment-id ocid1.compartment.oc1..exampleparent \
  --home-region your-home-region
```

The wizard does four important things before showing region choices:

- Fetches the OCI regions subscribed in your tenancy.
- Probes each subscribed region for active OCI Generative AI chat models.
- Shows only supported GenAI regions and writes the selected region to `.env`.
- Writes a Cohere chat model id that matches the app runtime.
- Writes `allowed_ingress_cidr` from your current public IP, or stops and asks you to pass `--allowed-ingress-cidr` explicitly if IP discovery fails.

## Prepared Infrastructure

Terraform files are ready under `terraform/`.

This repository is designed for local laptop deployment. It does not include GitHub Actions or any Git-based deployment automation. Your local OCI config, API keys, `.env`, Terraform state, and real `terraform.tfvars` are ignored and must not be committed. The Terraform provider lock file is tracked so provider resolution stays consistent across machines.

Create local variables from the sample:

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Then edit `terraform/terraform.tfvars` with your own compartment OCIDs, namespace, ingress CIDR, and SSH public key path.

```bash
cd terraform
terraform init
terraform plan
```

The plan prepares a private Object Storage bucket, VCN, public subnet, private subnet, security lists, public and private route tables, Internet Gateway, NAT Gateway, Service Gateway, and compute VM. It does not use NSGs.

Deploy end to end:

```bash
./scripts/deploy.sh
```

The deployed VM uses the existing OCI API key and policies from your local OCI profile.

The release package excludes local-only files and runtime-unneeded artifacts such as `.git/`, `.env`, `.oci/`, `.venv/`, Python caches, `terraform.tfvars`, Terraform state, API keys, private keys, and local metadata. Ansible also scrubs sensitive file patterns after unpacking before writing the intended runtime `.env` and OCI SDK config.

## Run Locally

```bash
streamlit run app.py
```

The app supports:

- Document upload
- Object Storage upload
- Document Understanding extraction
- GenAI JSON analysis
- Background worker queue with parallel processing
- Markdown report generation
- Local JSON metadata
- Approve and reject review actions
- Dashboard queue view with metrics, next-action guidance, search, split queue tables, shortcuts, and per-row Open actions
- Actions page for prioritized approvals, assignment, SLA tracking, comments, audit trail, retry history, failed-document follow-up, AI summary, lifecycle, extracted text, and downloads
- Processing lifecycle view for each document
- Field guide with `?` explanations for review and file metadata fields
- OCI Preflight checks in Settings

## Future Enhancements

- Add Autonomous Database for metadata
- Add APEX or Visual Builder as enterprise frontend
- Add OCI Events and Functions for automatic processing
- Add OCI Vault for secrets
- Add OCI Logging for operational visibility
