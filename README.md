# OCI AI Document Review Portal

A deployed Oracle Cloud Infrastructure demo that turns uploaded business documents into structured AI review reports using Streamlit, OCI Object Storage, OCI Document Understanding, and OCI Generative AI.

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

Run the setup wizard:

```bash
python scripts/setup.py
```

The wizard does three important things before showing region choices:

- Fetches the OCI regions subscribed in your tenancy.
- Probes each subscribed region for active OCI Generative AI chat models.
- Shows only GenAI-capable regions and writes the selected region to `.env`.

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

## Run Locally

```bash
streamlit run app.py
```

The app supports:

- Document upload
- Object Storage upload
- Document Understanding extraction
- GenAI JSON analysis
- Markdown report generation
- Local JSON metadata
- Approve and reject review actions
- Dashboard and detail views

## Future Enhancements

- Add Autonomous Database for metadata
- Add APEX or Visual Builder as enterprise frontend
- Add OCI Events and Functions for automatic processing
- Add OCI Vault for secrets
- Add OCI Logging for operational visibility
