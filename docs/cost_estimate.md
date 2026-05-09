# Cost Estimate

This document provides illustrative cost estimates for two deployment tiers of the OCI AI Document Review Portal: Small and Enterprise.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.4.0`

## Disclaimer

- These estimates are illustrative only and are not an official Oracle quote.
- Unit prices used throughout this document are approximate public list prices as of early 2026 and may be outdated, region-dependent, or inapplicable to your tenancy, contract, discount tier, free-tier eligibility, or currency.
- All numbers should be treated as order-of-magnitude planning inputs, not procurement figures.
- Use the Oracle Cost Estimator, OCI Cost Analysis, and a formal Oracle representative quote before making any budgeting, pricing, or purchasing decisions.

## Deployment Tiers At A Glance

```text
+---------------------------+----------------------------+------------------------------+
| Dimension                 | Small                      | Enterprise                   |
+---------------------------+----------------------------+------------------------------+
| Documents per month       | 100 - 500                  | 10,000 - 20,000              |
| Compute                   | 1 x VM.Standard.A1.Flex    | 3 x VM.Standard.E5.Flex      |
|                           | 2 OCPU / 12 GB             | 4 OCPU / 32 GB each          |
| Database                  | Local JSON metadata        | Autonomous Database          |
|                           |                            | Serverless                   |
| Secrets                   | API key on VM              | OCI Vault                    |
| Load balancing            | None                       | OCI Load Balancer            |
| Logging                   | journald on VM             | OCI Logging                  |
| Automation                | Manual deploy.sh           | OCI Events + Functions       |
| Approximate monthly range | $25 - $100                 | $1,500 - $3,500              |
+---------------------------+----------------------------+------------------------------+
```

GenAI is the dominant variable cost at both tiers. The percentage of scanned and image-only documents is the second largest driver because it determines how many Document Understanding calls are made.

## Cost Drivers

```text
Compute
  - VM OCPU and memory hours
  - Boot volume storage and performance units

Object Storage
  - Uploaded original documents in Standard tier
  - Optional incoming/ uploads and event-queue/ markers for automatic intake
  - Compliance knowledge-base object
  - PUT, GET, DELETE, list, and metadata requests
  - Preflight temporary object write/read/delete

Events and Functions
  - Optional OCI Events delivery for Object Storage create events
  - Optional OCI Functions invocations for intake marker creation
  - VM polling reads and deletes event-queue/ markers

Document Understanding
  - Rich OCR/table/key-value extraction for scanned PDFs and images
  - Text-only OCR fallback when rich extraction fails
  - No DU call for text-native files or PDFs with selectable text

Generative AI
  - Prompt size from extracted text and system instructions
  - Response size for structured JSON analysis
  - Model family and on-demand pricing unit
  - Reprocessing and retries

Networking
  - Public IP reservation
  - NAT Gateway and outbound data transfer
  - Load balancer hours and bandwidth (Enterprise only)

Additional services (Enterprise)
  - Autonomous Database Serverless OCPU and storage
  - OCI Vault key versions
  - OCI Logging ingestion
  - OCI Functions invocations and compute
```

## Extraction Cost Logic

The extraction path materially changes Document Understanding usage:

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
  -> Document Understanding rich extraction
  -> for scanned PDFs above synchronous request limits, multiple DU chunk requests are made and merged
  -> GenAI

Image or scanned PDF where rich extraction fails
  -> Object Storage upload
  -> Document Understanding rich extraction attempt (billable)
  -> Document Understanding text-only OCR fallback (billable)
  -> GenAI
```

The same document type produces very different cost profiles:

```text
1-page text PDF       -> Object Storage + GenAI
1-page scanned receipt -> Object Storage + DU rich + GenAI
12-page scanned PDF    -> Object Storage + 3 DU rich chunk requests + GenAI
1-page scan where DU rich fails -> Object Storage + DU rich attempt + DU OCR fallback + GenAI
```

Document Understanding billing remains page-driven in the estimate. Chunking changes the number of API requests for scanned PDFs above OCI's synchronous per-request limits, not the number of source pages being OCR processed.

## Pricing References

Oracle pricing changes over time. Verify current prices before any planning exercise:

```text
Oracle Cloud Price List:
https://www.oracle.com/cloud/price-list/

Oracle Cost Estimator:
https://www.oracle.com/cloud/costestimator/

OCI Generative AI on-demand pricing:
https://docs.oracle.com/en-us/iaas/Content/generative-ai/pay-on-demand.htm

OCI Always Free resource reference:
https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm
```

Illustrative unit prices used in this document (verify before use):

```text
VM.Standard.A1.Flex OCPU            $0.010 / OCPU-hour
VM.Standard.A1.Flex memory          $0.0015 / GB-hour
  Always Free allowance             3,000 OCPU-hours and 18,000 GB-hours per tenancy per month

VM.Standard.E5.Flex OCPU            $0.025 / OCPU-hour
VM.Standard.E5.Flex memory          $0.0015 / GB-hour

Boot volume storage                 $0.0255 / GB-month
Boot volume performance units       $0.0017 / GB-month

Object Storage Standard             $0.0255 / GB-month
Object Storage requests             $0.0034 / 10,000 requests

Document Understanding (rich OCR)   $1.50 / 1,000 pages
  First 1,000 pages per month       free
Document Understanding (text OCR)   $1.50 / 1,000 pages

Generative AI (Cohere Command R+)   ~$2.50 / 1M characters (combined input/output)
  This is a simplified illustrative rate. Actual pricing differs for input and output tokens.
  Check the OCI Generative AI price list for the current per-token or per-character rates.

Autonomous Database Serverless      $0.029 / OCPU-hour + $0.0255 / GB-month storage
OCI Load Balancer (Flexible)        ~$18 / month minimum + bandwidth
OCI Vault                           $1.50 / month per vault + $0.035 / month per key version
OCI Logging                         $0.50 / GB ingested (after 10 GB free per month)
OCI Functions                       $0.00002 / invocation + $0.00001417 / GB-second
```

## Small Deployment Estimate

### Assumptions

```text
Documents per month:      500
Text / selectable PDFs:   300  (60%)
Scanned / image docs:     200  (40%)
Average pages per doc:    3
DU text-only fallback:    10% of scanned docs = 20 docs
Average GenAI chars/doc:  20,000 characters (prompt + response)
Object Storage stored:    25 GB
Object Storage requests:  5,000 per month
Compute:                  1 x VM.Standard.A1.Flex, 2 OCPU, 12 GB RAM
Boot volume:              50 GB
Always Free A1:           Assumed available (see note below)
```

### Architecture

```text
Local laptop
  |
  | Terraform + Ansible
  v
OCI Compartment
  - 1 x VM.Standard.A1.Flex (2 OCPU, 12 GB)
  - 50 GB boot volume
  - VCN: public subnet, private subnet
  - Internet Gateway, NAT Gateway, Service Gateway
  - Private Object Storage bucket
  - OCI Document Understanding (on demand)
  - OCI Generative AI (on demand, Cohere Command R+)
```

### Monthly Estimate

All prices are illustrative. Replace with current Oracle price list values.

```text
+-----------------------------+------------+----------+----------+-------------+
| Service                     | Quantity   | Unit     | Price    | Monthly     |
+-----------------------------+------------+----------+----------+-------------+
| A1 OCPU (730h, 2 OCPU)      | 1,460 h    | OCPU-h   | $0.010   | $14.60      |
| A1 Memory (730h, 12 GB)     | 8,760 h    | GB-h     | $0.0015  | $13.14      |
|   A1 Always Free credit     |            |          |          | -$27.74 *   |
| Boot volume storage (50 GB) | 50 GB      | GB-month | $0.0255  | $1.28       |
| Boot volume VPUs (50 GB)    | 50 GB      | GB-month | $0.0017  | $0.09       |
| Object Storage (25 GB)      | 25 GB      | GB-month | $0.0255  | $0.64       |
| Object Storage requests     | 5,000 req  | 10K req  | $0.0034  | $0.00 **    |
| DU rich extraction (600 pg) | 600 pages  | 1K pages | $1.50    | $0.90 ***   |
| DU text-only fallback       | 60 pages   | 1K pages | $1.50    | $0.09       |
| Generative AI (10M chars)   | 10 units   | 1M chars | $2.50    | $25.00      |
| NAT Gateway                 | 730 h      | flat     | —        | ~$5.00      |
| Public IP                   | 730 h      | flat     | —        | ~$3.00      |
| Outbound data               | ~2 GB      | GB       | varies   | ~$1.00      |
+-----------------------------+------------+----------+----------+-------------+
| Total (with A1 Always Free) |            |          |          | ~$40/month  |
| Total (without Always Free) |            |          |          | ~$68/month  |
+-----------------------------+------------+----------+----------+-------------+

*   A1 Always Free: 3,000 OCPU-hours and 18,000 GB-hours per tenancy per month.
    This VM uses 1,460 OCPU-hours and 8,760 GB-hours and fits within the allowance
    if no other A1 resources consume the shared pool.

**  Requests cost is negligible at this volume.

*** DU free tier: first 1,000 pages per month are free. At 600 pages this VM may
    pay nothing in early months; above 1,000 pages the rate above applies.
```

### Range and Confidence

```text
Estimated monthly range:    $25 to $100
Confidence:                 low
Primary drivers:            GenAI usage and A1 Always Free eligibility
Main uncertainties:
  - Whether A1 Always Free is available in the tenancy
  - Actual GenAI character count per document
  - Scan ratio and DU fallback frequency
  - Data transfer pricing by region
```

## Enterprise Deployment Estimate

### Assumptions

```text
Documents per month:      15,000
Text / selectable PDFs:   8,250  (55%)
Scanned / image docs:     6,750  (45%)
Average pages per doc:    4
DU text-only fallback:    8% of scanned docs = 540 docs
Average GenAI chars/doc:  30,000 characters (prompt + response)
Object Storage stored:    500 GB
Object Storage requests:  50,000 per month
Compute:                  3 x VM.Standard.E5.Flex, 4 OCPU, 32 GB each
Boot volumes:             3 x 100 GB
Database:                 Autonomous Database Serverless, 2 OCPU baseline, 1 TB
Logging:                  50 GB ingested per month
Vault:                    1 vault, 10 key versions
Load Balancer:            1 x Flexible, 100 Mbps
Functions:                100,000 invocations, avg 5 seconds at 256 MB each
```

### Architecture

```text
Internet
  |
  v
OCI Load Balancer (Flexible)
  |
  v
OCI Compartment
  - 3 x VM.Standard.E5.Flex (4 OCPU, 32 GB each)
  - 3 x 100 GB boot volumes
  - VCN: public subnet, private subnet
  - Internet Gateway, NAT Gateway, Service Gateway
  - OCI Vault (secrets and API key rotation)
  - Autonomous Database Serverless (metadata and workflow)
  - Private Object Storage bucket (documents and compliance KB)
  - OCI Logging (application and audit logs)
  - OCI Events + Functions (automated processing triggers)
  - OCI Document Understanding (on demand)
  - OCI Generative AI (on demand, Cohere Command R+)
```

### Monthly Estimate

All prices are illustrative. Replace with current Oracle price list values.

```text
+------------------------------------------+------------+----------+----------+--------------+
| Service                                  | Quantity   | Unit     | Price    | Monthly      |
+------------------------------------------+------------+----------+----------+--------------+
| Compute                                                                                     |
|   E5 Flex OCPU (3 VMs x 4 OCPU x 730h)  | 8,760 h    | OCPU-h   | $0.025   | $219.00      |
|   E5 Flex Memory (3 VMs x 32 GB x 730h) | 70,080 h   | GB-h     | $0.0015  | $105.12      |
|   Boot volumes (3 x 100 GB storage)      | 300 GB     | GB-month | $0.0255  | $7.65        |
|   Boot volumes (3 x 100 GB VPUs)         | 300 GB     | GB-month | $0.0017  | $0.51        |
+------------------------------------------+------------+----------+----------+--------------+
| Database                                                                                    |
|   ADB Serverless OCPU (2 x 730h)         | 1,460 h    | OCPU-h   | $0.029   | $42.34       |
|   ADB Serverless Storage (1 TB)          | 1,000 GB   | GB-month | $0.0255  | $25.50       |
+------------------------------------------+------------+----------+----------+--------------+
| Networking                                                                                  |
|   Load Balancer (flexible minimum)       | 1          | month    | $18.00   | $18.00       |
|   NAT Gateway                            | —          | flat     | —        | ~$10.00      |
|   Public IPs (3 VMs)                     | 3          | each     | ~$3.00   | $9.00        |
|   Outbound data (~20 GB)                 | 20 GB      | GB       | varies   | ~$10.00      |
+------------------------------------------+------------+----------+----------+--------------+
| Storage                                                                                     |
|   Object Storage (500 GB)                | 500 GB     | GB-month | $0.0255  | $12.75       |
|   Object Storage requests (50K)          | 50K req    | 10K req  | $0.0034  | $0.02        |
+------------------------------------------+------------+----------+----------+--------------+
| AI Services                                                                                 |
|   DU rich extraction (27,000 pages)      | 26 units * | 1K pages | $1.50    | $39.00       |
|   DU text-only fallback (2,160 pages)    | 2.16 units | 1K pages | $1.50    | $3.24        |
|   Generative AI (450M chars)             | 450 units  | 1M chars | $2.50    | $1,125.00    |
+------------------------------------------+------------+----------+----------+--------------+
| Operations                                                                                  |
|   OCI Vault (1 vault + 10 key versions)  | —          | month    | —        | ~$2.00       |
|   OCI Logging (40 GB billed **)          | 40 GB      | GB       | $0.50    | $20.00       |
|   OCI Functions (100K inv, 5s, 256MB)    | —          | month    | —        | ~$20.00      |
+------------------------------------------+------------+----------+----------+--------------+
| TOTAL                                    |            |          |          | ~$1,669/month|
+------------------------------------------+------------+----------+----------+--------------+

*  DU free tier covers the first 1,000 pages per month. 27,000 - 1,000 = 26,000 pages billed.

** OCI Logging free tier: 10 GB per month. 50 GB - 10 GB = 40 GB billed.
```

### Range and Confidence

```text
Estimated monthly range:    $1,500 to $3,500
Confidence:                 very low
Primary driver:             Generative AI (accounts for ~65% of this estimate)
Secondary driver:           Compute (accounts for ~20% of this estimate)
Main uncertainties:
  - Actual GenAI character count per document (most sensitive variable)
  - Percentage of scanned documents that trigger DU
  - ADB OCPU autoscaling above 2 OCPU baseline under load
  - Functions invocation volume and execution duration
  - Data transfer and outbound pricing by region
  - Enterprise support tier (not included in estimate)
  - Negotiated discounts or Universal Credits

Sensitivity check (GenAI):
  At 15,000 docs per month, each 10,000 character increase in average document
  size adds 150M characters and approximately $375/month to the GenAI line item.
  Keep MAX_DOCUMENT_CHARS tuned and review prompt engineering to control this cost.
```

## Monthly Worksheet

Replace every unit price with the current Oracle price list or contracted rate.

```text
hours_per_month = 730

Compute OCPU cost
  = instance_count x ocpus_per_instance x hours_per_month
  x ocpu_hour_unit_price

Compute memory cost
  = instance_count x memory_gb_per_instance x hours_per_month
  x memory_gb_hour_unit_price

A1 Always Free credit (Small only)
  = min(total_a1_ocpu_hours, tenancy_free_ocpu_hours)
  x ocpu_hour_unit_price
  + min(total_a1_memory_gb_hours, tenancy_free_memory_gb_hours)
  x memory_gb_hour_unit_price

Boot volume cost per VM
  = boot_volume_gb x (boot_volume_storage_price + boot_volume_vpu_price)

Object Storage cost
  = stored_gb x object_storage_gb_month_price
  + (object_storage_requests / 10000) x request_unit_price

Document Understanding cost
  = max(0, rich_extraction_pages - 1000) / 1000 x rich_du_page_price
  + text_only_ocr_fallback_pages / 1000 x ocr_page_price

Generative AI cost
  = total_characters_per_month / 1_000_000 x genai_per_million_chars_price

Autonomous Database cost (Enterprise)
  = adb_ocpu_hours x adb_ocpu_hour_price
  + adb_storage_gb x object_storage_gb_month_price

Load Balancer cost (Enterprise)
  = lb_minimum_monthly_price
  + bandwidth_mbps x lb_bandwidth_unit_price

OCI Logging cost (Enterprise)
  = max(0, ingested_gb - 10) x logging_gb_price

OCI Functions cost (Enterprise)
  = invocations x function_invocation_price
  + invocations x duration_seconds x memory_gb x function_compute_price

Network cost
  = public_ip_count x public_ip_monthly_price
  + nat_gateway_flat_charge
  + outbound_data_gb x outbound_data_unit_price

Estimated monthly total
  = compute
  + boot_volumes
  + object_storage
  + document_understanding
  + generative_ai
  + database          (Enterprise)
  + load_balancer     (Enterprise)
  + vault             (Enterprise)
  + logging           (Enterprise)
  + functions         (Enterprise)
  + network
```

## Worked Usage Examples

### Example 1 - 500 Documents (Small Deployment)

```text
Documents:                500
Text / selectable PDFs:   300  (60%)
Scanned / image docs:     200  (40%), avg 3 pages each = 600 DU pages
DU text-only fallback:    10% of 200 = 20 docs, 3 pages = 60 pages
GenAI chars per doc:      20,000

DU rich extraction pages: 600
DU pages after free tier: max(0, 600 - 1000) = 0 in first month; 600 after free tier expires
DU fallback pages:        60

GenAI characters total:
  500 docs x 20,000 chars = 10,000,000 characters

GenAI cost estimate:
  10 units x $2.50 = $25.00

DU cost estimate (after free tier):
  (600 + 60) / 1,000 x $1.50 = $0.99
```

### Example 2 - 15,000 Documents (Enterprise Deployment)

```text
Documents:                15,000
Text / selectable PDFs:   8,250  (55%)
Scanned / image docs:     6,750  (45%), avg 4 pages each = 27,000 DU pages
DU text-only fallback:    8% of 6,750 = 540 docs, 4 pages = 2,160 pages
GenAI chars per doc:      30,000

DU rich extraction pages: 27,000
DU pages after free tier: 27,000 - 1,000 = 26,000
DU fallback pages:        2,160

GenAI characters total:
  15,000 docs x 30,000 chars = 450,000,000 characters

GenAI cost estimate:
  450 units x $2.50 = $1,125.00

DU cost estimate:
  (26,000 + 2,160) / 1,000 x $1.50 = $42.24
```

### Example 3 - Reprocessing and Retry Impact

```text
If a failed scanned document is retried 3 times:
  Object Storage uploads: 3
  DU rich extraction attempts: up to 3  (each attempt is billable)
  DU text-only OCR fallback calls: up to 3 if rich extraction fails each time
  GenAI calls: only for attempts where extraction succeeds

At the Enterprise tier, 100 retry events per month could add:
  DU pages: 100 x 3 retries x 4 pages = 1,200 additional pages
  DU cost: 1,200 / 1,000 x $1.50 = $1.80
  GenAI (if extraction succeeds): 100 x $2.50 = $0.25 per million chars of retry content
```

## Cost Controls

```text
Both Tiers
  Use text-native documents or PDFs with selectable text when possible.
  Keep scans clear, upright, and below MAX_UPLOAD_MB.
  Tune MAX_DOCUMENT_CHARS to prevent oversized GenAI prompts.
  Avoid repeatedly retrying the same failed scanned document.
  Store generated reports and JSON results; do not reprocess unchanged documents.
  Keep the default 30-day document retention unless the customer approves a different period.
  Apply Object Storage lifecycle policies for documents no longer needed.
  Run OCI Preflight intentionally, not in a tight loop.
  Tag all resources with project and owner for Cost Analysis filtering.
  Set OCI Budget alerts at 50% and 90% of expected monthly spend.
  Review OCI Cost Analysis after every significant processing run.

Small Tier
  Stop or resize the VM when the portal is not in active use.
  Monitor A1 Always Free consumption across the tenancy.
  Delete demo data and test uploads that are no longer needed.

Enterprise Tier
  Enable Autonomous Database autoscaling only if needed; monitor OCPU scaling events.
  Set maximum OCPU autoscaling limits on the ADB instance.
  Review OCI Functions execution duration and memory allocation; right-size both.
  Apply Object Storage lifecycle rules (archive or delete) for documents past SLA retention.
  Review OCI Logging retention period to avoid unnecessary ingestion of old log data.
  Use Universal Credits or commit-based pricing if monthly consumption is predictable.
  Request a formal Oracle quote for negotiated rates before production launch.
```

## What To Watch In OCI Cost Analysis

```text
Both Tiers
  AI Services
    - Document Understanding page counts and transaction tiers
    - Generative AI character or token consumption by model
  Object Storage
    - Storage GB-month growth over time
    - Request count spikes from bulk processing or retries
  Compute
    - OCPU and memory hours vs. Always Free allowance (Small)
    - Boot volume charges
  Networking
    - Outbound data transfer volume
    - NAT Gateway usage from VM-to-OCI-service calls

Enterprise Only
  Database
    - ADB Serverless autoscaling events and OCPU hours above baseline
    - ADB storage growth vs. retention policy
  Load Balancer
    - Bandwidth charges at higher ingress volumes
  Functions
    - Invocation count growth as document automation scales
    - Execution time and memory per invocation
  Logging
    - Ingestion GB-month; consider reducing log verbosity if cost rises
  Vault
    - Key version count; archive retired key versions when possible
```
