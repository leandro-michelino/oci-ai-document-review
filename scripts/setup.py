#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import os
import urllib.request
from dataclasses import dataclass
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
        text = "OCI AI Document Review Portal setup"
        if self.console and Panel:
            self.console.print(Panel.fit(text, subtitle="live GenAI region discovery"))
        else:
            print(f"\n{text}\n")

    def show_regions(self, regions: list[GenAIRegion]) -> None:
        if self.console and Table:
            table = Table(title="GenAI-capable regions discovered in this tenancy")
            table.add_column("#", justify="right")
            table.add_column("Region")
            table.add_column("Sample chat models")
            for index, region in enumerate(regions, start=1):
                table.add_row(str(index), region.name, ", ".join(region.models[:5]))
            self.console.print(table)
            return

        print("GenAI-capable regions discovered in this tenancy:")
        for index, region in enumerate(regions, start=1):
            print(f"{index}. {region.name}: {', '.join(region.models[:5])}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configure the OCI document review portal.")
    parser.add_argument("--config-file", default="~/.oci/config")
    parser.add_argument("--profile", default="DEFAULT")
    parser.add_argument("--compartment-id", default=os.getenv("OCI_COMPARTMENT_ID"))
    parser.add_argument("--parent-compartment-id", default=os.getenv("OCI_PARENT_COMPARTMENT_ID"))
    parser.add_argument("--bucket-name", default=DEFAULT_BUCKET)
    parser.add_argument("--home-region", default=os.getenv("OCI_HOME_REGION"))
    parser.add_argument("--allowed-ingress-cidr", default=None)
    parser.add_argument("--ssh-public-key-path", default="~/.ssh/id_rsa.pub")
    parser.add_argument("--instance-shape", default="VM.Standard.A1.Flex")
    parser.add_argument("--instance-ocpus", default="1")
    parser.add_argument("--instance-memory-gbs", default="6")
    parser.add_argument("--preferred-region", default=os.getenv("GENAI_REGION"))
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--skip-write", action="store_true")
    args = parser.parse_args()
    if not args.compartment_id:
        parser.error("--compartment-id or OCI_COMPARTMENT_ID is required")
    if not args.parent_compartment_id:
        parser.error("--parent-compartment-id or OCI_PARENT_COMPARTMENT_ID is required")
    if not args.home_region:
        parser.error("--home-region or OCI_HOME_REGION is required")
    return args


def load_oci(args: argparse.Namespace):
    try:
        import oci
    except ImportError as exc:
        raise SystemExit(
            "The OCI SDK is not installed. Run: python -m pip install -r requirements.txt"
        ) from exc

    config = oci.config.from_file(str(Path(args.config_file).expanduser()), args.profile)
    return oci, config


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
        name = getattr(item, "display_name", None)
        if name and name not in names:
            names.append(name)
    if not names:
        return None
    return GenAIRegion(name=region, models=names)


def discover_genai_regions(oci, config: dict, compartment_id: str, ui: UI) -> list[GenAIRegion]:
    regions = subscribed_regions(oci, config)
    ui.print(f"Checking OCI Generative AI availability across {len(regions)} subscribed regions...")
    discovered = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(list_chat_models_in_region, oci, config, region, compartment_id)
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
            "No GenAI chat-capable regions were discovered for this compartment. "
            "Check service availability, policies, and limits."
        )
    ui.show_regions(regions)
    by_name = {region.name: region for region in regions}
    if non_interactive:
        return by_name.get(preferred) or regions[0] if preferred else regions[0]

    default_index = next(
        (index for index, region in enumerate(regions, start=1) if region.name == preferred),
        1,
    )
    answer = input(f"Select GenAI region [default {default_index}]: ").strip()
    if not answer:
        return regions[default_index - 1]
    if answer in by_name:
        return by_name[answer]
    try:
        return regions[int(answer) - 1]
    except (ValueError, IndexError) as exc:
        raise SystemExit("Invalid region selection.") from exc


def choose_model(region: GenAIRegion, preferred: str, non_interactive: bool) -> str:
    if non_interactive:
        return preferred if preferred in region.models else region.models[0]
    print("\nAvailable chat models:")
    for index, name in enumerate(region.models, start=1):
        print(f"{index}. {name}")
    default_index = 1
    if preferred in region.models:
        default_index = region.models.index(preferred) + 1
    answer = input(f"Select model [default {default_index}]: ").strip()
    if not answer:
        return region.models[default_index - 1]
    try:
        return region.models[int(answer) - 1]
    except (ValueError, IndexError) as exc:
        raise SystemExit("Invalid model selection.") from exc


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
GENAI_TEMPERATURE=0.2
GENAI_MAX_TOKENS=3000
MAX_DOCUMENT_CHARS=50000
MAX_UPLOAD_MB=10
LOCAL_METADATA_DIR=data/metadata
LOCAL_REPORTS_DIR=data/reports
LOCAL_UPLOADS_DIR=data/uploads
APP_TITLE="OCI AI Document Review Portal"
LOG_LEVEL=INFO
"""
    (PROJECT_ROOT / ".env").write_text(env, encoding="utf-8")


def write_tfvars(
    args: argparse.Namespace,
    tenancy_id: str,
    region: str,
    genai_region: str,
    os_namespace: str,
) -> None:
    allowed_ingress_cidr = args.allowed_ingress_cidr or discover_current_ip_cidr()
    tfvars = f'''# Generated by scripts/setup.py
region = "{region}"
genai_region = "{genai_region}"
home_region = "{args.home_region}"
tenancy_id = "{tenancy_id}"
compartment_id = "{args.compartment_id}"
parent_compartment_id = "{args.parent_compartment_id}"
bucket_name = "{args.bucket_name}"
object_storage_namespace = "{os_namespace}"
allowed_ingress_cidr = "{allowed_ingress_cidr}"
ssh_public_key_path = "{args.ssh_public_key_path}"
instance_shape = "{args.instance_shape}"
instance_ocpus = {args.instance_ocpus}
instance_memory_gbs = {args.instance_memory_gbs}
'''
    (PROJECT_ROOT / "terraform" / "terraform.tfvars").write_text(tfvars, encoding="utf-8")


def discover_current_ip_cidr() -> str:
    try:
        with urllib.request.urlopen("https://ifconfig.me", timeout=5) as response:
            ip = response.read().decode("utf-8").strip()
        return f"{ip}/32"
    except Exception:
        return "0.0.0.0/0"


def main() -> None:
    args = parse_args()
    ui = UI()
    ui.banner()
    oci, config = load_oci(args)
    os_namespace = namespace(oci, config)

    genai_regions = discover_genai_regions(oci, config, args.compartment_id, ui)
    selected_region = choose_region(
        genai_regions, args.preferred_region, args.non_interactive, ui
    )
    selected_model = choose_model(
        selected_region,
        preferred="cohere.command-r-plus-08-2024",
        non_interactive=args.non_interactive,
    )

    if not args.skip_write:
        write_env(
            args=args,
            oci_region=selected_region.name,
            genai_region=selected_region.name,
            model_id=selected_model,
            os_namespace=os_namespace,
        )
        write_tfvars(
            args=args,
            tenancy_id=config["tenancy"],
            region=selected_region.name,
            genai_region=selected_region.name,
            os_namespace=os_namespace,
        )

    ui.print("")
    ui.print(f"Selected GenAI region: {selected_region.name}")
    ui.print(f"Selected GenAI model: {selected_model}")
    if args.skip_write:
        ui.print("Skipped writing files. No OCI resources were created.")
    else:
        ui.print("Wrote .env and terraform/terraform.tfvars. No OCI resources were created.")


if __name__ == "__main__":
    main()
