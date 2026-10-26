#!/usr/bin/env python3
"""Build a release from application sources without copying workstation data."""

from __future__ import annotations

import argparse
import tarfile
from pathlib import Path

RELEASE_PATHS = (
    "app.py",
    "src",
    "scripts",
    "requirements.txt",
    "requirements-dev.txt",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "docs",
    "ansible",
    "terraform",
    "functions",
    "oda",
    "data/compliance",
)
EXCLUDED_DIRECTORIES = {"__pycache__", ".terraform", ".git", "node_modules"}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".tfplan",
    ".log",
    ".tmp",
}


def release_file(path: Path) -> bool:
    name = path.name
    return not (
        any(part in EXCLUDED_DIRECTORIES for part in path.parts)
        or name.startswith((".env", "._", "id_rsa", "oci_api_key", "terraform.tfstate"))
        or name == ".DS_Store"
        or name.endswith((".tfvars", ".tfvars.json"))
        or path.suffix in EXCLUDED_SUFFIXES
    )


def build_release(root: Path, destination: Path) -> None:
    root = root.resolve()
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, "w:gz") as archive:
        for item in RELEASE_PATHS:
            source = root / item
            if not source.exists() or source.is_symlink():
                continue
            paths = sorted(source.rglob("*")) if source.is_dir() else [source]
            for path in paths:
                relative = path.relative_to(root)
                # Reject symlink files and directory ancestors, including links
                # pointing elsewhere inside the checkout.
                if any(parent.is_symlink() for parent in (path, *path.parents)):
                    continue
                if path.is_file() and path != destination and release_file(relative):
                    archive.add(path, arcname=str(relative), recursive=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    build_release(Path(__file__).resolve().parents[1], args.destination)


if __name__ == "__main__":
    main()
