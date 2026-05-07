from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TEXT_EXTENSIONS = {
    ".csv",
    ".htm",
    ".html",
    ".json",
    ".log",
    ".md",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
PDF_EXTENSION = ".pdf"
MIN_PDF_TEXT_CHARS = 40


@dataclass(frozen=True)
class LocalTextExtraction:
    text: str
    source: str


def extract_text_locally(path: Path, document_name: str) -> LocalTextExtraction | None:
    extension = Path(document_name).suffix.lower()
    if extension in TEXT_EXTENSIONS:
        text = _read_text_file(path)
        return LocalTextExtraction(text=text, source="Local text file")
    if extension == PDF_EXTENSION:
        text = _extract_pdf_text(path)
        if _has_meaningful_pdf_text(text):
            return LocalTextExtraction(text=text, source="Embedded PDF text")
    return None


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        page_text = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception:
        return ""
    return "\n\n".join(text for text in page_text if text)


def _has_meaningful_pdf_text(text: str) -> bool:
    return len(re.sub(r"\s+", "", text)) >= MIN_PDF_TEXT_CHARS
