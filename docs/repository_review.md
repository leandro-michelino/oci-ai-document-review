# Repository Review

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.6.1`

## Scope

This review covers the Streamlit app, worker queue, OCI clients, metadata store, report generation, Terraform, Ansible deployment, setup wizard, tests, documentation, and architecture assets.

## Current Hygiene State

- Tracked files are limited to source code, tests, Terraform, Ansible, setup scripts, documentation, the compliance seed catalog, and architecture assets.
- Runtime files are intentionally ignored: `.env`, `.deploy/`, `.venv/`, Terraform state/tfvars, local metadata, reports, uploads, caches, logs, and private key material.
- The rendered architecture image now lives with its editable Excalidraw source under `docs/assets/` instead of the repository root.
- `CHANGELOG.md` is the single source of truth for release history; the duplicate `docs/release_notes.md` file was removed.
- `README.md` is the concise front door. Deep operating detail stays in `docs/platform_usage.md`, `docs/implementation_guide.md`, `docs/security_notes.md`, `docs/cost_estimate.md`, and `docs/architecture_flows.md`.

## Recent Cleanup

- Moved `Architecture.png` to `docs/assets/oci-ai-document-review-architecture.png` and updated README plus architecture-flow references.
- Kept the rendered architecture PNG tracked while continuing to ignore generated SVG exports.
- Replaced the cumulative repository-review changelog with this shorter current-state hygiene note.
- Removed duplicate release notes from `docs/` so version history is maintained in one tracked file.
- Removed local generated deployment archives, temporary Ansible inventory, local runtime metadata, local generated reports, uploaded working copies, and Terraform plugin cache from the workstation.
- Kept local `.env`, `terraform/terraform.tfvars`, and Terraform state files out of Git. Those files are deployment inputs/state and should not be committed.
- Added the Reviewed archive page and upload-preview rendering regression coverage without introducing new tracked runtime artifacts.

## Configuration Review

- Setup normalizes automatic-intake Object Storage prefixes as relative paths.
- Terraform rejects empty, absolute, or parent-directory event-intake prefixes.
- Terraform rejects open ingress such as `0.0.0.0/0` and validates network CIDRs, OCPU count, memory size, retention days, automatic-intake tenancy OCID, and Function image requirements.
- The optional object-intake Function dynamic group is scoped to the deployed Function OCID, and its object policy is scoped to the configured project bucket.
- The Object Storage lifecycle policy deletes only `documents/` objects, leaving the compliance knowledge base under `compliance/` untouched.

## Verification

Run before committing or deploying:

```bash
.venv/bin/ruff check .
.venv/bin/pytest
terraform -chdir=terraform fmt -check -diff
terraform -chdir=terraform validate
ansible-playbook --syntax-check ansible/playbook.yml
```

For live OCI deployment, `git push` is not enough. Run `./setup.sh --deploy-only` or `./scripts/deploy.sh` from the repo root, then verify the VM service and portal URL.
