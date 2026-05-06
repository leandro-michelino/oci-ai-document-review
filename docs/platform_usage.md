# Platform Usage Guide

This guide explains how to deploy, operate, and use the OCI AI Document Review Portal from a local laptop.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

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
  - systemd service
  - runtime .env
  - OCI SDK config copied from local profile
  - local JSON metadata and Markdown reports
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

The repository includes safe examples:

```text
.env.example
terraform/terraform.tfvars.example
```

The deploy archive excludes local-only files and directories:

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

Ansible also scrubs these file patterns after unpacking the release on the VM. Then it writes the intended runtime `.env` and OCI SDK config under `/opt/oci-ai-document-review`.

## First-Time Setup

Create a virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the setup wizard:

```bash
python scripts/setup.py \
  --compartment-id ocid1.compartment.oc1..exampleproject \
  --parent-compartment-id ocid1.compartment.oc1..exampleparent \
  --home-region your-home-region
```

The setup wizard:

```text
1. Reads your local OCI config.
2. Fetches subscribed OCI regions.
3. Probes each region for active OCI Generative AI chat models.
4. Shows only supported GenAI regions for this app.
5. Writes a supported Cohere chat model id.
6. Writes local .env and terraform/terraform.tfvars.
```

## Deploy From Laptop

Run:

```bash
./scripts/deploy.sh
```

The deploy script:

```text
1. Packages the app.
2. Excludes local-only secrets, tfvars, state, metadata, and upload files.
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
2. Go to Upload Document.
3. Choose document type:
   CONTRACT, INVOICE, COMPLIANCE, TECHNICAL_REPORT, or GENERAL.
4. Upload a PDF, PNG, JPG, or JPEG.
5. Click Process Document.
6. Wait for each real step to complete:
   local working copy, Object Storage upload, Document Understanding extraction, GenAI analysis, metadata/report save.
7. Choose the next action shown by the app:
   Review Now, Open Dashboard, or Upload Another.
8. Use Review Dashboard to search, filter, triage, and approve or reject selected documents.
9. Open Document Details for tabbed analysis, review action, source preview, and downloads.
10. Review the executive summary, extracted fields, risk notes, and recommendations.
11. Approve or reject the review. Rejections require comments.
12. Download Markdown or JSON results.
```

Processing fails clearly if a required live service step fails. For example, if Document Understanding returns no extractable text, the app records a failed status instead of sending empty content to GenAI.

Document Understanding calls are bounded by runtime settings:

```text
DOCUMENT_AI_TIMEOUT_SECONDS=30
DOCUMENT_AI_RETRY_ATTEMPTS=1
STALE_PROCESSING_MINUTES=3
```

If a processing run remains in `PROCESSING` beyond the stale window, the dashboard and details page mark it as `FAILED` with a retry message.

## Review Workflow

The portal requests a human action after a document is processed.

```text
Upload Document
  - Shows real processing steps as they complete.
  - On success, asks for the next action:
    Review Now, Open Dashboard, or Upload Another.
  - On failure, shows the root error and offers Dashboard or Retry Upload.

Review Dashboard
  - Shows Action Required, High Risk, Failed, and Avg Confidence metrics.
  - Adds an Action column:
    Approve or reject, Fix and retry, Approved, Rejected, or Wait for processing.
  - Shows the selected document lifecycle:
    upload, Object Storage, Document Understanding, GenAI analysis, report, and human decision.
  - Lets the reviewer approve or reject the selected document directly.

Document Details
  - Shows status, review decision, risk, confidence, and next action.
  - Uses tabs for Lifecycle, Analysis, Review Action, Source, and Downloads.
  - Requires comments before rejecting a document.
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
Document Understanding extracted text from the file.
```

### Recreate Infrastructure

Review carefully before destroying:

```bash
cd terraform
terraform plan -destroy
terraform destroy
```

This can remove cloud resources. Local ignored files such as `.env`, `.deploy/`, and Terraform state remain on your laptop unless you delete them.
