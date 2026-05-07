# Cost Estimate

This is an illustrative cost estimate for the OCI AI Document Review Portal.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.3.0`

Important:

- This is not an official Oracle quote.
- This may be incomplete, inaccurate, or not realistic for your tenancy, contract, region, usage pattern, discounts, free tier status, service limits, or currency.
- Use the Oracle Cost Estimator, the OCI Cost Analysis page, and a formal Oracle quote before using this for budgeting, customer pricing, procurement, or production planning.
- The project intentionally keeps this file conservative: it explains the bill drivers and rough order of magnitude instead of pretending that public list pricing is your actual bill.

## Current Deployment Assumption

The current MVP deployment is:

```text
Project version: v0.3.0
Runtime: 1 OCI Compute VM
Shape: VM.Standard.A1.Flex
Size: 1 OCPU, 6 GB memory
Operating system: Oracle Linux 9
Application: Streamlit systemd service
Deployment: Terraform and Ansible from local laptop
Storage: boot volume plus private Object Storage bucket
Network: VCN, public subnet, private subnet, Internet Gateway, NAT Gateway, Service Gateway
AI services: OCI Document Understanding and OCI Generative AI
GenAI model used by current runtime: cohere.command-r-plus-08-2024
Persistence: local JSON metadata, local Markdown reports, local upload working copies
```

The app does not deploy Autonomous Database, APEX, Visual Builder, OCI Vault, OCI Logging, Load Balancer, Functions, Events, Queue service, or Container/Kubernetes infrastructure in this version.

## Cost Drivers

```text
Compute
  - VM.Standard.A1.Flex OCPU hours
  - VM.Standard.A1.Flex memory GB hours
  - Boot volume storage and performance units

Object Storage
  - Uploaded original documents in Standard Object Storage
  - Curated compliance knowledge-base object at compliance/public_sector_entities.csv
  - PUT, GET, DELETE, list, and metadata requests
  - Temporary preflight object write/read/delete
  - Optional retention/lifecycle policy if added later

Document Understanding
  - Rich OCR/table/key-value extraction for scanned PDFs and images
  - Text-only OCR fallback when rich extraction fails
  - No DU call for text-native files or PDFs with selectable text

Generative AI
  - Prompt size from extracted text and instructions
  - Response size for JSON analysis
  - Model family and on-demand pricing unit
  - Reprocessing or retries

Networking
  - Public IP and outbound data transfer, according to tenancy/region pricing
  - Internet Gateway, NAT Gateway, and Service Gateway resources from Terraform
  - SSH and browser traffic to the Streamlit VM

Operations and validation
  - OCI Preflight checks Object Storage, Document Understanding, and GenAI
  - Compliance KB seeding and reads use the same private Object Storage bucket
  - Smoke tests and manual retries call live services
  - Repeated demo uploads create more Object Storage, DU, and GenAI usage
```

The curated compliance knowledge base is expected to be very small in this MVP. Its storage cost should be negligible compared with uploaded documents, AI processing, NAT Gateway, and compute. Future scheduled refresh jobs may add a small number of Object Storage GET/PUT requests and optional archived snapshots.

## Pricing References To Check

Oracle pricing changes over time. Before quoting numbers, check:

```text
Oracle Cloud Pricing:
https://www.oracle.com/cloud/pricing/

Oracle Cloud Price List:
https://www.oracle.com/cloud/price-list/

OCI Generative AI on-demand pricing guide:
https://docs.oracle.com/en-us/iaas/Content/generative-ai/pay-on-demand.htm

OCI Always Free resource reference:
https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm
```

Public Oracle references currently describe these important units:

- Ampere A1 Compute has Always Free allowances for the first 3,000 OCPU hours and 18,000 GB hours per month for VM.Standard.A1 resources, shared across the tenancy.
- Document Understanding pricing is transaction-based, with first-transaction tiers and greater-than-first-tier pricing for OCR and document extraction.
- OCI Generative AI on-demand pricing is model-dependent. Oracle's price list defines a Generative AI transaction as a character for Cohere-style on-demand pricing, where 10,000 transactions equal 10,000 characters.
- Object Storage Standard pricing depends on stored GB-month, requests, retrieval, and transfer behavior. Check the price list for the selected country and region.

## Current Runtime Cost Logic

The v0.3.0 extraction path materially changes DU usage:

```text
Text file, CSV, JSON, Markdown, XML, HTML, LOG, YAML
  -> local text read
  -> GenAI
  -> no Document Understanding charge

PDF with selectable embedded text
  -> local PDF text extraction
  -> GenAI
  -> no Document Understanding charge

Image, scanned PDF, or image-only PDF
  -> Object Storage upload
  -> Document Understanding rich extraction attempt
  -> GenAI

Image/scanned PDF where rich DU extraction fails but text OCR works
  -> Object Storage upload
  -> Document Understanding rich extraction attempt
  -> Document Understanding text-only OCR fallback
  -> GenAI
```

For that reason, two small files can have very different cost profiles:

```text
1-page text PDF
  Cost drivers: Object Storage + GenAI

1-page scanned receipt
  Cost drivers: Object Storage + DU rich extraction + GenAI

1-page scanned receipt where rich DU returns an error
  Cost drivers: Object Storage + DU rich extraction attempt + DU text-only OCR fallback + GenAI
```

## Monthly Worksheet

Replace every unit price with the latest Oracle price list, Cost Estimator value, or your contracted quote.

```text
hours_per_month = 730

Compute OCPU cost
  = max(0, instance_ocpus x hours_per_month - free_a1_ocpu_hours_available)
  x a1_ocpu_hour_unit_price

Compute memory cost
  = max(0, instance_memory_gb x hours_per_month - free_a1_memory_gb_hours_available)
  x a1_memory_gb_hour_unit_price

Boot volume cost
  = boot_volume_gb x boot_volume_gb_month_unit_price
  + boot_volume_gb x boot_volume_vpu_per_gb_month_unit_price

Object Storage cost
  = max(0, stored_document_gb - free_storage_gb_available)
  x object_storage_gb_month_unit_price
  + max(0, object_storage_requests - free_request_allowance)
  / request_pricing_unit
  x object_storage_request_unit_price

Document Understanding cost
  = max(0, rich_du_transactions - free_du_rich_transactions_available)
  / du_pricing_unit
  x rich_du_unit_price
  + max(0, text_only_ocr_fallback_transactions - free_du_ocr_transactions_available)
  / du_pricing_unit
  x ocr_unit_price

Generative AI cost
  = (prompt_characters + response_characters)
  / genai_pricing_unit
  x selected_model_unit_price

Network cost
  = public_ip_cost
  + outbound_data_gb x outbound_data_unit_price
  + gateway_or_transfer_charges_from_current_price_list

Estimated monthly total
  = compute
  + boot_volume
  + object_storage
  + document_understanding
  + generative_ai
  + network
```

## Project-Specific Scenario Estimates

These ranges are intentionally rough. They are meant for planning conversation, not procurement.

### Scenario A - Article / Demo Run

```text
Documents processed: 10 to 50 per month
Typical document: 1 to 5 pages
Stored documents: below 5 GB
Runtime: 1 A1 Flex VM, always on
Document mix: mostly text PDFs plus a few scanned receipts
Human users: 1 or 2 reviewers
Validation: a few preflight checks and smoke tests
```

Expected cost behavior:

- Compute can be very low if the A1 VM fits inside the tenancy's available Always Free A1 allowance.
- Boot volume and Object Storage can still appear on the bill depending on free-tier eligibility and retained storage.
- Text PDFs avoid DU and should mainly incur GenAI usage.
- Scanned receipts and images incur DU usage, and occasional rich-extraction failures can add a text-only OCR fallback call.
- GenAI usage should remain small unless extracted text is large or documents are repeatedly retried.

Planning estimate:

```text
Likely demo range: low single digits to low tens of USD per month
Confidence: low
Main uncertainty: free-tier eligibility, AI usage units, and repeated test runs
```

### Scenario B - Internal Pilot

```text
Documents processed: 500 to 2,000 per month
Typical document: 2 to 10 pages
Stored documents: 25 to 100 GB
Runtime: 1 VM, always on
Document mix: invoices, contracts, scanned receipts, and business PDFs
Human users: small review team
Validation: preflight after deployments and periodic smoke tests
```

Expected cost behavior:

- DU and GenAI become the main variable costs.
- The percentage of scanned/image-only PDFs matters a lot.
- Text-native files and selectable PDFs are cheaper because they skip DU.
- The text-only OCR fallback can increase DU usage when rich extraction is unstable for scans.
- Object Storage remains modest unless documents are large or retained for a long time.
- A single VM may be enough for the UI, but processing latency can increase if many jobs queue behind `MAX_PARALLEL_JOBS`.

Planning estimate:

```text
Likely pilot range: low tens to several hundreds of USD per month
Confidence: very low
Main uncertainty: page count, scan ratio, prompt size, model pricing, and retention policy
```

### Scenario C - Production Evolution

```text
Documents processed: 10,000+ per month
Typical document: variable
Likely added services: Autonomous Database, Vault, Logging, Events, Functions, Load Balancer
Runtime: scaled compute, container platform, or managed app layer
Human users: routed approval groups
Controls: budgets, alarms, retention, IAM hardening, lifecycle policies
```

Expected cost behavior:

- AI service usage, storage retention, logging volume, database sizing, and networking can materially change the bill.
- Local JSON metadata should be replaced with database persistence.
- Secrets should move to Vault or approved workload identity patterns.
- A formal Oracle quote and workload sizing exercise are required.

Planning estimate:

```text
Production estimate: not estimated in this document
Confidence: not applicable
Reason: requires production architecture, workload sizing, data retention policy, and commercial terms
```

## Worked Usage Examples

Use these examples to reason about volume. Insert current unit prices before using them.

### Example 1 - 50 Mostly Text Documents

```text
Documents: 50
Text/selectable PDFs: 45
Scanned/image docs: 5
Fallback OCR rate: 20% of scanned/image docs
Average GenAI prompt + response: 15,000 characters per document

DU rich extraction transactions:
  5 scanned/image docs

DU text-only OCR fallback transactions:
  5 x 20% = 1 fallback doc

GenAI characters:
  50 x 15,000 = 750,000 characters
```

### Example 2 - 1,000 Mixed Pilot Documents

```text
Documents: 1,000
Text/selectable PDFs: 600
Scanned/image docs: 400
Fallback OCR rate: 10% of scanned/image docs
Average GenAI prompt + response: 25,000 characters per document

DU rich extraction transactions:
  400 scanned/image docs

DU text-only OCR fallback transactions:
  400 x 10% = 40 fallback docs

GenAI characters:
  1,000 x 25,000 = 25,000,000 characters
```

### Example 3 - Reprocessing Impact

```text
If a failed scanned document is retried 3 times:
  Object Storage uploads: 3
  DU rich extraction attempts: up to 3
  DU text-only OCR fallback calls: up to 3 if rich extraction fails each time
  GenAI calls: only for attempts that extract text successfully
```

Retries are useful for operations, but repeated retries can distort a demo bill. Prefer fixing the source document or configuration before retrying many times.

## Cost Controls

```text
Use text-native documents or PDFs with selectable text when possible.
Keep scans clear, upright, and below MAX_UPLOAD_MB.
Limit MAX_DOCUMENT_CHARS so very large documents do not create huge GenAI prompts.
Avoid repeatedly retrying the same failed scanned document.
Use Dashboard and metadata to see whether a document used local text, DU rich extraction, or DU text-only fallback.
Run OCI Preflight intentionally, not in a tight loop.
Store generated reports and JSON results instead of reprocessing unchanged documents.
Apply Object Storage lifecycle policies for old uploaded files when retention is no longer needed.
Delete demo data that is no longer needed.
Stop or resize the VM when the demo is not in use, if appropriate for the tenancy.
Use OCI Budgets, Cost Analysis, and alarms.
Tag all resources with project and owner.
Review costs after every customer demo or article test run.
```

## What To Watch In OCI Cost Analysis

```text
Compute
  - VM.Standard.A1.Flex OCPU and memory usage
  - Boot volume charges

Object Storage
  - Storage GB-month
  - Request counts

AI Services
  - Document Understanding OCR / extraction transactions
  - Generative AI transactions or token/character units

Networking
  - Outbound transfer
  - Public IP and gateway-related charges, if applicable in the selected price list
```
