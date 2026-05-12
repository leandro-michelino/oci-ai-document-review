#!/usr/bin/env bash
# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT_DIR/terraform"
DEPLOY_DIR="$ROOT_DIR/.deploy"
ARCHIVE="$DEPLOY_DIR/oci-ai-document-review.tar.gz"
INVENTORY="$DEPLOY_DIR/inventory.ini"
OCI_RUNTIME_META="$DEPLOY_DIR/oci_existing_config.env"

section() {
  local title="$1"
  printf '\n============================================================\n'
  printf '%s\n' "$title"
  printf '============================================================\n'
}

step() {
  printf '%s\n' "-> $1"
}

wait_for_ssh() {
  local ssh_key_path="$1"
  local public_ip="$2"

  step "Waiting for SSH and cloud-init on $public_ip so Ansible can take over"
  for _ in {1..60}; do
    if ssh \
      -o BatchMode=yes \
      -o ConnectTimeout=8 \
      -o StrictHostKeyChecking=accept-new \
      -i "$ssh_key_path" \
      "opc@$public_ip" "if command -v cloud-init >/dev/null 2>&1; then sudo cloud-init status --wait >/dev/null 2>&1 || true; fi" >/dev/null 2>&1; then
      step "SSH and cloud-init are ready"
      return 0
    fi
    sleep 5
  done

  echo "Timed out waiting for SSH on $public_ip."
  echo "Check that the VM is running and that your allowed_ingress_cidr includes this laptop."
  return 1
}

verify_portal() {
  local streamlit_url="$1"

  step "Checking browser-facing portal endpoint"
  for _ in {1..24}; do
    if curl -fsS -I --max-time 10 "$streamlit_url" >/dev/null; then
      step "Portal responded at $streamlit_url"
      return 0
    fi
    sleep 5
  done

  echo "The portal service started on the VM, but $streamlit_url did not respond from this laptop."
  echo "Check the public security list, local network path, and VM firewall rules."
  return 1
}

cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo ".env not found. Run scripts/setup.py with your compartment values first."
  exit 1
fi

if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
  echo "Python virtual environment not found at .venv/bin/python."
  echo "Run: python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt"
  exit 1
fi

env_value() {
  local key="$1"
  awk -v key="$key" '
    index($0, key "=") == 1 {
      value = substr($0, length(key) + 2)
    }
    END {
      print value
    }
  ' .env | sed -e 's/^"//' -e 's/"$//'
}

OCI_REGION="$(env_value OCI_REGION)"
GENAI_REGION="$(env_value GENAI_REGION)"
OCI_CONFIG_FILE="$(env_value OCI_CONFIG_FILE)"
OCI_PROFILE="$(env_value OCI_PROFILE)"
OCI_COMPARTMENT_ID="$(env_value OCI_COMPARTMENT_ID)"
OCI_NAMESPACE="$(env_value OCI_NAMESPACE)"
OCI_BUCKET_NAME="$(env_value OCI_BUCKET_NAME)"
GENAI_MODEL_ID="$(env_value GENAI_MODEL_ID)"
GENAI_TEMPERATURE="$(env_value GENAI_TEMPERATURE)"
GENAI_MAX_TOKENS="$(env_value GENAI_MAX_TOKENS)"
DOCUMENT_AI_TIMEOUT_SECONDS="$(env_value DOCUMENT_AI_TIMEOUT_SECONDS)"
DOCUMENT_AI_RETRY_ATTEMPTS="$(env_value DOCUMENT_AI_RETRY_ATTEMPTS)"
STALE_PROCESSING_MINUTES="$(env_value STALE_PROCESSING_MINUTES)"
RETENTION_DAYS="$(env_value RETENTION_DAYS)"
MAX_PARALLEL_JOBS="$(env_value MAX_PARALLEL_JOBS)"
MAX_DOCUMENT_CHARS="$(env_value MAX_DOCUMENT_CHARS)"
MAX_UPLOAD_MB="$(env_value MAX_UPLOAD_MB)"
COMPLIANCE_ENTITIES_OBJECT_NAME="$(env_value COMPLIANCE_ENTITIES_OBJECT_NAME)"
EVENT_INTAKE_QUEUE_PREFIX="$(env_value EVENT_INTAKE_QUEUE_PREFIX)"
EVENT_INTAKE_INCOMING_PREFIX="$(env_value EVENT_INTAKE_INCOMING_PREFIX)"

export OCI_CONFIG_FILE="${OCI_CONFIG_FILE:-~/.oci/config}"
export OCI_PROFILE="${OCI_PROFILE:-DEFAULT}"

mkdir -p "$DEPLOY_DIR"

section "1/5 Prepare Deployment Package"
step "Using existing OCI API key from local OCI config"
"$ROOT_DIR/.venv/bin/python" - <<'PY' > "$OCI_RUNTIME_META"
import os
from pathlib import Path
import shlex

import oci

config_file = Path(os.environ.get("OCI_CONFIG_FILE", "~/.oci/config")).expanduser()
profile = os.environ.get("OCI_PROFILE", "DEFAULT")
config = oci.config.from_file(str(config_file), profile)
key_file = Path(config["key_file"]).expanduser()

values = {
    "OCI_USER_ID": config["user"],
    "OCI_TENANCY_ID": config["tenancy"],
    "OCI_FINGERPRINT": config["fingerprint"],
    "OCI_EXISTING_KEY_FILE": str(key_file),
}
for key, value in values.items():
    print(f"{key}={shlex.quote(value)}")
PY

# shellcheck disable=SC1090
source "$OCI_RUNTIME_META"

step "Building sanitized application archive at $ARCHIVE"
COPYFILE_DISABLE=1 tar \
  --exclude='./.git' \
  --exclude='./.env' \
  --exclude='./.env.*' \
  --exclude='./.deploy' \
  --exclude='./.venv' \
  --exclude='./.oci' \
  --exclude='./.pytest_cache' \
  --exclude='./.ruff_cache' \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='._*' \
  --exclude='./terraform/.terraform' \
  --exclude='./terraform/terraform.tfstate*' \
  --exclude='./terraform/terraform.tfvars' \
  --exclude='./terraform/*.tfvars' \
  --exclude='./terraform/*.tfvars.json' \
  --exclude='./*.pem' \
  --exclude='./*.key' \
  --exclude='./id_rsa*' \
  --exclude='./oci_api_key*' \
  --exclude='./data/metadata/*.json' \
  --exclude='./data/reports/*.md' \
  --exclude='./data/uploads/*' \
  -czf "$ARCHIVE" .

cd "$TF_DIR"
section "2/5 Provision Or Refresh OCI Infrastructure With Terraform"
step "Running terraform init"
terraform init
step "Running terraform apply"
terraform apply -auto-approve

PUBLIC_IP="$(terraform output -raw instance_public_ip)"
STREAMLIT_URL="$(terraform output -raw streamlit_url)"
SSH_COMMAND="$(terraform output -raw ssh_command)"
TF_SSH_PRIVATE_KEY_PATH="$(terraform output -raw ssh_private_key_path)"
VCN_ID="$(terraform output -raw vcn_id)"
PUBLIC_SUBNET_ID="$(terraform output -raw public_subnet_id)"
PRIVATE_SUBNET_ID="$(terraform output -raw private_subnet_id)"
IGW_ID="$(terraform output -raw internet_gateway_id)"
NATGW_ID="$(terraform output -raw nat_gateway_id)"
SGW_ID="$(terraform output -raw service_gateway_id)"
AUTOMATIC_PROCESSING_ENABLED="$(terraform output -raw automatic_processing_enabled)"
EVENT_INTAKE_POLL_SECONDS="$(terraform output -raw event_intake_poll_seconds)"
TF_EVENT_INTAKE_QUEUE_PREFIX="$(terraform output -raw event_intake_queue_prefix)"
TF_EVENT_INTAKE_INCOMING_PREFIX="$(terraform output -raw event_intake_incoming_prefix)"
OBJECT_INTAKE_FUNCTION_ID="$(terraform output -raw object_intake_function_id 2>/dev/null || true)"
PLATFORM_SUMMARY_PATH="$DEPLOY_DIR/platform_summary.json"
terraform output -json platform_summary > "$PLATFORM_SUMMARY_PATH"

SSH_KEY_PATH="${SSH_PRIVATE_KEY_PATH:-$TF_SSH_PRIVATE_KEY_PATH}"
SSH_KEY_PATH="${SSH_KEY_PATH/#\~/$HOME}"

section "3/5 Connect Terraform Outputs To Ansible"
step "Terraform VM public IP: $PUBLIC_IP"
step "Terraform portal URL: $STREAMLIT_URL"
step "Terraform SSH key for Ansible: $SSH_KEY_PATH"
step "Writing temporary Ansible inventory to $INVENTORY"

cat > "$INVENTORY" <<EOF
[doc_review]
doc-review-app ansible_host=$PUBLIC_IP ansible_user=opc ansible_ssh_private_key_file=$SSH_KEY_PATH ansible_ssh_common_args='-o StrictHostKeyChecking=accept-new'
EOF

wait_for_ssh "$SSH_KEY_PATH" "$PUBLIC_IP"

cd "$ROOT_DIR"
section "4/5 Configure VM And Deploy App With Ansible"
step "Installing required Ansible collections"
ansible-galaxy collection install -r ansible/requirements.yml
step "Running ansible/playbook.yml"
ansible-playbook -i "$INVENTORY" ansible/playbook.yml \
  -e "oci_auth=config_file" \
  -e "oci_user_id=$OCI_USER_ID" \
  -e "oci_tenancy_id=$OCI_TENANCY_ID" \
  -e "oci_fingerprint=$OCI_FINGERPRINT" \
  -e "oci_api_key_file=$OCI_EXISTING_KEY_FILE" \
  -e "oci_region=$OCI_REGION" \
  -e "genai_region=$GENAI_REGION" \
  -e "compartment_id=$OCI_COMPARTMENT_ID" \
  -e "object_storage_namespace=$OCI_NAMESPACE" \
  -e "bucket_name=$OCI_BUCKET_NAME" \
  -e "genai_model_id=$GENAI_MODEL_ID" \
  -e "genai_temperature=${GENAI_TEMPERATURE:-0.2}" \
  -e "genai_max_tokens=${GENAI_MAX_TOKENS:-3000}" \
  -e "document_ai_timeout_seconds=${DOCUMENT_AI_TIMEOUT_SECONDS:-180}" \
  -e "document_ai_retry_attempts=${DOCUMENT_AI_RETRY_ATTEMPTS:-2}" \
  -e "stale_processing_minutes=${STALE_PROCESSING_MINUTES:-12}" \
  -e "retention_days=${RETENTION_DAYS:-30}" \
  -e "max_parallel_jobs=${MAX_PARALLEL_JOBS:-5}" \
  -e "max_document_chars=${MAX_DOCUMENT_CHARS:-50000}" \
  -e "max_upload_mb=${MAX_UPLOAD_MB:-10}" \
  -e "compliance_entities_object_name=${COMPLIANCE_ENTITIES_OBJECT_NAME:-compliance/public_sector_entities.csv}" \
  -e "event_intake_enabled=$AUTOMATIC_PROCESSING_ENABLED" \
  -e "event_intake_queue_prefix=${EVENT_INTAKE_QUEUE_PREFIX:-$TF_EVENT_INTAKE_QUEUE_PREFIX}" \
  -e "event_intake_incoming_prefix=${EVENT_INTAKE_INCOMING_PREFIX:-$TF_EVENT_INTAKE_INCOMING_PREFIX}" \
  -e "event_intake_poll_seconds=$EVENT_INTAKE_POLL_SECONDS"

section "5/5 Verify Deployed Portal"
verify_portal "$STREAMLIT_URL"

if [[ -z "$OBJECT_INTAKE_FUNCTION_ID" || "$OBJECT_INTAKE_FUNCTION_ID" == "null" ]]; then
  OBJECT_INTAKE_FUNCTION_ID="not enabled"
fi

if [[ "$AUTOMATIC_PROCESSING_ENABLED" == "true" ]]; then
  EVENT_INTAKE_TIMER_STATE="enabled, polls every ${EVENT_INTAKE_POLL_SECONDS}s"
else
  EVENT_INTAKE_TIMER_STATE="disabled"
fi

cat <<EOF

============================================================
OCI AI Document Review Portal - End-to-End Deployment Summary
============================================================

What just happened
  Terraform initialized the OCI provider, applied terraform/terraform.tfvars,
  and created or refreshed the cloud infrastructure. Ansible then used the
  Terraform VM output, copied the sanitized release archive, wrote runtime
  configuration, installed dependencies, configured systemd, restarted the
  portal, and waited for the app port. The deploy script also verified the
  public portal URL from this laptop.

Ready to use
  Portal URL:              $STREAMLIT_URL
  SSH command:             $SSH_COMMAND
  Service name:            oci-ai-document-review
  Remote app directory:    /opt/oci-ai-document-review

Terraform-managed infrastructure
  Runtime region:          $OCI_REGION
  VCN:                     $VCN_ID
  Public subnet:           $PUBLIC_SUBNET_ID
  Private subnet:          $PRIVATE_SUBNET_ID
  Internet gateway:        $IGW_ID
  NAT gateway:             $NATGW_ID
  Service gateway:         $SGW_ID
  Object Storage bucket:   $OCI_BUCKET_NAME
  Object Storage namespace: $OCI_NAMESPACE
  Retention days:          ${RETENTION_DAYS:-30}
  Automatic intake:        $AUTOMATIC_PROCESSING_ENABLED
  Intake Function:         $OBJECT_INTAKE_FUNCTION_ID

Ansible-managed runtime
  Runtime config:          /opt/oci-ai-document-review/.env
  OCI SDK config:          /opt/oci-ai-document-review/.oci/config
  Upload limit:            ${MAX_UPLOAD_MB:-10} MB per file
  Local metadata:          /opt/oci-ai-document-review/data/metadata
  Markdown reports:        /opt/oci-ai-document-review/data/reports
  Preserved uploads:       /opt/oci-ai-document-review/data/uploads
  Retention timer:         oci-ai-document-review-retention.timer
  Event intake timer:      $EVENT_INTAKE_TIMER_STATE

Operations
  Service status:          sudo systemctl status oci-ai-document-review --no-pager
  Follow logs:             sudo journalctl -u oci-ai-document-review -f
  Restart app:             sudo systemctl restart oci-ai-document-review
  Terraform output:        cd terraform && terraform output platform_summary
  Saved JSON summary:      $PLATFORM_SUMMARY_PATH

Security boundary
  Deployment runs from this laptop through Terraform and Ansible.
  GitHub is source control only; it is not the live deployment target.
  Real .env, terraform.tfvars, Terraform state, .deploy artifacts, and OCI keys
  stay ignored by Git.

============================================================

EOF
