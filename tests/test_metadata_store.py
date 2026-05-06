from types import SimpleNamespace

from src.metadata_store import MetadataStore
from src.models import DocumentRecord, DocumentType


def test_list_records_skips_invalid_metadata(tmp_path):
    config = SimpleNamespace(local_metadata_dir=tmp_path)
    valid = DocumentRecord(
        document_id="doc-1",
        document_name="contract.pdf",
        document_type=DocumentType.CONTRACT,
    )
    (tmp_path / "doc-1.json").write_text(valid.model_dump_json(), encoding="utf-8")
    (tmp_path / "broken.json").write_text("{not-json", encoding="utf-8")

    records = MetadataStore(config).list_records()

    assert [record.document_id for record in records] == ["doc-1"]
