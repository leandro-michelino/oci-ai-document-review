# Cost Estimate

This is an illustrative cost estimate for the OCI AI Document Review Portal.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Important:

- This is not an official Oracle quote.
- This may be incomplete, inaccurate, or not realistic for your tenancy, contract, region, usage pattern, discounts, free tier status, or service limits.
- Use the Oracle Cost Estimator and request a formal quote from your Oracle representative before using these numbers for budgeting, customer pricing, procurement, or production planning.

## Deployment Assumption

Current MVP deployment:

```text
Region: selected OCI region
Runtime: 1 OCI Compute VM
Shape: VM.Standard.A1.Flex
Size: 1 OCPU, 6 GB memory
Storage: Boot volume plus private Object Storage bucket
App: Streamlit running as a systemd service
AI services: OCI Document Understanding and OCI Generative AI
Deployment method: Terraform and Ansible from local laptop
```

## Cost Drivers

```text
Compute VM
  - OCPU hours
  - Memory GB hours
  - Boot volume storage
  - Boot volume performance units

Object Storage
  - GB stored per month
  - Request volume
  - Retrieval and transfer, if applicable

Document Understanding
  - OCR transactions
  - Document extraction transactions
  - Document properties transactions, if used
  - Custom extraction or custom training, if added later

Generative AI
  - Model family
  - On-demand transaction or token usage
  - Input size per document
  - Output size per response
  - Dedicated endpoint usage, if added later

Networking
  - Public IP
  - Outbound data transfer
  - Optional load balancer, if added later

Runtime validation
  - OCI Preflight creates a small temporary Object Storage object and deletes it.
  - Full smoke tests call Document Understanding and Generative AI.
  - Repeated validation runs can add small usage charges.
```

## Official Pricing References

Oracle pricing changes over time. Check these pages before quoting any number:

```text
Oracle Cloud Pricing:
https://www.oracle.com/cloud/pricing/

Oracle UK Cloud Price List:
https://www.oracle.com/uk/cloud/price-list/

OCI Generative AI on-demand pricing guide:
https://docs.oracle.com/en-us/iaas/Content/generative-ai/pay-on-demand.htm
```

Notes from Oracle public pricing pages:

- OCI Compute Ampere A1 has separate OCPU-hour and memory GB-hour pricing.
- Oracle states that each tenancy gets the first 3,000 OCPU hours and 18,000 GB hours per month free for Ampere A1 Compute, shared across supported A1 resources.
- Boot volumes are billed separately from compute.
- Object Storage Standard is priced per GB stored per month, with request-based charges.
- OCI Document Understanding pricing is transaction-based for OCR, document extraction, and document properties.
- OCI Generative AI pricing depends on the model family and is listed by transaction or token units depending on the model.

## Simple Monthly Estimate Template

Use this as a worksheet. Replace unit prices with the latest values from Oracle pricing or your Oracle quote.

```text
Monthly compute OCPU cost
  = instance_ocpus x hours_per_month x compute_ocpu_unit_price

Monthly compute memory cost
  = instance_memory_gb x hours_per_month x compute_memory_unit_price

Monthly boot volume cost
  = boot_volume_gb x block_volume_storage_unit_price
  + boot_volume_gb x block_volume_vpu_unit_price

Monthly object storage cost
  = stored_document_gb x object_storage_gb_month_unit_price
  + object_storage_requests x request_unit_price

Monthly Document Understanding cost
  = document_understanding_transactions / pricing_unit
  x document_understanding_unit_price

Monthly Generative AI cost
  = genai_usage_units / pricing_unit
  x selected_model_unit_price

Estimated monthly total
  = compute + boot_volume + object_storage + document_understanding + genai + network
```

## Illustrative Demo Scenarios

These scenarios are intentionally rough. They are meant to show what to check, not to predict a bill.

### Scenario A - Small Article MVP Run

```text
Documents processed: 10 to 50 per month
Average pages per document: 1 to 5
Stored documents: less than 5 GB
Runtime: 1 A1 Flex VM, always on
AI usage: light
```

Expected cost behavior:

- Compute may be very low if the A1 usage fits within available Always Free allowance and the tenancy is eligible.
- Boot volume, Object Storage, Document Understanding, and Generative AI can still generate charges.
- AI service calls may dominate the cost if documents are large or repeatedly reprocessed.

Planning estimate:

```text
Low MVP estimate: possibly low single digits to low tens of USD per month
Confidence: low
Reason: AI service usage and account-specific free tier eligibility can change the bill materially
```

### Scenario B - Internal Pilot

```text
Documents processed: 500 to 2,000 per month
Average pages per document: 2 to 10
Stored documents: 25 to 100 GB
Runtime: 1 VM, always on
AI usage: moderate
```

Expected cost behavior:

- Document Understanding and Generative AI are likely to become the main variable costs.
- Object Storage remains modest unless documents are large or retained for a long time.
- A single VM may still be enough for the UI, but processing time can increase.

Planning estimate:

```text
Pilot estimate: low tens to several hundreds of USD per month
Confidence: very low
Reason: transaction counts, model choice, token volume, and discount terms drive the final number
```

### Scenario C - Production Evolution

```text
Documents processed: 10,000+ per month
Average pages per document: variable
Added services: Autonomous Database, Vault, Logging, Events, Functions, Load Balancer
Runtime: scaled compute or container service
AI usage: high
```

Expected cost behavior:

- AI service usage, storage retention, logging volume, and database sizing can materially change the bill.
- A production design should include limits, monitoring, budgets, and chargeback tags.
- A formal Oracle quote is strongly recommended.

Planning estimate:

```text
Production estimate: not estimated in this document
Confidence: not applicable
Reason: requires workload sizing, data retention policy, security architecture, and Oracle commercial terms
```

## Cost Controls

```text
Limit file upload size.
Limit extracted text sent to GenAI.
Avoid reprocessing unchanged documents.
Store generated reports and JSON results.
Set Object Storage lifecycle policies for old uploaded files.
Stop or resize the VM when not needed.
Use OCI budgets and alarms.
Tag all resources with project and owner.
Review Cost Analysis after each processing run.
Use smaller documents for article screenshots.
Run preflight intentionally, not in a tight loop.
```

## Recommended Disclaimer For The Article

```text
Cost note: The cost estimates in this article are illustrative only and may not reflect actual OCI billing for your tenancy, region, usage, free tier eligibility, discounts, or contract terms. For accurate pricing, use the Oracle Cost Estimator and request a formal quote from your Oracle representative.
```
