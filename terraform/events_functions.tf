# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
resource "oci_functions_application" "object_intake" {
  count          = var.enable_automatic_processing ? 1 : 0
  compartment_id = var.compartment_id
  display_name   = "doc-review-object-intake"
  subnet_ids     = [oci_core_subnet.private.id]
  freeform_tags  = var.freeform_tags

  config = {
    OCI_REGION      = var.region
    OCI_NAMESPACE   = var.object_storage_namespace
    OCI_BUCKET_NAME = oci_objectstorage_bucket.documents.name
  }
}

resource "oci_functions_function" "object_intake" {
  count              = var.enable_automatic_processing ? 1 : 0
  application_id     = oci_functions_application.object_intake[0].id
  display_name       = "doc-review-object-intake"
  image              = trimspace(var.automatic_processing_function_image)
  memory_in_mbs      = var.function_memory_in_mbs
  timeout_in_seconds = var.function_timeout_in_seconds
  freeform_tags      = var.freeform_tags

  config = {
    OCI_REGION      = var.region
    OCI_NAMESPACE   = var.object_storage_namespace
    OCI_BUCKET_NAME = oci_objectstorage_bucket.documents.name
    INCOMING_PREFIX = var.event_intake_incoming_prefix
    QUEUE_PREFIX    = var.event_intake_queue_prefix
  }
}

resource "oci_identity_dynamic_group" "object_intake_function" {
  provider       = oci.home
  count          = var.enable_automatic_processing ? 1 : 0
  compartment_id = var.tenancy_id
  name           = "doc-review-object-intake-functions"
  description    = "OCI Functions allowed to queue Object Storage document intake events."
  matching_rule  = "ALL {resource.type = 'fnfunc', resource.id = '${oci_functions_function.object_intake[0].id}'}"
  freeform_tags  = var.freeform_tags
}

resource "oci_identity_policy" "object_intake_function" {
  provider       = oci.home
  count          = var.enable_automatic_processing ? 1 : 0
  compartment_id = var.parent_compartment_id
  name           = "doc-review-object-intake-function-policy"
  description    = "Allow the document intake function to write queue markers in the project bucket."

  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.object_intake_function[0].name} to manage objects in compartment id ${var.compartment_id} where target.bucket.name='${oci_objectstorage_bucket.documents.name}'",
  ]

  freeform_tags = var.freeform_tags
}

resource "oci_events_rule" "object_intake" {
  count          = var.enable_automatic_processing ? 1 : 0
  compartment_id = var.compartment_id
  display_name   = "doc-review-incoming-object-events"
  description    = "Invoke the intake function when Object Storage objects are created."
  is_enabled     = true
  freeform_tags  = var.freeform_tags

  condition = jsonencode({
    eventType = ["com.oraclecloud.objectstorage.createobject"]
    data = {
      additionalDetails = {
        bucketName = [oci_objectstorage_bucket.documents.name]
      }
    }
  })

  actions {
    actions {
      action_type = "FAAS"
      is_enabled  = true
      function_id = oci_functions_function.object_intake[0].id
    }
  }

  depends_on = [
    oci_identity_policy.object_intake_function,
  ]
}
