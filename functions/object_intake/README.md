# Object Intake Function

Contact: Leandro Michelino | ACE | leandro.michelino@oracle.com. In case of any question, get in touch.

Current project version: `v0.6.1`

This OCI Function receives Object Storage create events for objects under
`incoming/` and writes a small JSON marker under `event-queue/`. The VM imports
those markers with `scripts/poll_event_queue.py`, downloads the original object,
and sends it through the normal document processing workflow.

Build and push this function image to OCIR with the OCI Functions tooling, then
set `enable_automatic_processing = true`, `tenancy_id`, and
`automatic_processing_function_image` in `terraform/terraform.tfvars`.
The setup wizard normalizes incoming and queue prefixes as relative Object
Storage prefixes, and Terraform rejects empty, absolute, or parent-directory
prefix values before apply.

The Function intentionally does not write VM-local metadata, approve documents,
or call Document Understanding or Generative AI. It only creates durable queue
markers in the private bucket so the VM can import them through the same worker
queue, retention, Dashboard, and Actions workflow used by portal uploads.

Object naming convention:

```text
incoming/<expense-name-or-reference>/<file>
incoming/<file>
```

The optional first path segment becomes the Dashboard and Actions expense name or
reference.

Runtime configuration is supplied by Terraform:

```text
OCI_REGION
OCI_NAMESPACE
OCI_BUCKET_NAME
INCOMING_PREFIX
QUEUE_PREFIX
```
