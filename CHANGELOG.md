# Changelog

This project uses semantic-style MVP versioning: `vMAJOR.MINOR.PATCH`.

- `MAJOR`: production-breaking architecture or data model changes.
- `MINOR`: visible workflow, cloud integration, or capability changes.
- `PATCH`: bug fixes, documentation updates, and small UX refinements.

## Unreleased

- Added a first-class `Reviewed` page between Actions and How To Use so approved and rejected documents have a dedicated audit/archive view with search and decision filters.
- Fixed the selected-upload file preview so Streamlit renders the compact file list as HTML instead of showing escaped `<div>` markup as a code block.
- Moved the rendered architecture diagram from the repository root into `docs/assets/` beside its Excalidraw source and updated documentation references.
- Replaced the cumulative repository-review notes with a concise current hygiene summary.
- Removed ignored local deployment archives, generated runtime metadata/reports/uploads, and Terraform plugin cache from the workstation while keeping deployment state and secrets untracked.
- Polished the root README into a cleaner first-read guide with evaluator, deployment, operations, security, documentation, roadmap, and versioning sections.
- Added a root `setup.sh` end-to-end setup wrapper that creates or refreshes `.venv`, runs the guided configuration wizard, validates the repository, deploys Terraform and Ansible, waits for the portal, and prints the ready-to-use URL.
- Documented `setup.sh`, `--configure-only`, `--deploy-only`, and `--skip-checks` in the README, implementation guide, platform usage guide, and Terraform README.
- Updated `scripts/setup.py` completion output so the guided wizard hands back cleanly to `setup.sh` when orchestrated by the root wrapper.
- Reworked Dashboard queue sections so individual files and multi-file expense/reference groups appear in one selectable table, with `Review selected` opening the best next actionable file.
- Expanded Ansible deployment output with a clear deployment plan, portal access details, runtime settings, data paths, automation timers, troubleshooting commands, and security notes.
- Tightened automatic-intake configuration by normalizing setup wizard Object Storage prefixes, validating Terraform prefixes as relative paths, and narrowing the Function dynamic group to the specific deployed intake function.
- Increased the default background worker pool from 2 to 5 parallel jobs across runtime config, setup, deployment, Ansible, examples, and documentation.
- Refreshed release notes, repository review notes, cost-estimate review wording, and ASCII architecture flows for the README polish and automatic-intake hardening pass.
- Re-ran repository validation with ruff, pytest, Terraform validation, and Ansible syntax checks; all checks passed, with only dependency deprecation warnings from the Python 3.14 test environment.

## v0.5.1 - 2026-05-09

- Updated the project patch version and release notes for the repository cleanup pass.
- Updated cost estimates to use OCI Generative AI on-demand character transaction billing for the default Cohere Command R+ model.
- Added Terraform outputs for `retention_days` and `ssh_private_key_path`, matching the documented deployment outputs.
- Updated `scripts/deploy.sh` so the Ansible inventory uses the Terraform-resolved private SSH key path unless `SSH_PRIVATE_KEY_PATH` is explicitly overridden.
- Normalized automatic-intake Function prefixes at runtime so `incoming` and `incoming/` behave consistently.
- Narrowed the automatic-intake Function object policy to the configured project bucket.
- Reviewed Markdown documentation for v0.5.1 consistency, including automatic intake setup flags, Function README wiring, and current expense name/reference wording.

## v0.5.0 - 2026-05-09

- Actions now has a visible `Select document group` control before the file selector, making grouped expense/reference submissions easier to review together.
- Actions now shows the expanded AI review summary before the Decision panel, so approvers see the AI context before approving or rejecting.
- Dashboard grouped uploads now show expanded file details as a compact table instead of stacked vertical cards.
- Dashboard queue tabs now render individual files in compact selectable tables with a single `Review selected` action instead of tall stacked cards.
- Added optional OCI Events and Functions automatic intake for Object Storage uploads under `incoming/`, with Function queue markers and a VM systemd importer feeding the existing processing workflow.
- Added documentation release notes in `docs/release_notes.md`.
- Updated the cost estimate for Document Understanding transaction pricing, current free-tier assumptions, and OCI Functions free-tier intake examples.
- Tightened Terraform validation so automatic processing requires a valid tenancy OCID and an OCIR Function image.

## v0.4.0 - 2026-05-09

- Removed the separate Upload `Reference` field so customers use only `Expense name or reference` for upload grouping/context.
- Linked-file review lists now make the selected document visually obvious with a highlighted file card and selected marker.
- Dashboard and Actions now use stronger progressive disclosure: tabbed queues, collapsed expense groups, linked-file expanders, a focused Decision panel, and expanders for workflow, source document, AI summary, analysis details, lifecycle, extracted text, and downloads.
- Added configurable retention with a 30-day default across VM-local metadata, reports, preserved upload copies, and Object Storage uploaded document objects.
- Added a daily VM systemd retention timer for local cleanup.
- Setup now asks for retention days and writes the value to both `.env` and `terraform/terraform.tfvars`; deploy passes it through Ansible to the VM.
- Terraform now creates an Object Storage lifecycle policy scoped to `documents/`, leaving the compliance knowledge-base object under `compliance/` untouched.
- Actions now shows group aggregation for multi-file expense/reference submissions, including file counts, decision/fix counts, total extracted items/services, total risks, and Items / Services by file.
- OCI Document Understanding chunk uploads now use customer-readable names based on the original PDF stem plus `_1`, `_2`, and so on.
- Actions now identifies the exact selected file more clearly with file name, document ID, expense/reference, stage, upload time, linked-file count, and current action.
- Dashboard documentation now reflects compact multi-file expense groups with one `Review` button, collapsed `Show files` details, and best-next-action routing.
- Actions documentation now reflects the top Decision panel, so reviewers can correct type, approve, or reject before scrolling through source download and full AI analysis.
- Refreshed the in-app How to Use guide for one-to-five-file submissions, mandatory multi-file expense name or reference, Dashboard expense groups, stale processing cleanup, source-document download, and approver linked-file review.
- Updated README, platform usage, implementation notes, repository review, and ASCII architecture flows so documentation matches the current expense-grouped upload and review workflow.
- Cleaned generated local cache and personal agent artifacts from the working tree while keeping runtime secrets, Terraform state, deployment context, metadata, reports, and uploads ignored.

## v0.3.0

- Documentation now makes the live deployment boundary explicit: pushing to GitHub records source changes, but the OCI VM is updated only by running `./scripts/deploy.sh` from the local laptop.
- Added post-deployment verification guidance for confirming the VM has the current dashboard code, the `oci-ai-document-review` systemd service is active, and the portal responds on the Streamlit URL.
- Documented the Dashboard `At a glance` rendering guard: metric cards are emitted as one compact HTML block so Streamlit does not render later cards as escaped code text.
- Actions now includes a `Download Doc for Review` button for reviewer approval work when the local working copy is available.
- Provider content-safety JSON is sanitized across worker failures, existing metadata loads, preflight display, JSON downloads, and regenerated Markdown reports.
- Runtime settings now validate auth mode, numeric processing limits, and compliance knowledge-base object names before the app starts.
- Terraform now validates narrow ingress CIDRs, flexible-shape sizing, and network CIDR syntax; setup rejects explicit open ingress such as `0.0.0.0/0`.
- ASCII architecture flows now include source-document download, safety-filter sanitization, and the deployment/configuration boundary.
- Workspace cleanup removes generated Python, test, linter, and deployment-render scratch files from the local tree.
- Dashboard page state persists in the browser URL, so refresh stays on Dashboard.
- Dashboard status refresh uses Streamlit fragments instead of full browser reloads.
- Queue tables are split by Processing, Ready, Failed, and Reviewed.
- Dashboard row actions take reviewers directly to each document, while current multi-file groups use compact `Review` cards.
- Actions page supports approve/reject, next-in-line routing, workflow assignment, SLA, comments, audit trail, and retry history.
- Text-native files and PDFs with selectable text go directly to GenAI after local extraction.
- Images and scanned/image-only PDFs use OCI Document Understanding OCR.
- DU text-only OCR fallback is used when rich table/key-value extraction fails.
- Curated compliance knowledge-base matching flags public-sector expense risks and routes them to Actions as `Compliance review`.
- The compliance KB is read from `compliance/public_sector_entities.csv` in Object Storage, seeded from `data/compliance/public_sector_entities.csv` when missing.
- Dashboard and Actions risk display uses a green signal for no-risk documents and severity labels for actionable risks: `Risk Small`, `Risk Medium`, and `Risk High`.
- Actions now shows a reviewer-friendly Risk review panel with summarized compliance evidence instead of raw catalog details.
- Dashboard work queues now include a status filter for Approved, Rejected, Reviewed, Failed, Processing, Needs decision, Compliance review, Fix and retry, and Retry planned states.
- Future phase documentation now includes a read-only customer document chatbot grounded in metadata, audit events, workflow comments, reports, summaries, and reviewer decisions.
- Dashboard Ready work is presented as a horizontal middle band, while Failed and Reviewed stay in the paired queue layout.
- README architecture design appears near the beginning of the document.
- Documentation, ASCII architecture flows, and the rendered architecture image reflected the runtime path at the time of the v0.3.0 release.

## v0.2.0

- Added real OCI processing with Object Storage, Document Understanding, and Generative AI.
- Added background worker processing, stale-run detection, and retry support.
- Added Dashboard and Actions review workflow.
- Added Markdown/JSON report downloads and metadata persistence.

## v0.1.0

- Initial Streamlit MVP for document upload and AI-assisted review.
