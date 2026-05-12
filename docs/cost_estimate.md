# Cost Estimate

This is a simple planning estimate for the OCI AI Document Review Portal. It is not an Oracle quote.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.6.0`

## Read This First

- Prices are illustrative public-list planning inputs reviewed on 2026-05-10.
- Real cost depends on region, tenancy discounts, free-tier eligibility, selected model, document volume, scan quality, retries, and retention.
- Use the Oracle Cost Estimator, OCI Cost Analysis, and an Oracle representative quote before budgeting production use.
- Oracle pricing pages can render numeric values dynamically and may differ by geography, currency, contract, and date. Treat the values below as worksheet inputs to verify, not as a quote.

## Quick Estimate

```text
+----------------------+--------------------------+----------------------------+
| Tier                 | Small                    | Enterprise                 |
+----------------------+--------------------------+----------------------------+
| Monthly documents    | 100 - 500                | 10,000 - 20,000            |
| Runtime              | 1 x A1 Flex VM           | 3 x E5 Flex VMs            |
| Metadata             | Local JSON               | Autonomous Database        |
| Automation           | Manual deploy            | Events + Functions         |
| Review logging       | VM journald              | OCI Logging                |
| Rough monthly cost   | $20 - $100               | $1,200 - $3,000            |
+----------------------+--------------------------+----------------------------+
```

These ranges assume the default Cohere Command R+ model, moderate prompt sizes, default 30-day retention, and normal retry behavior. GenAI characters and Document Understanding OCR or extraction pages are the main variable costs.

## Main Cost Drivers

```text
Generative AI
  Prompt characters + response characters.
  The app limits prompt size with MAX_DOCUMENT_CHARS.

Document Understanding
  Used only for images, scanned PDFs, and image-only PDFs.
  Text files and PDFs with selectable text avoid DU charges.
  Rich extraction and text-only OCR fallback can have different unit prices.

Compute
  Small tier can fit inside A1 Always Free if the tenancy has capacity and no other A1 resources use the allowance.

Storage and retention
  Uploaded documents, generated reports, and local metadata are retained for 30 days by default.

Retries
  Reprocessing failed scanned documents can repeat DU and GenAI calls.

Optional automatic intake
  OCI Events and Functions overhead is usually small for this workload.
  Function invocation and GB-second charges matter only after the free tier or
  when high-volume external uploads are enabled.
```

## Pricing Assumptions

Verify current values before use. The worksheet currently uses:

```text
VM.Standard.A1.Flex OCPU            $0.010 / OCPU-hour
VM.Standard.A1.Flex memory          $0.0015 / GB-hour
A1 Always Free allowance            3,000 OCPU-hours + 18,000 GB-hours/month

VM.Standard.E5.Flex OCPU            $0.025 / OCPU-hour
VM.Standard.E5.Flex memory          $0.0015 / GB-hour

Object Storage Standard             $0.0255 / GB-month
Document Understanding extraction   $10.00 / 1,000 transactions
Document Understanding OCR          $1.00 / 1,000 transactions
Document Understanding free tier    First 5,000 transactions/month

Generative AI Command R+            $0.0156 / 10,000 transactions
OCI Functions free tier             2M invocations + 400K GB-seconds/month
```

OCI Generative AI on-demand chat billing counts prompt plus response characters. The OCI pricing page treats 1 character as 1 transaction. Command R+ maps to the Large Cohere pricing line at the time of this review.

The Oracle price-list page was checked for the current product line items and units: Document Understanding still exposes first-5,000 and greater-than-5,000 transaction tiers, Large Cohere is listed per 10,000 transactions, and Functions lists free monthly invocation and GB-second bands. Re-check the numeric rates in your region before using this worksheet for customer estimates.

## Example Assumptions

```text
Small
  500 documents/month
  60% text/selectable PDFs
  40% scanned/image documents
  3 pages per document average
  20,000 GenAI characters per document
  Estimated monthly cost: about $20 - $35 with A1 Always Free, about $35 - $70 without it

Enterprise
  15,000 documents/month
  55% text/selectable PDFs
  45% scanned/image documents
  4 pages per document average
  30,000 GenAI characters per document
  3 x E5 Flex VMs assumed for the application tier
  Estimated monthly cost: about $1,200 - $1,800 before production add-ons
```

Small estimate notes:

```text
GenAI characters: 500 x 20,000 = 10,000,000 characters
Scanned pages:    500 x 40% x 3 = 600 DU pages
DU free tier:     scanned-page volume remains inside the 5,000 transaction band
Compute:          A1 may be free if capacity and tenancy allowance are available
```

Enterprise estimate notes:

```text
GenAI characters: 15,000 x 30,000 = 450,000,000 characters
Scanned pages:    15,000 x 45% x 4 = 27,000 DU pages
DU paid pages:    about 22,000 pages after the first 5,000 transaction band
Add-ons:          Autonomous Database, OCI Logging, Vault, budgets, and support
                  can dominate the final production estimate.
```

## Simple Formula

```text
GenAI cost
  = total_prompt_and_response_characters / 10,000
  x GenAI price per 10,000 transactions

Document Understanding cost
  = max(0, scanned_pages - free_transactions) / 1,000
  x DU extraction or OCR price
  + OCR_fallback_pages / 1,000
  x DU OCR price

Compute cost
  = OCPU hours x OCPU price
  + memory GB-hours x memory price

Total estimate
  = compute
  + storage
  + Document Understanding
  + Generative AI
  + optional enterprise services
```

## Cost Controls

- Prefer text-native files or PDFs with selectable text.
- Keep scans clear, upright, and below `MAX_UPLOAD_MB`.
- Tune `MAX_DOCUMENT_CHARS` before large runs.
- Avoid repeated retries on the same failed scanned document.
- Keep 30-day retention unless the customer requires longer.
- Use lifecycle policies for document objects.
- Run OCI Preflight intentionally, not in a loop.
- Add OCI Budgets alerts and review OCI Cost Analysis after bulk processing.
- Revisit the worksheet whenever changing `GENAI_MODEL_ID`, `MAX_DOCUMENT_CHARS`, scan quality, retry policy, or the automatic-intake volume.

## Useful References

```text
Oracle Cloud Price List:
https://www.oracle.com/cloud/price-list/

Oracle Cost Estimator:
https://www.oracle.com/cloud/costestimator/

OCI Generative AI on-demand pricing:
https://docs.oracle.com/en-us/iaas/Content/generative-ai/pay-on-demand.htm

OCI Cohere Command R+ pricing-page mapping:
https://docs.oracle.com/en-us/iaas/Content/generative-ai/cohere-command-r-plus-08-2024.htm

OCI Document Understanding pricing:
https://www.oracle.com/artificial-intelligence/document-understanding/pricing/

OCI Functions pricing:
https://www.oracle.com/cloud/cloud-native/functions/pricing/

OCI Always Free reference:
https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm
```
