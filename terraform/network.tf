# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
resource "oci_core_vcn" "app" {
  compartment_id = var.compartment_id
  display_name   = "doc-review-vcn"
  cidr_block     = var.vcn_cidr
  dns_label      = "docreview"
  freeform_tags  = var.freeform_tags
}

resource "oci_core_internet_gateway" "app" {
  compartment_id = var.compartment_id
  display_name   = "doc-review-igw"
  vcn_id         = oci_core_vcn.app.id
  enabled        = true
  freeform_tags  = var.freeform_tags
}

resource "oci_core_nat_gateway" "app" {
  compartment_id = var.compartment_id
  display_name   = "doc-review-natgw"
  vcn_id         = oci_core_vcn.app.id
  freeform_tags  = var.freeform_tags
}

data "oci_core_services" "oracle_services" {
  filter {
    name   = "name"
    values = ["All .* Services In Oracle Services Network"]
    regex  = true
  }
}

resource "oci_core_service_gateway" "app" {
  compartment_id = var.compartment_id
  display_name   = "doc-review-sgw"
  vcn_id         = oci_core_vcn.app.id
  freeform_tags  = var.freeform_tags

  services {
    service_id = data.oci_core_services.oracle_services.services[0].id
  }
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_id
  display_name   = "doc-review-public-rt"
  vcn_id         = oci_core_vcn.app.id

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.app.id
  }

  freeform_tags = var.freeform_tags
}

resource "oci_core_route_table" "private" {
  compartment_id = var.compartment_id
  display_name   = "doc-review-private-rt"
  vcn_id         = oci_core_vcn.app.id

  route_rules {
    destination       = data.oci_core_services.oracle_services.services[0].cidr_block
    destination_type  = "SERVICE_CIDR_BLOCK"
    network_entity_id = oci_core_service_gateway.app.id
  }

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.app.id
  }

  freeform_tags = var.freeform_tags
}

resource "oci_core_security_list" "public" {
  compartment_id = var.compartment_id
  display_name   = "doc-review-public-sl"
  vcn_id         = oci_core_vcn.app.id

  ingress_security_rules {
    protocol = "6"
    source   = var.allowed_ingress_cidr

    tcp_options {
      min = 22
      max = 22
    }
  }

  ingress_security_rules {
    protocol = "6"
    source   = var.allowed_ingress_cidr

    tcp_options {
      min = 8501
      max = 8501
    }
  }

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }

  freeform_tags = var.freeform_tags
}

resource "oci_core_security_list" "private" {
  compartment_id = var.compartment_id
  display_name   = "doc-review-private-sl"
  vcn_id         = oci_core_vcn.app.id

  ingress_security_rules {
    protocol = "6"
    source   = var.vcn_cidr

    tcp_options {
      min = 1
      max = 65535
    }
  }

  ingress_security_rules {
    protocol = "1"
    source   = var.vcn_cidr
  }

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }

  freeform_tags = var.freeform_tags
}

resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_id
  display_name               = "doc-review-public-subnet"
  vcn_id                     = oci_core_vcn.app.id
  cidr_block                 = var.subnet_cidr
  dns_label                  = "public"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.public.id]
  prohibit_public_ip_on_vnic = false
  freeform_tags              = var.freeform_tags
}

resource "oci_core_subnet" "private" {
  compartment_id             = var.compartment_id
  display_name               = "doc-review-private-subnet"
  vcn_id                     = oci_core_vcn.app.id
  cidr_block                 = var.private_subnet_cidr
  dns_label                  = "private"
  route_table_id             = oci_core_route_table.private.id
  security_list_ids          = [oci_core_security_list.private.id]
  prohibit_public_ip_on_vnic = true
  freeform_tags              = var.freeform_tags
}
