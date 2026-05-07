import pytest
from argparse import Namespace

from scripts.setup import (
    GenAIRegion,
    choose_model,
    discover_current_ip_cidr,
    normalize_cidr,
    prompt_for_compartments,
    supported_chat_models,
    validate_cidr,
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
