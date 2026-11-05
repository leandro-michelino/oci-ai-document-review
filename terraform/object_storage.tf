# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
resource "oci_objectstorage_bucket" "documents" {
  compartment_id = var.compartment_id
  namespace      = var.object_storage_namespace
  name           = var.bucket_name
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"

  versioning = "Disabled"

  object_events_enabled = var.enable_automatic_processing

  freeform_tags = var.freeform_tags
}

resource "oci_objectstorage_object_lifecycle_policy" "documents_retention" {
  namespace  = var.object_storage_namespace
  bucket     = oci_objectstorage_bucket.documents.name
  depends_on = [time_sleep.lifecycle_policy_propagation]

  rules {
    name        = "delete-uploaded-documents-after-retention"
    action      = "DELETE"
    is_enabled  = true
    time_amount = tostring(var.retention_days)
    time_unit   = "DAYS"

    object_name_filter {
      inclusion_prefixes = ["documents/"]
    }
  }
}

resource "oci_identity_policy" "object_lifecycle_service" {
  provider       = oci.home
  count          = var.create_lifecycle_service_policy ? 1 : 0
  compartment_id = var.tenancy_id
  name           = "${var.resource_prefix}-object-lifecycle-service"
  description    = "Allow the regional Object Storage service to enforce this project's delete lifecycle."

  statements = [
    "Allow service objectstorage-${var.region} to manage object-family in compartment id ${var.compartment_id} where all {target.bucket.name='${oci_objectstorage_bucket.documents.name}', any {request.permission='BUCKET_INSPECT', request.permission='BUCKET_READ', request.permission='OBJECT_INSPECT', request.permission='OBJECT_DELETE', request.permission='OBJECT_VERSION_DELETE'}}",
  ]

  freeform_tags = var.freeform_tags
}

resource "time_sleep" "lifecycle_policy_propagation" {
  count           = var.create_lifecycle_service_policy ? 1 : 0
  depends_on      = [oci_identity_policy.object_lifecycle_service]
  create_duration = "${var.iam_propagation_wait_seconds}s"

  triggers = {
    policy_id = oci_identity_policy.object_lifecycle_service[0].id
  }
}
