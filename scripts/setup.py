#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import os
import subprocess
import urllib.request
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except Exception:  # pragma: no cover - fallback before dependencies are installed
    Console = None
    Panel = None
    Table = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUCKET = "doc-review-input"
DEFAULT_MODEL = "cohere.command-r-plus-08-2024"
SUPPORTED_CHAT_MODEL_PREFIXES = ("cohere.",)


@dataclass
class GenAIRegion:
    name: str
    models: list[str]


class UI:
    def __init__(self):
        self.console = Console() if Console else None

    def print(self, message: str = "") -> None:
        if self.console:
            self.console.print(message)
        else:
            print(message)

    def banner(self) -> None:
        text = (
            "OCI AI Document Review Portal setup\n"
            "Customer-friendly guided configuration for v0.5.0"
        )
        if self.console and Panel:
            self.console.print(Panel.fit(text, subtitle="no cloud resources created"))
        else:
            print(f"\n{text}\n")

    def section(self, title: str, detail: str | None = None) -> None:
        if self.console:
            self.console.rule(f"[bold]{title}[/bold]")
            if detail:
                self.console.print(detail)
            return
        print(f"\n== {title} ==")
        if detail:
            print(detail)

    def success(self, message: str) -> None:
        self.print(f"[green]{message}[/green]" if self.console else message)

    def warning(self, message: str) -> None:
        self.print(f"[yellow]{message}[/yellow]" if self.console else message)

    def show_regions(self, regions: list[GenAIRegion]) -> None:
        if self.console and Table:
            table = Table(title="Supported GenAI regions discovered in this tenancy")
            table.add_column("#", justify="right")
            table.add_column("Region")
            table.add_column("Supported chat models")
            for index, region in enumerate(regions, start=1):
                table.add_row(str(index), region.name, ", ".join(region.models[:5]))
            self.console.print(table)
            return

        print("Supported GenAI regions discovered in this tenancy:")
        for index, region in enumerate(regions, start=1):
            print(f"{index}. {region.name}: {', '.join(region.models[:5])}")

    def show_summary(self, values: dict[str, str]) -> None:
        if self.console and Table:
            table = Table(title="Configuration to write")
            table.add_column("Setting")
            table.add_column("Value")
            for key, value in values.items():
                table.add_row(key, value)
            self.console.print(table)
            return
        print("\nConfiguration to write:")
        for key, value in values.items():
            print(f"- {key}: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Customer-friendly setup wizard for the OCI document review portal."
    )
    parser.add_argument("--config-file", default=os.getenv("OCI_CONFIG_FILE"))
    parser.add_argument("--profile", default=os.getenv("OCI_PROFILE"))
    parser.add_argument("--compartment-id", default=os.getenv("OCI_COMPARTMENT_ID"))
    parser.add_argument(
        "--parent-compartment-id", default=os.getenv("OCI_PARENT_COMPARTMENT_ID")
    )
    parser.add_argument("--tenancy-id", default=os.getenv("OCI_TENANCY_ID"))
    parser.add_argument("--bucket-name", default=os.getenv("OCI_BUCKET_NAME"))
    parser.add_argument("--home-region", default=os.getenv("OCI_HOME_REGION"))
    parser.add_argument("--runtime-region", default=os.getenv("OCI_REGION"))
    parser.add_argument("--allowed-ingress-cidr", default=None)
    parser.add_argument("--ssh-public-key-path", default="~/.ssh/id_rsa.pub")
    parser.add_argument("--instance-shape", default="VM.Standard.A1.Flex")
    parser.add_argument("--instance-ocpus", default="1")
    parser.add_argument("--instance-memory-gbs", default="6")
    parser.add_argument("--preferred-region", default=os.getenv("GENAI_REGION"))
    parser.add_argument("--preferred-model", default=os.getenv("GENAI_MODEL_ID"))
    parser.add_argument("--genai-temperature", default="0.2")
    parser.add_argument("--genai-max-tokens", default="3000")
    parser.add_argument("--document-ai-timeout-seconds", default="180")
    parser.add_argument("--document-ai-retry-attempts", default="2")
    parser.add_argument("--stale-processing-minutes", default="12")
    parser.add_argument("--retention-days", default=os.getenv("RETENTION_DAYS", "30"))
    parser.add_argument("--enable-automatic-processing", action="store_true")
    parser.add_argument(
        "--automatic-processing-function-image",
        default=os.getenv("AUTOMATIC_PROCESSING_FUNCTION_IMAGE", ""),
    )
    parser.add_argument("--event-intake-incoming-prefix", default="incoming/")
    parser.add_argument("--event-intake-queue-prefix", default="event-queue/")
    parser.add_argument("--event-intake-poll-seconds", default="60")
    parser.add_argument("--max-parallel-jobs", default="2")
    parser.add_argument("--max-document-chars", default="50000")
    parser.add_argument("--max-upload-mb", default="10")
    parser.add_argument(
        "--compliance-entities-object-name",
        default=os.getenv(
            "COMPLIANCE_ENTITIES_OBJECT_NAME",
            "compliance/public_sector_entities.csv",
        ),
    )
    parser.add_argument("--app-title", default="OCI AI Document Review Portal")
    parser.add_argument("--generate-ssh-key", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Skip final confirmation.")
    parser.add_argument("--skip-write", action="store_true")
    args = parser.parse_args()
    args.config_file = args.config_file or "~/.oci/config"
    args.profile = args.profile or "DEFAULT"
    args.bucket_name = args.bucket_name or DEFAULT_BUCKET
    args.preferred_model = args.preferred_model or DEFAULT_MODEL
    validate_positive_integer(args.retention_days, "retention days")
    validate_positive_integer(
        args.event_intake_poll_seconds, "event intake poll seconds"
    )
    if args.non_interactive:
        require_non_interactive_values(args, parser)
        if (
            args.enable_automatic_processing
            and not args.automatic_processing_function_image
        ):
            parser.error(
                "--automatic-processing-function-image is required with "
                "--enable-automatic-processing"
            )
    return args


def require_non_interactive_values(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    required = {
        "--compartment-id or OCI_COMPARTMENT_ID": args.compartment_id,
        "--parent-compartment-id or OCI_PARENT_COMPARTMENT_ID": (
            args.parent_compartment_id
        ),
        "--home-region or OCI_HOME_REGION": args.home_region,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        parser.error("Missing required non-interactive value(s): " + ", ".join(missing))


def ask(
    prompt: str,
    default: str | None = None,
    required: bool = True,
    secret: bool = False,
) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        if secret:
            import getpass

            value = getpass.getpass(f"{prompt}{suffix}: ").strip()
        else:
            value = input(f"{prompt}{suffix}: ").strip()
        if not value and default is not None:
            return default
        if value or not required:
            return value
        print("This value is required.")


def confirm(prompt: str, default: bool = True) -> bool:
    label = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{label}]: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def choose_from_list(
    label: str,
    options: list[str],
    default: str | None = None,
    non_interactive: bool = False,
) -> str:
    if not options:
        raise SystemExit(f"No options available for {label}.")
    if non_interactive:
        return default if default in options else options[0]
    default_index = options.index(default) + 1 if default in options else 1
    print("")
    for index, option in enumerate(options, start=1):
        marker = " (default)" if index == default_index else ""
        print(f"{index}. {option}{marker}")
    answer = ask(f"Select {label}", default=str(default_index))
    if answer in options:
        return answer
    try:
        return options[int(answer) - 1]
    except (ValueError, IndexError) as exc:
        raise SystemExit(f"Invalid {label} selection.") from exc


def load_oci(args: argparse.Namespace):
    try:
        import oci
    except ImportError as exc:
        raise SystemExit(
            "The OCI SDK is not installed. Run: python -m pip install -r requirements.txt"
        ) from exc

    config_path = Path(args.config_file).expanduser()
    if not config_path.exists():
        raise SystemExit(
            f"OCI config file was not found at {config_path}. Run `oci setup config` "
            "or provide --config-file."
        )
    config = oci.config.from_file(str(config_path), args.profile)
    return oci, config


def validate_oci_config(config: dict) -> None:
    required = ("user", "tenancy", "fingerprint", "key_file", "region")
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise SystemExit(f"OCI profile is missing: {', '.join(missing)}")
    key_file = Path(config["key_file"]).expanduser()
    if not key_file.exists():
        raise SystemExit(f"OCI API key file was not found at {key_file}.")


def subscribed_regions(oci, config: dict) -> list[str]:
    identity = oci.identity.IdentityClient(config)
    tenancy_id = config["tenancy"]
    regions = []
    for item in identity.list_region_subscriptions(tenancy_id).data:
        if getattr(item, "status", None) == "READY":
            regions.append(item.region_name)
    return sorted(regions)


def namespace(oci, config: dict) -> str:
    client = oci.object_storage.ObjectStorageClient(config)
    return client.get_namespace().data


def list_chat_models_in_region(
    oci, base_config: dict, region: str, compartment_id: str
) -> GenAIRegion | None:
    region_config = dict(base_config)
    region_config["region"] = region
    endpoint = f"https://generativeai.{region}.oci.oraclecloud.com"
    client = oci.generative_ai.GenerativeAiClient(
        region_config,
        service_endpoint=endpoint,
        retry_strategy=oci.retry.NoneRetryStrategy(),
        timeout=(3, 8),
    )
    try:
        response = client.list_models(
            compartment_id=compartment_id,
            capability=["CHAT"],
            lifecycle_state="ACTIVE",
        )
    except Exception:
        return None

    names = []
    for item in getattr(response.data, "items", []) or []:
        for name in (getattr(item, "id", None), getattr(item, "display_name", None)):
            if name and name not in names:
                names.append(name)
    names = supported_chat_models(names)
    if not names:
        return None
    return GenAIRegion(name=region, models=names)


def discover_genai_regions(
    oci, config: dict, compartment_id: str, ui: UI
) -> list[GenAIRegion]:
    regions = subscribed_regions(oci, config)
    ui.print(
        f"Checking OCI Generative AI availability across {len(regions)} subscribed regions..."
    )
    discovered = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(
                list_chat_models_in_region, oci, config, region, compartment_id
            )
            for region in regions
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                discovered.append(result)
    return sorted(discovered, key=lambda item: item.name)


def choose_region(
    regions: list[GenAIRegion], preferred: str | None, non_interactive: bool, ui: UI
) -> GenAIRegion:
    if not regions:
        raise SystemExit(
            "No supported GenAI chat regions were discovered for this compartment. "
            "Check service availability, policies, and limits."
        )
    ui.show_regions(regions)
    by_name = {region.name: region for region in regions}
    if non_interactive:
        if preferred and preferred in by_name:
            return by_name[preferred]
        return regions[0]

    selected = choose_from_list(
        "GenAI region",
        [region.name for region in regions],
        default=preferred if preferred in by_name else regions[0].name,
    )
    return by_name[selected]


def supported_chat_models(models: list[str]) -> list[str]:
    return [
        model
        for model in models
        if model.lower().startswith(SUPPORTED_CHAT_MODEL_PREFIXES)
    ]


def choose_model(region: GenAIRegion, preferred: str, non_interactive: bool) -> str:
    models = supported_chat_models(region.models)
    if not models:
        raise SystemExit(
            "This app currently supports Cohere chat models through the OCI SDK "
            f"CohereChatRequest. Region {region.name} has chat models, but none with "
            "a supported model id prefix."
        )
    return choose_from_list(
        "GenAI model",
        models,
        default=preferred if preferred in models else models[0],
        non_interactive=non_interactive,
    )


def prompt_for_oci_profile(args: argparse.Namespace, ui: UI) -> tuple[object, dict]:
    if args.non_interactive:
        oci, config = load_oci(args)
        validate_oci_config(config)
        return oci, config

    ui.section(
        "1. OCI Credentials",
        "Use an existing OCI CLI/API-key profile. No key is generated or committed.",
    )
    while True:
        args.config_file = ask("OCI config file", args.config_file)
        args.profile = ask("OCI profile", args.profile)
        try:
            oci, config = load_oci(args)
            validate_oci_config(config)
        except SystemExit as exc:
            ui.warning(str(exc))
            if not confirm("Try a different OCI config/profile?", default=True):
                raise
            continue
        ui.success("OCI profile loaded successfully.")
        ui.print(f"Tenancy: {config['tenancy']}")
        ui.print(f"User: {config['user']}")
        ui.print(f"Profile region: {config['region']}")
        return oci, config


def prompt_for_compartments(
    args: argparse.Namespace, config: dict, subscribed: list[str], ui: UI
) -> None:
    if args.non_interactive:
        validate_ocid(args.parent_compartment_id, "parent compartment")
        validate_ocid(args.compartment_id, "project compartment")
        validate_region(args.home_region, subscribed, "home/IAM region")
        args.runtime_region = args.runtime_region or config["region"]
        validate_region(args.runtime_region, subscribed, "runtime region")
        if args.allowed_ingress_cidr:
            args.allowed_ingress_cidr = normalize_cidr(args.allowed_ingress_cidr)
        return

    ui.section(
        "2. Project Compartment",
        "Provide the customer compartment where Terraform will create the MVP resources.",
    )
    args.parent_compartment_id = ask(
        "Parent compartment OCID", args.parent_compartment_id
    )
    args.compartment_id = ask("Project compartment OCID", args.compartment_id)
    validate_ocid(args.parent_compartment_id, "parent compartment")
    validate_ocid(args.compartment_id, "project compartment")

    ui.section(
        "3. Regions",
        "Runtime region hosts compute, networking, Object Storage, and Document Understanding.",
    )
    args.home_region = choose_from_list(
        "home/IAM region",
        subscribed,
        default=(
            args.home_region if args.home_region in subscribed else config["region"]
        ),
    )
    args.runtime_region = choose_from_list(
        "runtime region",
        subscribed,
        default=(
            args.runtime_region
            if args.runtime_region in subscribed
            else config["region"]
        ),
    )


def prompt_for_runtime(
    args: argparse.Namespace, ui: UI, discovered_namespace: str
) -> str:
    if args.non_interactive:
        return discovered_namespace

    ui.section(
        "4. Storage, Network, And Runtime",
        "These values control bucket naming, browser/SSH access, VM size, and processing limits.",
    )
    args.bucket_name = ask("Object Storage bucket name", args.bucket_name)
    os_namespace = ask("Object Storage namespace", discovered_namespace)
    args.allowed_ingress_cidr = prompt_for_ingress_cidr(args.allowed_ingress_cidr, ui)
    args.ssh_public_key_path = prompt_for_ssh_key(args, ui)
    args.instance_shape = ask("Compute shape", args.instance_shape)
    args.instance_ocpus = ask("Compute OCPUs", args.instance_ocpus)
    args.instance_memory_gbs = ask("Compute memory GB", args.instance_memory_gbs)
    args.max_upload_mb = ask("Max upload size MB", args.max_upload_mb)
    args.max_parallel_jobs = ask("Parallel processing jobs", args.max_parallel_jobs)
    args.document_ai_timeout_seconds = ask(
        "Document Understanding timeout seconds", args.document_ai_timeout_seconds
    )
    args.document_ai_retry_attempts = ask(
        "Document Understanding retry attempts", args.document_ai_retry_attempts
    )
    args.retention_days = ask(
        "Retention days for VM data and Object Storage documents",
        args.retention_days,
    )
    validate_positive_integer(args.retention_days, "retention days")
    args.enable_automatic_processing = confirm(
        "Enable OCI Events and Functions for automatic Object Storage intake?",
        default=args.enable_automatic_processing,
    )
    if args.enable_automatic_processing:
        args.automatic_processing_function_image = ask(
            "OCIR image URI for functions/object_intake",
            args.automatic_processing_function_image,
        )
        args.event_intake_incoming_prefix = ask(
            "Incoming Object Storage prefix", args.event_intake_incoming_prefix
        )
        args.event_intake_queue_prefix = ask(
            "Function queue marker prefix", args.event_intake_queue_prefix
        )
        args.event_intake_poll_seconds = ask(
            "VM event-intake poll seconds", args.event_intake_poll_seconds
        )
        validate_positive_integer(
            args.event_intake_poll_seconds, "event intake poll seconds"
        )
    return os_namespace


def prompt_for_ingress_cidr(value: str | None, ui: UI) -> str:
    if value:
        return normalize_cidr(value)
    try:
        discovered = discover_current_ip_cidr()
    except SystemExit as exc:
        ui.warning(str(exc))
        discovered = None
    if discovered and confirm(
        f"Use current public IP for SSH and portal access ({discovered})?",
        default=True,
    ):
        return discovered
    manual = ask("Allowed ingress CIDR, for example 203.0.113.10/32")
    return normalize_cidr(manual)


def prompt_for_ssh_key(args: argparse.Namespace, ui: UI) -> str:
    path = Path(ask("SSH public key path", args.ssh_public_key_path)).expanduser()
    if path.exists():
        return str(path)
    private_key = path.with_suffix("") if path.suffix == ".pub" else path
    if args.generate_ssh_key or confirm(
        f"SSH public key does not exist at {path}. Generate {private_key}?",
        default=True,
    ):
        generate_ssh_key(private_key)
        ui.success(f"Generated SSH key pair: {private_key} and {private_key}.pub")
        return str(Path(f"{private_key}.pub"))
    raise SystemExit("SSH public key is required for Terraform compute provisioning.")


def generate_ssh_key(private_key: Path) -> None:
    private_key.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ssh-keygen", "-t", "rsa", "-b", "4096", "-f", str(private_key), "-N", ""],
        check=True,
    )


def validate_ocid(value: str, label: str) -> None:
    if not value.startswith("ocid1."):
        raise SystemExit(f"The {label} OCID should start with `ocid1.`.")


def validate_region(value: str, subscribed: list[str], label: str) -> None:
    if value not in subscribed:
        choices = ", ".join(subscribed) or "none"
        raise SystemExit(
            f"The {label} `{value}` is not in the READY subscribed regions: {choices}."
        )


def normalize_cidr(value: str) -> str:
    try:
        network = ip_network(value, strict=False)
    except ValueError as exc:
        raise SystemExit(f"Invalid CIDR: {value}") from exc
    if network.prefixlen == 0:
        raise SystemExit(
            "Invalid CIDR: open ingress is not allowed. Use a trusted /32 or narrow CIDR."
        )
    return str(network)


def validate_cidr(value: str) -> None:
    normalize_cidr(value)


def validate_positive_integer(value: str, label: str) -> None:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"The {label} value must be a positive integer.") from exc
    if parsed < 1:
        raise SystemExit(f"The {label} value must be a positive integer.")


def write_env(
    args: argparse.Namespace,
    oci_region: str,
    genai_region: str,
    model_id: str,
    os_namespace: str,
) -> None:
    env = f"""# Generated by scripts/setup.py
OCI_CONFIG_FILE={args.config_file}
OCI_PROFILE={args.profile}
OCI_AUTH=config_file
OCI_PARENT_COMPARTMENT_ID={args.parent_compartment_id}
OCI_COMPARTMENT_ID={args.compartment_id}
OCI_REGION={oci_region}
GENAI_REGION={genai_region}
OCI_NAMESPACE={os_namespace}
OCI_BUCKET_NAME={args.bucket_name}
GENAI_MODEL_ID={model_id}
GENAI_TEMPERATURE={args.genai_temperature}
GENAI_MAX_TOKENS={args.genai_max_tokens}
DOCUMENT_AI_TIMEOUT_SECONDS={args.document_ai_timeout_seconds}
DOCUMENT_AI_RETRY_ATTEMPTS={args.document_ai_retry_attempts}
STALE_PROCESSING_MINUTES={args.stale_processing_minutes}
RETENTION_DAYS={args.retention_days}
MAX_PARALLEL_JOBS={args.max_parallel_jobs}
MAX_DOCUMENT_CHARS={args.max_document_chars}
MAX_UPLOAD_MB={args.max_upload_mb}
COMPLIANCE_ENTITIES_OBJECT_NAME={args.compliance_entities_object_name}
EVENT_INTAKE_ENABLED={str(args.enable_automatic_processing).lower()}
EVENT_INTAKE_QUEUE_PREFIX={args.event_intake_queue_prefix}
EVENT_INTAKE_INCOMING_PREFIX={args.event_intake_incoming_prefix}
LOCAL_METADATA_DIR=data/metadata
LOCAL_REPORTS_DIR=data/reports
LOCAL_UPLOADS_DIR=data/uploads
APP_TITLE="{args.app_title}"
LOG_LEVEL=INFO
"""
    (PROJECT_ROOT / ".env").write_text(env, encoding="utf-8")


def write_tfvars(
    args: argparse.Namespace,
    region: str,
    genai_region: str,
    os_namespace: str,
) -> None:
    allowed_ingress_cidr = args.allowed_ingress_cidr or discover_current_ip_cidr()
    tfvars = f"""# Generated by scripts/setup.py
region = "{region}"
genai_region = "{genai_region}"
home_region = "{args.home_region}"
compartment_id = "{args.compartment_id}"
parent_compartment_id = "{args.parent_compartment_id}"
tenancy_id = "{args.tenancy_id}"
bucket_name = "{args.bucket_name}"
object_storage_namespace = "{os_namespace}"
enable_automatic_processing = {str(args.enable_automatic_processing).lower()}
automatic_processing_function_image = "{args.automatic_processing_function_image}"
event_intake_incoming_prefix = "{args.event_intake_incoming_prefix}"
event_intake_queue_prefix = "{args.event_intake_queue_prefix}"
event_intake_poll_seconds = {args.event_intake_poll_seconds}
retention_days = {args.retention_days}
allowed_ingress_cidr = "{allowed_ingress_cidr}"
ssh_public_key_path = "{args.ssh_public_key_path}"
instance_shape = "{args.instance_shape}"
instance_ocpus = {args.instance_ocpus}
instance_memory_gbs = {args.instance_memory_gbs}
"""
    (PROJECT_ROOT / "terraform" / "terraform.tfvars").write_text(
        tfvars, encoding="utf-8"
    )


def discover_current_ip_cidr() -> str:
    try:
        with urllib.request.urlopen("https://ifconfig.me", timeout=5) as response:
            ip = response.read().decode("utf-8").strip()
        ip_address(ip)
        return f"{ip}/32"
    except Exception as exc:
        raise SystemExit(
            "Could not discover the current public IP address. Re-run setup with "
            "--allowed-ingress-cidr set to your trusted CIDR, for example "
            "--allowed-ingress-cidr 203.0.113.10/32."
        ) from exc


def summary_values(
    args: argparse.Namespace,
    runtime_region: str,
    genai_region: str,
    model_id: str,
    os_namespace: str,
) -> dict[str, str]:
    return {
        "OCI profile": f"{args.config_file} [{args.profile}]",
        "Project compartment": args.compartment_id,
        "Parent compartment": args.parent_compartment_id,
        "Home region": args.home_region,
        "Runtime region": runtime_region,
        "GenAI region": genai_region,
        "GenAI model": model_id,
        "Object Storage namespace": os_namespace,
        "Bucket": args.bucket_name,
        "Allowed ingress CIDR": args.allowed_ingress_cidr or "(auto-discovered)",
        "SSH public key": args.ssh_public_key_path,
        "Compute": (
            f"{args.instance_shape}, {args.instance_ocpus} OCPU, "
            f"{args.instance_memory_gbs} GB"
        ),
        "Processing": (
            f"{args.max_parallel_jobs} workers, {args.max_upload_mb} MB upload limit"
        ),
        "Retention": f"{args.retention_days} days",
        "Automatic processing": (
            "enabled" if args.enable_automatic_processing else "disabled"
        ),
    }


def main() -> None:
    args = parse_args()
    ui = UI()
    ui.banner()

    oci, config = prompt_for_oci_profile(args, ui)
    args.tenancy_id = args.tenancy_id or config["tenancy"]
    subscribed = subscribed_regions(oci, config)
    if not subscribed:
        raise SystemExit("No READY subscribed OCI regions were found for this tenancy.")
    prompt_for_compartments(args, config, subscribed, ui)

    os_namespace = namespace(oci, config)
    os_namespace = prompt_for_runtime(args, ui, os_namespace)

    ui.section(
        "5. Generative AI",
        "Setup probes subscribed regions and only offers supported Cohere chat models.",
    )
    genai_regions = discover_genai_regions(oci, config, args.compartment_id, ui)
    selected_region = choose_region(
        genai_regions, args.preferred_region, args.non_interactive, ui
    )
    selected_model = choose_model(
        selected_region,
        preferred=args.preferred_model,
        non_interactive=args.non_interactive,
    )

    runtime_region = args.runtime_region or selected_region.name
    values = summary_values(
        args=args,
        runtime_region=runtime_region,
        genai_region=selected_region.name,
        model_id=selected_model,
        os_namespace=os_namespace,
    )
    ui.show_summary(values)

    if not args.skip_write and not (args.yes or args.non_interactive):
        if not confirm("Write .env and terraform/terraform.tfvars?", default=True):
            raise SystemExit("Setup cancelled before writing files.")

    if not args.skip_write:
        write_env(
            args=args,
            oci_region=runtime_region,
            genai_region=selected_region.name,
            model_id=selected_model,
            os_namespace=os_namespace,
        )
        write_tfvars(
            args=args,
            region=runtime_region,
            genai_region=selected_region.name,
            os_namespace=os_namespace,
        )

    ui.print("")
    ui.print(f"Selected runtime region: {runtime_region}")
    ui.print(f"Selected GenAI region: {selected_region.name}")
    ui.print(f"Selected GenAI model: {selected_model}")
    if args.skip_write:
        ui.print("Skipped writing files. No OCI resources were created.")
        return

    ui.success("Wrote .env and terraform/terraform.tfvars.")
    ui.print("No OCI resources were created by setup.")
    ui.print("")
    ui.print("Next steps:")
    ui.print("1. Review .env and terraform/terraform.tfvars")
    ui.print("2. Run: cd terraform && terraform plan")
    ui.print("3. Run from repo root: ./scripts/deploy.sh")
    ui.print("4. Open Settings in the portal and run OCI Preflight")


if __name__ == "__main__":
    main()
