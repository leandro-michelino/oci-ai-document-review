# Changelog

This project uses semantic-style MVP versioning: `vMAJOR.MINOR.PATCH`.

- `MAJOR`: production-breaking architecture or data model changes.
- `MINOR`: visible workflow, cloud integration, or capability changes.
- `PATCH`: bug fixes, documentation updates, and small UX refinements.

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
- Dashboard and Actions risk badges use green/yellow/red risk colors.
- README architecture design appears near the beginning of the document.
- Documentation, ASCII architecture flows, and the rendered architecture image reflect the current v0.3.0 runtime path.

## v0.2.0

- Added real OCI processing with Object Storage, Document Understanding, and Generative AI.
- Added background worker processing, stale-run detection, and retry support.
- Added Dashboard and Actions review workflow.
- Added Markdown/JSON report downloads and metadata persistence.

## v0.1.0

- Initial Streamlit MVP for document upload and AI-assisted review.
