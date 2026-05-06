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

variable "tenancy_id" {
  description = "OCI tenancy OCID."
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
}

variable "instance_memory_gbs" {
  description = "Memory in GB for flexible shapes."
  type        = number
  default     = 6
}

variable "vcn_cidr" {
  description = "VCN CIDR."
  type        = string
  default     = "10.42.0.0/16"
}

variable "subnet_cidr" {
  description = "Public subnet CIDR."
  type        = string
  default     = "10.42.1.0/24"
}

variable "private_subnet_cidr" {
  description = "Private subnet CIDR for future backend services."
  type        = string
  default     = "10.42.2.0/24"
}
