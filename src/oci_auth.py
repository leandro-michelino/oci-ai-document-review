from src.config import AppConfig


def load_oci_config(config: AppConfig, region: str | None = None) -> dict:
    import oci

    oci_config = oci.config.from_file(
        config.expanded_oci_config_file, config.oci_profile
    )
    if region:
        oci_config["region"] = region
    return oci_config


def get_oci_client_config(
    config: AppConfig, region: str | None = None
) -> tuple[dict, object | None]:
    import oci

    if config.oci_auth.lower() in {"instance_principal", "instance_principals"}:
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        return {"region": region or config.oci_region}, signer
    return load_oci_config(config, region), None
