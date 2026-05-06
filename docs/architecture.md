# Architecture

```text
Business User
  >
Python Web Portal
  >
Upload Document
  >
OCI Object Storage
  >
OCI Document Understanding
  >
Extracted Text / Tables / Fields
  >
OCI Generative AI
  >
Summary / Classification / Risk Notes
  >
Python Review Dashboard
  >
Approved / Rejected / Report Download
```

Phase 1 keeps the portal simple: Streamlit runs locally, metadata is stored as JSON, reports are written as Markdown, and original uploads are stored in a private Object Storage bucket.

The setup wizard discovers GenAI-capable regions dynamically. It fetches subscribed tenancy regions, probes OCI Generative AI for active chat models, and only then shows available GenAI regions to the user.

Additional ASCII architecture flows are available in [architecture_flows.md](architecture_flows.md).
