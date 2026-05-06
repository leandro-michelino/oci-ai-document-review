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

## Local App Run

For local development only:

```bash
streamlit run app.py
```
