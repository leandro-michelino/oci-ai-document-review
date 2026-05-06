import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from src.config import get_config
from src.metadata_store import MetadataStore
from src.models import DocumentType
from src.processor import DocumentProcessor


def load_app_config():
    try:
        return get_config()
    except Exception as exc:
        st.error("Configuration is incomplete. Run `python scripts/setup.py` first.")
        st.exception(exc)
        st.stop()


def record_to_row(record):
    analysis = record.analysis
    return {
        "Document ID": record.document_id,
        "Name": record.document_name,
        "Type": record.document_type.value,
        "Status": record.status.value,
        "Review": record.review_status.value,
        "Uploaded": record.uploaded_at.isoformat(),
        "Risks": len(analysis.risk_notes) if analysis else 0,
        "Confidence": analysis.confidence_score if analysis else None,
    }


def upload_page(config, store):
    st.header("Upload Document")
    document_type = st.selectbox("Document type", [item.value for item in DocumentType])
    business_reference = st.text_input("Business reference")
    notes = st.text_area("Notes")
    uploaded = st.file_uploader("Document file", type=["pdf", "png", "jpg", "jpeg"])

    if uploaded:
        size_mb = uploaded.size / (1024 * 1024)
        st.caption(f"{uploaded.name} - {size_mb:.2f} MB")
        if size_mb > config.max_upload_mb:
            st.error(f"File exceeds the configured {config.max_upload_mb} MB limit.")
            return

    if st.button("Process Document", disabled=uploaded is None):
        with NamedTemporaryFile(delete=False, suffix=f"-{uploaded.name}") as tmp:
            tmp.write(uploaded.getbuffer())
            tmp_path = Path(tmp.name)

        processor = DocumentProcessor(config)
        with st.status("Processing document", expanded=True) as status:
            st.write("Uploading to Object Storage")
            st.write("Extracting content with OCI Document Understanding")
            st.write(f"Analyzing with OCI Generative AI in `{config.genai_region}`")
            try:
                record = processor.process(
                    source_path=tmp_path,
                    document_name=uploaded.name,
                    document_type=DocumentType(document_type),
                    business_reference=business_reference or None,
                    notes=notes or None,
                )
                status.update(label="Document processed", state="complete")
                st.session_state["selected_document_id"] = record.document_id
                st.success("Document is ready for review.")
            except Exception as exc:
                status.update(label="Processing failed", state="error")
                st.error(str(exc))

        tmp_path.unlink(missing_ok=True)


def dashboard_page(store):
    st.header("Review Dashboard")
    records = store.list_records()
    if not records:
        st.info("No documents processed yet.")
        return

    rows = [record_to_row(record) for record in records]
    df = pd.DataFrame(rows)
    cols = st.columns(4)
    cols[0].metric("Total", len(records))
    cols[1].metric("Review Required", (df["Status"] == "REVIEW_REQUIRED").sum())
    cols[2].metric("Approved", (df["Review"] == "APPROVED").sum())
    cols[3].metric("Rejected", (df["Review"] == "REJECTED").sum())

    selected_status = st.multiselect("Status", sorted(df["Status"].unique()))
    selected_type = st.multiselect("Document type", sorted(df["Type"].unique()))
    filtered = df
    if selected_status:
        filtered = filtered[filtered["Status"].isin(selected_status)]
    if selected_type:
        filtered = filtered[filtered["Type"].isin(selected_type)]

    st.dataframe(filtered, use_container_width=True, hide_index=True)
    selected = st.selectbox("Open document", filtered["Document ID"].tolist())
    if st.button("Open"):
        st.session_state["selected_document_id"] = selected
        st.session_state["page"] = "Document Details"
        st.rerun()


def detail_page(config, store):
    st.header("Document Details")
    records = store.list_records()
    ids = [record.document_id for record in records]
    if not ids:
        st.info("No documents processed yet.")
        return

    default_id = st.session_state.get("selected_document_id", ids[0])
    index = ids.index(default_id) if default_id in ids else 0
    document_id = st.selectbox("Document", ids, index=index)
    record = store.load(document_id)

    st.subheader(record.document_name)
    st.write(f"Status: `{record.status.value}`")
    st.write(f"Object: `{record.object_storage_path or 'Not uploaded'}`")
    if record.error_message:
        st.error(record.error_message)

    if record.analysis:
        analysis = record.analysis
        st.markdown("### Executive Summary")
        st.write(analysis.executive_summary)
        st.markdown("### Key Points")
        st.write(analysis.key_points or ["None found"])
        st.markdown("### Extracted Fields")
        st.json(analysis.extracted_fields.model_dump())
        st.markdown("### Risk Notes")
        st.dataframe(
            pd.DataFrame([risk.model_dump() for risk in analysis.risk_notes]),
            use_container_width=True,
        )
        st.markdown("### Recommendations")
        st.write(analysis.recommendations or ["None found"])

    comments = st.text_area("Review comments", value=record.review_comments or "")
    col1, col2 = st.columns(2)
    if col1.button("Approve"):
        store.set_review(document_id, approved=True, comments=comments or None)
        st.success("Approved")
        st.rerun()
    if col2.button("Reject"):
        store.set_review(document_id, approved=False, comments=comments or None)
        st.warning("Rejected")
        st.rerun()

    metadata_json = json.dumps(record.model_dump(mode="json"), indent=2)
    st.download_button("Download JSON Result", metadata_json, f"{document_id}.json")
    if record.report_path and Path(record.report_path).exists():
        report = Path(record.report_path).read_text(encoding="utf-8")
        st.download_button("Download Markdown Report", report, f"{document_id}.md")


def settings_page(config):
    st.header("Settings")
    st.write(f"OCI region: `{config.oci_region}`")
    st.write(f"GenAI region: `{config.genai_region}`")
    st.write(f"GenAI endpoint: `{config.genai_endpoint}`")
    st.write(f"Compartment: `{config.oci_compartment_id}`")
    st.write(f"Bucket: `{config.oci_bucket_name}`")
    st.info("Run `python scripts/setup.py` to refresh GenAI region availability.")


def main():
    config = load_app_config()
    store = MetadataStore(config)
    st.set_page_config(page_title=config.app_title, layout="wide")
    st.title(config.app_title)

    pages = ["Upload Document", "Review Dashboard", "Document Details", "Settings"]
    page = st.sidebar.radio(
        "Navigation",
        pages,
        index=pages.index(st.session_state.get("page", "Upload Document")),
    )
    st.session_state["page"] = page

    if page == "Upload Document":
        upload_page(config, store)
    elif page == "Review Dashboard":
        dashboard_page(store)
    elif page == "Document Details":
        detail_page(config, store)
    else:
        settings_page(config)


if __name__ == "__main__":
    main()
