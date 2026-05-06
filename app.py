import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from src.config import get_config
from src.health_checks import run_preflight
from src.metadata_store import MetadataStore
from src.models import DocumentType
from src.processor import DocumentProcessor, error_message


RISK_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


def safe_upload_suffix(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name).strip("._")
    return f"-{cleaned or 'upload'}"


def load_app_config():
    try:
        return get_config()
    except Exception as exc:
        st.error("Configuration is incomplete. Run `python scripts/setup.py` first.")
        st.exception(exc)
        st.stop()


def highest_risk_level(record) -> str:
    if not record.analysis or not record.analysis.risk_notes:
        return "NONE"
    return max(
        (risk.severity for risk in record.analysis.risk_notes),
        key=lambda severity: RISK_ORDER.get(severity, 0),
    )


def confidence_percent(record) -> int | None:
    if not record.analysis:
        return None
    return round(record.analysis.confidence_score * 100)


def record_summary(record) -> str:
    if record.analysis:
        return record.analysis.executive_summary
    if record.error_message:
        return record.error_message
    if record.extracted_text_preview:
        return record.extracted_text_preview
    return "No analysis available yet."


def record_to_row(record):
    analysis = record.analysis
    summary = record_summary(record)
    search_parts = [
        record.document_id,
        record.document_name,
        record.document_type.value,
        record.status.value,
        record.review_status.value,
        record.business_reference or "",
        summary,
    ]
    return {
        "Document ID": record.document_id,
        "Name": record.document_name,
        "Type": record.document_type.value,
        "Status": record.status.value,
        "Review": record.review_status.value,
        "Uploaded": record.uploaded_at.strftime("%Y-%m-%d %H:%M"),
        "Uploaded Sort": record.uploaded_at.isoformat(),
        "Reference": record.business_reference or "",
        "Risk Level": highest_risk_level(record),
        "Risks": len(analysis.risk_notes) if analysis else 0,
        "Confidence": confidence_percent(record),
        "Summary": summary,
        "Search Text": " ".join(search_parts).lower(),
    }


def filter_dashboard_rows(
    df: pd.DataFrame,
    query: str,
    statuses: list[str],
    document_types: list[str],
    review_states: list[str],
    risk_levels: list[str],
    minimum_confidence: int,
    needs_attention_only: bool,
) -> pd.DataFrame:
    filtered = df.copy()
    if statuses:
        filtered = filtered[filtered["Status"].isin(statuses)]
    if document_types:
        filtered = filtered[filtered["Type"].isin(document_types)]
    if review_states:
        filtered = filtered[filtered["Review"].isin(review_states)]
    if risk_levels:
        filtered = filtered[filtered["Risk Level"].isin(risk_levels)]
    if minimum_confidence:
        confidence = filtered["Confidence"].fillna(-1)
        filtered = filtered[confidence >= minimum_confidence]
    if needs_attention_only:
        risk_score = filtered["Risk Level"].map(RISK_ORDER).fillna(0)
        filtered = filtered[
            (filtered["Status"].isin(["FAILED", "REVIEW_REQUIRED"]))
            | (filtered["Review"] == "PENDING")
            | (risk_score >= RISK_ORDER["HIGH"])
        ]
    terms = [term for term in query.lower().split() if term]
    for term in terms:
        filtered = filtered[filtered["Search Text"].str.contains(term, regex=False, na=False)]
    return filtered.sort_values("Uploaded Sort", ascending=False)


def selected_record_label(row: pd.Series) -> str:
    return f"{row['Name']} - {row['Status']} - {row['Uploaded']}"


def upload_page(config, store):
    st.header("Upload Document")
    document_type = st.selectbox("Document type", [item.value for item in DocumentType])
    business_reference = st.text_input("Business reference")
    notes = st.text_area("Notes")
    st.caption(f"Supported: PDF, PNG, JPG, JPEG. App upload limit: {config.max_upload_mb} MB.")
    uploaded = st.file_uploader(
        "Document file",
        type=["pdf", "png", "jpg", "jpeg"],
        help=(
            "Streamlit may show its server upload limit, but this app enforces "
            f"{config.max_upload_mb} MB before processing."
        ),
    )

    if uploaded:
        size_mb = uploaded.size / (1024 * 1024)
        st.caption(f"{uploaded.name} - {size_mb:.2f} MB")
        if size_mb > config.max_upload_mb:
            st.error(f"File exceeds the configured {config.max_upload_mb} MB limit.")
            return

    if st.button("Process Document", disabled=uploaded is None):
        with NamedTemporaryFile(delete=False, suffix=safe_upload_suffix(uploaded.name)) as tmp:
            tmp.write(uploaded.getbuffer())
            tmp_path = Path(tmp.name)

        processor = DocumentProcessor(config)
        with st.status("Processing document", expanded=True) as status:
            try:
                record = processor.process(
                    source_path=tmp_path,
                    document_name=uploaded.name,
                    document_type=DocumentType(document_type),
                    business_reference=business_reference or None,
                    notes=notes or None,
                    progress_callback=st.write,
                )
                status.update(label="Document processed", state="complete")
                st.session_state["selected_document_id"] = record.document_id
                st.success("Document is ready for review.")
            except Exception as exc:
                status.update(label="Processing failed", state="error")
                st.error(f"Processing failed: {error_message(exc)}")
                with st.expander("Technical details"):
                    st.exception(exc)

        tmp_path.unlink(missing_ok=True)


def dashboard_page(store):
    st.header("Review Dashboard")
    records = store.list_records()
    if not records:
        st.info("No documents processed yet.")
        return

    rows = [record_to_row(record) for record in records]
    df = pd.DataFrame(rows)
    cols = st.columns(5)
    cols[0].metric("Total", len(records))
    cols[1].metric("Pending Review", (df["Review"] == "PENDING").sum())
    cols[2].metric("High Risk", (df["Risk Level"] == "HIGH").sum())
    cols[3].metric("Failed", (df["Status"] == "FAILED").sum())
    avg_confidence = df["Confidence"].dropna().mean()
    cols[4].metric(
        "Avg Confidence",
        "N/A" if pd.isna(avg_confidence) else f"{avg_confidence:.0f}%",
    )

    failures = df[df["Status"] == "FAILED"]
    if not failures.empty:
        st.warning(f"{len(failures)} document processing run needs attention.")

    filter_row = st.columns([2, 1, 1, 1])
    search = filter_row[0].text_input(
        "Search",
        placeholder="Name, ID, reference, status, or summary",
    )
    selected_status = filter_row[1].multiselect("Status", sorted(df["Status"].unique()))
    selected_type = filter_row[2].multiselect("Type", sorted(df["Type"].unique()))
    selected_review = filter_row[3].multiselect("Review", sorted(df["Review"].unique()))

    advanced = st.columns([1, 1, 1])
    selected_risk = advanced[0].multiselect(
        "Risk",
        [level for level in ["HIGH", "MEDIUM", "LOW", "NONE"] if level in set(df["Risk Level"])],
    )
    min_confidence = advanced[1].slider("Min confidence", 0, 100, 0, step=5)
    needs_attention = advanced[2].toggle("Needs attention only", value=False)

    filtered = filter_dashboard_rows(
        df=df,
        query=search,
        statuses=selected_status,
        document_types=selected_type,
        review_states=selected_review,
        risk_levels=selected_risk,
        minimum_confidence=min_confidence,
        needs_attention_only=needs_attention,
    )

    st.caption(f"Showing {len(filtered)} of {len(df)} documents")
    display_columns = [
        "Name",
        "Type",
        "Status",
        "Review",
        "Uploaded",
        "Reference",
        "Risk Level",
        "Risks",
        "Confidence",
        "Summary",
    ]
    st.dataframe(
        filtered[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Confidence": st.column_config.ProgressColumn(
                "Confidence",
                min_value=0,
                max_value=100,
                format="%d%%",
            ),
            "Summary": st.column_config.TextColumn("Summary", width="large"),
        },
    )
    if filtered.empty:
        st.info("No documents match the selected filters.")
        return

    label_by_id = {
        row["Document ID"]: selected_record_label(row)
        for _, row in filtered.iterrows()
    }
    filtered_ids = filtered["Document ID"].tolist()
    previous_selection = st.session_state.get("dashboard_selected_document")
    selected_index = filtered_ids.index(previous_selection) if previous_selection in filtered_ids else 0
    selected = st.selectbox(
        "Selected document",
        filtered_ids,
        index=selected_index,
        format_func=lambda document_id: label_by_id.get(document_id, document_id),
        key="dashboard_selected_document",
    )

    record_by_id = {record.document_id: record for record in records}
    selected_record = record_by_id[selected]
    with st.container(border=True):
        st.subheader(selected_record.document_name)
        preview_cols = st.columns(4)
        preview_cols[0].metric("Status", selected_record.status.value)
        preview_cols[1].metric("Review", selected_record.review_status.value)
        preview_cols[2].metric("Risk", highest_risk_level(selected_record))
        confidence = confidence_percent(selected_record)
        preview_cols[3].metric("Confidence", "N/A" if confidence is None else f"{confidence}%")
        if selected_record.analysis:
            st.write(selected_record.analysis.executive_summary)
        elif selected_record.error_message:
            st.error(selected_record.error_message)
        else:
            st.info("Analysis is not available yet.")

    if st.button("Open Details", type="primary"):
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
        if analysis.risk_notes:
            st.dataframe(
                pd.DataFrame([risk.model_dump() for risk in analysis.risk_notes]),
                use_container_width=True,
            )
        else:
            st.info("No risk notes found.")
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

    st.subheader("OCI Preflight")
    st.write(
        "Run this before processing customer documents. It performs real OCI API "
        "calls with the same runtime credentials used by document processing."
    )
    if st.button("Run OCI Preflight", type="primary"):
        with st.spinner("Checking Object Storage, Document Understanding, and GenAI"):
            results = run_preflight(config)
        for result in results:
            if result.ok:
                st.success(f"{result.name}: {result.detail}")
            else:
                st.error(f"{result.name}: {result.detail}")
        if all(result.ok for result in results):
            st.success("All OCI runtime checks passed.")
        else:
            st.warning("Fix the failed checks before processing customer documents.")


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
