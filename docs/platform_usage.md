# Platform Usage Guide

This guide explains how to deploy, operate, and use the OCI AI Document Review Portal from a local laptop.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.3.0`

The repository does not include GitHub Actions or CI deployment workflows. Terraform and Ansible are run locally from your laptop with your existing OCI config and policies.

## What The Platform Deploys

```text
Local laptop
  |
  | Terraform
  v
OCI infrastructure
  - Object Storage bucket
  - VCN
  - Public subnet
  - Private subnet
  - Public security list
  - Private security list
  - Public route table
  - Private route table
  - Internet Gateway
  - NAT Gateway
  - Service Gateway
  - Compute VM

Local laptop
  |
  | Ansible
  v
Compute VM
  - Python runtime
  - Streamlit app
  - background worker pool
  - systemd service
  - runtime .env
  - OCI SDK config copied from local profile
  - local JSON metadata, workflow history, and Markdown reports
```

No NSGs are used. Access is controlled with security lists.

## Local Files

These files stay on your laptop and must not be committed:

```text
.env
.deploy/
terraform/terraform.tfvars
terraform/terraform.tfstate
terraform/terraform.tfstate.backup
```

The repository includes safe examples and safe tracked configuration:

```text
.env.example
terraform/.terraform.lock.hcl
terraform/terraform.tfvars.example
```

The deploy archive excludes local-only files and directories:

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

Ansible also scrubs these file patterns after unpacking the release on the VM. Then it writes the intended runtime `.env` and OCI SDK config under `/opt/oci-ai-document-review`.

## First-Time Setup

Create a virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the guided setup wizard:

```bash
python scripts/setup.py
```

The wizard asks for the required customer values and writes local `.env` plus `terraform/terraform.tfvars`. It validates your OCI profile, validates required OCIDs, checks subscribed regions, discovers the Object Storage namespace, normalizes ingress CIDR values, and probes OCI Generative AI before asking you to choose a model.

For a repeatable install, pass values explicitly:

```bash
python scripts/setup.py \
  --compartment-id ocid1.compartment.oc1..exampleproject \
  --parent-compartment-id ocid1.compartment.oc1..exampleparent \
  --home-region your-home-region \
  --runtime-region your-runtime-region \
  --allowed-ingress-cidr 203.0.113.10/32
```

The setup wizard:

```text
1. Reads your local OCI config.
2. Validates required compartment OCIDs.
3. Fetches subscribed OCI regions.
4. Separates runtime region from GenAI region selection.
5. Discovers the Object Storage namespace.
6. Probes each region for active OCI Generative AI chat models.
7. Shows only supported GenAI regions for this app.
8. Writes a supported Cohere chat model id.
9. Writes local .env and terraform/terraform.tfvars.
```

If setup cannot discover your current public IP, it stops instead of writing an open ingress CIDR. Re-run it with `--allowed-ingress-cidr` set to a trusted CIDR such as your current public IP with `/32`. If you pass a single host IP, setup normalizes it to `/32`.

## Deploy From Laptop

Run:

```bash
./scripts/deploy.sh
```

The deploy script:

```text
1. Packages the app.
2. Excludes source-control metadata, local-only secrets, caches, tfvars, state, metadata, and upload files.
3. Runs terraform init.
4. Runs terraform apply.
5. Writes a temporary local Ansible inventory in .deploy/.
6. Installs required Ansible collections.
7. Runs ansible/playbook.yml.
8. Scrubs accidental local-only files from the VM release tree.
9. Writes the runtime .env and OCI SDK config.
10. Restarts the systemd service.
11. Prints a structured deployment summary.
```

## Terraform Outputs

After deployment:

```bash
cd terraform
terraform output
terraform output platform_summary
```

Important outputs:

```text
streamlit_url
  Browser URL for the portal.

ssh_command
  Command to connect to the VM.

bucket_name
  Object Storage bucket for uploaded documents.

genai_region
  OCI Generative AI region discovered and selected by setup.

vcn_id
  VCN created for the portal.

public_subnet_id
  Subnet used by the Streamlit VM.

private_subnet_id
  Private subnet prepared for future backend services.

internet_gateway_id
  Public route path for the Streamlit VM.

nat_gateway_id
  Private subnet outbound internet path.

service_gateway_id
  Private access path to Oracle Services Network.
```

## Ansible Output

At the end of the playbook, Ansible prints:

```text
Portal URL
SSH command
Remote app directory
Systemd service name
Service status command
Log command
Restart command
Runtime config location
Metadata directory
Reports directory
```

The same information is also printed by `scripts/deploy.sh`.

## Using The Portal

Open the `streamlit_url` output in your browser.

Before processing customer documents, go to `Settings` and run `OCI Preflight`.

The preflight performs real runtime checks:

```text
Object Storage
  - Reads bucket metadata.
  - Uploads a temporary object.
  - Reads the object back.
  - Deletes the temporary object.

Document Understanding
  - Calls the service API with the configured compartment.

Generative AI
  - Sends a short prompt to the configured Cohere chat model.
```

Recommended processing flow:

```text
1. Open the portal.
2. Go to Upload.
3. Choose document type:
   Auto-detect, CONTRACT, INVOICE, COMPLIANCE, TECHNICAL_REPORT, or GENERAL.
4. Upload a PDF, image, or text-native file such as TXT, Markdown, CSV, JSON, XML, HTML, LOG, YAML, or YML.
5. Click Queue Document.
6. The portal saves the local working copy and queues the document.
7. Choose the next action shown by the app:
   View Dashboard, Open Actions, or Upload Another.
8. Use Dashboard to watch the queue while the worker pool runs the live steps:
   Object Storage upload, local text extraction for text-native files and PDFs with selectable text, Document Understanding only for images or scanned/image-only PDFs, DU text-only OCR fallback when rich extraction fails, GenAI analysis, compliance knowledge-base lookup, compliance risk overlay, metadata/report save.
9. Use Dashboard to scan Processing, Ready, Failed, and Reviewed tables.
10. Click Open next to a document.
11. Use the Actions page to review the executive summary, key points, risks, recommendations, and supporting details.
12. Use the Workflow panel to set the workflow status, assignee, and SLA due date.
13. Add workflow comments when the reviewer needs extra context or follow-up.
14. For failed documents, use Retry Processing to create a child processing run from the preserved local working copy.
15. Inspect the audit trail and retry history in the same Workflow panel.
16. Correct the document type from the Decision panel if the detected label needs adjustment.
17. Approve or reject the review from the Decision panel. Rejections require comments.
18. Download Markdown or JSON results from the Downloads section.
```

Processing fails clearly if a required live service step fails. For example, if local extraction and Document Understanding OCR return no extractable text, the app records a failed status instead of sending empty content to GenAI.

Workflow data is stored in the same local JSON metadata record as the processing result. The app records assignee, SLA due date, workflow status, comments, audit events, parent document id for retry children, retry count, and retry history. This phase intentionally keeps the MVP on local JSON metadata; it does not introduce database persistence, user authentication, or role-based approval routing.

Scanned PDFs and PDFs made from images rely on OCR. They are slower than PDFs with selectable text because Document Understanding must read page pixels. The app first tries rich OCR/table/key-value extraction, then falls back to text-only OCR if the rich mode fails. Use clear, upright scans and keep files below `MAX_UPLOAD_MB`. Password-protected, very large, low-resolution, or heavily compressed image PDFs may still return little text or fail.

Expense-like documents are checked against the curated compliance knowledge base after GenAI analysis. The default Object Storage object is `compliance/public_sector_entities.csv`, seeded from the bundled `data/compliance/public_sector_entities.csv` file if the object is missing. The check uses extracted text, file name, business reference, notes, and selected AI fields. Matching public-sector entities or cues add a `Public-sector expense compliance review` note, route the document to `Compliance review` in Actions, and show the risk with severity-labeled badges such as `Risk Small`, `Risk Medium`, and `Risk High`. Treat this as a reviewer-routing control, not as a final compliance determination.

To update the MVP knowledge base manually, edit a CSV with this schema:

```text
entity_name,aliases,country,type,risk_level,source,source_date,notes
```

Then upload it to the configured private bucket object:

```text
compliance/public_sector_entities.csv
```

Keep `source` and `source_date` populated so the risk evidence remains auditable. Do not use live internet search as the compliance authority for this MVP.

Document Understanding calls are bounded by runtime settings:

```text
DOCUMENT_AI_TIMEOUT_SECONDS=180
DOCUMENT_AI_RETRY_ATTEMPTS=2
STALE_PROCESSING_MINUTES=12
MAX_PARALLEL_JOBS=2
```

Uploads are queued into a background worker pool. The browser returns immediately after submission, and workers process up to `MAX_PARALLEL_JOBS` documents at the same time. If a processing run remains in an active stage beyond the stale window, the app marks it as `FAILED` with a retry message.

## Review Workflow

The portal requests a human action after a document is processed.

```text
Upload
  - Saves the upload and creates the initial metadata record.
  - Queues the document in the background worker pool.
  - Asks for the next action:
    View Dashboard, Open Actions, or Upload Another.

Dashboard
  - Shows Total, Ready, Processing, and Failed metrics.
  - Shows the next document that needs a human or operational action.
  - Provides search across document name, reference, status, action, and summary.
  - Provides Upload and Actions shortcuts for common navigation.
  - Shows split queue tables for Processing, Ready, Failed, and Reviewed documents.
  - Opens each document in Actions from the Open button at the start of its row.
  - Keeps the route in the browser URL with `?page=Dashboard`.
  - Refreshes Dashboard components with a Streamlit fragment instead of full browser reloads.

Actions
  - Prioritizes documents that need approval, rejection, or failed-processing follow-up.
  - Shows a focused AI review summary with key points and recommendations.
  - Shows the Decision panel for approve or reject.
  - Keeps analysis details, file and processing details, extracted text, and downloads in expanders.
  - Requires comments before rejecting a document.
  - After approval or rejection, selects the next action item when one exists.
```

## Operating The VM

Connect with:

```bash
cd terraform
terraform output -raw ssh_command
```

Run the printed SSH command.

Useful remote commands:

```bash
sudo systemctl status oci-ai-document-review
sudo journalctl -u oci-ai-document-review -f
sudo systemctl restart oci-ai-document-review
sudo systemctl stop oci-ai-document-review
sudo systemctl start oci-ai-document-review
```

Remote paths:

```text
/opt/oci-ai-document-review
/opt/oci-ai-document-review/.env
/opt/oci-ai-document-review/.oci/config
/opt/oci-ai-document-review/.oci/oci_api_key.pem
/opt/oci-ai-document-review/data/metadata
/opt/oci-ai-document-review/data/reports
/opt/oci-ai-document-review/data/uploads
```

Expected runtime files on the VM:

```text
.env
.oci/config
.oci/oci_api_key.pem
data/metadata/*.json
data/reports/*.md
data/uploads/*
```

Unexpected runtime files on the VM:

```text
terraform/terraform.tfvars
terraform/*.tfvars
terraform/terraform.tfstate*
local laptop .env files
local private keys outside .oci/oci_api_key.pem
```

## Updating The App

After changing code locally:

```bash
./scripts/deploy.sh
```

The script reuses Terraform state, refreshes the app archive, reruns Ansible, updates dependencies if needed, and restarts the systemd service.

## End-To-End Verification

Use this checklist after any wiring or deployment change:

```text
1. terraform validate
2. ./scripts/deploy.sh
3. Confirm Terraform reports 0 unexpected infrastructure changes.
4. Confirm Ansible finishes with failed=0.
5. Confirm service is active and enabled.
6. Run OCI Preflight from Settings.
7. Upload a small real PDF or image.
8. Confirm the record reaches REVIEW_REQUIRED.
9. Confirm object_storage_path is populated.
10. Confirm analysis is populated.
11. Confirm the Markdown report exists.
12. Confirm Dashboard opens the selected record in Actions.
13. Confirm approve or reject updates the review state.
```

Useful VM commands:

```bash
sudo systemctl is-active oci-ai-document-review
sudo systemctl is-enabled oci-ai-document-review
find /opt/oci-ai-document-review -path /opt/oci-ai-document-review/.venv -prune -o -type f \( -name "terraform.tfvars" -o -name "*.tfvars" -o -name "terraform.tfstate*" \) -print
```

## Network Model

```text
+------------------------------------------------------+
| VCN                                                  |
|                                                      |
|  Public subnet                 Private subnet        |
|  - Streamlit VM                - Future services     |
|  - Public IP enabled           - Public IP disabled  |
|  - Security list allows        - Security list allows|
|    22 and 8501 from CIDR         VCN CIDR traffic    |
|                                                      |
|  Public route table            Private route table   |
|  - 0.0.0.0/0 -> IGW            - OSN -> SGW          |
|                                - 0.0.0.0/0 -> NAT GW |
|                                                      |
|  Gateways                                            |
|  - Internet Gateway for public ingress               |
|  - NAT Gateway for private outbound internet         |
|  - Service Gateway for Oracle Services Network       |
+------------------------------------------------------+
```

No NSGs are created by this Terraform configuration.

## Security Notes

```text
Use a narrow allowed_ingress_cidr, usually your current public IP with /32.
Do not commit .env.
Do not commit terraform.tfvars.
Do not commit Terraform state.
Do not commit .deploy/.
Use your existing OCI policies and API keys from your laptop.
Rotate API keys according to your security process.
Review Object Storage retention and lifecycle rules before production use.
Add OCI Vault and instance principals for a production-grade deployment.
```

## Cost Notes

The deployment can create billable resources, including Compute, Boot Volume, Object Storage, NAT Gateway, Document Understanding, and Generative AI usage.

See:

```text
docs/cost_estimate.md
```

The estimate is illustrative only. Request a formal quote from your Oracle representative before using it for budgeting or production planning.

## Troubleshooting

### Portal Does Not Open

Check:

```bash
cd terraform
terraform output -raw streamlit_url
terraform output -raw ssh_command
```

SSH to the VM and run:

```bash
sudo systemctl status oci-ai-document-review
sudo journalctl -u oci-ai-document-review -n 100
```

Also verify that your current public IP still matches `allowed_ingress_cidr` in local `terraform.tfvars`.

### Document Processing Fails

Check:

```text
OCI bucket exists.
OCI namespace is correct.
OCI policies allow the configured user to use Object Storage, Document Understanding, and Generative AI.
Selected GenAI region has active supported Cohere chat models.
Uploaded file is supported and below MAX_UPLOAD_MB.
Settings -> OCI Preflight passes.
Text-native files and PDFs with selectable text extract locally.
Images and image-only PDFs extract text with Document Understanding, with text-only OCR fallback if rich extraction fails.
Generative AI receives extracted content only after extraction succeeds.
Public-sector expense risk overlay runs after GenAI analysis and before metadata/report save.
```

### Recreate Infrastructure

Review carefully before destroying:

```bash
cd terraform
terraform plan -destroy
terraform destroy
```

This can remove cloud resources. Local ignored files such as `.env`, `.deploy/`, and Terraform state remain on your laptop unless you delete them.
