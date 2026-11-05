# Cost Estimate

This is a simple planning estimate for the OCI AI Document Review Portal. It is not an Oracle quote.

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.8.0`

## Read This First

- Prices are illustrative public-list planning inputs captured on 2026-05-13;
  they are a historical worksheet, not current pricing.
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

These historical ranges use the worksheet's assumed GenAI unit rate, moderate prompt sizes, 30-day retention and ordinary retries. The unit rate has not been verified for the configured Cohere Command A model; these are not current model-specific estimates. GenAI characters and Document Understanding OCR or extraction pages are the main variable costs. VM boot volumes, networking egress, logging volume, support, taxes, and enterprise add-ons can move real totals outside these ranges.

## Main Cost Drivers

```text
Generative AI
  Prompt characters + response characters.
  MAX_DOCUMENT_CHARS limits extracted text. Instructions, OCR fields,
  retrieval context and responses add billable usage.

Document Understanding
  Used for images, scanned/image-only PDFs and mixed text/image PDFs.
  Text files and fully text-native PDFs avoid DU charges.
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

Verify current values before use. This historical worksheet uses Oracle
public-list units checked on 2026-05-13:

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

Generative AI configured model       Verify current regional price before use
OCI Functions free tier             2M invocations + 400K GB-seconds/month
```

Pricing-source review on 2026-11-05: the [official on-demand guide](https://docs.oracle.com/en-us/iaas/Content/generative-ai/pay-on-demand.htm) describes model-specific prices per 10,000 transactions or per 1,000,000 tokens. Transaction-priced chat counts prompt plus response characters. Use the billing unit and SKU for the selected model rather than assuming every model uses the same character rate.

The [Oracle price list](https://www.oracle.com/cloud/price-list/) exposes product/unit definitions, but numeric rates were not available in the retrieved page. The older Document Understanding pricing URL now redirects to its [cost estimator](https://www.oracle.com/artificial-intelligence/document-understanding/cost-estimator/). No updated London price, tenancy discount or actual invoice total was verified. Historical numbers below remain explicit assumptions.

The real London test confirmed provisioning, OCR and model operation; it did not establish monthly cost. IAM propagation waits and Dynamic Groups do not substitute for metering evidence. The single-VM Terraform configuration does not deploy the three-node/database enterprise planning scenario below.

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
GenAI estimate:   10,000,000 / 10,000 x $0.0156 = $15.60
Scanned pages:    500 x 40% x 3 = 600 DU pages
DU free tier:     scanned-page volume remains inside the 5,000 transaction band
Compute:          1 OCPU + 6 GB memory is about $13.87/month before Always Free
Total shape:      about $20 - $35 with A1 Always Free; about $35 - $70 without it
```

Enterprise estimate notes:

```text
GenAI characters: 15,000 x 30,000 = 450,000,000 characters
GenAI estimate:   450,000,000 / 10,000 x $0.0156 = $702.00
Scanned pages:    15,000 x 45% x 4 = 27,000 DU pages
DU paid pages:    about 22,000 pages after the first 5,000 transaction band
DU extraction:    22,000 / 1,000 x $10.00 = $220.00
Compute:          3 x E5 Flex nodes at 1 OCPU / 8 GB each is about $81.03/month
Add-ons:          Autonomous Database, OCI Logging, Vault, budgets, and support
                  can dominate the final production estimate.
```

## Simple Formula

Use the transaction formula only for a transaction-priced model. For a token-priced model, calculate input and output separately using that model's current per-million-token rates:

```text
GenAI token cost
  = input_tokens / 1,000,000 x input_rate
  + output_tokens / 1,000,000 x output_rate
```

The following character formula retains the historical worksheet's assumed unit:

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
- Re-check estimates after enabling enterprise services such as Autonomous Database, OCI Logging, Vault, private networking, or larger compute shapes.

## Useful References

```text
Oracle Cloud Price List:
https://www.oracle.com/cloud/price-list/

Oracle Cost Estimator:
https://www.oracle.com/cloud/costestimator/

OCI Generative AI on-demand pricing:
https://docs.oracle.com/en-us/iaas/Content/generative-ai/pay-on-demand.htm

OCI Document Understanding pricing:
https://www.oracle.com/artificial-intelligence/document-understanding/pricing/

OCI Functions pricing:
https://www.oracle.com/cloud/cloud-native/functions/pricing/

OCI Always Free reference:
https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm
```
