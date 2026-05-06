# OCI AI Document Review Portal

A deployed Oracle Cloud Infrastructure MVP that turns uploaded business documents into structured AI review reports using Streamlit, OCI Object Storage, OCI Document Understanding, and OCI Generative AI.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

## What This Project Does

This project is a working document review portal for OCI. It is designed for business documents such as receipts, invoices, contracts, compliance files, reports, and general PDFs or images.

Users upload a document in the web portal. The platform then:

```text
1. Stores the original file in a private OCI Object Storage bucket.
2. Extracts text, tables, and key values with OCI Document Understanding.
3. Sends the extracted content to OCI Generative AI for structured review.
4. Creates a JSON metadata record and a Markdown report.
5. Shows a next-action prompt asking the user to review now, open the dashboard, or upload another file.
6. Shows the result in a dashboard for human review with an action-required queue.
7. Shows a processing lifecycle so reviewers can see what completed behind the scenes.
8. Lets a reviewer approve or reject the document.
9. Provides search, filters, risk level, confidence, and report downloads.
```

The goal is not to replace human approval. The goal is to give reviewers a real, end-to-end AI-assisted workflow that reduces manual reading, highlights risks, and keeps the final decision with a person.

## What Happens After Upload

After the user clicks Process Document, the portal performs the live backend workflow and then asks for a human action.

```text
User uploads file
  |
  v
Local working copy saved
  |
  v
Original file uploaded to OCI Object Storage
  |
  v
OCI Document Understanding extracts text
  |
  v
OCI Generative AI creates structured review
  |
  v
Metadata and Markdown report are saved
  |
  v
Portal asks reviewer to choose the next action:
  Review Now, Open Dashboard, or Upload Another
  |
  v
Reviewer approves or rejects the document
```

The dashboard and Document Details page both show the same next action. Documents that are ready for review show `Approve or reject`. Failed documents show `Fix and retry`. Reviewed documents show `Approved` or `Rejected`.

## Field Reference

The portal shows a `?` marker beside the main review and file fields. Hover over it in the app to see the same definitions below.

| Field | Meaning |
| --- | --- |
| Status | Processing state for the document lifecycle, from upload through approval or failure. |
| Review | Human review decision state: `PENDING`, `APPROVED`, or `REJECTED`. |
| Risk | Highest severity found in AI risk notes. `NONE` means no risk note was returned. |
| Confidence | AI confidence score returned by the review analysis, shown as 0 to 100 percent. It is not a guarantee of correctness. |
| Action | The next human or operational step for the selected document. |
| Document type | Review category chosen during upload. It guides the GenAI prompt. |
| File name | Original uploaded file name. |
| Extension | File extension from the uploaded file name. |
| File size | Original upload size captured by the portal for new uploads. |
| MIME type | Browser-reported file content type captured during upload. |
| Business reference | Optional user-provided reference, such as invoice number, case ID, or contract ID. |
| Document ID | Internal portal identifier created for this processing run. |
| Report | Whether a Markdown review report exists on the VM. |
| Text preview | Number of extracted characters stored for quick inspection in the portal. |
| Storage | Whether the original file has an OCI Object Storage path recorded. |

Confidence, extracted fields, recommendations, missing information, and risk notes are AI-assisted signals. A human reviewer must still verify the document and make the final approval or rejection decision.

## Description

This project implements an end-to-end AI document review portal on Oracle Cloud Infrastructure. Users upload PDFs or images through a Streamlit web interface, the app stores the originals in a private Object Storage bucket, extracts text and fields with OCI Document Understanding, analyzes the content with OCI Generative AI, and presents a review dashboard with summaries, risks, recommendations, approval actions, and downloadable Markdown or JSON reports.

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
| OCI Object Storage   |
+-------+--------------+
        |
        v
+----------------------+
| Document             |
| Understanding        |
+-------+--------------+
        |
        v
+----------------------+
| OCI Generative AI    |
+-------+--------------+
        |
        v
+----------------------+
| Review Dashboard     |
+----------------------+
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
  -> private Object Storage bucket
  -> OCI Document Understanding using ObjectStorageDocumentDetails
  -> OCI Generative AI Cohere chat model
  -> local metadata JSON
  -> Markdown report
  -> human review dashboard
```

If Document Understanding returns no text, the app fails clearly instead of sending empty content to GenAI.

Document Understanding calls are bounded by runtime settings:

```text
DOCUMENT_AI_TIMEOUT_SECONDS=60
DOCUMENT_AI_RETRY_ATTEMPTS=2
STALE_PROCESSING_MINUTES=3
```

If a browser session is interrupted or a processing run stays in `PROCESSING` beyond the stale window, the portal marks it as `FAILED` with a retry message instead of leaving it stuck.

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

## Prepared Infrastructure

Terraform files are ready under `terraform/`.

This repository is designed for local laptop deployment. It does not include GitHub Actions or any Git-based deployment automation. Your local OCI config, API keys, `.env`, Terraform state, and real `terraform.tfvars` are ignored and must not be committed.

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

The release package excludes local-only files such as `.env`, `.oci/`, `terraform.tfvars`, Terraform state, API keys, private keys, and local metadata. Ansible also scrubs those file patterns after unpacking before writing the intended runtime `.env` and OCI SDK config.

## Run Locally

```bash
streamlit run app.py
```

The app supports:

- Document upload
- Object Storage upload
- Document Understanding extraction
- GenAI JSON analysis
- Post-processing next-action prompt
- Markdown report generation
- Local JSON metadata
- Approve and reject review actions
- Dashboard and detail views
- Dashboard decision panel for pending reviews
- Processing lifecycle view for each document
- Field guide with `?` explanations for review and file metadata fields
- Document Details tabs for analysis, review action, source data, and downloads
- OCI Preflight checks in Settings

## Future Enhancements

- Add Autonomous Database for metadata
- Add APEX or Visual Builder as enterprise frontend
- Add OCI Events and Functions for automatic processing
- Add OCI Vault for secrets
- Add OCI Logging for operational visibility
