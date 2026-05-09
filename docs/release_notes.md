# Release Notes

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.5.1`

Release notes summarize user-visible workflow, infrastructure, documentation, and cost-estimate changes. `CHANGELOG.md` remains the source of truth for full repository history.

## v0.5.1 - 2026-05-09

### Cost Estimate

- Updated GenAI estimates to use OCI Generative AI on-demand character transaction billing for the default Cohere Command R+ model.
- Updated Small and Enterprise monthly totals, ranges, worksheet formulas, and retry sensitivity examples.

### Deployment Wiring

- Added Terraform outputs for `retention_days` and `ssh_private_key_path`.
- Updated `scripts/deploy.sh` so Ansible uses the Terraform-resolved private SSH key path unless explicitly overridden.
- Normalized Function prefixes at runtime and narrowed the automatic-intake Function object policy to the project bucket.

## v0.5.0 - 2026-05-09

### Automatic Intake

- Added optional OCI Events and Functions automatic intake for Object Storage uploads under `incoming/`.
- Added `functions/object_intake`, which writes queue markers under `event-queue/` instead of processing documents directly.
- Added VM event-intake polling through `oci-ai-document-review-event-intake.timer`, gated by Terraform and Ansible configuration.
- Added setup, Terraform, deployment, and documentation wiring for incoming prefixes, queue prefixes, and polling intervals.

### Review UX

- Actions now starts with a `Select document group` control before choosing a file.
- Actions shows the expanded AI review summary before the Decision panel.
- Dashboard queues use compact selectable tables with one `Review selected` action.
- Multi-file expense/reference groups stay collapsed by default and show compact file details only when expanded.

### Cost And Architecture

- Updated the cost estimate for Document Understanding transaction pricing and the 5,000 transactions/month free tier.
- Updated OCI Functions estimates for the 2M invocations/month and 400K GB-seconds/month free tier.
- Updated ASCII architecture flows and implementation notes for automatic Object Storage intake.
- Tightened Terraform validation so automatic processing requires a valid tenancy OCID and an OCIR Function image.

## v0.4.0 - 2026-05-09

- Added configurable 30-day default retention across VM-local metadata, reports, uploads, and Object Storage document objects.
- Added Object Storage lifecycle policy scoped to `documents/`.
- Improved Dashboard and Actions progressive disclosure for grouped uploads.
- Added customer-readable Document Understanding chunk names based on the original filename.
- Refreshed the How to Use guide and ASCII architecture flows for one-to-five-file submissions.

## v0.3.0

- Documented the live deployment boundary between GitHub commits and VM deployment.
- Added source-document download for reviewer approval work.
- Added content-safety JSON sanitization across UI, metadata, downloads, and regenerated reports.
- Added Dashboard URL state, queue tables, status filters, and reviewer actions.

## v0.2.0

- Added real OCI processing with Object Storage, Document Understanding, and Generative AI.
- Added background worker processing, stale-run detection, and retry support.
- Added Dashboard and Actions review workflow.

## v0.1.0

- Initial Streamlit MVP for document upload and AI-assisted review.
