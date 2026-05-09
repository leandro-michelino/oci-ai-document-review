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
DOCUMENT_UNDERSTANDING_SYNC_PAGE_LIMIT = 5
DOCUMENT_UNDERSTANDING_SYNC_FILE_SIZE_LIMIT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class LocalTextExtraction:
    text: str
    source: str


@dataclass(frozen=True)
class PdfPageChunk:
    path: Path
    start_page: int
    end_page: int

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page + 1


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


def pdf_page_count(path: Path, document_name: str) -> int | None:
    if Path(document_name).suffix.lower() != PDF_EXTENSION:
        return None
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def write_pdf_page_chunks(
    path: Path,
    output_dir: Path,
    pages_per_chunk: int = DOCUMENT_UNDERSTANDING_SYNC_PAGE_LIMIT,
    max_chunk_bytes: int = DOCUMENT_UNDERSTANDING_SYNC_FILE_SIZE_LIMIT_BYTES,
) -> list[PdfPageChunk]:
    if pages_per_chunk < 1:
        raise ValueError("pages_per_chunk must be greater than zero")
    if max_chunk_bytes < 1:
        raise ValueError("max_chunk_bytes must be greater than zero")

    from pypdf import PdfReader, PdfWriter

    output_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(path))
    chunks: list[PdfPageChunk] = []
    total_pages = len(reader.pages)

    def write_range(start_index: int, end_index: int) -> Path:
        writer = PdfWriter()
        for page_index in range(start_index, end_index):
            writer.add_page(reader.pages[page_index])
        start_page = start_index + 1
        end_page = end_index
        chunk_path = (
            output_dir
            / f"chunk-pages-{start_page:04d}-{end_page:04d}.pdf"
        )
        with chunk_path.open("wb") as chunk_file:
            writer.write(chunk_file)
        return chunk_path

    def add_range(start_index: int, end_index: int) -> None:
        chunk_path = write_range(start_index, end_index)
        if chunk_path.stat().st_size > max_chunk_bytes:
            if end_index - start_index <= 1:
                chunk_path.unlink(missing_ok=True)
                raise ValueError(
                    "A PDF page exceeds the OCI Document Understanding synchronous "
                    "8 MB file-size limit after chunking."
                )
            chunk_path.unlink(missing_ok=True)
            mid_index = start_index + max(1, (end_index - start_index) // 2)
            add_range(start_index, mid_index)
            add_range(mid_index, end_index)
            return
        start_page = start_index + 1
        end_page = end_index
        chunks.append(
            PdfPageChunk(path=chunk_path, start_page=start_page, end_page=end_page)
        )

    for start_index in range(0, total_pages, pages_per_chunk):
        end_index = min(start_index + pages_per_chunk, total_pages)
        add_range(start_index, end_index)
    return chunks


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
