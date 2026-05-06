# Platform Usage Guide

This guide explains how to deploy, operate, and use the OCI AI Document Review Portal from a local laptop.

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
2. Runs terraform init.
3. Runs terraform apply.
4. Writes a temporary local Ansible inventory in .deploy/.
5. Installs required Ansible collections.
6. Runs ansible/playbook.yml.
7. Prints a structured deployment summary.
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

Recommended demo flow:

```text
1. Open the portal.
2. Go to Upload Document.
3. Choose document type:
   CONTRACT, INVOICE, COMPLIANCE, TECHNICAL_REPORT, or GENERAL.
4. Upload a PDF, PNG, JPG, or JPEG.
5. Click Process Document.
6. Wait for Object Storage upload, Document Understanding extraction, and GenAI analysis.
7. Use Review Dashboard to search, filter, and triage processed documents.
8. Review the executive summary, extracted fields, risk notes, and recommendations.
9. Approve or reject the review.
10. Download Markdown or JSON results.
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
/opt/oci-ai-document-review/data/metadata
/opt/oci-ai-document-review/data/reports
/opt/oci-ai-document-review/data/uploads
```

## Updating The App

After changing code locally:

```bash
./scripts/deploy.sh
```

The script reuses Terraform state, refreshes the app archive, reruns Ansible, updates dependencies if needed, and restarts the systemd service.

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
```

### Recreate Infrastructure

Review carefully before destroying:

```bash
cd terraform
terraform plan -destroy
terraform destroy
```

This can remove cloud resources. Local ignored files such as `.env`, `.deploy/`, and Terraform state remain on your laptop unless you delete them.
