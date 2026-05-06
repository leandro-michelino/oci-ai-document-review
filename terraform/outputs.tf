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

output "platform_summary" {
  description = "Operator-friendly summary for laptop-based deployment."
  value = {
    application = {
      name          = "OCI AI Document Review Portal"
      streamlit_url = "http://${oci_core_instance.app.public_ip}:8501"
      ssh_command   = "ssh -i ${replace(var.ssh_public_key_path, ".pub", "")} opc@${oci_core_instance.app.public_ip}"
      service_name  = "oci-ai-document-review"
      app_directory = "/opt/oci-ai-document-review"
    }

    regions = {
      runtime_region = var.region
      genai_region   = var.genai_region
      home_region    = var.home_region
    }

    storage = {
      bucket_name      = oci_objectstorage_bucket.documents.name
      bucket_namespace = oci_objectstorage_bucket.documents.namespace
    }

    network = {
      vcn_id                   = oci_core_vcn.app.id
      public_subnet_id         = oci_core_subnet.public.id
      private_subnet_id        = oci_core_subnet.private.id
      public_route_table       = oci_core_route_table.public.id
      private_route_table      = oci_core_route_table.private.id
      internet_gateway_id      = oci_core_internet_gateway.app.id
      nat_gateway_id           = oci_core_nat_gateway.app.id
      service_gateway_id       = oci_core_service_gateway.app.id
      public_security_list_id  = oci_core_security_list.public.id
      private_security_list_id = oci_core_security_list.private.id
      nsgs_used                = false
    }

    access = {
      allowed_ingress_cidr = var.allowed_ingress_cidr
      public_ports         = [22, 8501]
      auth_mode            = "existing OCI config copied by Ansible from local laptop"
    }

    operations = {
      service_status = "sudo systemctl status oci-ai-document-review"
      service_logs   = "sudo journalctl -u oci-ai-document-review -f"
      restart        = "sudo systemctl restart oci-ai-document-review"
      app_env        = "/opt/oci-ai-document-review/.env"
      local_redeploy = "./scripts/deploy.sh"
    }
  }
}
