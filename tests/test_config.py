# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
import pytest
from pydantic import ValidationError

from src.config import AppConfig


def config_kwargs(**overrides):
    values = {
        "OCI_REGION": "uk-london-1",
        "GENAI_REGION": "uk-london-1",
        "OCI_COMPARTMENT_ID": "ocid1.compartment.oc1..exampleproject",
        "OCI_NAMESPACE": "example",
        "OCI_BUCKET_NAME": "doc-review-input",
        "GENAI_MODEL_ID": "cohere.command-r-plus-08-2024",
    }
    values.update(overrides)
    return values


def test_app_config_accepts_valid_runtime_settings():
    config = AppConfig(**config_kwargs(OCI_AUTH="instance_principal"))

    assert config.oci_auth == "instance_principal"
    assert config.max_parallel_jobs == 5
    assert config.retention_days == 30


def test_app_config_rejects_invalid_numeric_limits():
    with pytest.raises(ValidationError):
        AppConfig(**config_kwargs(MAX_PARALLEL_JOBS=0))

    with pytest.raises(ValidationError):
        AppConfig(**config_kwargs(GENAI_TEMPERATURE=8))

    with pytest.raises(ValidationError):
        AppConfig(**config_kwargs(RETENTION_DAYS=0))


def test_app_config_rejects_bad_auth_and_object_name():
    with pytest.raises(ValidationError):
        AppConfig(**config_kwargs(OCI_AUTH="api_key"))

    with pytest.raises(ValidationError):
        AppConfig(**config_kwargs(COMPLIANCE_ENTITIES_OBJECT_NAME="../private.csv"))
