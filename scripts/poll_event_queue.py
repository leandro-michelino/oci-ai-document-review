#!/usr/bin/env python3
# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_config  # noqa: E402
from src.event_intake import import_event_queue  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import OCI Events + Functions Object Storage queue markers."
    )
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = get_config()
    result = import_event_queue(config, limit=args.limit)
    print(
        "event_intake "
        f"imported={result.imported} skipped={result.skipped} failed={result.failed}"
    )
    for message in result.messages:
        print(message)
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
