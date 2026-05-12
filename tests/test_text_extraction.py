# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
from src.text_extraction import extract_text_locally, pdf_page_count, write_pdf_page_chunks


def test_extract_text_locally_reads_text_file(tmp_path):
    source = tmp_path / "contract.txt"
    source.write_text("This is a text-native contract.", encoding="utf-8")

    extraction = extract_text_locally(source, "contract.txt")

    assert extraction is not None
    assert extraction.text == "This is a text-native contract."
    assert extraction.source == "Local text file"


def test_extract_text_locally_skips_images(tmp_path):
    source = tmp_path / "receipt.png"
    source.write_bytes(b"not really an image")

    assert extract_text_locally(source, "receipt.png") is None


def test_pdf_page_count_returns_none_for_non_pdf(tmp_path):
    source = tmp_path / "receipt.txt"
    source.write_text("hello", encoding="utf-8")

    assert pdf_page_count(source, "receipt.txt") is None


def test_pdf_page_count_handles_invalid_pdf(tmp_path):
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"not really a pdf")

    assert pdf_page_count(source, "scan.pdf") is None


def test_write_pdf_page_chunks_respects_document_understanding_page_limit(tmp_path):
    from pypdf import PdfReader, PdfWriter

    source = tmp_path / "scan.pdf"
    writer = PdfWriter()
    for _ in range(12):
        writer.add_blank_page(width=72, height=72)
    with source.open("wb") as file:
        writer.write(file)

    chunks = write_pdf_page_chunks(source, tmp_path / "chunks", pages_per_chunk=5)

    assert [(chunk.start_page, chunk.end_page) for chunk in chunks] == [
        (1, 5),
        (6, 10),
        (11, 12),
    ]
    assert [len(PdfReader(str(chunk.path)).pages) for chunk in chunks] == [5, 5, 2]


def test_write_pdf_page_chunks_reports_page_above_ocr_size_limit(tmp_path):
    import pytest
    from pypdf import PdfWriter

    source = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with source.open("wb") as file:
        writer.write(file)

    with pytest.raises(ValueError, match="8 MB file-size limit"):
        write_pdf_page_chunks(
            source,
            tmp_path / "chunks",
            pages_per_chunk=5,
            max_chunk_bytes=1,
        )
