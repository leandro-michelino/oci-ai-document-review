# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
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

output "ssh_private_key_path" {
  value = pathexpand(replace(var.ssh_public_key_path, ".pub", ""))
}

output "retention_days" {
  value = var.retention_days
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

output "automatic_processing_enabled" {
  value = var.enable_automatic_processing
}

output "event_intake_incoming_prefix" {
  value = var.event_intake_incoming_prefix
}

output "event_intake_queue_prefix" {
  value = var.event_intake_queue_prefix
}

output "event_intake_poll_seconds" {
  value = var.event_intake_poll_seconds
}

output "object_intake_function_id" {
  value = (
    var.enable_automatic_processing
    ? oci_functions_function.object_intake[0].id
    : null
  )
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
      incoming_prefix  = var.event_intake_incoming_prefix
      queue_prefix     = var.event_intake_queue_prefix
    }

    automatic_processing = {
      enabled              = var.enable_automatic_processing
      object_events        = var.enable_automatic_processing
      function_id          = var.enable_automatic_processing ? oci_functions_function.object_intake[0].id : null
      vm_poll_seconds      = var.event_intake_poll_seconds
      intake_object_prefix = var.event_intake_incoming_prefix
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
      ssh_private_key_path = pathexpand(replace(var.ssh_public_key_path, ".pub", ""))
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
