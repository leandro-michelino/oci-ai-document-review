"""Publication checks use constructed synthetic markers, never real credentials."""

import pytest

from scripts.check_publication import findings


@pytest.mark.parametrize(
    "name", [".env", "src/.aws/credentials", "docs/secrets.json", "data/uploads/a.txt"]
)
def test_private_paths_are_rejected(name):
    assert findings(name, b"synthetic")


@pytest.mark.parametrize(
    "marker",
    [
        b"-----BEGIN " + b"PRIVATE KEY-----",
        b"ghp_" + b"A" * 36,
        b"AKIA" + b"B" * 16,
        b":".join([b"ab"] * 16),
        b"ocid1.compartment.oc1.." + b"a" * 64,
    ],
)
def test_credential_and_real_identifier_patterns_are_rejected(marker):
    assert findings("docs/example.txt", marker)


def test_safe_examples_and_documentation_are_allowed():
    assert (
        findings(
            ".env.example",
            b"OCI_COMPARTMENT_ID=ocid1.compartment.oc1..exampleproject",
            allow_env_example=True,
        )
        == []
    )
    assert (
        findings("terraform/terraform.tfvars.example", b'region = "your-region"') == []
    )
    assert findings("docs/security_notes.md", b"Use instance principals.") == []
