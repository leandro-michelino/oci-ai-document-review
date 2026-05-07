#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT_DIR/terraform"
DEPLOY_DIR="$ROOT_DIR/.deploy"
ARCHIVE="$DEPLOY_DIR/oci-ai-document-review.tar.gz"
INVENTORY="$DEPLOY_DIR/inventory.ini"
OCI_RUNTIME_META="$DEPLOY_DIR/oci_existing_config.env"

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
MAX_PARALLEL_JOBS="$(env_value MAX_PARALLEL_JOBS)"
MAX_DOCUMENT_CHARS="$(env_value MAX_DOCUMENT_CHARS)"
MAX_UPLOAD_MB="$(env_value MAX_UPLOAD_MB)"

export OCI_CONFIG_FILE="${OCI_CONFIG_FILE:-~/.oci/config}"
export OCI_PROFILE="${OCI_PROFILE:-DEFAULT}"

mkdir -p "$DEPLOY_DIR"

echo "Using existing OCI API key from local OCI config."
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
terraform init
terraform apply -auto-approve

PUBLIC_IP="$(terraform output -raw instance_public_ip)"
STREAMLIT_URL="$(terraform output -raw streamlit_url)"
SSH_COMMAND="$(terraform output -raw ssh_command)"
VCN_ID="$(terraform output -raw vcn_id)"
PUBLIC_SUBNET_ID="$(terraform output -raw public_subnet_id)"
PRIVATE_SUBNET_ID="$(terraform output -raw private_subnet_id)"
IGW_ID="$(terraform output -raw internet_gateway_id)"
NATGW_ID="$(terraform output -raw nat_gateway_id)"
SGW_ID="$(terraform output -raw service_gateway_id)"

cat > "$INVENTORY" <<EOF
[doc_review]
doc-review-app ansible_host=$PUBLIC_IP ansible_user=opc ansible_ssh_private_key_file=${SSH_PRIVATE_KEY_PATH:-$HOME/.ssh/id_rsa} ansible_ssh_common_args='-o StrictHostKeyChecking=accept-new'
EOF

cd "$ROOT_DIR"
ansible-galaxy collection install -r ansible/requirements.yml
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
  -e "max_parallel_jobs=${MAX_PARALLEL_JOBS:-2}" \
  -e "max_document_chars=${MAX_DOCUMENT_CHARS:-50000}" \
  -e "max_upload_mb=${MAX_UPLOAD_MB:-10}"

cat <<EOF

============================================================
OCI AI Document Review Portal - Deployment Summary
============================================================

Application
  Portal URL:      $STREAMLIT_URL
  SSH command:     $SSH_COMMAND
  Service name:    oci-ai-document-review
  Remote app dir:  /opt/oci-ai-document-review

OCI Services
  Runtime region:  $OCI_REGION
  GenAI region:    $GENAI_REGION
  Bucket:          $OCI_BUCKET_NAME
  Namespace:       $OCI_NAMESPACE

Network
  VCN:             $VCN_ID
  Public subnet:   $PUBLIC_SUBNET_ID
  Private subnet:  $PRIVATE_SUBNET_ID
  Internet GW:     $IGW_ID
  NAT GW:          $NATGW_ID
  Service GW:      $SGW_ID
  NSGs used:       false

Useful Commands
  Open portal:     $STREAMLIT_URL
  SSH to VM:       $SSH_COMMAND
  Service status:  sudo systemctl status oci-ai-document-review
  Follow logs:     sudo journalctl -u oci-ai-document-review -f
  Restart app:     sudo systemctl restart oci-ai-document-review
  Terraform summary:
                   cd terraform && terraform output platform_summary

Security Notes
  Deployment runs from this laptop.
  No GitHub Actions or CI deployment is configured.
  Real .env, terraform.tfvars, Terraform state, and OCI keys are ignored by Git.

============================================================

EOF
