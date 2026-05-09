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
  namespace = var.object_storage_namespace
  bucket    = oci_objectstorage_bucket.documents.name

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
