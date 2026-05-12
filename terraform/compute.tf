# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_id
}

data "oci_core_images" "oracle_linux" {
  compartment_id           = var.compartment_id
  operating_system         = "Oracle Linux"
  operating_system_version = "9"
  shape                    = var.instance_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "app" {
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  compartment_id      = var.compartment_id
  display_name        = "doc-review-app"
  shape               = var.instance_shape
  freeform_tags       = var.freeform_tags

  shape_config {
    ocpus         = var.instance_ocpus
    memory_in_gbs = var.instance_memory_gbs
  }

  create_vnic_details {
    assign_public_ip = true
    display_name     = "doc-review-app-vnic"
    hostname_label   = "docreview"
    subnet_id        = oci_core_subnet.public.id
  }

  metadata = {
    ssh_authorized_keys = file(pathexpand(var.ssh_public_key_path))
  }

  source_details {
    source_type = "image"
    source_id   = data.oci_core_images.oracle_linux.images[0].id
  }
}
