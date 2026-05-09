# Terraform

This directory prepares the OCI resources for the MVP.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.5.1`

Deployment is intended to run from your laptop only. There are no GitHub Actions or CI deployment workflows in this repository.

Do not commit:

- `terraform.tfvars`
- `terraform.tfstate`
- `.env`
- OCI config files
- API keys or private keys

Commit `terraform/.terraform.lock.hcl`. It pins provider checksums and keeps Terraform provider resolution consistent across machines.

Prepared resources:

- Private Object Storage bucket for uploads
- Object Storage lifecycle policy that deletes uploaded document objects under `documents/` after `retention_days`
- Same private Object Storage bucket also stores the curated compliance KB object at `compliance/public_sector_entities.csv`
- Optional Object Storage Events, OCI Functions, dynamic group, and policy for automatic intake from `incoming/`
- VCN with public and private subnets
- Security lists only, no NSGs
- Public route table to Internet Gateway
- Private route table to NAT Gateway and Service Gateway
- Internet Gateway, NAT Gateway, and Service Gateway
- Compute VM for the Streamlit app
- Optional IAM policy for an existing admin group, disabled by default

Terraform does not deploy Streamlit application code. Application deployment is handled by `../scripts/deploy.sh` and `../ansible/playbook.yml` after Terraform creates or refreshes the infrastructure. Ansible writes `RETENTION_DAYS` to the VM and installs the daily local cleanup timer. When automatic processing is enabled, Ansible also installs `oci-ai-document-review-event-intake.timer` so the VM imports queue markers written by the Object Storage intake Function.

The compliance knowledge-base CSV is not a Terraform resource. The app seeds it into the existing private bucket from `../data/compliance/public_sector_entities.csv` if `COMPLIANCE_ENTITIES_OBJECT_NAME` is missing at runtime. The lifecycle policy applies only to `documents/`, so the compliance KB under `compliance/` is not deleted by the document-retention rule.

Automatic processing is optional because OCI Functions requires an OCIR image and tenancy-scope IAM for the Function resource principal. Build and push `../functions/object_intake`, then set:

```hcl
tenancy_id                          = "ocid1.tenancy.oc1..exampletenancy"
enable_automatic_processing         = true
automatic_processing_function_image = "<region-key>.ocir.io/<namespace>/<repo>:<tag>"
event_intake_incoming_prefix        = "incoming/"
event_intake_queue_prefix           = "event-queue/"
```

Terraform validates that `tenancy_id` is a valid tenancy OCID and `automatic_processing_function_image` is populated when automatic processing is enabled. The Function dynamic-group policy is scoped to the configured project bucket. External systems then upload to `incoming/<expense-name-or-reference>/<file>`. The Function normalizes prefix slashes, writes queue markers to `event-queue/`, and the VM imports those markers through the normal processing workflow.

Create or choose a project compartment before deployment:

```text
ocid1.compartment.oc1..exampleproject
```

Run the setup wizard first. It validates the OCI profile, validates compartment OCIDs, fetches subscribed OCI regions, discovers the Object Storage namespace, separates runtime region from GenAI region selection, normalizes ingress CIDRs, asks for retention days, and probes OCI Generative AI before writing local config files.

Interactive setup:

```bash
python scripts/setup.py
```

Repeatable setup:

```bash
python scripts/setup.py \
  --compartment-id ocid1.compartment.oc1..exampleproject \
  --parent-compartment-id ocid1.compartment.oc1..exampleparent \
  --home-region your-home-region \
  --runtime-region your-runtime-region \
  --allowed-ingress-cidr 203.0.113.10/32 \
  --retention-days 30
```

Optional automatic intake can also be configured from setup after the Function image is available:

```bash
python scripts/setup.py \
  --compartment-id ocid1.compartment.oc1..exampleproject \
  --parent-compartment-id ocid1.compartment.oc1..exampleparent \
  --home-region your-home-region \
  --runtime-region your-runtime-region \
  --allowed-ingress-cidr 203.0.113.10/32 \
  --enable-automatic-processing \
  --automatic-processing-function-image <region-key>.ocir.io/<namespace>/<repo>:<tag>
```

Or copy the sample and edit it manually for recovery or advanced edits:

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Review the plan without applying:

```bash
cd terraform
terraform init
terraform plan
```

Show the structured platform output after deployment:

```bash
terraform output platform_summary
```

Apply only after explicit approval:

```bash
terraform apply
```

Expected network wiring:

```text
Public subnet
  - Streamlit VM
  - Public IP enabled
  - Route table sends 0.0.0.0/0 to Internet Gateway
  - Security list allows SSH and Streamlit from allowed_ingress_cidr
  - Open ingress such as 0.0.0.0/0 is rejected by variable validation

Private subnet
  - Reserved for future backend services
  - Public IP disabled
  - Route table sends Oracle Services Network to Service Gateway
  - Route table sends 0.0.0.0/0 to NAT Gateway
  - Security list allows VCN CIDR traffic
```

No NSGs are created by this configuration.

Terraform variable validation also checks VCN/subnet CIDR syntax and requires positive flexible-shape CPU and memory values before apply.
