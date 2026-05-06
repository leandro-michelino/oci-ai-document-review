# Simple OCI AI Document Review Portal

## Recommended Simple Version - Streamlit + OCI Document Understanding + OCI Generative AI

This blueprint describes the recommended **simple but useful** implementation for an AI-powered document review portal on Oracle Cloud Infrastructure.

The goal is to avoid unnecessary complexity while still creating a strong technical article, a practical demo, and a project that Codex can implement quickly.

---

## 1. Article Title

Recommended title:

```text
Building a Simple AI-Powered Document Review Portal with OCI Generative AI and Document Understanding
```

Subtitle:

```text
From static PDFs to structured business insights using OCI AI services and a lightweight Python web application.
```

---

## 2. Why This Version

This version is the best balance between value and simplicity.

Instead of starting with APEX or Visual Builder, the first implementation uses a lightweight Python web portal, preferably **Streamlit**.

This keeps the solution:

```text
Easy to implement
Easy to explain
Easy to demo
Easy for Codex to generate
Low-complexity
Still enterprise-relevant
```

APEX or Visual Builder can be added later as an enterprise frontend, but they should not be required for the first article or MVP.

---

## 3. Solution Summary

The solution allows a user to upload a document, process it with OCI AI services, and review the generated insights in a simple web portal.

The user can upload documents such as:

```text
Contracts
Invoices
Purchase orders
Compliance documents
Technical reports
Operational forms
```

The system then:

```text
Uploads the document to OCI Object Storage
Extracts text, tables, and fields using OCI Document Understanding
Sends the extracted content to OCI Generative AI
Generates an executive summary, key points, risk notes, and recommendations
Displays the result in a Python web dashboard
Allows the user to approve, reject, or download the report
```

---

## 4. Textual Diagram - Final Architecture

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

---

## 5. Recommended Technology Stack

### 5.1 Frontend

Use:

```text
Streamlit
```

Why Streamlit:

```text
Very fast to build
Native file upload support
Easy dashboard creation
Simple tables and status cards
Easy to run locally
Easy to containerize later
Codex can generate it reliably
```

Alternative:

```text
FastAPI + Jinja2 templates
```

But for the first version, Streamlit is simpler and more visual.

### 5.2 Backend

Use Python modules:

```text
oci
streamlit
python-dotenv
pydantic
tenacity
markdown
```

Optional:

```text
oracledb
pandas
pytest
ruff
black
```

### 5.3 OCI Services

Required:

```text
OCI Object Storage
OCI Document Understanding
OCI Generative AI
OCI IAM
```

Optional for Phase 2:

```text
Autonomous Database
OCI Container Instance
OCI Compute VM
OCI API Gateway
OCI Functions
OCI Logging
OCI Vault
```

---

## 6. MVP Scope

### Included in MVP

```text
Streamlit web portal
Document upload
Object Storage upload
Document Understanding extraction
Generative AI analysis
Structured JSON output
Markdown report generation
Review dashboard
Approve / reject status
Local metadata storage using JSON files
Download report button
Basic logging
Basic error handling
```

### Not Included in MVP

```text
APEX
Visual Builder
OCI Functions
OCI Events
API Gateway
Autonomous Database
Complex authentication
Multi-user role model
Advanced workflow engine
Complex approval matrix
Production CI/CD
```

These can be added in later phases.

---

## 7. MVP User Flow

```text
User opens Streamlit portal
  >
User uploads PDF/image document
  >
Application uploads the original file to Object Storage
  >
Application calls OCI Document Understanding
  >
Application extracts text/tables/key-values
  >
Application sends extracted content to OCI Generative AI
  >
OCI GenAI returns structured JSON
  >
Application generates Markdown report
  >
User reviews the summary and risks
  >
User approves or rejects the analysis
  >
Application stores status and report
```

---

## 8. Recommended Repository Structure

```text
oci-ai-document-review-portal/
  README.md
  .env.example
  requirements.txt
  app.py
  src/
    config.py
    object_storage_client.py
    document_understanding_client.py
    genai_client.py
    prompts.py
    models.py
    report_generator.py
    metadata_store.py
    logger.py
  data/
    metadata/
      .gitkeep
    reports/
      .gitkeep
    uploads/
      .gitkeep
  docs/
    architecture.md
    implementation_guide.md
    operations_guide.md
    security_notes.md
    article_outline.md
  tests/
    test_prompt_output.py
    test_report_generator.py
  docker/
    Dockerfile
  terraform/
    README.md
    provider.tf
    variables.tf
    object_storage.tf
    iam.tf
    outputs.tf
```

---

## 9. Environment Variables

Create `.env.example`:

```bash
# OCI Authentication
OCI_CONFIG_FILE=~/.oci/config
OCI_PROFILE=DEFAULT
OCI_REGION=your-region
OCI_COMPARTMENT_ID=ocid1.compartment.oc1..example

# Object Storage
OCI_NAMESPACE=your_namespace
OCI_BUCKET_NAME=doc-review-input

# Generative AI
GENAI_ENDPOINT=https://inference.generativeai.<region>.oci.oraclecloud.com
GENAI_MODEL_ID=cohere.command-r-plus
GENAI_TEMPERATURE=0.2
GENAI_MAX_TOKENS=3000

# Processing
MAX_DOCUMENT_CHARS=50000
LOCAL_METADATA_DIR=data/metadata
LOCAL_REPORTS_DIR=data/reports
LOCAL_UPLOADS_DIR=data/uploads

# Application
APP_TITLE=OCI AI Document Review Portal
```

---

## 10. Python Requirements

Create `requirements.txt`:

```txt
oci
streamlit
python-dotenv
pydantic
tenacity
markdown
pandas
```

For development:

```txt
pytest
ruff
black
```

---

## 11. Data Model for Simple MVP

For the first version, use local JSON metadata files instead of Autonomous Database.

Each processed document can have one metadata JSON file.

Example:

```json
{
  "document_id": "20260506-001",
  "document_name": "sample_contract.pdf",
  "document_type": "CONTRACT",
  "object_storage_path": "documents/sample_contract.pdf",
  "status": "REVIEW_REQUIRED",
  "uploaded_at": "2026-05-06T10:00:00Z",
  "processed_at": "2026-05-06T10:02:00Z",
  "review_status": "PENDING",
  "review_comments": null,
  "analysis": {
    "document_class": "CONTRACT",
    "executive_summary": "This contract defines a service agreement between two parties.",
    "key_points": [],
    "risk_notes": [],
    "recommendations": [],
    "confidence_score": 0.82
  },
  "report_path": "data/reports/20260506-001.md"
}
```

Recommended status values:

```text
UPLOADED
PROCESSING
EXTRACTED
AI_ANALYZED
REVIEW_REQUIRED
APPROVED
REJECTED
FAILED
```

---

## 12. Streamlit Pages / Sections

Since this is a simple app, it can start as a single `app.py` with sidebar navigation.

### 12.1 Upload Document

Fields:

```text
Document type
Document file
Optional business reference
Optional notes
```

Button:

```text
Process Document
```

### 12.2 Processing Result

Display:

```text
Document name
Document type
Processing status
Executive summary
Key points
Extracted fields
Risk notes
Recommendations
Missing information
Confidence score
```

Actions:

```text
Approve
Reject
Download Markdown Report
Download JSON Result
```

### 12.3 Review Dashboard

Display all processed documents with:

```text
Document ID
Document name
Document type
Status
Review status
Uploaded at
Processed at
Risk count
Confidence score
```

Filters:

```text
Status
Document type
Review status
```

### 12.4 Document Detail

Display:

```text
Original metadata
AI analysis
Risk notes
Recommendations
Review comments
Report download
```

---

## 13. AI Prompt Strategy

The model must return valid JSON.

### 13.1 General Prompt

```text
You are an enterprise document intelligence assistant.

Analyze the extracted document text below and return a strict JSON object.

Rules:
- Do not invent information.
- If a field is not present, return null.
- Use concise business language.
- Identify risks only when supported by the document text.
- Always include a human_review_required boolean.
- Return JSON only. Do not include markdown.

Required JSON schema:
{
  "document_class": "CONTRACT | INVOICE | COMPLIANCE | TECHNICAL_REPORT | GENERAL | UNKNOWN",
  "executive_summary": "string",
  "key_points": ["string"],
  "extracted_fields": {
    "parties": ["string"],
    "document_date": "string or null",
    "effective_date": "string or null",
    "expiration_date": "string or null",
    "total_amount": "string or null",
    "currency": "string or null",
    "payment_terms": "string or null"
  },
  "risk_notes": [
    {
      "risk": "string",
      "severity": "LOW | MEDIUM | HIGH",
      "evidence": "string"
    }
  ],
  "recommendations": ["string"],
  "missing_information": ["string"],
  "confidence_score": 0.0,
  "human_review_required": true
}

Document text:
{{EXTRACTED_TEXT}}
```

### 13.2 Contract Prompt

```text
You are a contract review assistant.

Analyze the contract text and return a strict JSON object.

Focus on:
- Parties
- Contract value
- Start date
- End date
- Renewal clause
- Termination clause
- Payment terms
- Liability clauses
- Data protection clauses
- Missing signatures
- Risks that require legal review

Rules:
- Do not provide legal advice.
- Highlight review points for a human legal or business reviewer.
- Do not invent fields.
- Return JSON only.

Contract text:
{{EXTRACTED_TEXT}}
```

### 13.3 Invoice Prompt

```text
You are an invoice processing assistant.

Analyze the invoice text and return a strict JSON object.

Focus on:
- Supplier
- Customer
- Invoice number
- Invoice date
- Due date
- PO number
- Total amount
- Currency
- Tax
- Payment terms
- Potential anomalies

Rules:
- Do not invent values.
- If a field is not present, return null.
- Return JSON only.

Invoice text:
{{EXTRACTED_TEXT}}
```

---

## 14. Expected AI Output Example

```json
{
  "document_class": "CONTRACT",
  "executive_summary": "This contract defines a service agreement between Company A and Company B for managed IT services over a 12-month term.",
  "key_points": [
    "The agreement has a 12-month duration.",
    "Payment is due within 30 days of invoice date.",
    "Termination requires 60 days written notice."
  ],
  "extracted_fields": {
    "parties": ["Company A", "Company B"],
    "document_date": "2026-04-01",
    "effective_date": "2026-05-01",
    "expiration_date": "2027-04-30",
    "total_amount": "120000",
    "currency": "EUR",
    "payment_terms": "Net 30"
  },
  "risk_notes": [
    {
      "risk": "The limitation of liability clause is not clearly defined.",
      "severity": "MEDIUM",
      "evidence": "The document does not specify a maximum liability cap."
    }
  ],
  "recommendations": [
    "Ask the legal team to review the liability clause.",
    "Confirm whether automatic renewal applies."
  ],
  "missing_information": [
    "No explicit data protection clause was found."
  ],
  "confidence_score": 0.82,
  "human_review_required": true
}
```

---

## 15. Markdown Report Template

The app should generate a Markdown report for each document.

```markdown
# Document Intelligence Report

## Document Metadata

- Document Name: {{document_name}}
- Document Type: {{document_type}}
- Uploaded At: {{uploaded_at}}
- Processing Status: {{status}}

## Executive Summary

{{executive_summary}}

## Key Points

{{key_points}}

## Extracted Fields

{{extracted_fields_table}}

## Risk Notes

{{risk_notes_table}}

## Recommendations

{{recommendations}}

## Missing Information

{{missing_information}}

## Human Review

- Human Review Required: {{human_review_required}}
- Review Status: {{review_status}}
- Review Comments: {{review_comments}}

## Processing Metadata

- Model ID: {{model_id}}
- Confidence Score: {{confidence_score}}
```

---

## 16. Core Processing Logic

Pseudo-code:

```python
def process_document(uploaded_file, document_type):
    document_id = generate_document_id(uploaded_file.name)

    save_local_upload(document_id, uploaded_file)

    object_name = upload_to_object_storage(
        bucket=config.bucket_name,
        file_path=local_file_path,
        object_name=f"documents/{document_id}/{uploaded_file.name}"
    )

    update_metadata(
        document_id=document_id,
        status="PROCESSING",
        object_name=object_name
    )

    extraction_result = document_understanding.extract_document(
        bucket=config.bucket_name,
        object_name=object_name
    )

    update_metadata(
        document_id=document_id,
        status="EXTRACTED",
        extracted_text=extraction_result.text
    )

    prompt = build_prompt(
        document_type=document_type,
        extracted_text=extraction_result.text
    )

    ai_response = genai_client.analyze_document(prompt)

    parsed_result = validate_ai_response(ai_response)

    report = generate_markdown_report(
        document_id=document_id,
        document_name=uploaded_file.name,
        document_type=document_type,
        analysis=parsed_result
    )

    save_report(document_id, report)

    update_metadata(
        document_id=document_id,
        status="REVIEW_REQUIRED",
        analysis=parsed_result,
        report_path=f"data/reports/{document_id}.md"
    )

    return parsed_result
```

---

## 17. Suggested Python Modules

### 17.1 `src/config.py`

Responsible for:

```text
Loading environment variables
Validating required variables
Exposing app configuration
```

### 17.2 `src/object_storage_client.py`

Responsible for:

```text
Creating OCI Object Storage client
Uploading files
Downloading files
Uploading reports
Checking bucket access
```

### 17.3 `src/document_understanding_client.py`

Responsible for:

```text
Calling OCI Document Understanding
Extracting text
Extracting tables
Extracting key-value pairs
Normalizing the result
```

### 17.4 `src/genai_client.py`

Responsible for:

```text
Creating OCI Generative AI inference client
Sending prompts
Receiving model output
Handling retries
Returning raw response
```

### 17.5 `src/prompts.py`

Responsible for:

```text
Selecting prompt by document type
Injecting extracted text
Keeping prompt versions
```

### 17.6 `src/models.py`

Responsible for:

```text
Pydantic validation
AI JSON schema
Risk note model
Document analysis model
```

### 17.7 `src/report_generator.py`

Responsible for:

```text
Generating Markdown reports
Formatting extracted fields
Formatting risks
Formatting recommendations
```

### 17.8 `src/metadata_store.py`

Responsible for:

```text
Creating local metadata files
Updating status
Saving analysis
Loading dashboard data
Approving or rejecting documents
```

---

## 18. Streamlit UI Layout

### Sidebar

```text
OCI AI Document Review Portal
- Upload Document
- Review Dashboard
- Document Details
- Settings
```

### Upload Page

```text
Title: Upload Document

Inputs:
- Document Type
- File uploader
- Business Reference
- Notes

Button:
- Process Document
```

### Result Page

```text
Title: AI Analysis Result

Sections:
- Executive Summary
- Key Points
- Extracted Fields
- Risk Notes
- Recommendations
- Missing Information
- Review Actions
```

### Review Dashboard

```text
Title: Document Review Dashboard

Cards:
- Total Documents
- Review Required
- Approved
- Rejected
- Failed

Table:
- Document ID
- Name
- Type
- Status
- Review Status
- Risk Count
- Confidence Score
```

---

## 19. Security Considerations

For the article and MVP, mention:

```text
Use private Object Storage buckets
Do not hardcode credentials
Use OCI config locally for development
Use instance principals when running on OCI
Avoid logging full document text
Mask sensitive values in logs
Use least privilege IAM policies
Keep human review before approval
```

For a production version, add:

```text
OCI Vault
OCI Logging
Autonomous Database
User authentication
Audit trail
Role-based access
Private endpoints where applicable
```

---

## 20. Cost Control

To keep the demo low-cost:

```text
Use small test documents
Limit file size to 10 MB
Limit extracted text sent to GenAI
Do not reprocess the same document repeatedly
Store generated outputs
Start with local execution
Deploy only when needed
```

Recommended MVP limits:

```text
Max file size: 10 MB
Max extracted characters sent to GenAI: 50,000
Max documents per demo batch: 10
Supported document types first: PDF, PNG, JPG
```

---

## 21. Two-Phase Implementation Plan

The implementation should be delivered in two clear phases.

The goal is to keep Phase 1 simple, fast, and fully demonstrable, while Phase 2 introduces enterprise persistence and an optional enterprise-grade frontend.

---

### Phase 1 - Simple MVP

```text
Streamlit + Object Storage + Document Understanding + GenAI
```

#### Objective

Create a working document review portal that can be implemented quickly and used as the core demo for the article.

This phase should avoid unnecessary enterprise complexity and focus on proving the value of the AI workflow.

#### Phase 1 Architecture

```text
Business User
  >
Streamlit Web Portal
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
Streamlit Review Dashboard
  >
Approved / Rejected / Report Download
```

#### Phase 1 Components

```text
Streamlit
Python backend modules
OCI Object Storage
OCI Document Understanding
OCI Generative AI
Local JSON metadata store
Local Markdown reports
OCI IAM policies
```

#### Phase 1 Deliverables

```text
Streamlit app
Document upload page
Object Storage upload integration
Document Understanding extraction
OCI GenAI analysis
Structured JSON AI output
Pydantic validation
Markdown report generation
Local JSON metadata
Review dashboard
Approve / reject actions
Download Markdown report
Download JSON result
Basic logging
Basic error handling
README and implementation guide
```

#### Phase 1 Success Criteria

```text
A user can upload a document through Streamlit.
The document is stored in OCI Object Storage.
OCI Document Understanding extracts the content.
OCI Generative AI generates a structured analysis.
The app displays the summary, fields, risks, and recommendations.
The user can approve or reject the result.
The user can download the Markdown report and JSON output.
All document metadata is stored locally as JSON files.
No database is required in this phase.
```

#### Phase 1 Recommended Storage Model

Use local JSON files for metadata:

```text
data/metadata/
```

Use local Markdown files for generated reports:

```text
data/reports/
```

Use Object Storage for original uploaded documents:

```text
oci://<bucket>/documents/<document_id>/<filename>
```

---

### Phase 2 - Enterprise Persistence and Optional Enterprise Frontend

```text
Add Autonomous Database for metadata + Optional APEX or Visual Builder
```

#### Objective

Evolve the simple MVP into a more enterprise-ready architecture by replacing local JSON metadata with Autonomous Database and optionally adding APEX or Visual Builder as the business-facing application.

Phase 2 should preserve the working Phase 1 logic and improve persistence, governance, auditability, and user experience.

#### Phase 2 Architecture - With Streamlit and Autonomous Database

```text
Business User
  >
Streamlit Web Portal
  >
OCI Object Storage
  >
OCI Document Understanding
  >
OCI Generative AI
  >
Autonomous Database
  >
Streamlit Review Dashboard
```

#### Phase 2 Architecture - Optional APEX Frontend

```text
Business User
  >
Oracle APEX Application
  >
Autonomous Database
  >
Python Processor / Backend API
  >
OCI Object Storage
  >
OCI Document Understanding
  >
OCI Generative AI
  >
Autonomous Database Results
  >
APEX Review Dashboard
```

#### Phase 2 Architecture - Optional Visual Builder Frontend

```text
Business User
  >
Oracle Visual Builder Web App
  >
Backend REST API
  >
Autonomous Database
  >
OCI Object Storage
  >
OCI Document Understanding
  >
OCI Generative AI
  >
Visual Builder Review Dashboard
```

#### Phase 2 Components

```text
Autonomous Database
Database schema for document metadata
Database schema for extracted content
Database schema for AI analysis
Database schema for human review
Optional APEX application
Optional Visual Builder application
Optional backend REST API
Optional OCI API Gateway
Optional OCI Vault
Optional OCI Logging
```

#### Phase 2 Deliverables

```text
Autonomous Database schema
Migration from local JSON metadata to database tables
Document metadata table
Extraction results table
AI analysis table
Review table
Processing log table
Updated Python metadata repository layer
Optional APEX page design
Optional Visual Builder page design
Optional REST API design
Audit-friendly review workflow
Improved dashboard and filtering
```

#### Phase 2 Success Criteria

```text
Metadata is stored in Autonomous Database instead of local JSON.
Document status history is persistent.
AI analysis results are queryable from the database.
Review decisions are stored with reviewer, timestamp, and comments.
The app can show dashboard metrics from database queries.
The original Phase 1 workflow still works.
APEX or Visual Builder can be added without changing the AI processing core.
```

#### Phase 2 Recommended Database Tables

```text
DOC_REVIEW_DOCUMENTS
DOC_REVIEW_EXTRACTIONS
DOC_REVIEW_AI_ANALYSIS
DOC_REVIEW_REVIEWS
DOC_REVIEW_PROCESSING_LOG
```

#### Phase 2 Frontend Recommendation

Use this decision rule:

```text
Keep Streamlit if the goal is a technical demo or article.
Use APEX if the goal is a database-centric internal business application.
Use Visual Builder if the goal is a modern REST/API-first business web application.
```

#### Phase 2 Optional Enhancements

```text
OCI Vault for secrets
OCI Logging for operational visibility
OCI Events for automatic processing
OCI Functions for serverless processing
OCI API Gateway for REST API exposure
Role-based access control
Advanced search and filtering
Dashboard by document type, risk severity, and review status
```

---

## 22. Terraform Scope for MVP

Keep Terraform simple.

Provision:

```text
Object Storage bucket
IAM policies
Optional Compute VM
Optional Container Instance
```

Avoid provisioning everything in the first version.

### Example IAM Policies

For local development user group:

```text
Allow group doc-review-admins to manage objects in compartment <compartment_name>
Allow group doc-review-admins to use ai-service-document-family in compartment <compartment_name>
Allow group doc-review-admins to use generative-ai-family in compartment <compartment_name>
```

For OCI runtime using dynamic group:

```text
Allow dynamic-group doc-review-runtime-dg to manage objects in compartment <compartment_name>
Allow dynamic-group doc-review-runtime-dg to use ai-service-document-family in compartment <compartment_name>
Allow dynamic-group doc-review-runtime-dg to use generative-ai-family in compartment <compartment_name>
```

---

## 23. Acceptance Criteria

The MVP is successful when:

```text
A user can open the Streamlit portal.
A user can upload a document.
The file is uploaded to OCI Object Storage.
OCI Document Understanding extracts document text.
OCI Generative AI generates structured JSON.
The app displays executive summary, risks, and recommendations.
The app generates a Markdown report.
The user can approve or reject the result.
The dashboard shows processed documents.
Errors are displayed clearly.
No credentials are hardcoded.
```

---

## 24. Suggested Article Structure

```text
1. Introduction
   - Why document-heavy processes are still manual
   - Why GenAI is useful when combined with document extraction

2. Solution Overview
   - What the portal does
   - Why the first version uses Streamlit instead of APEX or Visual Builder

3. Architecture
   - Object Storage
   - Document Understanding
   - Generative AI
   - Python Web Portal

4. Textual Diagram - Final Architecture

5. Implementation Walkthrough
   - Environment setup
   - Object Storage bucket
   - Uploading a document
   - Extracting content
   - Generating AI insights
   - Reviewing the result

6. Example Output
   - Executive summary
   - Extracted fields
   - Risk notes
   - Recommendations

7. Security and Cost Considerations

8. How to Evolve the Solution
   - Autonomous Database
   - APEX
   - Visual Builder
   - OCI Functions and Events

9. Conclusion
```

---

## 25. Codex Prompt

Use this prompt with Codex to implement the project.

```text
Build a complete MVP project called `oci-ai-document-review-portal`.

The project must implement a simple AI-powered document review portal using:

- Streamlit as the web UI
- OCI Object Storage for uploaded documents and generated reports
- OCI Document Understanding for document extraction
- OCI Generative AI for document summarization, classification, risk notes, and recommendations
- Local JSON metadata storage for the MVP
- Python 3.11+

Create the full repository structure with:

1. README.md
2. .env.example
3. requirements.txt
4. app.py
5. src/config.py
6. src/object_storage_client.py
7. src/document_understanding_client.py
8. src/genai_client.py
9. src/prompts.py
10. src/models.py
11. src/report_generator.py
12. src/metadata_store.py
13. src/logger.py
14. docs/architecture.md
15. docs/implementation_guide.md
16. docs/operations_guide.md
17. docs/security_notes.md
18. docs/article_outline.md
19. terraform skeleton files
20. tests/test_prompt_output.py
21. tests/test_report_generator.py
22. docker/Dockerfile

Functional requirements:

- The Streamlit app must allow document upload.
- The app must let the user choose document type: CONTRACT, INVOICE, COMPLIANCE, TECHNICAL_REPORT, GENERAL.
- The uploaded document must be saved locally and uploaded to OCI Object Storage.
- The app must call OCI Document Understanding to extract text, tables, and key-value data.
- The app must build a document-type-specific prompt.
- The app must call OCI Generative AI.
- The model response must be requested in strict JSON format.
- The app must validate the AI JSON output with Pydantic.
- The app must generate a Markdown report.
- The app must save document metadata in local JSON files.
- The app must provide a review dashboard.
- The user must be able to approve or reject the AI result.
- The user must be able to download the Markdown report and JSON result.
- The app must handle errors clearly and update document status to FAILED when processing fails.

Coding requirements:

- Use the official OCI Python SDK.
- Use python-dotenv for configuration.
- Use Pydantic for AI output validation.
- Use tenacity for retries.
- Use structured logging.
- Do not hardcode credentials.
- Do not use public buckets.
- Keep the implementation simple, readable, and MVP-friendly.
- Include comments where helpful.
- Include a README with setup and run instructions.

Architecture requirement:

Include this textual diagram in README.md and docs/architecture.md:

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

Future enhancement section:

- Add Autonomous Database for metadata
- Add APEX or Visual Builder as enterprise frontend
- Add OCI Events and Functions for automatic processing
- Add OCI Vault for secrets
- Add OCI Logging for operational visibility
```

---

## 26. Final Recommendation

Implement the project in two phases:

### Phase 1

```text
Streamlit + Object Storage + Document Understanding + GenAI
```

This is the simple MVP and the best version for the first article and demo.

### Phase 2

```text
Add Autonomous Database for metadata + Optional APEX or Visual Builder
```

This is the enterprise evolution. Autonomous Database should become the persistent metadata layer, while APEX or Visual Builder can be added only if a more enterprise-grade frontend is required.

This approach gives the best balance between simplicity, speed, business value, and future enterprise readiness.
