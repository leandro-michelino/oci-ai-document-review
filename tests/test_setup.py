import pytest

from scripts.setup import GenAIRegion, choose_model, supported_chat_models


def test_supported_chat_models_filters_to_cohere_ids():
    models = ["meta.llama-3.1", "cohere.command-r-plus-08-2024"]

    assert supported_chat_models(models) == ["cohere.command-r-plus-08-2024"]


def test_choose_model_rejects_unsupported_chat_models():
    region = GenAIRegion(name="example-region", models=["meta.llama-3.1"])

    with pytest.raises(SystemExit):
        choose_model(
            region, preferred="cohere.command-r-plus-08-2024", non_interactive=True
        )
