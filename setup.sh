#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

RUN_CONFIGURE=true
RUN_DEPLOY=true
RUN_CHECKS=true
SETUP_ARGS=()

usage() {
  cat <<'EOF'
Usage:
  ./setup.sh [options] [scripts/setup.py options]

End-to-end local laptop setup for OCI AI Document Review Portal.

By default this script:
  1. Creates or refreshes .venv
  2. Runs scripts/setup.py to write .env and terraform/terraform.tfvars
  3. Runs local validation
  4. Runs scripts/deploy.sh to provision/update OCI and restart the portal

Options handled by setup.sh:
  --configure-only   Run configuration and validation, but do not deploy
  --deploy-only      Skip scripts/setup.py and deploy existing local config
  --skip-checks      Skip ruff, pytest, Terraform validate, and Ansible syntax
  -h, --help         Show this help

All other flags are passed through to scripts/setup.py. Examples:
  ./setup.sh
  ./setup.sh --configure-only
  ./setup.sh --non-interactive --yes \
    --compartment-id ocid1.compartment.oc1..exampleproject \
    --parent-compartment-id ocid1.compartment.oc1..exampleparent \
    --home-region us-ashburn-1 \
    --runtime-region us-ashburn-1 \
    --allowed-ingress-cidr 203.0.113.10/32
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --configure-only)
      RUN_DEPLOY=false
      shift
      ;;
    --deploy-only)
      RUN_CONFIGURE=false
      shift
      ;;
    --skip-checks)
      RUN_CHECKS=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      SETUP_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$RUN_CONFIGURE" == false && ${#SETUP_ARGS[@]} -gt 0 ]]; then
  echo "setup.py options cannot be used with --deploy-only because configuration is skipped."
  echo "Run ./setup.sh --configure-only with setup options first, then ./setup.sh --deploy-only."
  exit 1
fi

cd "$ROOT_DIR"

need_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required command not found: $command_name"
    exit 1
  fi
}

python_bin() {
  if command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  echo "Python 3.11 or later is required." >&2
  exit 1
}

python_version_check() {
  "$VENV_DIR/bin/python" - <<'PY'
import sys

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or later is required.")
PY
}

echo "== OCI AI Document Review: end-to-end setup =="

need_command terraform
need_command ansible-playbook
need_command ansible-galaxy

PYTHON_BIN="$(python_bin)"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Creating virtual environment in .venv"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

python_version_check

echo "Installing Python dependencies"
"$VENV_DIR/bin/python" -m pip install -r requirements-dev.txt

if [[ "$RUN_CONFIGURE" == true ]]; then
  echo "Running guided configuration"
  SETUP_SH_ORCHESTRATED=1 "$VENV_DIR/bin/python" scripts/setup.py "${SETUP_ARGS[@]}"
else
  echo "Skipping configuration because --deploy-only was supplied"
fi

if [[ ! -f .env ]]; then
  echo ".env was not found. Run ./setup.sh without --deploy-only or create .env first."
  exit 1
fi

if [[ ! -f terraform/terraform.tfvars ]]; then
  echo "terraform/terraform.tfvars was not found. Run ./setup.sh without --deploy-only first."
  exit 1
fi

if [[ "$RUN_CHECKS" == true ]]; then
  echo "Running local validation"
  "$VENV_DIR/bin/ruff" check .
  "$VENV_DIR/bin/pytest"
  terraform -chdir=terraform fmt -check -diff
  terraform -chdir=terraform init
  terraform -chdir=terraform validate
  mkdir -p .deploy
  cat > .deploy/ansible_syntax_inventory.ini <<'EOF'
[doc_review]
doc-review-app ansible_connection=local
EOF
  ansible-playbook -i .deploy/ansible_syntax_inventory.ini --syntax-check ansible/playbook.yml
else
  echo "Skipping local validation because --skip-checks was supplied"
fi

if [[ "$RUN_DEPLOY" == true ]]; then
  echo "Deploying infrastructure with Terraform and application runtime with Ansible"
  ./scripts/deploy.sh
else
  cat <<'EOF'

Configuration complete. Deployment was skipped because --configure-only was supplied.

Next command:
  ./setup.sh --deploy-only

EOF
fi
