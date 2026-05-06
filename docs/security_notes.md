# Security Notes

## MVP Controls

- Keep Object Storage buckets private.
- Do not commit `.env`, `terraform.tfvars`, Terraform state, `.deploy/`, OCI config files, API keys, private keys, or downloaded reports.
- Use a narrow `allowed_ingress_cidr`, ideally your current public IP with `/32`.
- Keep the Streamlit VM behind security lists only. No NSGs are created in this version.
- Use existing least-privilege OCI policies for Object Storage, Document Understanding, and Generative AI.
- Avoid logging full document text.
- Keep human review before business approval.

## Credential Model

The MVP deploys from your laptop and copies the existing OCI API key referenced by your local OCI profile to the VM. This keeps Git clean, but it is still a demo-friendly credential model.

For production, replace the copied API key with instance principals or another approved workload identity pattern, store secrets in OCI Vault, and add OCI Logging, audit review, budgets, and lifecycle policies.
