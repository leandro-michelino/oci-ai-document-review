# Changelog

This project uses semantic-style MVP versioning: `vMAJOR.MINOR.PATCH`.

- `MAJOR`: production-breaking architecture or data model changes.
- `MINOR`: visible workflow, cloud integration, or capability changes.
- `PATCH`: bug fixes, documentation updates, and small UX refinements.

## Unreleased

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
- Documentation, ASCII architecture flows, and the rendered architecture image reflect the current v0.3.0 runtime path.

## v0.2.0

- Added real OCI processing with Object Storage, Document Understanding, and Generative AI.
- Added background worker processing, stale-run detection, and retry support.
- Added Dashboard and Actions review workflow.
- Added Markdown/JSON report downloads and metadata persistence.

## v0.1.0

- Initial Streamlit MVP for document upload and AI-assisted review.
