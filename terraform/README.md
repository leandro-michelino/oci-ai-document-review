# Terraform

This directory prepares the OCI resources for the MVP.

Deployment is intended to run from your laptop only. There are no GitHub Actions or CI deployment workflows in this repository.

Do not commit:

- `terraform.tfvars`
- `terraform.tfstate`
- `.env`
- OCI config files
- API keys or private keys

Prepared resources:

- Private Object Storage bucket for uploads
- VCN with public and private subnets
- Security lists only, no NSGs
- Public route table to Internet Gateway
- Private route table to NAT Gateway and Service Gateway
- Internet Gateway, NAT Gateway, and Service Gateway
- Compute VM for the Streamlit app
- Optional IAM policy for an existing admin group, disabled by default

Create or choose a project compartment before deployment:

```text
ocid1.compartment.oc1..exampleproject
```

Run the setup wizard first. It fetches subscribed OCI regions and probes OCI Generative AI before writing local config files.

```bash
python scripts/setup.py
```

Or copy the sample and edit it manually:

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Review the plan without applying:

```bash
cd terraform
terraform init
terraform plan
```

Apply only after explicit approval:

```bash
terraform apply
```
