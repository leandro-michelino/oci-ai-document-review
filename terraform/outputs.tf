output "bucket_name" {
  value = oci_objectstorage_bucket.documents.name
}

output "bucket_namespace" {
  value = oci_objectstorage_bucket.documents.namespace
}

output "compartment_id" {
  value = var.compartment_id
}

output "genai_region" {
  value = var.genai_region
}

output "instance_public_ip" {
  value = oci_core_instance.app.public_ip
}

output "streamlit_url" {
  value = "http://${oci_core_instance.app.public_ip}:8501"
}

output "ssh_command" {
  value = "ssh -i ${replace(var.ssh_public_key_path, ".pub", "")} opc@${oci_core_instance.app.public_ip}"
}

output "vcn_id" {
  value = oci_core_vcn.app.id
}

output "public_subnet_id" {
  value = oci_core_subnet.public.id
}

output "private_subnet_id" {
  value = oci_core_subnet.private.id
}

output "internet_gateway_id" {
  value = oci_core_internet_gateway.app.id
}

output "nat_gateway_id" {
  value = oci_core_nat_gateway.app.id
}

output "service_gateway_id" {
  value = oci_core_service_gateway.app.id
}
