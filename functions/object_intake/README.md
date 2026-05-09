# Object Intake Function

This OCI Function receives Object Storage create events for objects under
`incoming/` and writes a small JSON marker under `event-queue/`. The VM imports
those markers with `scripts/poll_event_queue.py`, downloads the original object,
and sends it through the normal document processing workflow.

Build and push this function image to OCIR with the OCI Functions tooling, then
set `automatic_processing_function_image` in `terraform/terraform.tfvars`.

Object naming convention:

```text
incoming/<expense-name-or-reference>/<file>
incoming/<file>
```

The optional first path segment becomes the Dashboard and Actions expense name or
reference.
