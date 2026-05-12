#!/usr/bin/env python3
# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_config  # noqa: E402
from src.metadata_store import MetadataStore  # noqa: E402


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
