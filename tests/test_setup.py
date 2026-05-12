# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
import pytest
from argparse import Namespace

from scripts.setup import (
    GenAIRegion,
    choose_model,
    discover_current_ip_cidr,
    normalize_cidr,
    normalize_object_prefix,
    prompt_for_compartments,
    summary_values,
    supported_chat_models,
    validate_cidr,
    validate_positive_integer,
)


def test_supported_chat_models_filters_to_cohere_ids():
    models = ["meta.llama-3.1", "cohere.command-r-plus-08-2024"]

    assert supported_chat_models(models) == ["cohere.command-r-plus-08-2024"]


def test_choose_model_rejects_unsupported_chat_models():
    region = GenAIRegion(name="example-region", models=["meta.llama-3.1"])

    with pytest.raises(SystemExit):
        choose_model(
            region, preferred="cohere.command-r-plus-08-2024", non_interactive=True
        )


def test_discover_current_ip_cidr_requires_explicit_cidr_when_lookup_fails(
    monkeypatch,
):
    def fail_urlopen(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr("scripts.setup.urllib.request.urlopen", fail_urlopen)

    with pytest.raises(SystemExit, match="--allowed-ingress-cidr"):
        discover_current_ip_cidr()


def test_normalize_cidr_converts_host_to_cidr():
    assert normalize_cidr("203.0.113.10") == "203.0.113.10/32"
    assert normalize_cidr("203.0.113.0/24") == "203.0.113.0/24"


def test_validate_cidr_rejects_invalid_values():
    with pytest.raises(SystemExit, match="Invalid CIDR"):
        validate_cidr("not-a-cidr")


def test_validate_cidr_rejects_open_ingress():
    with pytest.raises(SystemExit, match="open ingress"):
        validate_cidr("0.0.0.0/0")


def test_validate_positive_integer_rejects_retention_zero():
    validate_positive_integer("30", "retention days")

    with pytest.raises(SystemExit, match="positive integer"):
        validate_positive_integer("0", "retention days")


def test_normalize_object_prefix_makes_prefix_relative_and_slash_terminated():
    assert normalize_object_prefix("/incoming", "incoming prefix") == "incoming/"
    assert normalize_object_prefix("event-queue", "queue prefix") == "event-queue/"


def test_normalize_object_prefix_rejects_empty_or_parent_segments():
    with pytest.raises(SystemExit, match="non-empty"):
        normalize_object_prefix("/", "incoming prefix")

    with pytest.raises(SystemExit, match="parent directory"):
        normalize_object_prefix("incoming/../secrets", "incoming prefix")


def test_setup_summary_includes_retention_days():
    args = Namespace(
        config_file="~/.oci/config",
        profile="DEFAULT",
        compartment_id="ocid1.compartment.oc1..project",
        parent_compartment_id="ocid1.compartment.oc1..parent",
        home_region="us-ashburn-1",
        bucket_name="doc-review-input",
        allowed_ingress_cidr="203.0.113.10/32",
        ssh_public_key_path="~/.ssh/id_rsa.pub",
        instance_shape="VM.Standard.A1.Flex",
        instance_ocpus="1",
        instance_memory_gbs="6",
        max_parallel_jobs="5",
        max_upload_mb="10",
        retention_days="30",
        enable_automatic_processing=False,
    )

    values = summary_values(
        args=args,
        runtime_region="us-ashburn-1",
        genai_region="us-ashburn-1",
        model_id="cohere.command-r-plus-08-2024",
        os_namespace="example",
    )

    assert values["Retention"] == "30 days"
    assert values["Processing"] == "5 workers, 10 MB upload limit"
    assert values["Automatic processing"] == "disabled"


def test_non_interactive_setup_validates_regions_and_uses_profile_runtime_region():
    args = Namespace(
        non_interactive=True,
        parent_compartment_id="ocid1.compartment.oc1..parent",
        compartment_id="ocid1.compartment.oc1..project",
        home_region="us-ashburn-1",
        runtime_region=None,
        preferred_region="eu-frankfurt-1",
        allowed_ingress_cidr="203.0.113.10",
    )

    prompt_for_compartments(
        args,
        config={"region": "us-phoenix-1"},
        subscribed=["us-ashburn-1", "us-phoenix-1", "eu-frankfurt-1"],
        ui=object(),
    )

    assert args.runtime_region == "us-phoenix-1"
    assert args.allowed_ingress_cidr == "203.0.113.10/32"


def test_non_interactive_setup_rejects_unsubscribed_home_region():
    args = Namespace(
        non_interactive=True,
        parent_compartment_id="ocid1.compartment.oc1..parent",
        compartment_id="ocid1.compartment.oc1..project",
        home_region="ap-missing-1",
        runtime_region=None,
        preferred_region=None,
        allowed_ingress_cidr=None,
    )

    with pytest.raises(SystemExit, match="home/IAM region"):
        prompt_for_compartments(
            args,
            config={"region": "us-phoenix-1"},
            subscribed=["us-ashburn-1", "us-phoenix-1"],
            ui=object(),
        )
