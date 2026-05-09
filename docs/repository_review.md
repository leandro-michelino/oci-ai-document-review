# Repository Review

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.5.0`

## Scope

This review covers the Streamlit app, worker queue, OCI clients, metadata store, report generation, Terraform, Ansible deployment, setup wizard, tests, documentation, and ASCII architecture flows.

## Fixes Applied

- Reworked Dashboard and Actions around progressive disclosure: Dashboard uses tabbed queue sections and collapsed expense groups, while Actions keeps Decision visible and moves workflow, notes, retry, linked files, source document, AI summary, analysis details, lifecycle, extracted text, and downloads into focused expanders.
- Added Actions group aggregation for multi-file expense/reference submissions, including decision/fix counts, total items/services, total risk notes, and Items / Services by file.
- Renamed OCI Document Understanding chunk object naming from opaque numbered prefixes to original-file-stem sequence names such as `Receipt_21Apr2026_112647_1.pdf`.
- Added configurable retention with a 30-day default across VM-local metadata, Markdown reports, preserved upload copies, and Object Storage uploaded document objects.
- Added a daily VM systemd timer for local retention cleanup so expiry is enforced even without a browser session.
- Added an Object Storage lifecycle policy scoped to `documents/` so uploaded files expire without deleting the compliance knowledge base under `compliance/`.
- Added optional OCI Events and Functions automatic intake: external uploads under `incoming/` create Object Storage events, invoke `functions/object_intake`, write queue markers under `event-queue/`, and are imported by a VM systemd timer into the existing worker queue.
- Tightened Terraform validation so automatic processing cannot be enabled without both a valid tenancy OCID and an OCIR image for `functions/object_intake`.
- Updated release notes in `CHANGELOG.md` and `docs/release_notes.md` for `v0.5.0`.
- Updated the cost estimate for Document Understanding transaction pricing, the 5,000 transactions/month free tier, and OCI Functions free-tier assumptions.
- Reviewed all tracked Markdown files for v0.5.0 consistency, including automatic intake setup flags, Function README wiring, and expense name/reference terminology.
- Updated `scripts/setup.py`, `.env.example`, Terraform examples, Ansible, and deploy automation so customers can choose retention days during setup and redeploy the same value to the VM.
- Made Actions selection clearer by documenting and testing exact selected-file labeling with file name, document ID, expense/reference, stage, upload time, linked-file count, and current action.
- Updated all user-facing documentation for the latest review UX: compact Dashboard expense groups, one `Review` action per multi-file group, collapsed `Show files` details, best-next-action routing, and the Actions Decision panel placed near the top.
- Updated ASCII architecture flows with a Compact Dashboard Review Flow showing selectable file tables, multi-file group cards, `Review`, collapsed file details, and the top Decision panel.
- Refreshed the in-app How to Use guide so uploaders see the current one-to-five-file submission flow, mandatory multi-file expense name or reference, Dashboard expense groups, active elapsed processing time, stale failure handling, and reviewer linked-file/source-download workflow.
- Updated README, platform usage, implementation notes, and ASCII flows so the documented architecture matches the current multi-file expense grouping and stale-processing behavior.
- Added an Upload Batch and Expense Group ASCII flow that shows how one metadata record per file stays tied together by the shared expense name or reference through Dashboard and Actions.
- Re-reviewed tracked repository contents for secret exposure and redundant configuration. Real `.env`, Terraform state/tfvars, deployment archives, local metadata, uploads, reports, and caches are ignored; personal agent settings are not present in tracked files; tracked OCIDs are placeholders or tests.
- Re-ran full validation across the Streamlit app, tests, Terraform, and Ansible syntax after the dashboard filter, chatbot documentation, and architecture updates.
- Ran an end-to-end acceptance walkthrough across preflight, upload/processing, Dashboard, Actions approval/rejection, workflow comments, retry, event-intake polling, and retention cleanup. Notes are tracked in `docs/e2e_acceptance_notes.md`.
- Fixed Actions review-comment state initialization, retry child routing, next-item selector state, and the direct retention cleanup script import path found during the walkthrough.
- Added Dashboard status filtering documentation and ASCII flow coverage for Approved, Rejected, Reviewed, Failed, Processing, Needs decision, Compliance review, Fix and retry, and Retry planned states.
- Added Phase 2 customer chatbot documentation and ASCII flow coverage for read-only status, rejection reason, retry, owner, SLA, and risk-summary questions.
- Replaced the Actions inline source preview with a `Download Doc for Review` button, avoiding optional Streamlit PDF dependencies on the VM.
- Added runtime configuration validation for OCI auth mode, GenAI temperature, processing limits, upload limits, worker count, and compliance knowledge-base object name.
- Added Terraform variable validation for ingress CIDR, network CIDRs, OCPU count, and memory size.
- Updated setup validation so explicit open ingress such as `0.0.0.0/0` fails before Terraform is written.
- Kept content-safety provider JSON sanitization in shared code so UI, metadata reloads, downloads, and regenerated reports do not expose raw provider errors.
- Updated ASCII architecture flows for source-document download, safety-filter handling, local working copies, and deployment boundaries.
- Expanded `.gitignore` for coverage output, local Streamlit secrets, logs, and common caches.
- Removed generated personal agent settings from the local workspace and kept repository documentation free of named agent-tool configuration.

## Cleanup

Generated local artifacts are safe to remove from the working tree and remain ignored by Git:

```text
__pycache__/
scripts/__pycache__/
src/__pycache__/
tests/__pycache__/
.pytest_cache/
.ruff_cache/
.deploy/*.tar.gz
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

Latest validation for `v0.5.0` also included `terraform plan -detailed-exitcode -input=false`, which reported no infrastructure changes for the current local Terraform state.

For live OCI deployment, `git push` is not enough. Run `./scripts/deploy.sh` from the repo root, then verify the VM service and portal URL.
