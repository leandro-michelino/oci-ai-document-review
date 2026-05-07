# Article Outline

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.3.0`

1. Why document-heavy processes remain manual
2. Why selective Document Understanding plus GenAI is useful
3. Architecture overview
   - Use `Architecture.png` as the LinkedIn post image and README architecture image.
   - The editable source is `docs/assets/oci-ai-document-review-architecture.excalidraw`.
4. MVP versioning and what `v0.3.0` includes
5. Dynamic GenAI region discovery
6. Environment setup
7. Terraform and Ansible deployment from a laptop
8. Release package hygiene and why credentials stay out of Git
9. Object Storage bucket and uploaded document storage
10. OCI Preflight checks before processing
11. Uploading documents and queueing background processing
12. Extracting content locally, with Document Understanding OCR, or with DU text-only OCR fallback
13. Converting extraction results into JSON-safe metadata
14. Generating structured AI insights with GenAI
15. Applying a deterministic compliance knowledge-base lookup
    - Mention `COMPLIANCE_ENTITIES_OBJECT_NAME`.
    - Explain the default Object Storage object: `compliance/public_sector_entities.csv`.
    - Explain that the bundled seed file lives at `data/compliance/public_sector_entities.csv`.
    - Show that matches route documents to `Compliance review` in Actions.
16. Using the Dashboard queue to find Ready, Processing, Failed, and Reviewed documents
    - Mention URL-backed Dashboard state and component refresh with Streamlit fragments.
    - Mention severity-labeled risk badges.
17. Tracking workflow assignment, SLA, comments, audit trail, and retry history
18. Reviewing and approving output in the Actions page
    - Mention the `Download Doc for Review` button when the local working copy exists.
    - Mention that metadata, extracted text, and AI analysis remain available for review.
    - Mention next-in-line routing after approval or rejection.
19. Handling OCI GenAI content-safety blocks without exposing raw provider JSON
20. End-to-end smoke test results
21. Security and cost controls
    - Include cost estimate disclaimer
    - Recommend Oracle Cost Estimator and Oracle representative quote
22. Phase 2 with Autonomous Database, APEX, or Visual Builder
