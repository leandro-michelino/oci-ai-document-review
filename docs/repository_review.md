# Repository Review

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.7.0`

## Scope

This review covers the Streamlit app, worker queue, OCI clients, metadata store, report generation, Terraform, Ansible deployment, setup wizard, tests, documentation, and architecture assets.

## Local review: 2026-10-26

The existing 146 tests passed before changes. Additional regression tests found gaps outside that coverage. Corrections address:

- Atomic metadata replacement and local filesystem locking around mutations, including between separate portal/timer processes. Worker checkpoints update processing fields without replacing reviewer comments, assignment, feedback, or audit history.
- Document-ID validation, containment of metadata paths, and matching the stored identity to its filename.
- Retryable local source preservation when processor initialization or executor submission fails. A failed record with a worker still registered in the current process cannot be retried or discarded. Decisions require a completed review state.
- Legacy timestamps without timezone information in stale-job cleanup.
- Default denial for malformed ACL structures, required OIDC expiration and identity claims, asymmetric signature algorithms, bounded JWKS refresh behavior, and a controlled HTTP 503 when case-chat generation fails.
- Redaction of detected PII in restricted-case chat evidence, including analysis and reviewer comments.
- OCR for the full document when a PDF contains pages without meaningful embedded text, avoiding partial review of mixed text/scanned documents. This can increase OCR use for text PDFs containing blank or very short pages.
- Rejection of zero Document Understanding attempts, which previously skipped the service call entirely.
- Deployment packaging from explicit source paths, excluding runtime data, local ACLs, deletion tombstones, workstation output, Terraform state/plans, keys, and symlinks. Optional case-chat deployment settings now load from `.env` while preserving environment overrides.
- Automated Python tests, lint checks, and shell syntax checks in GitHub Actions.

Local verification: **177 tests passed**, including 31 added regression cases. Static checks, Terraform formatting and configuration validation, Ansible syntax validation, shell syntax validation, and release-archive content checks also passed. Regression tests use synthetic files and OCI/provider doubles; no cloud resources were changed. The new GitHub Actions workflow has been configured locally and has not been run on GitHub during this review.

Limits: live OCI OCR/GenAI, IAM authorization, OIDC-provider integration, deployment, and browser acceptance against a deployed VM were not exercised. The portal remains an unauthenticated MVP requiring the access controls described in `security_notes.md`. PII detection is heuristic, citation checks validate citation IDs rather than factual entailment, sensitive retention overrides apply locally, and Object Storage lifecycle remains governed by its separate Terraform policy. Filesystem locking targets the supported macOS development and Linux VM environments; this is not a distributed worker queue. Active-worker retry/discard protection uses the current process registry.

## Current Hygiene State

- Tracked files are limited to source code, tests, Terraform, Ansible, setup scripts, documentation, the compliance seed catalog, and architecture assets.
- Runtime files are intentionally ignored: `.env`, `.deploy/`, `.venv/`, Terraform state/tfvars, local metadata, reports, uploads, deletion tombstones, caches, logs, and private key material.
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
- Reset the browser Upload form after a successful queue operation, with test coverage that the uploader key changes and only upload-specific form values are cleared.

## Configuration Review

- Setup normalizes automatic-intake Object Storage prefixes as relative paths.
- Terraform rejects empty, absolute, or parent-directory event-intake prefixes.
- Terraform rejects open ingress such as `0.0.0.0/0` and validates network CIDRs, OCPU count, memory size, retention days, automatic-intake tenancy OCID, and Function image requirements.
- The optional object-intake Function dynamic group is scoped to the deployed Function OCID, and its object policy is scoped to the configured project bucket.
- The Object Storage lifecycle policy deletes only `documents/` objects, leaving the compliance knowledge base under `compliance/` untouched.
- The failed-document discard control targets only the portal-managed `documents/<document-id>/...` object, retains a local audit tombstone, and never deletes external `incoming/` objects.

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
