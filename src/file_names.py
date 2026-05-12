# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
import re
from pathlib import Path


def safe_document_name(document_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(document_name).name).strip("._")
    return cleaned or "document"


def chunk_document_name(storage_name: str, index: int) -> str:
    path = Path(storage_name)
    suffix = path.suffix or ".pdf"
    stem = path.stem if path.suffix else path.name
    stem = stem.strip("._") or "document"
    return f"{stem}_{index}{suffix}"
