import pytest

from scripts.setup import (
    GenAIRegion,
    choose_model,
    discover_current_ip_cidr,
    supported_chat_models,
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
