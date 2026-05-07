# Changelog

This project uses semantic-style MVP versioning: `vMAJOR.MINOR.PATCH`.

- `MAJOR`: production-breaking architecture or data model changes.
- `MINOR`: visible workflow, cloud integration, or capability changes.
- `PATCH`: bug fixes, documentation updates, and small UX refinements.

## Unreleased

- Documentation now makes the live deployment boundary explicit: pushing to GitHub records source changes, but the OCI VM is updated only by running `./scripts/deploy.sh` from the local laptop.
- Added post-deployment verification guidance for confirming the VM has the current dashboard code, the `oci-ai-document-review` systemd service is active, and the portal responds on the Streamlit URL.
- Documented the Dashboard `At a glance` rendering guard: metric cards are emitted as one compact HTML block so Streamlit does not render later cards as escaped code text.
- Actions now includes an inline Source document preview for reviewer approval work when the local working copy is available. PDFs, images, and text-like files render in the browser; unsupported types fall back to metadata and extracted text.
- Provider content-safety JSON is sanitized across worker failures, existing metadata loads, preflight display, JSON downloads, and regenerated Markdown reports.

## v0.3.0

- Dashboard page state persists in the browser URL, so refresh stays on Dashboard.
- Dashboard status refresh uses Streamlit fragments instead of full browser reloads.
- Queue tables are split by Processing, Ready, Failed, and Reviewed.
- Row-level Open actions take reviewers directly to each document.
- Actions page supports approve/reject, next-in-line routing, workflow assignment, SLA, comments, audit trail, and retry history.
- Text-native files and PDFs with selectable text go directly to GenAI after local extraction.
- Images and scanned/image-only PDFs use OCI Document Understanding OCR.
- DU text-only OCR fallback is used when rich table/key-value extraction fails.
- Curated compliance knowledge-base matching flags public-sector expense risks and routes them to Actions as `Compliance review`.
- The compliance KB is read from `compliance/public_sector_entities.csv` in Object Storage, seeded from `data/compliance/public_sector_entities.csv` when missing.
- Dashboard and Actions risk display uses a green signal for no-risk documents and severity labels for actionable risks: `Risk Small`, `Risk Medium`, and `Risk High`.
- Actions now shows a reviewer-friendly Risk review panel with summarized compliance evidence instead of raw catalog details.
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
