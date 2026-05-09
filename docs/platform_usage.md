# Platform Usage Guide

This guide explains how to deploy, operate, and use the OCI AI Document Review Portal from a local laptop.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.4.0`

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

The wizard asks for the required customer values and writes local `.env` plus `terraform/terraform.tfvars`. It validates your OCI profile, validates required OCIDs, checks subscribed regions, discovers the Object Storage namespace, normalizes ingress CIDR values, asks for the retention period, and probes OCI Generative AI before asking you to choose a model. Retention defaults to 30 days.

For a repeatable install, pass values explicitly:

```bash
python scripts/setup.py \
  --compartment-id ocid1.compartment.oc1..exampleproject \
  --parent-compartment-id ocid1.compartment.oc1..exampleparent \
  --home-region your-home-region \
  --runtime-region your-runtime-region \
  --allowed-ingress-cidr 203.0.113.10/32 \
  --retention-days 30
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
9. Writes RETENTION_DAYS and Terraform retention_days.
10. Writes local .env and terraform/terraform.tfvars.
```

If setup cannot discover your current public IP, it stops instead of writing an open ingress CIDR. Re-run it with `--allowed-ingress-cidr` set to a trusted CIDR such as your current public IP with `/32`. If you pass a single host IP, setup normalizes it to `/32`. Explicit open ingress such as `0.0.0.0/0` is rejected.

## Deploy From Laptop

Run:

```bash
./scripts/deploy.sh
```

GitHub is not the live deployment target. Committing and pushing source changes preserves them in the remote repository, but the running portal changes only after this local deployment script builds a new release archive, copies it to the VM, and restarts the `oci-ai-document-review` service.

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

For a code-only redeploy, Terraform should normally show `No changes`; the important app update happens in the Ansible tasks named `Unpack app release` and `Start portal service`.

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

retention_days
  Days to keep VM-local data and uploaded Object Storage document objects.

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
4. Upload one to five PDFs, images, or text-native files such as TXT, Markdown, CSV, JSON, XML, HTML, LOG, YAML, or YML.
5. If more than one file is selected, enter an Expense name or reference. The app requires it for multi-file uploads and stores it on every file in that upload.
6. Click Queue Document or Queue Documents.
7. The portal validates file count, required expense name or reference, extension, empty-file state, configured size limit, and PDF page-count warning before queueing.
8. The portal saves the local working copies and queues one document record per file.
9. Choose the next action shown by the app:
   View Dashboard, Open Actions, or Upload Another.
10. Use Dashboard to watch the queue while the worker pool runs the live steps:
   Object Storage upload, local text extraction for text-native files and PDFs with selectable text, Document Understanding only for images or scanned/image-only PDFs, automatic limit-safe OCR chunks for scanned PDFs above OCI's synchronous request limits, DU text-only OCR fallback when rich extraction fails, GenAI analysis, compliance knowledge-base lookup, compliance risk overlay, metadata/report save.
11. Use Dashboard to scan Ready, Processing, Failed, and Reviewed tabs. Multi-file uploads stay grouped under their shared Expense name or reference in the collapsed Expense groups area and as compact cards inside each phase queue. Active rows show how long they have been working, and stale runs are marked failed automatically during Dashboard refresh. Use the Status filter to narrow the queue to Approved, Rejected, Reviewed, Failed, Processing, Needs decision, Compliance review, Fix and retry, or Retry planned.
12. Click Review on a single file or on a compact expense group. Group cards open the best next actionable file first and keep the file list collapsed under Show files until the reviewer needs the details.
13. Use the Actions page to review the selected-file summary. Open linked files, source document, workflow, analysis, lifecycle, extracted text, and downloads only when needed.
14. Correct the document type from the top Decision panel if the detected label needs adjustment.
15. Approve or reject the review from the top Decision panel. Rejections require comments.
16. Open the `Workflow, notes, retry, and audit` expander to set the workflow status, assignee, and SLA due date.
17. Add workflow comments when the reviewer needs extra context or follow-up.
18. For failed documents, use Retry Processing to create a child processing run from the preserved local working copy.
19. Inspect the audit trail and retry history in the same Workflow expander.
20. Open the AI review summary expander to review the executive summary, key points, receipt or invoice items and services, risks, recommendations, and supporting details when the decision needs deeper analysis.
21. Download Markdown or JSON results from the Downloads section.
```

Processing fails clearly if a required live service step fails. For example, if local extraction and Document Understanding OCR return no extractable text, the app records a failed status instead of sending empty content to GenAI.

Workflow data is stored in the same local JSON metadata record as the processing result. The app records assignee, SLA due date, workflow status, comments, audit events, parent document id for retry children, retry count, and retry history. This phase intentionally keeps the MVP on local JSON metadata; it does not introduce database persistence, user authentication, or role-based approval routing.

Future phase option: add a customer document chatbot that answers read-only questions from the same workflow data. The assistant can answer questions such as `What is the status of my file?`, `Why was it rejected?`, `Who is reviewing it?`, `When is the SLA due?`, or `What do I need to retry?`. It should retrieve from document metadata, audit events, workflow comments, reports, extracted summaries, and approval decisions, then answer with the relevant document id and next step. It should not change review state or expose documents outside the authenticated customer context.

Scanned PDFs and PDFs made from images rely on OCR. They are slower than PDFs with selectable text because Document Understanding must read page pixels. The app first tries rich OCR/table/key-value extraction, then falls back to text-only OCR if the rich mode fails. Scanned PDFs above OCI's synchronous request limits are split into temporary chunks and merged before GenAI analysis. Chunk object names keep the original file stem and add `_1`, `_2`, and so on, for example `Receipt_21Apr2026_112647_1.pdf`, so logs and temporary Object Storage activity remain understandable. Use clear, upright scans and keep files below `MAX_UPLOAD_MB`. Password-protected, very large, low-resolution, single-page files above the synchronous OCR size limit, or heavily compressed image PDFs may still return little text or fail.

Expense-like documents are checked against the curated compliance knowledge base after GenAI analysis. The default Object Storage object is `compliance/public_sector_entities.csv`, seeded from the bundled `data/compliance/public_sector_entities.csv` file if the object is missing. The check uses extracted text, file name, business reference, notes, and selected AI fields. Matching public-sector entities or cues add a `Public-sector expense compliance review` note, route the document to `Compliance review` in Actions, and show the risk with severity-labeled badges such as `Risk Small`, `Risk Medium`, and `Risk High`. The catalog uses `LOW`, `MEDIUM`, and `HIGH` values so routine public-service fees can be lower severity, generic public-sector cues can be medium severity, and public officials, facilitation payments, political contributions, sanctions, conflicts of interest, or sole-source exceptions can be high severity. Treat this as a reviewer-routing control, not as a final compliance determination.

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
  - Accepts up to five files per submission.
  - Requires an expense name or reference when more than one file is selected.
  - Saves each upload and creates one initial metadata record per file.
  - Stores the shared expense name or reference on each record so Dashboard and Actions can keep the files together.
  - Queues the document in the background worker pool.
  - Asks for the next action:
    View Dashboard, Open Actions, or Upload Another.

Dashboard
  - Shows Total, Ready, Processing, and Failed metrics.
  - Shows the next document that needs a human or operational action.
  - Provides search across document name, reference, status, action, and summary.
  - Provides Upload and Actions shortcuts for common navigation.
  - Keeps multi-file uploads together in a collapsed Expense groups area and as compact expense/reference cards in each phase queue.
  - Gives each compact expense/reference card one Review button and a collapsed Show files detail area.
  - Opens the best next actionable file first when Review is clicked on a multi-file group.
  - Shows elapsed working time for active processing rows.
  - Shows Ready, Processing, Failed, and Reviewed as tabs below one search and status-filter area.
  - Opens single files in Actions from the row action button.
  - Keeps the route in the browser URL with `?page=Dashboard`.
  - Refreshes Dashboard components with a Streamlit fragment instead of full browser reloads.
  - Marks stale active records as failed during refresh so stuck uploads do not remain in Processing forever.

Actions
  - Prioritizes documents that need approval, rejection, or failed-processing follow-up.
  - Starts with `Select document group` so reviewers can choose all documents or a specific expense/reference group before choosing a file.
  - Labels the selector as `Selected file for review` and includes file name, document ID, expense/reference, stage, and upload time in each option.
  - Repeats the selected file name, document ID, linked-file count, workflow state, SLA, and risk/action badges in a compact summary above the Decision panel.
  - Keeps linked files for the same Expense name or reference inside a collapsed expander.
  - Aggregates each multi-file expense/reference group inside that expander with file count, files needing decision, files needing fix, total extracted items/services, total risks, and Items / Services by file when line items exist.
  - Places the Decision panel near the top of the page so reviewers can correct the type, approve, or reject without scrolling through the full analysis first.
  - Shows a `Download Doc for Review` button when the VM still has the local working copy.
  - Keeps Workflow, notes, retry, retry history, and audit trail in one expander.
  - Shows a focused AI review summary in an expander with key points, receipt or invoice items and services, and recommendations.
  - Keeps source document, analysis details, file and processing details, extracted text, and downloads in expanders.
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

The default retention period is 30 days. The Streamlit app deletes expired local JSON metadata, Markdown reports, and preserved upload copies from the VM while protecting active in-flight records. Ansible installs `oci-ai-document-review-retention.timer` so the same local cleanup also runs daily on the VM. Terraform configures Object Storage lifecycle deletion for uploaded objects under `documents/` after the same number of days. The compliance knowledge base object under `compliance/` is outside that lifecycle rule.

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
.venv/bin/pytest
git status --short
git add <changed-files>
git commit -m "<message>"
git push origin main
./scripts/deploy.sh
```

The script reuses Terraform state, refreshes the app archive, reruns Ansible, updates dependencies if needed, and restarts the systemd service. The push and the VM deployment are intentionally both listed: GitHub records the release, while `./scripts/deploy.sh` applies it to `/opt/oci-ai-document-review` on the VM.

Verify the live VM after deployment:

```bash
ssh -i ~/.ssh/id_rsa opc@<vm-public-ip> "grep -n 'def dashboard_metrics_html' /opt/oci-ai-document-review/app.py && grep -n 'st.markdown(dashboard_metrics_html(metric_cards)' /opt/oci-ai-document-review/app.py && sudo systemctl is-active oci-ai-document-review"
curl -fsS -I http://<vm-public-ip>:8501
```

For the Dashboard `At a glance` cards specifically, the deployed `app.py` should contain `dashboard_metrics_html()`. That helper emits the metric cards as one compact HTML block, which prevents Streamlit Markdown from treating later card markup as an indented code block.

For Actions source downloads, the deployed `app.py` should contain `render_source_document_download()`. It reads the local working copy from `/opt/oci-ai-document-review/data/uploads` and exposes it through a `Download Doc for Review` button for the approver.

For OCI Generative AI content-safety failures, the deployed source should contain `src/safety_messages.py`. That helper replaces raw provider JSON such as `InvalidParameter` and `Inappropriate content detected` before it reaches UI display, metadata reloads, JSON downloads, or regenerated Markdown reports.

Runtime configuration is validated before the app starts. Invalid auth modes, negative or zero processing limits, out-of-range GenAI temperature, and unsafe compliance knowledge-base object names fail fast instead of starting a misconfigured service.

## End-To-End Verification

Use this checklist after any wiring or deployment change:

```text
1. .venv/bin/pytest
2. terraform validate
3. git commit and git push origin main, when the change should be recorded remotely.
4. ./scripts/deploy.sh
5. Confirm Terraform reports 0 unexpected infrastructure changes for code-only deploys.
6. Confirm Ansible finishes with failed=0 and restarts the service.
7. Confirm the deployed file under /opt/oci-ai-document-review contains the expected code.
8. Confirm service is active and enabled.
9. Hard refresh the browser or reopen the Streamlit URL.
10. Run OCI Preflight from Settings.
11. Upload a small real PDF or image.
12. Confirm the record reaches REVIEW_REQUIRED.
13. Confirm object_storage_path is populated.
14. Confirm analysis is populated.
15. Confirm the Markdown report exists.
16. Confirm Dashboard Review opens the selected single file or the best next actionable file from a compact multi-file group.
17. Confirm Actions shows the Decision panel near the top and the `Download Doc for Review` button when the local working copy exists.
18. Confirm approve or reject updates the review state.
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
Review Object Storage retention and lifecycle rules before production use. The default deployment deletes uploaded document objects after 30 days.
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
