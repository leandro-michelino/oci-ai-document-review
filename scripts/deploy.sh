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
  echo ".env not found. Run: python scripts/setup.py"
  exit 1
fi

env_value() {
  local key="$1"
  grep -E "^${key}=" .env | tail -n 1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'
}

OCI_REGION="$(env_value OCI_REGION)"
GENAI_REGION="$(env_value GENAI_REGION)"
OCI_COMPARTMENT_ID="$(env_value OCI_COMPARTMENT_ID)"
OCI_NAMESPACE="$(env_value OCI_NAMESPACE)"
OCI_BUCKET_NAME="$(env_value OCI_BUCKET_NAME)"
GENAI_MODEL_ID="$(env_value GENAI_MODEL_ID)"
GENAI_TEMPERATURE="$(env_value GENAI_TEMPERATURE)"
GENAI_MAX_TOKENS="$(env_value GENAI_MAX_TOKENS)"
MAX_DOCUMENT_CHARS="$(env_value MAX_DOCUMENT_CHARS)"
MAX_UPLOAD_MB="$(env_value MAX_UPLOAD_MB)"

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

tar \
  --exclude='./.deploy' \
  --exclude='./.venv' \
  --exclude='./.pytest_cache' \
  --exclude='./.ruff_cache' \
  --exclude='./terraform/.terraform' \
  --exclude='./terraform/terraform.tfstate*' \
  --exclude='./data/metadata/*.json' \
  --exclude='./data/reports/*.md' \
  --exclude='./data/uploads/*' \
  -czf "$ARCHIVE" .

cd "$TF_DIR"
terraform init
terraform apply -auto-approve

PUBLIC_IP="$(terraform output -raw instance_public_ip)"
STREAMLIT_URL="$(terraform output -raw streamlit_url)"

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
  -e "max_document_chars=${MAX_DOCUMENT_CHARS:-50000}" \
  -e "max_upload_mb=${MAX_UPLOAD_MB:-10}"

echo "Portal URL: $STREAMLIT_URL"
