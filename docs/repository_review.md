# Repository Review

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.3.0`

## Scope

This review covers the Streamlit app, worker queue, OCI clients, metadata store, report generation, Terraform, Ansible deployment, setup wizard, tests, documentation, and ASCII architecture flows.

## Fixes Applied

- Re-ran full validation across the Streamlit app, tests, Terraform, and Ansible syntax after the dashboard filter, chatbot documentation, and architecture updates.
- Added Dashboard status filtering documentation and ASCII flow coverage for Approved, Rejected, Reviewed, Failed, Processing, Needs decision, Compliance review, Fix and retry, and Retry planned states.
- Added Phase 2 customer chatbot documentation and ASCII flow coverage for read-only status, rejection reason, retry, owner, SLA, and risk-summary questions.
- Replaced the Actions inline source preview with a `Download Doc for Review` button, avoiding optional Streamlit PDF dependencies on the VM.
- Added runtime configuration validation for OCI auth mode, GenAI temperature, processing limits, upload limits, worker count, and compliance knowledge-base object name.
- Added Terraform variable validation for ingress CIDR, network CIDRs, OCPU count, and memory size.
- Updated setup validation so explicit open ingress such as `0.0.0.0/0` fails before Terraform is written.
- Kept content-safety provider JSON sanitization in shared code so UI, metadata reloads, downloads, and regenerated reports do not expose raw provider errors.
- Updated ASCII architecture flows for source-document download, safety-filter handling, local working copies, and deployment boundaries.
- Expanded `.gitignore` for coverage output, local Streamlit secrets, logs, and common caches.
- Added local agent settings to `.gitignore` so personal `.claude/` configuration is not accidentally committed.

## Cleanup

Generated local artifacts were removed from the working tree:

```text
__pycache__/
scripts/__pycache__/
src/__pycache__/
tests/__pycache__/
.pytest_cache/
.ruff_cache/
.deploy/*.tar.gz
.claude/
```

The following local runtime files remain intentionally ignored and must not be committed:

```text
.env
.deploy/
.venv/
terraform/terraform.tfvars
terraform/terraform.tfstate*
data/metadata/*.json
data/reports/*.md
data/uploads/*
```

## Verification

Run before committing or deploying:

```bash
.venv/bin/ruff check .
.venv/bin/pytest
terraform -chdir=terraform validate
ansible-playbook --syntax-check ansible/playbook.yml
```

For live OCI deployment, `git push` is not enough. Run `./scripts/deploy.sh` from the repo root, then verify the VM service and portal URL.
