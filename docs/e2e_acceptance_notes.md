# End-To-End Acceptance Notes

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.5.0`

Run date: 2026-05-09

## Scope

This walkthrough exercised the documented MVP paths as a human uploader, reviewer, and operator would use them:

- OCI Preflight
- Upload and processing path using text-native documents
- Multi-file expense name/reference grouping
- Dashboard review queues and compact grouped display
- Actions review summary, workflow, comments, approve, reject, and next-item routing
- Public-sector expense compliance routing
- Failed-document retry from the preserved local working copy
- Markdown report generation and source-document retention
- Optional OCI Events and Functions event-intake importer path
- Local retention cleanup timer entrypoint

The run used repository documentation files as uploaded documents for the normal text-native flow. A small synthetic receipt was also used to exercise the compliance-risk path because the repository docs are not expense receipts.

## Process Notes

```text
1. Ran static and automated validation.
   Result: Ruff passed, Terraform validated, Ansible syntax checked, and pytest passed.

2. Ran OCI Preflight with the configured runtime credentials.
   Result: Object Storage write/read/delete passed, Document Understanding API access passed, and OCI Generative AI responded with the configured Cohere model.

3. Processed README.md and docs/platform_usage.md as a grouped documentation upload.
   Result: Both documents were uploaded to private Object Storage, extracted locally, analyzed by OCI Generative AI, saved as metadata, and rendered into Markdown reports.

4. Processed a synthetic public-sector receipt.
   Result: The document was classified as INVOICE, compliance-risk notes were added, and Actions routed it as Compliance review.

5. Opened Dashboard as the reviewer.
   Result: Dashboard showed the grouped documentation upload as one compact expense/reference group and showed the receipt as priority compliance work.

6. Opened Actions as the reviewer.
   Result: The selected file summary, AI review summary, Decision panel, workflow controls, source download, analysis, lifecycle, extracted text, and downloads were available through the expected focused sections.

7. Tried to reject without comments.
   Result: The app correctly required comments, but the Streamlit test harness exposed a session-state stability issue in the review comments widget.
   Fix applied: Initialized the review-comments widget key before rendering the text area.

8. Rejected the compliance receipt with comments.
   Result: The record moved to REJECTED, review state became REJECTED, workflow closed, and the app advanced to the next action item.

9. Assigned workflow, added a reviewer comment, and approved the documentation files.
   Result: Workflow assignment and comment were persisted, audit events were written, reports were refreshed, and approval advanced to the next action item.

10. Simulated an initial failed document with a preserved local working copy, then queued Retry Processing.
    Result: The parent record moved to RETRY_PLANNED, retry history was written, a child processing record was created, the child reached REVIEW_REQUIRED, and the child was approved.
    Fix applied: Retry now also sets the pending-detail routing key so Actions opens the retry child deterministically after queueing.

11. Ran the optional event-intake importer entrypoint.
    Result: `scripts/poll_event_queue.py --limit 1` ran successfully and reported that event intake is disabled in the current deployment.

12. Ran the local retention cleanup entrypoint.
    Result: The first run exposed that `scripts/cleanup_retention.py` could not import `src` when executed the same way systemd runs it.
    Fix applied: Added the project root to `sys.path`, matching the already-correct event-intake script pattern. The cleanup command now runs successfully.
```

## Evidence Summary

```text
Automated tests:
  .venv/bin/pytest -q

Lint:
  .venv/bin/ruff check .

Terraform:
  terraform -chdir=terraform validate

Ansible:
  ansible-playbook --syntax-check -i localhost, ansible/playbook.yml

Live OCI preflight:
  Object Storage: PASS
  Document Understanding: PASS
  Generative AI: PASS

Event intake:
  event_intake imported=0 skipped=0 failed=0
  Event intake is disabled.

Retention cleanup:
  Retention cleanup complete: 0 metadata record(s), 0 invalid metadata file(s), 0 report(s), 0 upload(s) removed.
```

## Local Runtime Artifacts

The run created ignored local metadata, upload, and report artifacts under:

```text
data/metadata/
data/reports/
data/uploads/
```

The live processing path also uploaded source objects under the configured private Object Storage bucket. The project lifecycle policy deletes uploaded document objects under `documents/` after the configured retention period.

## Fixes Applied During The Walkthrough

- Stabilized the Actions review-comments widget before rejection validation.
- Removed noisy same-run widget-state assignment for the Actions group/file selectors during next-item routing.
- Routed retry children through the same pending-detail selection key used by approve/reject navigation.
- Fixed `scripts/cleanup_retention.py` so it can be executed directly by the VM systemd timer.
