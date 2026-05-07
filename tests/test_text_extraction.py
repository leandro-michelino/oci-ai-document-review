from src.text_extraction import extract_text_locally


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
