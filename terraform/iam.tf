# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
resource "oci_identity_policy" "admin_group" {
  provider       = oci.home
  count          = var.enable_admin_group_policy && trimspace(var.admin_group_name) != "" ? 1 : 0
  compartment_id = var.parent_compartment_id
  name           = "${var.resource_prefix}-admin-policy"
  description    = "Least-privilege access for the OCI AI Document Review Portal MVP."

  statements = [
    "Allow group ${trimspace(var.admin_group_name)} to manage objects in compartment id ${var.compartment_id}",
    "Allow group ${trimspace(var.admin_group_name)} to use ai-service-document-family in compartment id ${var.compartment_id}",
    "Allow group ${trimspace(var.admin_group_name)} to use generative-ai-family in compartment id ${var.compartment_id}",
  ]

  freeform_tags = var.freeform_tags
}

resource "oci_identity_dynamic_group" "app_instance" {
  provider       = oci.home
  count          = var.enable_instance_principal ? 1 : 0
  compartment_id = var.tenancy_id
  name           = "${var.resource_prefix}-app-instance"
  description    = "Only the document-review VM may use the runtime instance-principal policy."
  matching_rule  = "ALL {instance.id = '${oci_core_instance.app.id}'}"
  freeform_tags  = var.freeform_tags
}

resource "oci_identity_policy" "app_instance" {
  provider       = oci.home
  count          = var.enable_instance_principal ? 1 : 0
  compartment_id = var.parent_compartment_id
  name           = "${var.resource_prefix}-app-instance-policy"
  description    = "Bucket-scoped storage and compartment-scoped AI access for the review VM."

  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.app_instance[0].name} to read buckets in compartment id ${var.compartment_id} where target.bucket.name='${oci_objectstorage_bucket.documents.name}'",
    "Allow dynamic-group ${oci_identity_dynamic_group.app_instance[0].name} to manage objects in compartment id ${var.compartment_id} where target.bucket.name='${oci_objectstorage_bucket.documents.name}'",
    "Allow dynamic-group ${oci_identity_dynamic_group.app_instance[0].name} to use ai-service-document-family in compartment id ${var.compartment_id}",
    "Allow dynamic-group ${oci_identity_dynamic_group.app_instance[0].name} to use generative-ai-family in compartment id ${var.compartment_id}",
  ]

  freeform_tags = var.freeform_tags
}
