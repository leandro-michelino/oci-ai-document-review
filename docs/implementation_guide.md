# Implementation Guide

1. Create a Python 3.11+ virtual environment.
2. Install `requirements-dev.txt`.
3. Run `python scripts/setup.py`.
4. Review `.env` and `terraform/terraform.tfvars`.
5. Run `terraform plan` from `terraform/`.
6. Apply Terraform only after explicit approval.
7. Start the portal with `streamlit run app.py`.

The wizard writes both `.env` and `terraform/terraform.tfvars`. It does not create OCI resources.

Create or choose a project compartment before deployment:

```text
ocid1.compartment.oc1..exampleproject
```
