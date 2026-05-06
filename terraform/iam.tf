resource "oci_identity_policy" "admin_group" {
  provider       = oci.home
  count          = var.enable_admin_group_policy && var.admin_group_name != "" ? 1 : 0
  compartment_id = var.parent_compartment_id
  name           = "doc-review-admin-policy"
  description    = "Least-privilege access for the OCI AI Document Review Portal MVP."

  statements = [
    "Allow group ${var.admin_group_name} to manage objects in compartment id ${var.compartment_id}",
    "Allow group ${var.admin_group_name} to use ai-service-document-family in compartment id ${var.compartment_id}",
    "Allow group ${var.admin_group_name} to use generative-ai-family in compartment id ${var.compartment_id}",
  ]

  freeform_tags = var.freeform_tags
}
