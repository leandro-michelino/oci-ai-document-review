import json
import re
from html import escape
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from src.config import get_config
from src.health_checks import run_preflight
from src.job_queue import submit_document_processing, submitted_document_ids
from src.metadata_store import MetadataStore
from src.models import DocumentRecord, DocumentType, ProcessingStatus
from src.processor import create_document_id


RISK_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
READY_FOR_DECISION = {"REVIEW_REQUIRED"}
ACTIVE_STATUSES = {"UPLOADED", "PROCESSING", "EXTRACTED", "AI_ANALYZED"}
CONTACT_TEXT = "Leandro Michelino | ACE | leandro.michelino@oracle.com"
CONTACT_MESSAGE = "In case of any question, get in touch."
PAGE_UPLOAD = "Upload"
PAGE_DASHBOARD = "Dashboard"
PAGE_DETAIL = "Document"
PAGE_SETTINGS = "Settings"
LEGACY_PAGE_NAMES = {
    "Upload Document": PAGE_UPLOAD,
    "Review Dashboard": PAGE_DASHBOARD,
    "Document Details": PAGE_DETAIL,
}
RISK_TONE = {
    "HIGH": "risk-high",
    "MEDIUM": "risk-medium",
    "LOW": "risk-low",
    "NONE": "risk-none",
}
STATE_TONE = {
    "APPROVED": "state-good",
    "COMPLETE": "state-good",
    "REJECTED": "state-bad",
    "FAILED": "state-bad",
    "REVIEW_REQUIRED": "state-warn",
    "PENDING": "state-warn",
    "PROCESSING": "state-info",
    "EXTRACTED": "state-info",
    "AI_ANALYZED": "state-info",
    "UPLOADED": "state-info",
}
FIELD_HELP = {
    "Action": "The next human or operational step for the selected document.",
    "Business reference": "Optional user-provided reference, such as invoice number, case ID, or contract ID.",
    "Confidence": "AI confidence score returned by the review analysis, shown as 0 to 100 percent. It is not a guarantee of correctness.",
    "Document ID": "Internal portal identifier created for this processing run.",
    "Document type": "Review category chosen during upload. It guides the GenAI prompt.",
    "Extension": "File extension from the uploaded file name.",
    "File name": "Original uploaded file name.",
    "File size": "Original upload size captured by the portal for new uploads.",
    "MIME type": "Browser-reported file content type captured during upload.",
    "Report": "Whether a Markdown review report exists on the VM.",
    "Review": "Human review decision state: PENDING, APPROVED, or REJECTED.",
    "Risk": "Highest severity found in AI risk notes. NONE means no risk note was returned.",
    "Status": "Processing state for the document lifecycle, from upload through approval or failure.",
    "Stage": "Simple queue state: Queued, Processing, Ready, Reviewed, or Failed.",
    "Storage": "Whether the original file has an OCI Object Storage path recorded.",
    "Text preview": "Number of extracted characters stored for quick inspection in the portal.",
}
FIELD_GUIDE_ROWS = [
    ("Status", FIELD_HELP["Status"]),
    ("Review", FIELD_HELP["Review"]),
    ("Risk", FIELD_HELP["Risk"]),
    ("Confidence", FIELD_HELP["Confidence"]),
    ("Action", FIELD_HELP["Action"]),
    ("Document type", FIELD_HELP["Document type"]),
    ("File size", FIELD_HELP["File size"]),
    ("MIME type", FIELD_HELP["MIME type"]),
    ("Report", FIELD_HELP["Report"]),
    ("Text preview", FIELD_HELP["Text preview"]),
    ("Storage", FIELD_HELP["Storage"]),
]


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --app-bg: #f7f7f5;
            --panel-bg: #ffffff;
            --panel-border: #d9d5cd;
            --text-soft: #5f5a52;
            --text-strong: #26221d;
            --brand: #b23b2e;
            --brand-dark: #7d251f;
            --good-bg: #e8f3ec;
            --good-text: #23623b;
            --warn-bg: #fff4df;
            --warn-text: #8a5a08;
            --bad-bg: #fbe8e5;
            --bad-text: #9a2f23;
            --info-bg: #e8f0f6;
            --info-text: #2c5d7e;
        }
        .stApp {
            background: var(--app-bg);
        }
        .block-container {
            padding-top: 1rem;
            padding-bottom: 2.5rem;
            max-width: 1180px;
        }
        h1, h2, h3 {
            letter-spacing: 0;
            color: var(--text-strong);
        }
        [data-testid="stSidebar"] {
            background: #efede8;
            border-right: 1px solid var(--panel-border);
        }
        [data-testid="stMetric"] {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 0.7rem 0.85rem;
            min-height: 80px;
            box-shadow: 0 1px 2px rgba(38, 34, 29, 0.04);
        }
        div[data-testid="stMetricLabel"] p {
            color: var(--text-soft);
            font-size: 0.82rem;
        }
        div[data-testid="stMetricValue"] {
            color: var(--text-strong);
            font-size: 1.22rem;
        }
        .app-page-header {
            border-bottom: 1px solid var(--panel-border);
            padding-bottom: 0.75rem;
            margin-bottom: 1.1rem;
        }
        .app-kicker {
            color: var(--brand-dark);
            font-size: 0.74rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.15rem;
        }
        .app-page-header h1 {
            font-size: 1.58rem;
            line-height: 1.15;
            margin: 0;
        }
        .app-page-header p {
            color: var(--text-soft);
            margin: 0.35rem 0 0;
            max-width: 860px;
        }
        .status-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            align-items: center;
            margin: 0.35rem 0 0.85rem;
        }
        .badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            border: 1px solid transparent;
            padding: 0.22rem 0.55rem;
            font-size: 0.76rem;
            font-weight: 700;
            line-height: 1.2;
            white-space: nowrap;
        }
        .state-good, .risk-low {
            color: var(--good-text);
            background: var(--good-bg);
            border-color: #b7dbc2;
        }
        .state-warn, .risk-medium {
            color: var(--warn-text);
            background: var(--warn-bg);
            border-color: #edcf91;
        }
        .state-bad, .risk-high {
            color: var(--bad-text);
            background: var(--bad-bg);
            border-color: #e4afa8;
        }
        .state-info {
            color: var(--info-text);
            background: var(--info-bg);
            border-color: #bdd1df;
        }
        .risk-none {
            color: #5f5a52;
            background: #efede8;
            border-color: #d4d0c8;
        }
        .soft-panel {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 1px 2px rgba(38, 34, 29, 0.04);
        }
        .muted-label {
            color: var(--text-soft);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.25rem;
        }
        .summary-text {
            color: var(--text-strong);
            font-size: 1rem;
            line-height: 1.55;
            margin: 0;
        }
        .fine-print {
            color: var(--text-soft);
            font-size: 0.84rem;
            line-height: 1.45;
        }
        .review-snapshot {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.6rem;
            margin: 0.55rem 0 0.75rem;
        }
        .snapshot-cell {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 0.75rem 0.85rem;
            min-width: 0;
        }
        .snapshot-label {
            color: var(--text-soft);
            font-size: 0.74rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.3rem;
        }
        .snapshot-value {
            color: var(--text-strong);
            font-size: 0.98rem;
            font-weight: 800;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.6rem;
            margin: 0.35rem 0 0.65rem;
        }
        .info-item {
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 0.62rem 0.7rem;
            background: #fbfaf7;
            min-width: 0;
        }
        .simple-note {
            color: var(--text-soft);
            font-size: 0.9rem;
            line-height: 1.45;
            margin: 0.25rem 0 0.75rem;
        }
        .action-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            align-items: center;
        }
        .info-label {
            color: var(--text-soft);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.25rem;
        }
        .info-value {
            color: var(--text-strong);
            font-size: 0.9rem;
            font-weight: 700;
            line-height: 1.35;
            overflow-wrap: anywhere;
        }
        .help-dot {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1rem;
            height: 1rem;
            margin-left: 0.25rem;
            border-radius: 999px;
            border: 1px solid #c7c1b8;
            color: #5f5a52;
            background: #ffffff;
            font-size: 0.68rem;
            font-weight: 900;
            cursor: help;
            vertical-align: text-top;
        }
        @media (max-width: 980px) {
            .review-snapshot,
            .info-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        .stButton > button,
        .stDownloadButton > button {
            border-radius: 6px;
            font-weight: 700;
        }
        .stButton > button[kind="primary"] {
            background: var(--brand);
            border-color: var(--brand);
        }
        .stButton > button[kind="primary"]:hover {
            background: var(--brand-dark);
            border-color: var(--brand-dark);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def page_header(kicker: str, title: str, subtitle: str | None = None) -> None:
    subtitle_html = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class="app-page-header">
          <div class="app-kicker">{escape(kicker)}</div>
          <h1>{escape(title)}</h1>
          {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(label: str, tone: str) -> str:
    return f'<span class="badge {tone}">{escape(label)}</span>'


def help_dot(label: str) -> str:
    help_text = FIELD_HELP.get(label)
    if not help_text:
        return ""
    return f'<span class="help-dot" title="{escape(help_text)}">?</span>'


def state_tone(value: str) -> str:
    return STATE_TONE.get(value.upper(), "state-info")


def risk_tone(value: str) -> str:
    return RISK_TONE.get(value.upper(), "risk-none")


def render_status_strip(record) -> None:
    risk = highest_risk_level(record)
    confidence = confidence_percent(record)
    confidence_label = "Confidence N/A" if confidence is None else f"Confidence {confidence}%"
    chips = [
        badge(record.status.value, state_tone(record.status.value)),
        badge(record.review_status.value, state_tone(record.review_status.value)),
        badge(f"Risk {risk}", risk_tone(risk)),
        badge(confidence_label, "state-info"),
        badge(next_action(record), state_tone(record.status.value)),
    ]
    st.markdown(f'<div class="status-strip">{"".join(chips)}</div>', unsafe_allow_html=True)


def render_summary_panel(title: str, body: str, label: str | None = None) -> None:
    label_html = f'<div class="muted-label">{escape(label)}</div>' if label else ""
    st.markdown(
        f"""
        <div class="soft-panel">
          {label_html}
          <div class="muted-label">{escape(title)}</div>
          <p class="summary-text">{escape(body)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_field_guide() -> None:
    with st.expander("Field guide"):
        st.dataframe(
            pd.DataFrame(FIELD_GUIDE_ROWS, columns=["Field", "Meaning"]),
            width="stretch",
            hide_index=True,
        )
        st.caption("Confidence and risk are AI-assisted signals. The human reviewer owns the final decision.")


def file_size_label(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "Not captured"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    size_kb = size_bytes / 1024
    if size_kb < 1024:
        return f"{size_kb:.1f} KB"
    return f"{size_kb / 1024:.2f} MB"


def file_extension(record) -> str:
    extension = Path(record.document_name).suffix.lower().lstrip(".")
    return extension.upper() if extension else "Unknown"


def report_state(record) -> str:
    if record.report_path and Path(record.report_path).exists():
        return "Available"
    return "Not available"


def extracted_text_label(record) -> str:
    if not record.extracted_text_preview:
        return "No preview"
    return f"{len(record.extracted_text_preview):,} preview chars"


def render_review_snapshot(record) -> None:
    confidence = confidence_percent(record)
    values = [
        ("Status", record.status.value),
        ("Risk", highest_risk_level(record)),
        ("Confidence", "N/A" if confidence is None else f"{confidence}%"),
        ("Next action", next_action(record)),
    ]
    cells = "\n".join(
        f"""
        <div class="snapshot-cell">
          <div class="snapshot-label">{escape(label)}{help_dot(label)}</div>
          <div class="snapshot-value">{escape(value)}</div>
        </div>
        """
        for label, value in values
    )
    st.markdown(f'<div class="review-snapshot">{cells}</div>', unsafe_allow_html=True)


def render_file_information(record, compact: bool = False) -> None:
    core_info = [
        ("File name", record.document_name),
        ("Document type", record.document_type.value),
        ("File size", file_size_label(record.source_file_size_bytes)),
        ("Uploaded", record.uploaded_at.strftime("%Y-%m-%d %H:%M")),
        ("Status", record.status.value),
        ("Action", next_action(record)),
    ]
    extra_info = [
        ("Extension", file_extension(record)),
        ("MIME type", record.source_file_mime_type or "Not captured"),
        ("Business reference", record.business_reference or "Not provided"),
        (
            "Processed",
            record.processed_at.strftime("%Y-%m-%d %H:%M") if record.processed_at else "Not processed",
        ),
        ("Document ID", record.document_id),
        ("Report", report_state(record)),
        ("Text preview", extracted_text_label(record)),
        ("Storage", "Uploaded to OCI" if record.object_storage_path else "Not uploaded"),
    ]
    info = core_info if compact else core_info + extra_info
    items = "\n".join(
        f"""
        <div class="info-item">
          <div class="info-label">{escape(label)}{help_dot(label)}</div>
          <div class="info-value">{escape(value)}</div>
        </div>
        """
        for label, value in info
    )
    st.markdown(f'<div class="info-grid">{items}</div>', unsafe_allow_html=True)


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


def requires_human_action(record) -> bool:
    return record.status.value in READY_FOR_DECISION and record.review_status.value == "PENDING"


def next_action(record) -> str:
    if record.status.value == "FAILED":
        return "Fix and retry"
    if requires_human_action(record):
        return "Approve or reject"
    if record.review_status.value == "APPROVED":
        return "Approved"
    if record.review_status.value == "REJECTED":
        return "Rejected"
    return "Wait for processing"


def queue_stage(record) -> str:
    if record.status.value == "FAILED":
        return "Failed"
    if record.review_status.value in {"APPROVED", "REJECTED"}:
        return "Reviewed"
    if record.status.value == "REVIEW_REQUIRED":
        return "Ready"
    if record.status.value in ACTIVE_STATUSES:
        return "Processing" if record.status.value != "UPLOADED" else "Queued"
    return record.status.value.replace("_", " ").title()


def processing_stage_rows(record) -> list[dict[str, str]]:
    has_extraction = bool(record.extracted_text_preview)
    has_report = bool(record.report_path and Path(record.report_path).exists())
    return [
        {
            "Stage": "Upload",
            "State": "Complete",
            "Evidence": record.uploaded_at.strftime("%Y-%m-%d %H:%M"),
        },
        {
            "Stage": "Object Storage",
            "State": "Complete" if record.object_storage_path else "Not complete",
            "Evidence": record.object_storage_path or "No object recorded",
        },
        {
            "Stage": "Document Understanding",
            "State": "Complete" if has_extraction else "Not complete",
            "Evidence": "Extracted text preview saved" if has_extraction else "No extracted text",
        },
        {
            "Stage": "GenAI analysis",
            "State": "Complete" if record.analysis else "Not complete",
            "Evidence": (
                f"{confidence_percent(record)}% confidence"
                if record.analysis
                else "No analysis saved"
            ),
        },
        {
            "Stage": "Review report",
            "State": "Complete" if has_report else "Not complete",
            "Evidence": "Markdown report available" if has_report else "No report file",
        },
        {
            "Stage": "Human decision",
            "State": record.review_status.value,
            "Evidence": next_action(record),
        },
    ]


def render_lifecycle(record) -> None:
    st.markdown("### Processing Lifecycle")
    st.write(f"Next action: `{next_action(record)}`")
    st.dataframe(
        pd.DataFrame(processing_stage_rows(record)),
        width="stretch",
        hide_index=True,
    )
    if record.status.value == "FAILED":
        st.error(record.error_message or "Processing failed before completion.")


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
    action = next_action(record)
    stage = queue_stage(record)
    search_parts = [
        record.document_id,
        record.document_name,
        record.document_type.value,
        record.status.value,
        stage,
        record.review_status.value,
        record.business_reference or "",
        action,
        summary,
    ]
    return {
        "Document ID": record.document_id,
        "Name": record.document_name,
        "Type": record.document_type.value,
        "Status": record.status.value,
        "Stage": stage,
        "Review": record.review_status.value,
        "Uploaded": record.uploaded_at.strftime("%Y-%m-%d %H:%M"),
        "Uploaded Sort": record.uploaded_at.isoformat(),
        "Reference": record.business_reference or "",
        "Risk Level": highest_risk_level(record),
        "Risks": len(analysis.risk_notes) if analysis else 0,
        "Confidence": confidence_percent(record),
        "Action": action,
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


def filter_queue_rows(df: pd.DataFrame, view: str, query: str) -> pd.DataFrame:
    filtered = df.copy()
    if view == "Ready":
        filtered = filtered[filtered["Action"] == "Approve or reject"]
    elif view == "Processing":
        filtered = filtered[filtered["Status"].isin(ACTIVE_STATUSES)]
    elif view == "Failed":
        filtered = filtered[filtered["Status"] == "FAILED"]
    elif view == "Reviewed":
        filtered = filtered[filtered["Review"].isin(["APPROVED", "REJECTED"])]

    terms = [term for term in query.lower().split() if term]
    for term in terms:
        filtered = filtered[filtered["Search Text"].str.contains(term, regex=False, na=False)]
    return filtered.sort_values("Uploaded Sort", ascending=False)


def selected_record_label(row: pd.Series) -> str:
    return f"{row['Name']} - {row['Stage']} - {row['Uploaded']}"


def open_page(page: str, document_id: str | None = None) -> None:
    page = LEGACY_PAGE_NAMES.get(page, page)
    if document_id:
        st.session_state["selected_document_id"] = document_id
        if page == PAGE_DASHBOARD:
            st.session_state["dashboard_selected_document"] = document_id
    st.session_state["page"] = page
    st.rerun()


def set_page(page: str) -> None:
    st.session_state["page"] = LEGACY_PAGE_NAMES.get(page, page)


def render_queued_actions(record) -> None:
    with st.container(border=True):
        st.subheader("Queued")
        render_status_strip(record)
        st.write("The file is in the background queue. You can follow it from the dashboard.")
        cols = st.columns([1, 1, 1])
        if cols[0].button("View Dashboard", type="primary"):
            open_page(PAGE_DASHBOARD, record.document_id)
        if cols[1].button("Open Document"):
            open_page(PAGE_DETAIL, record.document_id)
        if cols[2].button("Upload Another"):
            st.session_state["upload_widget_version"] = (
                st.session_state.get("upload_widget_version", 0) + 1
            )
            open_page(PAGE_UPLOAD)


def apply_review_action(store, document_id: str, approved: bool, comments: str | None) -> bool:
    if not approved and not (comments or "").strip():
        st.error("Add review comments before rejecting.")
        return False
    store.set_review(document_id, approved=approved, comments=comments or None)
    st.success("Approved" if approved else "Rejected")
    return True


def render_review_action_panel(store, record, key_prefix: str) -> None:
    if record.status.value == "FAILED":
        st.error("This document failed processing. Upload a corrected file or check service logs.")
        return
    if not record.analysis:
        st.info("This document is not ready for review yet.")
        return

    if requires_human_action(record):
        st.warning("Action required: approve or reject this document.")
    else:
        st.info(f"Current review decision: {record.review_status.value}")

    comments = st.text_area(
        "Review comments",
        value=record.review_comments or "",
        key=f"{key_prefix}_comments_{record.document_id}",
    )
    cols = st.columns(2)
    if cols[0].button("Approve", type="primary", key=f"{key_prefix}_approve_{record.document_id}"):
        if apply_review_action(store, record.document_id, approved=True, comments=comments):
            st.rerun()
    if cols[1].button("Reject", key=f"{key_prefix}_reject_{record.document_id}"):
        if apply_review_action(store, record.document_id, approved=False, comments=comments):
            st.rerun()


def render_analysis_overview(record) -> None:
    if not record.analysis:
        if record.error_message:
            st.error(record.error_message)
        else:
            st.info("Analysis is not available yet.")
        return

    analysis = record.analysis
    render_summary_panel("Executive Summary", analysis.executive_summary)
    st.caption(
        f"Document class: {analysis.document_class} | "
        f"Confidence: {confidence_percent(record)}% | Risk: {highest_risk_level(record)}"
    )

    col_left, col_right = st.columns(2, gap="large")
    with col_left:
        st.markdown("### Key Points")
        if analysis.key_points:
            for item in analysis.key_points[:5]:
                st.write(f"- {item}")
        else:
            st.info("No key points found.")
    with col_right:
        st.markdown("### Recommendations")
        if analysis.recommendations:
            for item in analysis.recommendations[:5]:
                st.write(f"- {item}")
        else:
            st.info("No recommendations found.")


def render_analysis_details(record) -> None:
    analysis = record.analysis
    if not analysis:
        st.info("Analysis is not available for this document.")
        return

    st.markdown("### Extracted Fields")
    st.json(analysis.extracted_fields.model_dump())

    st.markdown("### Risk Notes")
    if analysis.risk_notes:
        st.dataframe(
            pd.DataFrame([risk.model_dump() for risk in analysis.risk_notes]),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No risk notes found.")

    st.markdown("### Missing Information")
    if analysis.missing_information:
        for item in analysis.missing_information:
            st.write(f"- {item}")
    else:
        st.info("None found.")


def render_downloads(record, document_id: str) -> None:
    metadata_json = json.dumps(record.model_dump(mode="json"), indent=2)
    st.download_button(
        "Download JSON Result",
        metadata_json,
        f"{document_id}.json",
        width="stretch",
    )
    if record.report_path and Path(record.report_path).exists():
        report = Path(record.report_path).read_text(encoding="utf-8")
        st.download_button(
            "Download Markdown Report",
            report,
            f"{document_id}.md",
            width="stretch",
        )
    else:
        st.info("Markdown report is not available.")


def upload_page(config, store):
    page_header(
        "Intake",
        "Upload",
        "Add a document. The app queues it, processes it in OCI, then sends it to review.",
    )
    st.caption(
        f"GenAI region: {config.genai_region} | Parallel jobs: {config.max_parallel_jobs} | "
        f"Upload limit: {config.max_upload_mb} MB"
    )

    with st.container(border=True):
        document_type = st.selectbox("Document type", [item.value for item in DocumentType])
        business_reference = st.text_input("Reference", placeholder="Optional")
        uploaded = st.file_uploader(
            "File",
            type=["pdf", "png", "jpg", "jpeg"],
            key=f"document_file_{st.session_state.get('upload_widget_version', 0)}",
            help=f"Maximum file size enforced by the app: {config.max_upload_mb} MB.",
        )
        notes = st.text_area("Notes", height=90, placeholder="Optional review context")

        uploaded_ok = uploaded is not None
        if uploaded:
            size_mb = uploaded.size / (1024 * 1024)
            st.caption(f"Selected: {uploaded.name} - {size_mb:.2f} MB")
            if size_mb > config.max_upload_mb:
                st.error(f"File exceeds the configured {config.max_upload_mb} MB limit.")
                uploaded_ok = False
        process_clicked = st.button(
            "Queue Document",
            disabled=not uploaded_ok,
            type="primary",
            width="stretch",
        )

    if process_clicked and uploaded:
        document_id = create_document_id()
        document_type_value = DocumentType(document_type)
        with NamedTemporaryFile(
            delete=False,
            dir=config.local_uploads_dir,
            prefix=f"queued-{document_id}",
            suffix=safe_upload_suffix(uploaded.name),
        ) as tmp:
            tmp.write(uploaded.getbuffer())
            tmp_path = Path(tmp.name)

        record = DocumentRecord(
            document_id=document_id,
            document_name=uploaded.name,
            document_type=document_type_value,
            source_file_size_bytes=uploaded.size,
            source_file_mime_type=uploaded.type or None,
            status=ProcessingStatus.UPLOADED,
            business_reference=business_reference or None,
            notes=notes or None,
        )
        store.save(record)
        submit_document_processing(
            config=config,
            source_path=tmp_path,
            document_id=document_id,
            document_name=uploaded.name,
            document_type=document_type_value,
            business_reference=business_reference or None,
            notes=notes or None,
            source_file_size_bytes=uploaded.size,
            source_file_mime_type=uploaded.type or None,
        )
        st.session_state["selected_document_id"] = record.document_id
        st.session_state["dashboard_selected_document"] = record.document_id
        st.success("Document was queued for background processing.")
        render_queued_actions(record)


def dashboard_page(config, store):
    page_header(
        "Review",
        "Dashboard",
        "Track processing, find documents, and approve or reject completed reviews.",
    )
    records = store.list_records()
    if not records:
        with st.container(border=True):
            st.info("No documents processed yet.")
            if st.button("Upload", type="primary"):
                open_page(PAGE_UPLOAD)
        return

    rows = [record_to_row(record) for record in records]
    df = pd.DataFrame(rows)
    active_runs = df[df["Status"].isin(ACTIVE_STATUSES)]
    ready_count = (df["Action"] == "Approve or reject").sum()
    failed_count = (df["Status"] == "FAILED").sum()
    cols = st.columns(4)
    cols[0].metric("Total", len(records))
    cols[1].metric("Ready", ready_count)
    cols[2].metric("Processing", len(active_runs))
    cols[3].metric("Failed", failed_count)

    failures = df[df["Status"] == "FAILED"]
    if not failures.empty:
        noun = "document is" if len(failures) == 1 else "documents are"
        st.info(f"{len(failures)} failed {noun} available in the Failed view.")
    if not active_runs.empty:
        suffix = "s are" if len(active_runs) != 1 else " is"
        st.info(
            f"{len(active_runs)} document{suffix} processing. Worker pool size: {config.max_parallel_jobs}."
        )
        if st.button("Refresh Status"):
            st.rerun()

    views = ["Ready", "Processing", "Failed", "Reviewed", "All"]
    default_view = "All"
    if ready_count:
        default_view = "Ready"
    elif len(active_runs):
        default_view = "Processing"
    elif failed_count:
        default_view = "Failed"

    control_cols = st.columns([0.7, 1.3])
    view = control_cols[0].selectbox(
        "Show",
        views,
        index=views.index(default_view),
    )
    search = control_cols[1].text_input(
        "Search",
        placeholder="Search documents",
    )

    filtered = filter_queue_rows(df=df, view=view, query=search)

    st.caption(f"Showing {len(filtered)} of {len(df)} documents")
    display_columns = [
        "Name",
        "Stage",
        "Uploaded",
        "Type",
        "Risk Level",
        "Confidence",
        "Action",
    ]
    st.dataframe(
        filtered[display_columns],
        width="stretch",
        hide_index=True,
        column_config={
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "Stage": st.column_config.TextColumn(
                "Stage",
                help=FIELD_HELP["Stage"],
                width="small",
            ),
            "Type": st.column_config.TextColumn(
                "Type",
                help=FIELD_HELP["Document type"],
                width="small",
            ),
            "Risk Level": st.column_config.TextColumn(
                "Risk",
                help=FIELD_HELP["Risk"],
                width="small",
            ),
            "Action": st.column_config.TextColumn(
                "Action",
                help=FIELD_HELP["Action"],
                width="medium",
            ),
            "Confidence": st.column_config.ProgressColumn(
                "Confidence",
                help=FIELD_HELP["Confidence"],
                min_value=0,
                max_value=100,
                format="%d%%",
            ),
        },
    )
    if filtered.empty:
        st.info("No documents in this view.")
        return

    label_by_id = {
        row["Document ID"]: selected_record_label(row)
        for _, row in filtered.iterrows()
    }
    filtered_ids = filtered["Document ID"].tolist()
    previous_selection = st.session_state.get("dashboard_selected_document")
    selected_index = filtered_ids.index(previous_selection) if previous_selection in filtered_ids else 0
    open_cols = st.columns([1.5, 0.5])
    selected = open_cols[0].selectbox(
        "Open document",
        filtered_ids,
        index=selected_index,
        format_func=lambda document_id: label_by_id.get(document_id, document_id),
        key="dashboard_selected_document",
    )
    if open_cols[1].button("Open", type="primary", width="stretch"):
        open_page(PAGE_DETAIL, selected)


def detail_page(config, store):
    page_header(
        "Review",
        "Document",
        "Review the AI result, make a decision, and open supporting details only when needed.",
    )
    records = store.list_records()
    ids = [record.document_id for record in records]
    if not ids:
        with st.container(border=True):
            st.info("No documents processed yet.")
            if st.button("Upload", type="primary"):
                open_page(PAGE_UPLOAD)
        return

    default_id = st.session_state.get("selected_document_id", ids[0])
    index = ids.index(default_id) if default_id in ids else 0
    labels = {
        record.document_id: f"{record.document_name} - {queue_stage(record)} - "
        f"{record.uploaded_at.strftime('%Y-%m-%d %H:%M')}"
        for record in records
    }
    picker_cols = st.columns([1.4, 0.3, 0.3])
    document_id = picker_cols[0].selectbox(
        "Document",
        ids,
        index=index,
        format_func=lambda item: labels.get(item, item),
    )
    if picker_cols[1].button("Dashboard", width="stretch"):
        open_page(PAGE_DASHBOARD)
    if picker_cols[2].button("Upload", width="stretch"):
        open_page(PAGE_UPLOAD)

    record = store.load(document_id)
    st.session_state["selected_document_id"] = document_id

    st.subheader(record.document_name)
    render_status_strip(record)

    review_col, decision_col = st.columns([1.45, 0.85], gap="large")
    with review_col:
        render_analysis_overview(record)
    with decision_col:
        with st.container(border=True):
            st.subheader("Decision")
            render_review_action_panel(store, record, "detail")
            if record.review_comments:
                st.markdown("### Comments")
                st.write(record.review_comments)

    with st.expander("Analysis details"):
        render_analysis_details(record)

    with st.expander("File and processing"):
        render_file_information(record)
        st.markdown("### Lifecycle")
        render_lifecycle(record)
        st.markdown("### Object Storage")
        st.code(record.object_storage_path or "Not uploaded")

    with st.expander("Extracted text"):
        st.text_area(
            "Preview",
            value=record.extracted_text_preview or "No extracted text preview available.",
            height=220,
            disabled=True,
            label_visibility="collapsed",
        )

    with st.expander("Downloads"):
        render_downloads(record, document_id)

    render_field_guide()


def settings_page(config):
    page_header(
        "Operations",
        "Settings",
        "Check runtime configuration and validate OCI service access.",
    )
    config_col, health_col = st.columns([1, 1], gap="large")
    with config_col:
        with st.container(border=True):
            st.subheader("Runtime Configuration")
            st.write(f"OCI region: `{config.oci_region}`")
            st.write(f"GenAI region: `{config.genai_region}`")
            st.write(f"GenAI endpoint: `{config.genai_endpoint}`")
            st.write(f"Compartment: `{config.oci_compartment_id}`")
            st.write(f"Bucket: `{config.oci_bucket_name}`")
            st.write(f"Max parallel jobs: `{config.max_parallel_jobs}`")
            st.write(f"Document AI timeout: `{config.document_ai_timeout_seconds}s`")
            st.info("Run `python scripts/setup.py` to refresh GenAI region availability.")

    with health_col:
        with st.container(border=True):
            st.subheader("OCI Preflight")
            st.write(
                "Run this before processing customer documents. It performs real OCI API "
                "calls with the same runtime credentials used by document processing."
            )
            if st.button("Run OCI Preflight", type="primary", width="stretch"):
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

    st.divider()
    st.caption(f"{CONTACT_TEXT}. {CONTACT_MESSAGE}")


def main():
    config = load_app_config()
    store = MetadataStore(config)
    st.set_page_config(page_title=config.app_title, layout="wide")
    apply_theme()
    stale_count = store.fail_stale_processing(
        config.stale_processing_minutes,
        protected_document_ids=submitted_document_ids(),
    )
    if stale_count:
        st.warning(f"{stale_count} stale processing run was marked as failed.")

    pages = [PAGE_UPLOAD, PAGE_DASHBOARD, PAGE_DETAIL, PAGE_SETTINGS]
    st.sidebar.title(config.app_title)
    st.sidebar.caption("AI document review on OCI")
    current_page = LEGACY_PAGE_NAMES.get(st.session_state.get("page", PAGE_UPLOAD), PAGE_UPLOAD)
    if current_page not in pages:
        current_page = PAGE_UPLOAD
    st.session_state["page"] = current_page
    st.sidebar.markdown("Navigation")
    for nav_page in pages:
        st.sidebar.button(
            nav_page,
            key=f"nav_{nav_page}",
            type="primary" if current_page == nav_page else "secondary",
            width="stretch",
            on_click=set_page,
            args=(nav_page,),
        )
    page = st.session_state["page"]
    st.sidebar.divider()
    st.sidebar.metric("GenAI region", config.genai_region)
    st.sidebar.caption("Deployment is managed from the local laptop.")
    st.sidebar.divider()
    st.sidebar.caption(CONTACT_TEXT)
    st.sidebar.caption(CONTACT_MESSAGE)

    if page == PAGE_UPLOAD:
        upload_page(config, store)
    elif page == PAGE_DASHBOARD:
        dashboard_page(config, store)
    elif page == PAGE_DETAIL:
        detail_page(config, store)
    else:
        settings_page(config)


if __name__ == "__main__":
    main()
