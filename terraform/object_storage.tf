resource "oci_objectstorage_bucket" "documents" {
  compartment_id = var.compartment_id
  namespace      = var.object_storage_namespace
  name           = var.bucket_name
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"

  versioning = "Disabled"

  freeform_tags = var.freeform_tags
}
