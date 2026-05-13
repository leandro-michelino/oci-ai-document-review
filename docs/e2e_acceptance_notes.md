# End-To-End Acceptance Notes

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.6.1`

Run date: 2026-05-09

## Scope

This walkthrough exercised the documented MVP paths as a human uploader, reviewer, and operator would use them:

- Upload page, including the `How To Use` button
- How To Use guide, including uploader, approver, and operator paths
- Dashboard queues, expense groups, and existing uploaded document records
- Actions review page using the already-uploaded E2E records
- Reviewed archive page for approved and rejected records
- Settings page and live OCI Preflight
- Local metadata, reports, preserved upload copies, and source-download readiness
- Public-sector expense compliance routing evidence
- Failed-document retry state
- Optional OCI Events and Functions event-intake importer path
- Local retention cleanup entrypoint
- Terraform, Ansible, lint, and automated test validation

The run reused ignored local runtime artifacts already present under `data/uploads`, `data/metadata`, and `data/reports`. Those artifacts represent repository documentation uploads plus a synthetic public-sector receipt used for compliance routing.

## Human Walkthrough Notes

```text
1. Opened the app as an uploader.
   Result: Upload opened by default and showed runtime context, upload controls,
   and the How To Use button.

2. Clicked How To Use.
   Result: The guide opened with uploader, approver, and operator sections.
   The operator path covered OCI Preflight, cost awareness, retention, and
   automatic-intake readiness.

3. Verified legacy guide routing.
   Result: The older `?page=How to Use` URL still normalized to `How To Use`.

4. Opened Dashboard.
   Result: The Dashboard rendered against the existing uploaded records and
   exposed queue/group review context without requiring new uploads.

5. Opened Actions.
   Result: The Actions page rendered the existing review queue state, including
   reviewed records and the failed retry-planned parent record.

6. Opened Reviewed.
   Result: The Reviewed page rendered the closed approved/rejected records as a
   searchable archive separate from open Actions work.

7. Opened Settings.
   Result: Settings rendered the OCI Preflight controls and runtime settings.

8. Ran live OCI Preflight.
   Result: Object Storage, Document Understanding, and Generative AI all passed
   with the configured runtime credentials.

9. Checked existing uploaded document artifacts.
   Result: Five local metadata records were present. Approved, rejected, failed,
   retry-planned, risk-noted, report-backed, and upload-copy states were all
   represented.

10. Ran optional event-intake importer.
   Result: The command completed successfully and reported that event intake is
   disabled for the current deployment.

11. Ran local retention cleanup.
    Result: The command completed successfully and removed no active artifacts.

12. Ran full repository validation.
    Result: Ruff, pytest, Terraform validation, and Ansible syntax checks passed.
```

## Existing Runtime Records

```text
20260509-133022-89aeca30
  security_notes.md
  status: APPROVED
  review: APPROVED
  report: present
  upload copy: present

e2e-failed-retry-source
  security_notes.md
  status: FAILED
  review: PENDING
  workflow: RETRY_PLANNED
  upload copy: present

e2e-platform-usage-doc
  platform_usage.md
  status: APPROVED
  review: APPROVED
  report: present
  upload copy: present

e2e-public-sector-receipt
  e2e_public_sector_receipt.txt
  status: REJECTED
  review: REJECTED
  compliance risks: present
  report: present
  upload copy: present

e2e-readme-doc
  README.md
  status: APPROVED
  review: APPROVED
  report: present
  upload copy: present
```

## Evidence Summary

```text
UI walkthrough:
  PYTHONPATH=. .venv/bin/python /tmp/e2e_ui_walkthrough.py
  Result: ui_walkthrough=PASS

Live OCI Preflight:
  Object Storage: PASS
  Document Understanding: PASS
  Generative AI: PASS

Event intake:
  PYTHONPATH=. .venv/bin/python scripts/poll_event_queue.py --limit 1
  Result: event_intake imported=0 skipped=0 failed=0
  Result detail: Event intake is disabled.

Retention cleanup:
  PYTHONPATH=. .venv/bin/python scripts/cleanup_retention.py
  Result: 0 metadata record(s), 0 invalid metadata file(s), 0 report(s),
  0 upload(s) removed.

Lint:
  .venv/bin/ruff check .
  Result: passed

Automated tests:
  .venv/bin/pytest
  Result: 118 passed

Terraform:
  terraform -chdir=terraform fmt -check -diff
  terraform -chdir=terraform validate
  Result: passed

Ansible:
  ansible-playbook --syntax-check ansible/playbook.yml
  Result: passed
```

## Issues Found

No application bug was found during this run.

One manual-harness issue appeared when the standalone Streamlit walkthrough script was launched from `/tmp` without the repository on `PYTHONPATH`. Running it with `PYTHONPATH=.` matched the project `pytest.ini` configuration and passed. No repository fix was needed.

## Local Runtime Artifacts

The walkthrough reused ignored local artifacts under:

```text
data/metadata/
data/reports/
data/uploads/
```

These files are intentionally ignored and must not be committed. They may include customer-like document content, extracted text previews, report output, and workflow history.
