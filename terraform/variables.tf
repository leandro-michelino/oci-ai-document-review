variable "region" {
  description = "Primary OCI region for Object Storage and Document Understanding."
  type        = string
}

variable "genai_region" {
  description = "OCI Generative AI region discovered by scripts/setup.py."
  type        = string
}

variable "home_region" {
  description = "OCI tenancy home region for IAM writes."
  type        = string
}

variable "compartment_id" {
  description = "Project compartment OCID."
  type        = string
}

variable "parent_compartment_id" {
  description = "Parent compartment OCID."
  type        = string
}

variable "bucket_name" {
  description = "Private Object Storage bucket for uploaded documents."
  type        = string
  default     = "doc-review-input"
}

variable "tenancy_id" {
  description = "Tenancy OCID used only when automatic processing creates a Functions dynamic group."
  type        = string
  default     = ""

  validation {
    condition = (
      (
        !var.enable_automatic_processing &&
        (
          var.tenancy_id == "" ||
          can(regex("^ocid1\\.tenancy\\.", var.tenancy_id))
        )
      ) ||
      (
        var.enable_automatic_processing &&
        can(regex("^ocid1\\.tenancy\\.", var.tenancy_id))
      )
    )
    error_message = "tenancy_id must be a valid tenancy OCID when enable_automatic_processing is true."
  }
}

variable "enable_automatic_processing" {
  description = "Enable Object Storage events, OCI Functions, and VM queue import for incoming/ objects."
  type        = bool
  default     = false
}

variable "automatic_processing_function_image" {
  description = "OCIR image URI for functions/object_intake. Required when enable_automatic_processing is true."
  type        = string
  default     = ""

  validation {
    condition = (
      !var.enable_automatic_processing ||
      length(trimspace(var.automatic_processing_function_image)) > 0
    )
    error_message = "automatic_processing_function_image is required when enable_automatic_processing is true."
  }
}

variable "event_intake_incoming_prefix" {
  description = "Object Storage prefix watched for automatic document intake."
  type        = string
  default     = "incoming/"

  validation {
    condition = (
      length(trimspace(var.event_intake_incoming_prefix)) > 0 &&
      !startswith(trimspace(var.event_intake_incoming_prefix), "/") &&
      !can(regex("(^|/)\\.\\.(/|$)", trimspace(var.event_intake_incoming_prefix)))
    )
    error_message = "event_intake_incoming_prefix must be a non-empty relative Object Storage prefix."
  }
}

variable "event_intake_queue_prefix" {
  description = "Object Storage prefix where the intake Function writes VM queue markers."
  type        = string
  default     = "event-queue/"

  validation {
    condition = (
      length(trimspace(var.event_intake_queue_prefix)) > 0 &&
      !startswith(trimspace(var.event_intake_queue_prefix), "/") &&
      !can(regex("(^|/)\\.\\.(/|$)", trimspace(var.event_intake_queue_prefix)))
    )
    error_message = "event_intake_queue_prefix must be a non-empty relative Object Storage prefix."
  }
}

variable "event_intake_poll_seconds" {
  description = "VM systemd timer interval for importing function queue markers."
  type        = number
  default     = 60

  validation {
    condition     = var.event_intake_poll_seconds >= 30
    error_message = "event_intake_poll_seconds must be at least 30."
  }
}

variable "function_memory_in_mbs" {
  description = "Memory for the Object Storage intake function."
  type        = number
  default     = 256
}

variable "function_timeout_in_seconds" {
  description = "Timeout for the Object Storage intake function."
  type        = number
  default     = 30
}

variable "retention_days" {
  description = "Number of days to retain uploaded document objects and local VM runtime artifacts."
  type        = number
  default     = 30

  validation {
    condition     = var.retention_days > 0
    error_message = "retention_days must be greater than zero."
  }
}

variable "object_storage_namespace" {
  description = "Object Storage namespace discovered by scripts/setup.py."
  type        = string
}

variable "enable_admin_group_policy" {
  description = "Create a least-privilege policy for a named user group."
  type        = bool
  default     = false
}

variable "admin_group_name" {
  description = "Existing OCI IAM group name for local developers."
  type        = string
  default     = ""
}

variable "freeform_tags" {
  description = "Freeform tags applied to resources."
  type        = map(string)
  default = {
    project = "oci-ai-document-review"
  }
}

variable "allowed_ingress_cidr" {
  description = "CIDR allowed to access SSH and Streamlit."
  type        = string

  validation {
    condition = (
      can(cidrnetmask(var.allowed_ingress_cidr)) &&
      var.allowed_ingress_cidr != "0.0.0.0/0" &&
      var.allowed_ingress_cidr != "::/0"
    )
    error_message = "allowed_ingress_cidr must be a valid, narrow CIDR and must not be 0.0.0.0/0 or ::/0."
  }
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key for the compute instance."
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

variable "instance_shape" {
  description = "Compute shape for the Streamlit runtime."
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "instance_ocpus" {
  description = "OCPUs for flexible shapes."
  type        = number
  default     = 1

  validation {
    condition     = var.instance_ocpus > 0
    error_message = "instance_ocpus must be greater than zero."
  }
}

variable "instance_memory_gbs" {
  description = "Memory in GB for flexible shapes."
  type        = number
  default     = 6

  validation {
    condition     = var.instance_memory_gbs > 0
    error_message = "instance_memory_gbs must be greater than zero."
  }
}

variable "vcn_cidr" {
  description = "VCN CIDR."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vcn_cidr))
    error_message = "vcn_cidr must be a valid CIDR block."
  }
}

variable "subnet_cidr" {
  description = "Public subnet CIDR."
  type        = string
  default     = "10.42.1.0/24"

  validation {
    condition     = can(cidrnetmask(var.subnet_cidr))
    error_message = "subnet_cidr must be a valid CIDR block."
  }
}

variable "private_subnet_cidr" {
  description = "Private subnet CIDR for future backend services."
  type        = string
  default     = "10.42.2.0/24"

  validation {
    condition     = can(cidrnetmask(var.private_subnet_cidr))
    error_message = "private_subnet_cidr must be a valid CIDR block."
  }
}
