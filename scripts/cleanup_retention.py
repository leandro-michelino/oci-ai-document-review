#!/usr/bin/env python3
from __future__ import annotations

from src.config import get_config
from src.metadata_store import MetadataStore


def main() -> None:
    config = get_config()
    result = MetadataStore(config).cleanup_expired_local_data(config.retention_days)
    print(
        "Retention cleanup complete: "
        f"{result.metadata_records} metadata record(s), "
        f"{result.invalid_metadata_files} invalid metadata file(s), "
        f"{result.reports} report(s), "
        f"{result.uploads} upload(s) removed."
    )


if __name__ == "__main__":
    main()
