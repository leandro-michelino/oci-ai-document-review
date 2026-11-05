#!/usr/bin/env python3
"""Check the Git index and an optional source archive without printing secret values."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
import tarfile

try:
    from scripts.package_release import release_file
except ModuleNotFoundError:  # Standalone invocation from scripts/.
    from package_release import release_file


PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"),
    "GitHub token": re.compile(
        rb"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b"
    ),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "OCI fingerprint": re.compile(rb"\b(?:[a-fA-F0-9]{2}:){15}[a-fA-F0-9]{2}\b"),
    "real OCI identifier": re.compile(
        rb"\bocid1\.[a-z_]+\.[a-z0-9-]+\.[a-z0-9-]*\.[a-z0-9]{40,}\b"
    ),
}


def findings(name: str, data: bytes, *, allow_env_example: bool = False) -> list[str]:
    path = Path(name)
    reasons = []
    if not (allow_env_example and name == ".env.example") and not release_file(path):
        reasons.append("private or generated file path")
    if (
        path.parts[:2]
        in {
            ("data", "metadata"),
            ("data", "uploads"),
            ("data", "reports"),
            ("data", "deleted"),
        }
        or name == "data/case_chat_access.json"
    ):
        reasons.append("runtime data")
    reasons.extend(label for label, pattern in PATTERNS.items() if pattern.search(data))
    return reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, help="Also inspect a generated tar.gz package"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    names = (
        subprocess.check_output(["git", "ls-files", "--cached", "-z"], cwd=root)
        .decode()
        .split("\0")
    )
    problems = []
    count = 0
    for name in filter(None, names):
        data = subprocess.check_output(["git", "show", f":{name}"], cwd=root)
        problems.extend(
            (name, reason) for reason in findings(name, data, allow_env_example=True)
        )
        count += 1
    members = 0
    if args.archive:
        with tarfile.open(args.archive, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile() or member.issym() or member.islnk():
                    problems.append((member.name, "non-regular archive member"))
                    continue
                stream = archive.extractfile(member)
                assert stream is not None
                with stream:
                    data = stream.read()
                problems.extend(
                    (member.name, reason) for reason in findings(member.name, data)
                )
                members += 1
    for name, reason in problems:
        print(f"BLOCKED: {name}: {reason}", file=sys.stderr)
    if problems:
        return 1
    print(f"Publication check passed: {count} indexed files, {members} archive files.")
    print(
        "Checked excluded paths and credential/OCI-identifier patterns; no values printed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
