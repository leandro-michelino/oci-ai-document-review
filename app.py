import json
import re
from datetime import date, datetime, time, timezone
from html import escape
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from src.config import get_config
from src.health_checks import run_preflight
from src.job_queue import (
    retry_document_processing,
    submit_document_processing,
    submitted_document_ids,
)
from src.metadata_store import MetadataStore
from src.models import DocumentRecord, DocumentType, ProcessingStatus, WorkflowStatus
from src.compliance import load_compliance_catalog, load_local_compliance_catalog
from src.object_storage_client import ObjectStorageClient
from src.processor import (
    PUBLIC_SECTOR_EXPENSE_RISK,
    apply_compliance_attention,
    create_document_id,
    safe_document_name,
)
from src.report_generator import generate_markdown_report
from src.safety_messages import GENAI_SAFETY_REVIEW_MESSAGE, sanitize_provider_message
from src.text_extraction import (
    DOCUMENT_UNDERSTANDING_SYNC_FILE_SIZE_LIMIT_BYTES,
    DOCUMENT_UNDERSTANDING_SYNC_PAGE_LIMIT,
    pdf_page_count,
)
from src.version import VERSION_LABEL

RISK_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
RISK_LABELS = {
    "NONE": "Risk None",
    "LOW": "Risk Small",
    "MEDIUM": "Risk Medium",
    "HIGH": "Risk High",
}
RISK_SEVERITY_LABELS = {
    "LOW": "Small",
    "MEDIUM": "Medium",
    "HIGH": "High",
}
READY_FOR_DECISION = {"REVIEW_REQUIRED"}
ACTIVE_STATUSES = {"UPLOADED", "PROCESSING", "EXTRACTED", "AI_ANALYZED"}
QUEUE_SECTION_VIEWS = ["Processing", "Ready", "Failed", "Reviewed"]
DASHBOARD_STATUS_FILTERS = [
    "All",
    "Approved",
    "Compliance review",
    "Failed",
    "Fix and retry",
    "Needs decision",
    "Processing",
    "Rejected",
    "Retry planned",
    "Reviewed",
]
MAX_FILES_PER_UPLOAD = 5
ALLOWED_UPLOAD_EXTENSIONS = [
    "csv",
    "htm",
    "html",
    "jpeg",
    "jpg",
    "json",
    "log",
    "md",
    "pdf",
    "png",
    "txt",
    "xml",
    "yaml",
    "yml",
]
OCI_OCR_EXTENSIONS = {"jpeg", "jpg", "png"}
DASHBOARD_REFRESH_SECONDS = 10
CONTACT_TEXT = "Leandro Michelino | ACE | leandro.michelino@oracle.com"
CONTACT_MESSAGE = "In case of any question, get in touch."
PAGE_UPLOAD = "Upload"
PAGE_DASHBOARD = "Dashboard"
PAGE_DETAIL = "Actions"
PAGE_HELP = "How to Use"
PAGE_SETTINGS = "Settings"
PAGE_QUERY_PARAM = "page"
DETAIL_ACTION_PICKER_KEY = "detail_action_item"
PENDING_DETAIL_DOCUMENT_KEY = "pending_detail_document_id"
LEGACY_PAGE_NAMES = {
    "Upload Document": PAGE_UPLOAD,
    "Review Dashboard": PAGE_DASHBOARD,
    "Document Details": PAGE_DETAIL,
    "Document": PAGE_DETAIL,
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
    "Document type": "Review category chosen during upload or detected by GenAI. Reviewers can correct it before approval.",
    "Extension": "File extension from the uploaded file name.",
    "File name": "Original uploaded file name.",
    "File size": "Original upload size captured by the portal for new uploads.",
    "Expense name or reference": "Shared expense name or reference for a multi-file upload batch, used to keep related files together.",
    "MIME type": "Browser-reported file content type captured during upload.",
    "Report": "Whether a Markdown review report exists on the VM.",
    "Review": "Human review decision state: PENDING, APPROVED, or REJECTED.",
    "Risk": (
        "Highest AI or compliance risk-note severity for the document. The value is "
        "based on returned risk notes and supporting evidence, not a final compliance "
        "decision."
    ),
    "Status": "Processing state for the document lifecycle, from upload through approval or failure.",
    "Stage": "Simple queue state: Queued, Processing, Ready, Reviewed, or Failed.",
    "Storage": "Whether the original file has an OCI Object Storage path recorded.",
    "Workflow": "Human workflow state used for assignment, SLA tracking, escalation, and closure.",
    "Assignee": "Person or team responsible for the next review action.",
    "SLA": "Due date for the current review workflow.",
    "Retries": "Number of retry attempts recorded for this document.",
    "Text source": "How text was extracted before GenAI analysis: local text/PDF extraction or OCI Document Understanding OCR.",
    "Text preview": "Number of extracted characters stored for quick inspection in the portal.",
}
FIELD_GUIDE_ROWS = [
    ("Status", FIELD_HELP["Status"]),
    ("Review", FIELD_HELP["Review"]),
    ("Risk", FIELD_HELP["Risk"]),
    ("Confidence", FIELD_HELP["Confidence"]),
    ("Action", FIELD_HELP["Action"]),
    ("Workflow", FIELD_HELP["Workflow"]),
    ("Assignee", FIELD_HELP["Assignee"]),
    ("SLA", FIELD_HELP["SLA"]),
    ("Document type", FIELD_HELP["Document type"]),
    ("File size", FIELD_HELP["File size"]),
    ("Expense name or reference", FIELD_HELP["Expense name or reference"]),
    ("MIME type", FIELD_HELP["MIME type"]),
    ("Report", FIELD_HELP["Report"]),
    ("Text preview", FIELD_HELP["Text preview"]),
    ("Text source", FIELD_HELP["Text source"]),
    ("Storage", FIELD_HELP["Storage"]),
]


def normalize_page(page: str | None) -> str | None:
    if page is None:
        return None
    return LEGACY_PAGE_NAMES.get(page, page)


def query_page() -> str | None:
    try:
        value = st.query_params.get(PAGE_QUERY_PARAM)
    except Exception:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    return normalize_page(value)


def sync_page_query(page: str) -> None:
    try:
        if query_page() != page:
            st.query_params[PAGE_QUERY_PARAM] = page
    except Exception:
        return


def document_type_label(document_type: DocumentType | str) -> str:
    value = (
        document_type.value
        if isinstance(document_type, DocumentType)
        else document_type
    )
    labels = {
        DocumentType.AUTO_DETECT.value: "Auto-detect",
        DocumentType.TECHNICAL_REPORT.value: "Technical report",
    }
    return labels.get(value, value.replace("_", " ").title())


def workflow_status_label(status: WorkflowStatus | str) -> str:
    value = status.value if isinstance(status, WorkflowStatus) else status
    return value.replace("_", " ").title()


def utc_start_of_day(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def review_document_type_options(current: DocumentType) -> list[DocumentType]:
    options = sorted(
        (item for item in DocumentType if item != DocumentType.AUTO_DETECT),
        key=document_type_label,
    )
    if current == DocumentType.AUTO_DETECT:
        return [DocumentType.AUTO_DETECT, *options]
    return options


def upload_document_type_options() -> list[str]:
    options = [
        DocumentType.AUTO_DETECT,
        *review_document_type_options(DocumentType.CONTRACT),
    ]
    return [item.value for item in options]


def workflow_status_options() -> list[WorkflowStatus]:
    return sorted(WorkflowStatus, key=workflow_status_label)


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
            padding-left: clamp(1rem, 2vw, 2rem);
            padding-right: clamp(1rem, 2vw, 2rem);
            max-width: min(96vw, 1480px);
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
        .risk-signal {
            width: 0.85rem;
            height: 0.85rem;
            min-width: 0.85rem;
            padding: 0;
            border-radius: 999px;
            font-size: 0;
            color: transparent;
        }
        .state-good, .risk-low, .risk-none {
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
        .soft-panel {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 1px 2px rgba(38, 34, 29, 0.04);
        }
        .risk-summary {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-left-width: 5px;
            border-radius: 8px;
            padding: 0.95rem 1rem;
            margin: 0.9rem 0 1rem;
            box-shadow: 0 1px 2px rgba(38, 34, 29, 0.04);
        }
        .risk-panel-high {
            border-left-color: #c74634;
            background: #fff8f6;
        }
        .risk-panel-medium {
            border-left-color: #c47a00;
            background: #fffaf0;
        }
        .risk-panel-low,
        .risk-panel-none {
            border-left-color: #4b8f5a;
            background: #f7fbf7;
        }
        .risk-summary-head {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.55rem;
        }
        .risk-summary-title {
            color: var(--text-strong);
            font-size: 0.95rem;
            font-weight: 800;
        }
        .risk-summary-text {
            color: var(--text-soft);
            line-height: 1.45;
            margin: 0.35rem 0 0.65rem;
        }
        .risk-note {
            border-top: 1px solid var(--panel-border);
            padding-top: 0.65rem;
            margin-top: 0.65rem;
        }
        .risk-note-title {
            color: var(--text-strong);
            font-weight: 800;
            line-height: 1.35;
            overflow-wrap: anywhere;
        }
        .risk-evidence {
            color: var(--text-soft);
            font-size: 0.88rem;
            line-height: 1.45;
            margin-top: 0.3rem;
            overflow-wrap: anywhere;
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.65rem;
            margin: 0.4rem 0 0.95rem;
        }
        .dashboard-card {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 0.8rem 0.9rem;
            min-width: 0;
            box-shadow: 0 1px 2px rgba(38, 34, 29, 0.04);
        }
        .dashboard-card strong {
            display: block;
            color: var(--text-strong);
            font-size: 1.45rem;
            line-height: 1.15;
            margin-top: 0.12rem;
        }
        .dashboard-card span {
            color: var(--text-soft);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .dashboard-card p {
            color: var(--text-soft);
            font-size: 0.78rem;
            line-height: 1.35;
            margin: 0.35rem 0 0;
        }
        .dashboard-card.danger {
            border-color: #e4afa8;
            background: #fff7f5;
        }
        .dashboard-card.warning {
            border-color: #edcf91;
            background: #fffaf0;
        }
        .dashboard-card.good {
            border-color: #b7dbc2;
            background: #f5fbf6;
        }
        .dashboard-card.info {
            border-color: #bdd1df;
            background: #f5f9fc;
        }
        .dashboard-workbench {
            display: grid;
            grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
            gap: 0.85rem;
            align-items: stretch;
            margin: 0.45rem 0 0.95rem;
        }
        .dashboard-panel {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 0.95rem;
            min-height: 168px;
            box-shadow: 0 1px 2px rgba(38, 34, 29, 0.04);
        }
        .dashboard-panel h3 {
            font-size: 1.02rem;
            margin: 0 0 0.45rem;
        }
        .dashboard-panel .document-title {
            color: var(--text-strong);
            font-size: 1rem;
            font-weight: 800;
            line-height: 1.35;
            margin: 0.4rem 0 0.25rem;
            overflow-wrap: anywhere;
        }
        .dashboard-panel .panel-note {
            color: var(--text-soft);
            font-size: 0.86rem;
            line-height: 1.45;
            margin: 0.35rem 0 0;
        }
        .queue-card {
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            background: #fffefb;
            padding: 0.55rem 0.6rem;
            margin: 0.45rem 0;
        }
        .expense-group-card {
            border: 1px solid #d5c2b5;
            border-left: 5px solid var(--brand);
            border-radius: 8px;
            background: #fffaf6;
            padding: 0.85rem 0.95rem;
            margin: 0.6rem 0 0.75rem;
            box-shadow: 0 1px 2px rgba(38, 34, 29, 0.04);
        }
        .expense-group-head {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            gap: 0.55rem;
            align-items: flex-start;
            margin-bottom: 0.55rem;
        }
        .expense-group-title {
            color: var(--text-strong);
            font-size: 1rem;
            font-weight: 900;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }
        .expense-group-label {
            color: var(--brand-dark);
            font-size: 0.7rem;
            font-weight: 900;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 0.18rem;
        }
        .expense-file-list {
            color: var(--text-soft);
            font-size: 0.82rem;
            line-height: 1.45;
            overflow-wrap: anywhere;
        }
        .expense-file-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.45rem;
            margin-top: 0.65rem;
        }
        .expense-file-card {
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            background: #ffffff;
            padding: 0.55rem 0.65rem;
            min-width: 0;
        }
        .expense-file-title {
            color: var(--text-strong);
            font-size: 0.9rem;
            font-weight: 800;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }
        .expense-file-meta {
            color: var(--text-soft);
            font-size: 0.78rem;
            line-height: 1.35;
            margin-top: 0.25rem;
        }
        .queue-title {
            color: var(--text-strong);
            font-weight: 800;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }
        .queue-meta, .queue-action {
            color: var(--text-soft);
            font-size: 0.78rem;
            line-height: 1.35;
        }
        .ready-band {
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            background: #fffdf7;
            padding: 0.75rem;
            margin: 0.75rem 0 1rem;
        }
        .ready-card-title {
            color: var(--text-strong);
            font-weight: 800;
            line-height: 1.25;
            min-height: 2.5rem;
            overflow-wrap: anywhere;
        }
        .ready-card-meta {
            color: var(--text-soft);
            font-size: 0.78rem;
            line-height: 1.35;
            min-height: 2.1rem;
            margin: 0.35rem 0;
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
        .howto-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin: 0.65rem 0 1rem;
        }
        .howto-panel {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 1px 2px rgba(38, 34, 29, 0.04);
        }
        .howto-panel h3 {
            font-size: 1.02rem;
            margin: 0 0 0.35rem;
        }
        .howto-panel p {
            color: var(--text-soft);
            line-height: 1.45;
            margin: 0 0 0.8rem;
        }
        .howto-step {
            display: grid;
            grid-template-columns: 1.65rem minmax(0, 1fr);
            gap: 0.55rem;
            align-items: start;
            border-top: 1px solid var(--panel-border);
            padding-top: 0.65rem;
            margin-top: 0.65rem;
        }
        .howto-number {
            align-items: center;
            background: #f6e6dd;
            border: 1px solid #ddb7a7;
            border-radius: 999px;
            color: var(--brand-dark);
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 900;
            height: 1.55rem;
            justify-content: center;
            width: 1.55rem;
        }
        .howto-title {
            color: var(--text-strong);
            font-size: 0.92rem;
            font-weight: 800;
            line-height: 1.3;
            margin-bottom: 0.15rem;
        }
        .howto-copy {
            color: var(--text-soft);
            font-size: 0.86rem;
            line-height: 1.45;
        }
        .howto-status-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.6rem;
            margin: 0.75rem 0 1rem;
        }
        .howto-status {
            background: #fbfaf7;
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 0.75rem;
        }
        .howto-status strong {
            color: var(--text-strong);
            display: block;
            font-size: 0.88rem;
            margin-bottom: 0.25rem;
        }
        .howto-status span {
            color: var(--text-soft);
            display: block;
            font-size: 0.8rem;
            line-height: 1.4;
        }
        @media (max-width: 980px) {
            .dashboard-grid,
            .dashboard-workbench,
            .howto-grid,
            .howto-status-grid {
                grid-template-columns: 1fr;
            }
            .review-snapshot,
            .info-grid,
            .expense-file-grid {
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


def validate_upload_requirements(uploaded, local_path: Path, config) -> tuple[list[str], list[str]]:
    errors = []
    notices = []
    extension = Path(uploaded.name).suffix.lower().lstrip(".")
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        errors.append(
            f"Unsupported file type `.{extension or 'unknown'}`. Allowed types: {allowed}."
        )
    if uploaded.size <= 0:
        errors.append("The selected file is empty.")
    size_mb = uploaded.size / (1024 * 1024)
    if size_mb > config.max_upload_mb:
        errors.append(
            f"File size is {size_mb:.2f} MB, above the configured {config.max_upload_mb} MB limit."
        )
    ocr_limit_mb = DOCUMENT_UNDERSTANDING_SYNC_FILE_SIZE_LIMIT_BYTES / (1024 * 1024)
    if (
        extension in OCI_OCR_EXTENSIONS
        and uploaded.size > DOCUMENT_UNDERSTANDING_SYNC_FILE_SIZE_LIMIT_BYTES
    ):
        errors.append(
            f"Image OCR files must be {ocr_limit_mb:.0f} MB or smaller for the current "
            "OCI Document Understanding synchronous path."
        )
    if extension == "pdf":
        pages = pdf_page_count(local_path, uploaded.name)
        if pages and (
            pages > DOCUMENT_UNDERSTANDING_SYNC_PAGE_LIMIT
            or uploaded.size > DOCUMENT_UNDERSTANDING_SYNC_FILE_SIZE_LIMIT_BYTES
        ):
            notices.append(
                f"This PDF has {pages} pages. Scanned pages will be OCR processed in "
                "OCI chunks automatically when page count or chunk file size exceeds "
                "the synchronous request limit."
            )
        elif pages is None:
            notices.append(
                "The app could not read the PDF page count locally. It will still queue the file, "
                "but encrypted, damaged, or password-protected PDFs can fail during extraction."
            )
        if (
            uploaded.size > DOCUMENT_UNDERSTANDING_SYNC_FILE_SIZE_LIMIT_BYTES
            and pages == 1
        ):
            notices.append(
                f"If this single-page PDF requires OCR, it may exceed the {ocr_limit_mb:.0f} MB "
                "OCI synchronous file-size limit."
            )
    return errors, notices


def validate_upload_batch_requirements(uploaded_files, job_description: str) -> list[str]:
    errors = []
    selected_count = len(uploaded_files or [])
    if selected_count > MAX_FILES_PER_UPLOAD:
        errors.append(f"Select up to {MAX_FILES_PER_UPLOAD} files per upload.")
    if selected_count > 1 and not job_description.strip():
        errors.append(
            "Expense name or reference is required when uploading more than one file."
        )
    return errors


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


def action_tone(action: str) -> str:
    normalized = action.strip().lower()
    if normalized == "approved":
        return "state-good"
    if normalized in {"rejected", "fix and retry"}:
        return "state-bad"
    if normalized in {"retry planned", "compliance review", "approve or reject"}:
        return "state-warn"
    if normalized in {"processing", "wait for processing"}:
        return "state-info"
    return "state-info"


def action_badge(action: str) -> str:
    return badge(action, action_tone(action))


def help_dot(label: str) -> str:
    help_text = FIELD_HELP.get(label)
    if not help_text:
        return ""
    return f'<span class="help-dot" title="{escape(help_text)}">?</span>'


def state_tone(value: str) -> str:
    return STATE_TONE.get(value.upper(), "state-info")


def risk_tone(value: str) -> str:
    return RISK_TONE.get(value.upper(), "risk-none")


def risk_severity_label(value: str) -> str:
    return RISK_SEVERITY_LABELS.get(value.upper(), value.title())


def risk_badge(value: str) -> str:
    if value.upper() == "NONE":
        return (
            '<span class="badge risk-none risk-signal" '
            'title="Risk None" aria-label="Risk None"></span>'
        )
    return badge(RISK_LABELS.get(value.upper(), value), risk_tone(value))


def render_status_strip(record) -> None:
    risk = highest_risk_level(record)
    confidence = confidence_percent(record)
    confidence_label = (
        "Confidence N/A" if confidence is None else f"Confidence {confidence}%"
    )
    chips = [
        badge(record.status.value, state_tone(record.status.value)),
        badge(record.review_status.value, state_tone(record.review_status.value)),
        risk_badge(risk),
        badge(confidence_label, "state-info"),
        badge(next_action(record), state_tone(record.status.value)),
    ]
    st.markdown(
        f'<div class="status-strip">{"".join(chips)}</div>', unsafe_allow_html=True
    )


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
        st.caption(
            "Confidence and risk are AI-assisted signals. The human reviewer owns the final decision."
        )


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


def elapsed_since_label(started_at: datetime) -> str:
    value = started_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    seconds = max(0, int((datetime.now(timezone.utc) - value).total_seconds()))
    if seconds < 60:
        return "less than 1 min"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes:
        return f"{hours} hr {remaining_minutes} min"
    return f"{hours} hr"


def sla_label(record) -> str:
    if not record.due_at:
        return "No SLA"
    if record.workflow_status == WorkflowStatus.CLOSED:
        return "Closed"
    now = datetime.now(timezone.utc)
    due_at = record.due_at
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    if due_at.date() < now.date():
        return "Overdue"
    if due_at.date() == now.date():
        return "Due today"
    return f"Due {due_at.date().isoformat()}"


def local_working_copy_path(config, record) -> Path:
    return config.local_uploads_dir / (
        f"{record.document_id}-{safe_document_name(record.document_name)}"
    )


def normalized_mime_type(record) -> str:
    return (record.source_file_mime_type or "").split(";", 1)[0].strip().lower()


def source_download_mime(record) -> str:
    return normalized_mime_type(record) or "application/octet-stream"


def source_download_name(record) -> str:
    return safe_document_name(record.document_name)


def render_source_document_download(config, record) -> None:
    working_copy = local_working_copy_path(config, record)
    if not working_copy.exists():
        st.info(
            "The source file is not available on this VM. Use the extracted text "
            "and metadata, or upload the source again if a visual review is required."
        )
        return

    st.caption(f"{working_copy.name} | {file_size_label(working_copy.stat().st_size)}")
    st.download_button(
        "Download Doc for Review",
        data=working_copy.read_bytes(),
        file_name=source_download_name(record),
        mime=source_download_mime(record),
        key=f"source_download_{record.document_id}",
        width="stretch",
    )


def render_file_information(record, compact: bool = False) -> None:
    core_info = [
        ("File name", record.document_name),
        ("Document type", document_type_label(record.document_type)),
        ("File size", file_size_label(record.source_file_size_bytes)),
        ("Uploaded", record.uploaded_at.strftime("%Y-%m-%d %H:%M")),
        ("Status", record.status.value),
        ("Workflow", workflow_status_label(record.workflow_status)),
        ("Action", next_action(record)),
    ]
    extra_info = [
        ("Assignee", record.assignee or "Unassigned"),
        ("SLA", sla_label(record)),
        ("Retries", str(record.retry_count)),
        ("Extension", file_extension(record)),
        ("MIME type", record.source_file_mime_type or "Not captured"),
        ("Expense name or reference", record.job_description or "Not provided"),
        ("Business reference", record.business_reference or "Not provided"),
        (
            "Processed",
            (
                record.processed_at.strftime("%Y-%m-%d %H:%M")
                if record.processed_at
                else "Not processed"
            ),
        ),
        ("Document ID", record.document_id),
        ("Report", report_state(record)),
        ("Text preview", extracted_text_label(record)),
        ("Text source", record.extraction_source or "Not extracted"),
        (
            "Storage",
            "Uploaded to OCI" if record.object_storage_path else "Not uploaded",
        ),
    ]
    info = core_info if compact else core_info + extra_info
    items = "\n".join(f"""
        <div class="info-item">
          <div class="info-label">{escape(label)}{help_dot(label)}</div>
          <div class="info-value">{escape(value)}</div>
        </div>
        """ for label, value in info)
    st.markdown(f'<div class="info-grid">{items}</div>', unsafe_allow_html=True)


def highest_risk_level(record) -> str:
    if not record.analysis or not record.analysis.risk_notes:
        return "NONE"
    return max(
        (risk.severity for risk in record.analysis.risk_notes),
        key=lambda severity: RISK_ORDER.get(severity, 0),
    )


def risk_counts(record) -> dict[str, int]:
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    if not record.analysis:
        return counts
    for risk in record.analysis.risk_notes:
        severity = risk.severity.upper()
        if severity in counts:
            counts[severity] += 1
    return counts


def risk_detail_label(record) -> str:
    if not record.analysis:
        return "Risk not analyzed yet."
    if not record.analysis.risk_notes:
        return "No AI risk notes returned."
    counts = risk_counts(record)
    parts = [
        f"{counts[severity]} {risk_severity_label(severity)}"
        for severity in ("HIGH", "MEDIUM", "LOW")
        if counts[severity]
    ]
    note_count = len(record.analysis.risk_notes)
    note_word = "note" if note_count == 1 else "notes"
    return f"{note_count} risk {note_word}: {', '.join(parts)}."


def clean_sentence(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" ;.")
    return f"{cleaned}." if cleaned else cleaned


def parse_key_value_segments(value: str) -> dict[str, str]:
    parsed = {}
    for segment in value.split(";"):
        if ":" not in segment:
            continue
        key, raw_value = segment.split(":", 1)
        parsed[key.strip().lower()] = raw_value.strip()
    return parsed


def compliance_entity_label(entity: str | None, term: str | None) -> str:
    normalized_entity = (entity or "").strip()
    normalized_term = (term or "").strip()
    generic_labels = {
        "government keyword": "government or public-sector reference",
        "public sector keyword": "public-sector reference",
        "ministry keyword": "ministry or department reference",
        "municipality keyword": "municipality or council reference",
        "state-owned entity keyword": "state-owned entity reference",
        "public official keyword": "public official reference",
        "embassy keyword": "embassy reference",
        "security forces keyword": "security-force reference",
    }
    label = generic_labels.get(normalized_entity.lower(), normalized_entity)
    return label or normalized_term or "public-sector reference"


def format_compliance_evidence(evidence: str) -> str | None:
    if "public-sector match:" not in evidence:
        return None

    source = None
    source_match = re.search(
        r"knowledge-base:\s*(.*?)(?:;\s*public-sector match:|$)",
        evidence,
        flags=re.IGNORECASE,
    )
    if source_match:
        source = source_match.group(1).strip(" ;.")

    match_text = evidence.split("public-sector match:", 1)[1]
    expense_cues = None
    expense_match = re.search(
        r";\s*expense cue:\s*(.*?)(?:\.|$)",
        match_text,
        flags=re.IGNORECASE,
    )
    if expense_match:
        expense_cues = expense_match.group(1).strip(" ;.")
        match_text = match_text[: expense_match.start()]

    matches = []
    for raw_match in match_text.split("|"):
        fields = parse_key_value_segments(raw_match)
        entity = fields.get("entity")
        term = fields.get("matched term")
        country = fields.get("country")
        if not entity and not term:
            continue
        qualifiers = []
        if country and country.lower() != "global":
            qualifiers.append(country)
        detail = compliance_entity_label(entity, term)
        if qualifiers:
            detail = f"{detail} ({', '.join(qualifiers)})"
        matches.append(detail)

    summary_parts = []
    if matches:
        summary_parts.append(
            "Compliance knowledge base matched public-sector context: "
            + "; ".join(dict.fromkeys(matches[:3]))
            + "."
        )
    if expense_cues:
        summary_parts.append(f"Expense cues found: {expense_cues}.")
    if source:
        summary_parts.append("Review before approval.")
    if summary_parts:
        return " ".join(summary_parts)
    return None


def format_risk_evidence(risk) -> str:
    if not risk.evidence:
        return "No supporting evidence returned by the analysis."
    compliance_summary = format_compliance_evidence(risk.evidence)
    if compliance_summary:
        return compliance_summary
    return clean_sentence(risk.evidence)


def risk_notes_by_priority(record):
    if not record.analysis:
        return []
    return sorted(
        record.analysis.risk_notes,
        key=lambda risk: RISK_ORDER.get(risk.severity.upper(), 0),
        reverse=True,
    )


def highest_risk_evidence(record) -> str | None:
    for risk in risk_notes_by_priority(record):
        return format_risk_evidence(risk)
    return None


def render_risk_review_panel(record) -> None:
    risk_level = highest_risk_level(record)
    notes = risk_notes_by_priority(record)
    if not notes:
        return

    panel_tone = risk_level.lower()
    note_html = []
    for risk in notes[:3]:
        note_html.append(
            '<div class="risk-note">'
            f'<div class="status-strip">{risk_badge(risk.severity)}</div>'
            f'<div class="risk-note-title">{escape(risk.risk)}</div>'
            f'<div class="risk-evidence">{escape(format_risk_evidence(risk))}</div>'
            "</div>"
        )
    extra_count = len(notes) - len(note_html)
    extra_html = (
        f'<p class="risk-summary-text">{extra_count} additional risk note'
        f'{"s" if extra_count != 1 else ""} available in the Risk Notes table.</p>'
        if extra_count > 0
        else ""
    )
    panel_html = (
        f'<div class="risk-summary risk-panel-{panel_tone}">'
        '<div class="risk-summary-head">'
        '<div class="risk-summary-title">Risk review</div>'
        f"{risk_badge(risk_level)}"
        "</div>"
        f'<p class="risk-summary-text">{escape(risk_detail_label(record))}</p>'
            f'{"".join(note_html)}'
            f"{extra_html}"
            "</div>"
    )
    st.markdown(panel_html, unsafe_allow_html=True)


def has_compliance_risk(record) -> bool:
    if not record.analysis:
        return False
    return any(
        risk.risk == PUBLIC_SECTOR_EXPENSE_RISK for risk in record.analysis.risk_notes
    )


def confidence_percent(record) -> int | None:
    if not record.analysis:
        return None
    return round(record.analysis.confidence_score * 100)


def requires_human_action(record) -> bool:
    return (
        record.status.value in READY_FOR_DECISION
        and record.review_status.value == "PENDING"
    )


def next_action(record) -> str:
    if record.workflow_status == WorkflowStatus.ESCALATED:
        return "Escalated review"
    if record.workflow_status == WorkflowStatus.WAITING_FOR_INFO:
        return "Waiting for info"
    if record.workflow_status == WorkflowStatus.RETRY_PLANNED:
        return "Retry planned"
    if record.status.value == "FAILED":
        return "Fix and retry"
    if requires_human_action(record) and has_compliance_risk(record):
        return "Compliance review"
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


def action_priority(record) -> int:
    if record.workflow_status == WorkflowStatus.ESCALATED:
        return 0
    if requires_human_action(record) and has_compliance_risk(record):
        return 1
    if requires_human_action(record):
        return 2
    if record.status.value == "FAILED":
        return 3
    if record.status.value in ACTIVE_STATUSES:
        return 4
    if record.review_status.value in {"APPROVED", "REJECTED"}:
        return 6
    return 5


def is_actionable_record(record) -> bool:
    return (
        requires_human_action(record)
        or record.status.value == "FAILED"
        or record.workflow_status == WorkflowStatus.ESCALATED
    )


def sort_action_records(records: list[DocumentRecord]) -> list[DocumentRecord]:
    return sorted(
        records,
        key=lambda record: (
            action_priority(record),
            (record.job_description or "").lower(),
            -record.uploaded_at.timestamp(),
        ),
    )


def expense_reference_groups(
    records: list[DocumentRecord],
) -> list[tuple[str, list[DocumentRecord]]]:
    grouped: dict[str, list[DocumentRecord]] = {}
    for record in records:
        reference = (record.job_description or "").strip()
        if reference:
            grouped.setdefault(reference, []).append(record)
    groups = [
        (reference, sort_action_records(items))
        for reference, items in grouped.items()
        if len(items) > 1
    ]
    return sorted(
        groups,
        key=lambda item: max(record.uploaded_at for record in item[1]),
        reverse=True,
    )


def next_action_document_id(
    records: list[DocumentRecord], current_document_id: str
) -> str | None:
    for record in sort_action_records(records):
        if record.document_id != current_document_id and is_actionable_record(record):
            return record.document_id
    return None


def reviewer_action_count(records: list[DocumentRecord]) -> int:
    return sum(1 for record in records if is_actionable_record(record))


def processing_stage_rows(record) -> list[dict[str, str]]:
    has_extraction = bool(record.extracted_text_preview)
    has_report = bool(record.report_path and Path(record.report_path).exists())
    extraction_source = record.extraction_source or "Extraction source not recorded"
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
            "Stage": "Extraction",
            "State": "Complete" if has_extraction else "Not complete",
            "Evidence": (
                f"{extraction_source}; text preview saved"
                if has_extraction
                else "No extracted text"
            ),
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
        {
            "Stage": "Workflow",
            "State": workflow_status_label(record.workflow_status),
            "Evidence": (
                f"{record.assignee or 'Unassigned'}; {sla_label(record)}; "
                f"{record.retry_count} retr{'y' if record.retry_count == 1 else 'ies'}"
            ),
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
        st.error(display_error_message(record.error_message))


def record_summary(record) -> str:
    if record.analysis:
        return record.analysis.executive_summary
    if record.error_message:
        return display_error_message(record.error_message)
    if record.extracted_text_preview:
        return record.extracted_text_preview
    return "No analysis available yet."


def display_error_message(message: str | None) -> str:
    if not message:
        return "Processing failed before completion."
    return sanitize_provider_message(message) or GENAI_SAFETY_REVIEW_MESSAGE


def fail_stale_processing_runs(config, store) -> int:
    return store.fail_stale_processing(
        config.stale_processing_minutes,
        protected_document_ids=submitted_document_ids(),
    )


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
        record.workflow_status.value,
        record.assignee or "",
        sla_label(record),
        str(record.retry_count),
        record.job_description or "",
        record.business_reference or "",
        elapsed_since_label(record.uploaded_at),
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
        "Workflow": workflow_status_label(record.workflow_status),
        "Assignee": record.assignee or "Unassigned",
        "SLA": sla_label(record),
        "Retries": record.retry_count,
        "Uploaded": record.uploaded_at.strftime("%Y-%m-%d %H:%M"),
        "Uploaded Sort": record.uploaded_at.isoformat(),
        "Elapsed": elapsed_since_label(record.uploaded_at),
        "Expense Name or Reference": record.job_description or "",
        "Reference": record.business_reference or "",
        "Risk Level": highest_risk_level(record),
        "Risks": len(analysis.risk_notes) if analysis else 0,
        "Risk Detail": risk_detail_label(record),
        "Confidence": confidence_percent(record),
        "Action": action,
        "Summary": summary,
        "Search Text": " ".join(search_parts).lower(),
    }


def filter_dashboard_status(
    df: pd.DataFrame, status_filter: str = "All"
) -> pd.DataFrame:
    if status_filter == "Needs decision":
        return df[df["Stage"] == "Ready"]
    if status_filter == "Compliance review":
        return df[df["Action"] == "Compliance review"]
    if status_filter == "Fix and retry":
        return df[df["Action"] == "Fix and retry"]
    if status_filter == "Retry planned":
        return df[df["Action"] == "Retry planned"]
    if status_filter == "Processing":
        return df[df["Status"].isin(ACTIVE_STATUSES)]
    if status_filter == "Failed":
        return df[df["Status"] == "FAILED"]
    if status_filter == "Approved":
        return df[df["Review"] == "APPROVED"]
    if status_filter == "Rejected":
        return df[df["Review"] == "REJECTED"]
    if status_filter == "Reviewed":
        return df[df["Review"].isin(["APPROVED", "REJECTED"])]
    return df


def filter_queue_rows(
    df: pd.DataFrame, view: str, query: str, status_filter: str = "All"
) -> pd.DataFrame:
    filtered = df.copy()
    filtered = filter_dashboard_status(filtered, status_filter)
    if view == "Ready":
        filtered = filtered[filtered["Stage"] == "Ready"]
    elif view == "Processing":
        filtered = filtered[filtered["Status"].isin(ACTIVE_STATUSES)]
    elif view == "Failed":
        filtered = filtered[filtered["Status"] == "FAILED"]
    elif view == "Reviewed":
        filtered = filtered[filtered["Review"].isin(["APPROVED", "REJECTED"])]

    terms = [term for term in query.lower().split() if term]
    for term in terms:
        filtered = filtered[
            filtered["Search Text"].str.contains(term, regex=False, na=False)
        ]
    return filtered.sort_values("Uploaded Sort", ascending=False)


def queue_view_frames(
    df: pd.DataFrame, query: str, status_filter: str = "All"
) -> dict[str, pd.DataFrame]:
    return {
        view: filter_queue_rows(
            df=df,
            view=view,
            query=query,
            status_filter=status_filter,
        )
        for view in QUEUE_SECTION_VIEWS
    }


def queue_section_hint(view: str, count: int) -> str:
    noun = "document" if count == 1 else "documents"
    hints = {
        "Processing": "being handled by the worker pool",
        "Ready": "waiting for reviewer action",
        "Failed": "needing upload or service follow-up",
        "Reviewed": "already approved or rejected",
    }
    return f"{count} {noun} {hints.get(view, '').strip()}".strip()


def expense_row_groups(rows: pd.DataFrame) -> list[tuple[str | None, pd.DataFrame]]:
    if rows.empty:
        return []
    grouped_rows = []
    with_reference = rows[rows["Expense Name or Reference"].astype(bool)]
    for reference, group in with_reference.groupby(
        "Expense Name or Reference", sort=False
    ):
        grouped_rows.append((str(reference), group))
    without_reference = rows[~rows["Expense Name or Reference"].astype(bool)]
    for _, row in without_reference.iterrows():
        grouped_rows.append((None, pd.DataFrame([row])))
    return sorted(
        grouped_rows,
        key=lambda item: item[1]["Uploaded Sort"].max(),
        reverse=True,
    )


def expense_group_stage_summary(records: list[DocumentRecord]) -> str:
    stages = {}
    for record in records:
        stage = queue_stage(record)
        stages[stage] = stages.get(stage, 0) + 1
    return ", ".join(f"{count} {stage}" for stage, count in sorted(stages.items()))


def expense_group_badges_html(records: list[DocumentRecord]) -> str:
    stage_tones = {
        "Failed": "state-bad",
        "Processing": "state-info",
        "Queued": "state-info",
        "Ready": "state-warn",
        "Reviewed": "state-good",
    }
    stages = {}
    for record in records:
        stage = queue_stage(record)
        stages[stage] = stages.get(stage, 0) + 1
    badges = [
        badge(f"{count} {stage}", stage_tones.get(stage, "state-info"))
        for stage, count in sorted(stages.items())
    ]
    return f'<div class="status-strip">{"".join(badges)}</div>'


def expense_group_file_list(records: list[DocumentRecord], limit: int = 4) -> str:
    names = [record.document_name for record in records[:limit]]
    if len(records) > limit:
        names.append(f"+{len(records) - limit} more")
    return ", ".join(names)


def expense_row_stage_summary(rows: pd.DataFrame) -> str:
    stages = {}
    for stage in rows["Stage"].tolist():
        stages[stage] = stages.get(stage, 0) + 1
    return ", ".join(f"{count} {stage}" for stage, count in sorted(stages.items()))


def expense_row_group_target(rows: pd.DataFrame) -> pd.Series:
    action_priority = {
        "Compliance review": 0,
        "Approve or reject": 1,
        "Fix and retry": 2,
        "Retry planned": 3,
    }
    stage_priority = {
        "Ready": 0,
        "Failed": 1,
        "Processing": 2,
        "Queued": 3,
        "Reviewed": 4,
    }

    def priority(row: pd.Series) -> tuple[int, int]:
        return (
            action_priority.get(str(row["Action"]), 9),
            stage_priority.get(str(row["Stage"]), 9),
        )

    return min((row for _, row in rows.iterrows()), key=priority)


def expense_row_group_header(reference: str, rows: pd.DataFrame) -> str:
    file_word = "file" if len(rows) == 1 else "files"
    return f"""
    <div class="expense-group-card">
      <div class="expense-group-head">
        <div>
          <div class="expense-group-label">Expense name or reference</div>
          <div class="expense-group-title">{escape(reference)}</div>
        </div>
        <span class="badge state-info">{len(rows)} {file_word}</span>
      </div>
      <div class="expense-file-list">
        {escape(expense_row_stage_summary(rows))}. Expand the file list only when you need the details.
      </div>
    </div>
    """


def render_compact_expense_row_group(
    view: str, reference: str, group_rows: pd.DataFrame, key_prefix: str
) -> None:
    target = expense_row_group_target(group_rows)
    target_document_id = target["Document ID"]
    with st.container(border=True):
        st.markdown(
            expense_row_group_header(reference, group_rows),
            unsafe_allow_html=True,
        )
        action_cols = st.columns([0.34, 1.66], vertical_alignment="center")
        if action_cols[0].button(
            "Review",
            type="primary" if view == "Ready" else "secondary",
            key=f"{key_prefix}_review_group_{view}_{target_document_id}",
            help=f"Review {reference} in Actions",
            width="stretch",
        ):
            open_page_from_dashboard(PAGE_DETAIL, target_document_id)
        action_cols[1].caption(
            f"Starts with {target['Name']}. {expense_row_stage_summary(group_rows)}."
        )

        with st.expander("Show files", expanded=False):
            for _, row in group_rows.iterrows():
                details = [f"{row['Uploaded']} | {row['Type']}"]
                if row["Status"] in ACTIVE_STATUSES:
                    details.append(f"Working for {row['Elapsed']}")
                if row["Reference"]:
                    details.append(f"Ref: {row['Reference']}")
                if row["Assignee"] != "Unassigned":
                    details.append(f"Owner: {row['Assignee']}")
                st.markdown(
                    f"""
                    <div class="expense-file-card">
                      <div class="expense-file-title">{escape(row["Name"])}</div>
                      <div class="expense-file-meta">{escape(" | ".join(details))}</div>
                      <div class="status-strip">
                        {badge(row["Stage"], state_tone(row["Status"]))}
                        {action_badge(row["Action"])}
                        {risk_badge(row["Risk Level"])}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def dashboard_focus_record(records: list[DocumentRecord]) -> DocumentRecord | None:
    return next(
        (
            record
            for record in sort_action_records(records)
            if is_actionable_record(record)
        ),
        None,
    )


def dashboard_metrics_html(
    metric_cards: list[tuple[str, int, str, str]],
) -> str:
    cards = "".join(
        (
            f'<div class="dashboard-card {escape(tone, quote=True)}">'
            f"<span>{escape(label)}</span>"
            f"<strong>{escape(str(value))}</strong>"
            f"<p>{escape(detail)}</p>"
            "</div>"
        )
        for label, value, detail, tone in metric_cards
    )
    return f'<div class="dashboard-grid">{cards}</div>'


def render_dashboard_metrics(df: pd.DataFrame, active_runs: pd.DataFrame) -> None:
    total = len(df)
    ready_count = int((df["Stage"] == "Ready").sum())
    compliance_count = int((df["Action"] == "Compliance review").sum())
    failed_count = int((df["Status"] == "FAILED").sum())
    reviewed_count = int(df["Review"].isin(["APPROVED", "REJECTED"]).sum())
    active_count = len(active_runs)
    metric_cards = [
        (
            "Needs action",
            ready_count,
            "Ready for a reviewer decision",
            "warning" if ready_count else "good",
        ),
        (
            "Compliance",
            compliance_count,
            "Knowledge-base matches",
            "danger" if compliance_count else "good",
        ),
        (
            "Processing",
            active_count,
            "Currently in the worker pool",
            "info" if active_count else "good",
        ),
        (
            "Failed",
            failed_count,
            "Needs retry or service follow-up",
            "danger" if failed_count else "good",
        ),
        (
            "Total",
            total,
            f"{reviewed_count} already reviewed",
            "info",
        ),
    ]
    st.markdown(dashboard_metrics_html(metric_cards), unsafe_allow_html=True)


def render_dashboard_focus(config, records: list[DocumentRecord]) -> None:
    focus = dashboard_focus_record(records)
    active_count = sum(
        1 for record in records if record.status.value in ACTIVE_STATUSES
    )
    reviewed_count = sum(
        1
        for record in records
        if record.review_status.value in {"APPROVED", "REJECTED"}
    )

    with st.container():
        if focus:
            risk = highest_risk_level(focus)
            evidence = highest_risk_evidence(focus)
            confidence = confidence_percent(focus)
            confidence_label = (
                "Confidence N/A" if confidence is None else f"Confidence {confidence}%"
            )
            context = [
                f"{workflow_status_label(focus.workflow_status)} workflow",
                sla_label(focus),
            ]
            if focus.job_description:
                context.append(f"Expense: {focus.job_description}")
            if focus.assignee:
                context.append(f"Owner: {focus.assignee}")
            panel_html = f"""
            <div class="dashboard-workbench">
              <div class="dashboard-panel">
                <div class="muted-label">Priority work</div>
                <h3>{escape(next_action(focus))}</h3>
                <div class="document-title">{escape(focus.document_name)}</div>
                <div class="status-strip">
                  {badge(focus.status.value, state_tone(focus.status.value))}
                  {risk_badge(risk)}
                  {badge(confidence_label, "state-info")}
                </div>
                <p class="panel-note">{escape(" | ".join(context))}</p>
                <p class="panel-note">{escape(evidence or record_summary(focus))}</p>
              </div>
              <div class="dashboard-panel">
                <div class="muted-label">Queue health</div>
                <h3>{active_count} processing | {reviewed_count} reviewed</h3>
                <p class="panel-note">The worker pool can run {config.max_parallel_jobs} document{'s' if config.max_parallel_jobs != 1 else ''} at a time.</p>
                <p class="panel-note">Ready and compliance items are prioritized before failed, active, and reviewed work.</p>
              </div>
            </div>
            """
            st.markdown(panel_html, unsafe_allow_html=True)
            cols = st.columns([0.45, 0.35, 1.2])
            if cols[0].button(
                "Review",
                type="primary",
                key=f"dashboard_focus_open_{focus.document_id}",
                width="stretch",
            ):
                open_page_from_dashboard(PAGE_DETAIL, focus.document_id)
            if cols[1].button(
                "Upload",
                key="dashboard_focus_upload",
                width="stretch",
            ):
                open_page_from_dashboard(PAGE_UPLOAD)
            return

        if active_count:
            st.markdown(
                f"""
                <div class="dashboard-workbench">
                  <div class="dashboard-panel">
                    <div class="muted-label">Queue status</div>
                    <h3>{active_count} file{'s are' if active_count != 1 else ' is'} processing</h3>
                    <p class="panel-note">The worker pool can run {config.max_parallel_jobs} at a time.</p>
                  </div>
                  <div class="dashboard-panel">
                    <div class="muted-label">Reviewed</div>
                    <h3>{reviewed_count} complete</h3>
                    <p class="panel-note">Refresh the status if a processing file looks stale.</p>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Refresh Status", key="dashboard_focus_refresh"):
                rerun_dashboard_fragment()
            return

        st.markdown(
            f"""
            <div class="dashboard-workbench">
              <div class="dashboard-panel">
                <div class="muted-label">Queue status</div>
                <h3>No files need action</h3>
                <p class="panel-note">{reviewed_count} file{'s have' if reviewed_count != 1 else ' has'} already been reviewed.</p>
              </div>
              <div class="dashboard-panel">
                <div class="muted-label">Next step</div>
                <h3>Upload files</h3>
                <p class="panel-note">New uploads will appear here as processing, ready, failed, or reviewed.</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Upload",
            type="primary",
            key="dashboard_focus_upload_clear",
        ):
            open_page_from_dashboard(PAGE_UPLOAD)


def render_expense_groups_overview(records: list[DocumentRecord]) -> None:
    groups = expense_reference_groups(records)
    if not groups:
        return
    st.markdown("### Expense groups")
    for reference, group_records in groups[:6]:
        target = next(
            (record for record in group_records if is_actionable_record(record)),
            group_records[0],
        )
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="expense-group-card">
                  <div class="expense-group-head">
                    <div>
                      <div class="expense-group-label">Expense name or reference</div>
                      <div class="expense-group-title">{escape(reference)}</div>
                    </div>
                    <span class="badge state-info">{len(group_records)} files</span>
                  </div>
                  {expense_group_badges_html(group_records)}
                  <div class="expense-file-list">
                    {escape(expense_group_file_list(group_records))}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            cols = st.columns([0.35, 1.65], vertical_alignment="center")
            if cols[0].button(
                "Review",
                type="primary",
                key=f"expense_group_open_{target.document_id}",
                width="stretch",
            ):
                open_page_from_dashboard(PAGE_DETAIL, target.document_id)
            cols[1].caption(
                f"Review starts with {target.document_name}; "
                f"{expense_group_stage_summary(group_records)}."
            )


def render_queue_section(view: str, rows: pd.DataFrame) -> None:
    st.markdown(f"### {view}")
    st.caption(queue_section_hint(view, len(rows)))
    if rows.empty:
        empty_messages = {
            "Processing": "No documents are currently processing.",
            "Ready": "No documents are waiting for a decision.",
            "Failed": "No failed documents need follow-up.",
            "Reviewed": "No approved or rejected documents yet.",
        }
        st.info(empty_messages.get(view, f"No {view.lower()} documents."))
        return

    for reference, group_rows in expense_row_groups(rows):
        if reference and len(group_rows) > 1:
            render_compact_expense_row_group(
                view=view,
                reference=reference,
                group_rows=group_rows,
                key_prefix="queue",
            )
            continue
        if reference:
            st.markdown(
                expense_row_group_header(reference, group_rows),
                unsafe_allow_html=True,
            )
        for _, row in group_rows.iterrows():
            with st.container(border=True):
                row_cols = st.columns(
                    [0.22, 1.65, 0.72, 0.92], vertical_alignment="center"
                )
                document_id = row["Document ID"]
                if row_cols[0].button(
                    "↗",
                    key=f"queue_open_{view}_{document_id}",
                    help=f"Open {row['Name']} in Actions",
                    width="content",
                ):
                    open_page_from_dashboard(PAGE_DETAIL, document_id)
                details = [f"{row['Uploaded']} · {row['Type']}"]
                if row["Status"] in ACTIVE_STATUSES:
                    details.append(f"Working for {row['Elapsed']}")
                if row["Reference"]:
                    details.append(f"Ref: {row['Reference']}")
                if row["Assignee"] != "Unassigned":
                    details.append(f"Owner: {row['Assignee']}")
                row_cols[1].markdown(
                    f"""
                    <div class="queue-title">{escape(row["Name"])}</div>
                    <div class="queue-meta">{escape(" | ".join(details))}</div>
                    """,
                    unsafe_allow_html=True,
                )
                row_cols[2].markdown(
                    risk_badge(row["Risk Level"]), unsafe_allow_html=True
                )
                confidence = row["Confidence"]
                confidence_text = (
                    "N/A" if pd.isna(confidence) else f"{int(confidence)}%"
                )
                row_cols[2].caption(f"{confidence_text} confidence")
                row_cols[3].markdown(
                    f"""
                    <div class="queue-title">{action_badge(row["Action"])}</div>
                    <div class="queue-action">{escape(row["Workflow"])} | {escape(row["SLA"])}</div>
                    """,
                    unsafe_allow_html=True,
                )
                if row["Risk Level"] != "NONE":
                    st.caption(row["Risk Detail"])


def render_ready_queue_band(rows: pd.DataFrame) -> None:
    st.markdown("### Ready")
    st.caption(queue_section_hint("Ready", len(rows)))
    if rows.empty:
        st.info("No documents are waiting for a decision.")
        return

    with st.container(border=True):
        for reference, group_rows in expense_row_groups(rows):
            if reference and len(group_rows) > 1:
                render_compact_expense_row_group(
                    view="Ready",
                    reference=reference,
                    group_rows=group_rows,
                    key_prefix="ready",
                )
                continue
            if reference:
                st.markdown(
                    expense_row_group_header(reference, group_rows),
                    unsafe_allow_html=True,
                )
            row_items = list(group_rows.iterrows())
            for start in range(0, len(row_items), 3):
                cols = st.columns(3, gap="medium")
                for col, (_, row) in zip(cols, row_items[start : start + 3]):
                    document_id = row["Document ID"]
                    details = [f"{row['Uploaded']} | {row['Type']}"]
                    if row["Status"] in ACTIVE_STATUSES:
                        details.append(f"Working for {row['Elapsed']}")
                    if row["Reference"]:
                        details.append(f"Ref: {row['Reference']}")
                    confidence = row["Confidence"]
                    confidence_text = (
                        "N/A" if pd.isna(confidence) else f"{int(confidence)}%"
                    )
                    with col.container(border=True):
                        st.markdown(
                            f"""
                            <div class="ready-card-title">{escape(row["Name"])}</div>
                            <div class="ready-card-meta">{escape(" | ".join(details))}</div>
                            <div class="status-strip">
                              {risk_badge(row["Risk Level"])}
                              {badge(f"Confidence {confidence_text}", "state-info")}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if row["Risk Level"] != "NONE":
                            st.caption(row["Risk Detail"])
                        action_cols = st.columns([0.44, 0.56])
                        if action_cols[0].button(
                            "Review",
                            type="primary",
                            key=f"ready_open_{document_id}",
                            help=f"Open {row['Name']} in Actions",
                            width="stretch",
                        ):
                            open_page_from_dashboard(PAGE_DETAIL, document_id)
                        action_cols[1].caption(f"{row['Action']} | {row['SLA']}")


def rerun_dashboard_fragment() -> None:
    st.rerun(scope="fragment")


def open_page_from_dashboard(page: str, document_id: str | None = None) -> None:
    open_page(page, document_id)
    st.rerun()


def render_dashboard_refresh_note(active_count: int) -> None:
    if active_count <= 0:
        return
    st.caption(
        "Refreshing Dashboard components every "
        f"{DASHBOARD_REFRESH_SECONDS} seconds while documents are processing."
    )


def render_expense_reference_panel(
    records: list[DocumentRecord], current: DocumentRecord
) -> None:
    reference = (current.job_description or "").strip()
    if not reference:
        return
    related = sort_action_records(
        [
            record
            for record in records
            if (record.job_description or "").strip() == reference
        ]
    )
    if len(related) <= 1:
        return
    with st.container(border=True):
        st.markdown(
            f"""
            <div class="expense-group-card">
              <div class="expense-group-head">
                <div>
                  <div class="expense-group-label">Expense name or reference</div>
                  <div class="expense-group-title">{escape(reference)}</div>
                </div>
                <span class="badge state-info">{len(related)} linked files</span>
              </div>
              {expense_group_badges_html(related)}
              <div class="expense-file-list">
                Review these files together; decisions can still be made per document.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for record in related:
            cols = st.columns([1.2, 0.42, 0.45, 0.32], vertical_alignment="center")
            cols[0].markdown(
                f"""
                <div class="expense-file-card">
                  <div class="expense-file-title">{escape(record.document_name)}</div>
                  <div class="expense-file-meta">
                    {escape(record.uploaded_at.strftime("%Y-%m-%d %H:%M"))}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            cols[1].markdown(badge(queue_stage(record), state_tone(record.status.value)), unsafe_allow_html=True)
            cols[2].caption(next_action(record))
            if record.document_id == current.document_id:
                cols[3].caption("Current")
            elif cols[3].button(
                "Open",
                key=f"expense_related_open_{current.document_id}_{record.document_id}",
                width="stretch",
            ):
                open_page(PAGE_DETAIL, record.document_id)
                st.rerun()


def open_page(page: str, document_id: str | None = None) -> None:
    page = normalize_page(page) or PAGE_UPLOAD
    if document_id:
        st.session_state["selected_document_id"] = document_id
        if page == PAGE_DASHBOARD:
            st.session_state["dashboard_selected_document"] = document_id
        if page == PAGE_DETAIL:
            st.session_state[PENDING_DETAIL_DOCUMENT_KEY] = document_id
    st.session_state["page"] = page
    st.session_state["requested_page"] = page
    st.session_state["action_navigation"] = True
    sync_page_query(page)


def open_fresh_upload() -> None:
    st.session_state["upload_widget_version"] = (
        st.session_state.get("upload_widget_version", 0) + 1
    )
    open_page(PAGE_UPLOAD)


def render_queued_actions(record) -> None:
    with st.container(border=True):
        st.subheader("Queued")
        render_status_strip(record)
        st.write(
            "The file is in the background queue. You can follow it from the dashboard."
        )
        cols = st.columns([1, 1, 1])
        cols[0].button(
            "View Dashboard",
            type="primary",
            key=f"queued_dashboard_{record.document_id}",
            on_click=open_page,
            args=(PAGE_DASHBOARD, record.document_id),
        )
        cols[1].button(
            "Open Actions",
            key=f"queued_open_{record.document_id}",
            on_click=open_page,
            args=(PAGE_DETAIL, record.document_id),
        )
        cols[2].button(
            "Upload Another",
            key=f"queued_upload_another_{record.document_id}",
            on_click=open_fresh_upload,
        )


def render_batch_queued_actions(records: list[DocumentRecord]) -> None:
    first_record = records[0]
    with st.container(border=True):
        st.subheader("Queued")
        st.write(
            f"{len(records)} files are in the background queue. You can follow the job from the dashboard."
        )
        if first_record.job_description:
            st.caption(f"Expense: {first_record.job_description}")
        st.write(", ".join(record.document_name for record in records))
        cols = st.columns([1, 1, 1])
        cols[0].button(
            "View Dashboard",
            type="primary",
            key=f"queued_batch_dashboard_{first_record.document_id}",
            on_click=open_page,
            args=(PAGE_DASHBOARD, first_record.document_id),
        )
        cols[1].button(
            "Open Actions",
            key=f"queued_batch_open_{first_record.document_id}",
            on_click=open_page,
            args=(PAGE_DETAIL, first_record.document_id),
        )
        cols[2].button(
            "Upload Another",
            key=f"queued_batch_upload_another_{first_record.document_id}",
            on_click=open_fresh_upload,
        )


def refresh_markdown_report(config, record) -> None:
    if not record.analysis or not record.report_path:
        return
    Path(record.report_path).write_text(
        generate_markdown_report(record, config.genai_model_id),
        encoding="utf-8",
    )


def compliance_catalog_for_app(config):
    try:
        return load_compliance_catalog(
            config, object_storage=ObjectStorageClient(config)
        )
    except Exception:
        return load_local_compliance_catalog()


def backfill_compliance_attention(config, store, catalog=None) -> int:
    records = [record for record in store.list_records() if record.analysis]
    if not records:
        return 0
    catalog = catalog or compliance_catalog_for_app(config)
    updated_count = 0
    for record in records:
        before = record.model_dump_json()
        apply_compliance_attention(
            record, record.extracted_text_preview or "", catalog=catalog
        )
        if record.model_dump_json() == before:
            continue
        store.save(record)
        refresh_markdown_report(config, record)
        updated_count += 1
    return updated_count


def run_compliance_backfill_once(config, store) -> int:
    if st.session_state.get("compliance_backfill_checked"):
        return 0
    updated_count = backfill_compliance_attention(config, store)
    st.session_state["compliance_backfill_checked"] = True
    return updated_count


def apply_review_action(
    config, store, document_id: str, approved: bool, comments: str | None
) -> bool:
    if not approved and not (comments or "").strip():
        st.error("Add review comments before rejecting.")
        return False
    updated = store.set_review(
        document_id, approved=approved, comments=comments or None
    )
    refresh_markdown_report(config, updated)
    next_document_id = next_action_document_id(store.list_records(), document_id)
    if next_document_id:
        st.session_state["selected_document_id"] = next_document_id
        st.session_state["dashboard_selected_document"] = next_document_id
        st.session_state[PENDING_DETAIL_DOCUMENT_KEY] = next_document_id
        decision = "Approved" if approved else "Rejected"
        st.success(f"{decision}. Opening the next action item.")
    else:
        st.session_state["selected_document_id"] = document_id
        st.success("Approved" if approved else "Rejected")
    return True


def render_document_type_editor(config, store, record, key_prefix: str) -> None:
    options = review_document_type_options(record.document_type)
    selected_type = st.selectbox(
        "Document type",
        options,
        index=(
            options.index(record.document_type)
            if record.document_type in options
            else 0
        ),
        format_func=document_type_label,
        help=FIELD_HELP["Document type"],
        key=f"{key_prefix}_document_type_{record.document_id}",
    )
    if st.button(
        "Save Type",
        key=f"{key_prefix}_save_type_{record.document_id}",
        disabled=selected_type == record.document_type,
        width="stretch",
    ):
        updated = store.update(record.document_id, document_type=selected_type)
        if updated.analysis and updated.report_path:
            Path(updated.report_path).write_text(
                generate_markdown_report(updated, config.genai_model_id),
                encoding="utf-8",
            )
        st.success(f"Document type updated to {document_type_label(selected_type)}.")
        st.rerun()


def render_review_action_panel(config, store, record, key_prefix: str) -> None:
    if record.status.value == "FAILED":
        st.error(
            "This document failed processing. Upload a corrected file or check service logs."
        )
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
    if cols[0].button(
        "Approve", type="primary", key=f"{key_prefix}_approve_{record.document_id}"
    ):
        if apply_review_action(
            config, store, record.document_id, approved=True, comments=comments
        ):
            st.rerun()
    if cols[1].button("Reject", key=f"{key_prefix}_reject_{record.document_id}"):
        if apply_review_action(
            config, store, record.document_id, approved=False, comments=comments
        ):
            st.rerun()


def workflow_option_index(record) -> int:
    options = workflow_status_options()
    try:
        return options.index(record.workflow_status)
    except ValueError:
        return 0


def render_retry_panel(config, store, record, key_prefix: str) -> None:
    if record.status != ProcessingStatus.FAILED:
        return

    st.markdown("### Retry processing")
    working_copy = local_working_copy_path(config, record)
    if working_copy.exists():
        st.caption(f"Source copy ready: {working_copy.name}")
    else:
        st.warning(
            "The local working copy is missing. Upload the source file again before retrying."
        )

    actor = st.text_input(
        "Retry requested by",
        value=record.assignee or "Reviewer",
        key=f"{key_prefix}_retry_actor_{record.document_id}",
    )
    reason = st.text_area(
        "Retry reason",
        value="",
        height=90,
        key=f"{key_prefix}_retry_reason_{record.document_id}",
    )
    if st.button(
        "Retry Processing",
        type="primary",
        key=f"{key_prefix}_retry_{record.document_id}",
        disabled=not working_copy.exists(),
        width="stretch",
    ):
        try:
            new_document_id = retry_document_processing(
                config=config,
                document_id=record.document_id,
                actor=actor,
                reason=reason or None,
            )
        except (FileNotFoundError, ValueError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Retry could not be queued: {exc}")
        else:
            refresh_markdown_report(config, store.load(record.document_id))
            st.session_state["selected_document_id"] = new_document_id
            st.session_state["dashboard_selected_document"] = new_document_id
            st.success("Retry queued. Opening the new processing record.")
            st.rerun()


def render_workflow_comments(config, store, record, key_prefix: str) -> None:
    st.markdown("### Notes")
    author = st.text_input(
        "Comment author",
        value=record.assignee or "Reviewer",
        key=f"{key_prefix}_comment_author_{record.document_id}",
    )
    comment = st.text_area(
        "Add workflow comment",
        value="",
        height=90,
        key=f"{key_prefix}_workflow_comment_{record.document_id}",
    )
    if st.button(
        "Add Comment",
        key=f"{key_prefix}_add_comment_{record.document_id}",
        disabled=not comment.strip(),
        width="stretch",
    ):
        updated = store.add_comment(record.document_id, author=author, comment=comment)
        refresh_markdown_report(config, updated)
        st.success("Comment added.")
        st.rerun()

    if record.workflow_comments:
        comment_rows = [
            {
                "Created": item.created_at.strftime("%Y-%m-%d %H:%M"),
                "Author": item.author,
                "Comment": item.comment,
            }
            for item in sorted(
                record.workflow_comments,
                key=lambda item: item.created_at,
                reverse=True,
            )
        ]
        st.dataframe(pd.DataFrame(comment_rows), width="stretch", hide_index=True)
    else:
        st.info("No workflow comments yet.")


def render_audit_trail(record) -> None:
    st.markdown("### Audit trail")
    if not record.audit_events:
        st.info("No workflow events recorded yet.")
        return
    rows = [
        {
            "Created": item.created_at.strftime("%Y-%m-%d %H:%M"),
            "Actor": item.actor,
            "Action": item.action.replace("_", " ").title(),
            "Detail": display_error_message(item.detail) if item.detail else "",
        }
        for item in sorted(record.audit_events, key=lambda item: item.created_at)
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_retry_history(record) -> None:
    if not record.retry_history:
        return
    st.markdown("### Retry history")
    rows = [
        {
            "Created": item.created_at.strftime("%Y-%m-%d %H:%M"),
            "Actor": item.actor,
            "Reason": item.reason or "",
            "New document": item.new_document_id or "",
        }
        for item in sorted(
            record.retry_history,
            key=lambda item: item.created_at,
            reverse=True,
        )
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_workflow_panel(config, store, record, key_prefix: str) -> None:
    st.subheader("Workflow")
    if record.parent_document_id:
        st.caption(f"Retry of document `{record.parent_document_id}`")

    options = workflow_status_options()
    selected_status = st.selectbox(
        "Workflow status",
        options,
        index=workflow_option_index(record),
        format_func=workflow_status_label,
        help=FIELD_HELP["Workflow"],
        key=f"{key_prefix}_workflow_status_{record.document_id}",
    )
    assignee = st.text_input(
        "Assignee",
        value=record.assignee or "",
        placeholder="Reviewer, team, or queue",
        help=FIELD_HELP["Assignee"],
        key=f"{key_prefix}_assignee_{record.document_id}",
    )
    has_sla = st.checkbox(
        "Use SLA due date",
        value=record.due_at is not None,
        key=f"{key_prefix}_has_sla_{record.document_id}",
    )
    due_date = st.date_input(
        "SLA due date",
        value=record.due_at.date() if record.due_at else date.today(),
        disabled=not has_sla,
        help=FIELD_HELP["SLA"],
        key=f"{key_prefix}_due_date_{record.document_id}",
    )
    actor = st.text_input(
        "Updated by",
        value=record.assignee or "Reviewer",
        key=f"{key_prefix}_workflow_actor_{record.document_id}",
    )
    due_at = utc_start_of_day(due_date) if has_sla else None
    if st.button(
        "Save Workflow",
        type="primary",
        key=f"{key_prefix}_save_workflow_{record.document_id}",
        width="stretch",
    ):
        updated = store.set_workflow(
            document_id=record.document_id,
            workflow_status=selected_status,
            assignee=assignee,
            due_at=due_at,
            actor=actor,
        )
        refresh_markdown_report(config, updated)
        st.success("Workflow updated.")
        st.rerun()

    render_retry_panel(config, store, record, key_prefix)
    render_workflow_comments(config, store, record, key_prefix)
    render_retry_history(record)
    render_audit_trail(record)


def render_analysis_overview(record) -> None:
    if not record.analysis:
        if record.error_message:
            st.error(display_error_message(record.error_message))
        else:
            st.info("Analysis is not available yet.")
        return

    analysis = record.analysis
    render_summary_panel("Executive Summary", analysis.executive_summary)
    st.caption(
        f"Document class: {analysis.document_class} | "
        f"Confidence: {confidence_percent(record)}% | Risk: {highest_risk_level(record)}"
    )
    render_risk_review_panel(record)

    col_left, col_right = st.columns(2, gap="large")
    with col_left:
        st.markdown("### Key Points")
        if analysis.key_points:
            for item in analysis.key_points[:8]:
                st.write(f"- {item}")
        else:
            st.info("No key points found.")
        if analysis.extracted_fields.line_items:
            st.markdown("### Items / Services")
            for item in analysis.extracted_fields.line_items[:8]:
                st.write(f"- {item}")
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
        risk_rows = [
            {
                "Severity": risk.severity,
                "Risk note": risk.risk,
                "Supporting evidence": risk.evidence or "No evidence returned",
            }
            for risk in analysis.risk_notes
        ]
        st.dataframe(
            pd.DataFrame(risk_rows),
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
        key=f"download_json_{document_id}",
        width="stretch",
    )
    if record.report_path and Path(record.report_path).exists():
        report = Path(record.report_path).read_text(encoding="utf-8")
        st.download_button(
            "Download Markdown Report",
            report,
            f"{document_id}.md",
            key=f"download_report_{document_id}",
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
    intro_cols = st.columns([1, 0.24], vertical_alignment="center")
    intro_cols[0].caption(
        f"GenAI region: {config.genai_region} | Parallel jobs: {config.max_parallel_jobs} | "
        f"Upload limit: {config.max_upload_mb} MB"
    )
    intro_cols[1].button(
        "How to Use",
        key="upload_howto",
        width="stretch",
        on_click=open_page,
        args=(PAGE_HELP,),
    )

    with st.container(border=True):
        document_type = st.selectbox(
            "Document type",
            upload_document_type_options(),
            format_func=document_type_label,
            help=FIELD_HELP["Document type"],
            key="upload_document_type",
        )
        business_reference = st.text_input(
            "Reference", placeholder="Optional", key="upload_business_reference"
        )
        uploaded_files = st.file_uploader(
            "Files",
            type=ALLOWED_UPLOAD_EXTENSIONS,
            accept_multiple_files=True,
            key=f"document_file_{st.session_state.get('upload_widget_version', 0)}",
            help=(
                f"Select up to {MAX_FILES_PER_UPLOAD} files. Maximum file size enforced by "
                f"the app: {config.max_upload_mb} MB."
            ),
        )
        selected_count = len(uploaded_files or [])
        job_description = st.text_area(
            "Expense name or reference",
            height=80,
            placeholder=(
                "Required when uploading more than one file"
                if selected_count > 1
                else "Optional shared context for this upload"
            ),
            key="upload_job_description",
            help=FIELD_HELP["Expense name or reference"],
        )
        notes = st.text_area(
            "Notes",
            height=90,
            placeholder="Optional review context",
            key="upload_notes",
        )

        uploaded_ok = selected_count > 0
        if selected_count:
            names = ", ".join(file.name for file in uploaded_files)
            st.caption(f"Selected {selected_count}: {names}")
            batch_errors = validate_upload_batch_requirements(
                uploaded_files, job_description
            )
            for message in batch_errors:
                st.error(message)
            if batch_errors:
                uploaded_ok = False
            for uploaded in uploaded_files:
                size_mb = uploaded.size / (1024 * 1024)
                st.caption(f"{uploaded.name} - {size_mb:.2f} MB")
            oversized = [
                file.name
                for file in uploaded_files
                if file.size / (1024 * 1024) > config.max_upload_mb
            ]
            if oversized:
                st.error(
                    f"File exceeds the configured {config.max_upload_mb} MB limit: "
                    + ", ".join(oversized)
                )
                uploaded_ok = False
        process_clicked = st.button(
            "Queue Documents" if selected_count > 1 else "Queue Document",
            disabled=not uploaded_ok,
            type="primary",
            width="stretch",
        )

    if process_clicked and uploaded_files:
        document_type_value = DocumentType(document_type)
        job_description_value = job_description.strip() or None
        queued_files = []
        requirement_errors = []
        requirement_notices = []
        for uploaded in uploaded_files:
            document_id = create_document_id()
            with NamedTemporaryFile(
                delete=False,
                dir=config.local_uploads_dir,
                prefix=f"queued-{document_id}",
                suffix=safe_upload_suffix(uploaded.name),
            ) as tmp:
                tmp.write(uploaded.getbuffer())
                tmp_path = Path(tmp.name)
            file_errors, file_notices = validate_upload_requirements(
                uploaded, tmp_path, config
            )
            requirement_errors.extend(
                f"{uploaded.name}: {message}" for message in file_errors
            )
            requirement_notices.extend(
                f"{uploaded.name}: {message}" for message in file_notices
            )
            queued_files.append((uploaded, document_id, tmp_path))
        if requirement_errors:
            for message in requirement_errors:
                st.error(message)
            for _, _, tmp_path in queued_files:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
            st.stop()
        for message in requirement_notices:
            st.info(message)

        records = []
        for uploaded, document_id, tmp_path in queued_files:
            record = DocumentRecord(
                document_id=document_id,
                document_name=uploaded.name,
                document_type=document_type_value,
                source_file_size_bytes=uploaded.size,
                source_file_mime_type=uploaded.type or None,
                status=ProcessingStatus.UPLOADED,
                job_description=job_description_value,
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
                job_description=job_description_value,
                source_file_size_bytes=uploaded.size,
                source_file_mime_type=uploaded.type or None,
            )
            records.append(record)
        first_record = records[0]
        st.session_state["selected_document_id"] = first_record.document_id
        st.session_state["dashboard_selected_document"] = first_record.document_id
        if len(records) == 1:
            st.success("Document was queued for background processing.")
            render_queued_actions(first_record)
        else:
            st.success(f"{len(records)} documents were queued for background processing.")
            render_batch_queued_actions(records)


@st.fragment(run_every=f"{DASHBOARD_REFRESH_SECONDS}s")
def render_dashboard_live_content(config, store) -> None:
    stale_count = fail_stale_processing_runs(config, store)
    if stale_count:
        st.warning(f"{stale_count} stale processing run was marked as failed.")
    records = store.list_records()
    if not records:
        with st.container(border=True):
            st.info("No documents processed yet.")
            empty_cols = st.columns([0.5, 0.5, 1.5])
            if empty_cols[0].button(
                "Upload",
                type="primary",
                key="dashboard_empty_upload",
                width="stretch",
            ):
                open_page_from_dashboard(PAGE_UPLOAD)
            if empty_cols[1].button(
                "Settings",
                key="dashboard_empty_settings",
                width="stretch",
            ):
                open_page_from_dashboard(PAGE_SETTINGS)
            empty_cols[2].caption(
                "Run OCI Preflight in Settings before processing customer documents."
            )
        return

    rows = [record_to_row(record) for record in records]
    df = pd.DataFrame(rows)
    active_runs = df[df["Status"].isin(ACTIVE_STATUSES)]
    st.markdown("### At a glance")
    render_dashboard_metrics(df, active_runs)

    render_dashboard_focus(config, records)
    render_expense_groups_overview(records)

    failures = df[df["Status"] == "FAILED"]
    if not failures.empty:
        noun = "document is" if len(failures) == 1 else "documents are"
        st.info(f"{len(failures)} failed {noun} available in the Failed view.")
    if not active_runs.empty:
        suffix = "s are" if len(active_runs) != 1 else " is"
        st.info(
            f"{len(active_runs)} document{suffix} processing. Worker pool size: "
            f"{config.max_parallel_jobs}. Items older than "
            f"{config.stale_processing_minutes} minutes are marked failed automatically."
        )
        if st.button("Refresh Status", key="dashboard_active_refresh"):
            rerun_dashboard_fragment()
        render_dashboard_refresh_note(len(active_runs))

    st.markdown("### Work queues")
    search_cols = st.columns([1.05, 0.5, 0.3, 0.3], vertical_alignment="bottom")
    search = search_cols[0].text_input(
        "Search documents",
        placeholder="Name, reference, status, action, or summary",
        help="Search applies to every queue section below.",
        key="dashboard_search",
    )
    status_filter = search_cols[1].selectbox(
        "Status filter",
        DASHBOARD_STATUS_FILTERS,
        key="dashboard_status_filter",
        help="Filter queue cards by decision, processing state, or next action.",
    )
    if search_cols[2].button(
        "Upload",
        key="dashboard_upload_action",
        width="stretch",
    ):
        open_page_from_dashboard(PAGE_UPLOAD)
    if search_cols[3].button(
        "Actions",
        key="dashboard_actions_action",
        width="stretch",
    ):
        open_page_from_dashboard(PAGE_DETAIL)

    sections = queue_view_frames(
        df=df,
        query=search,
        status_filter=status_filter,
    )
    filtered = filter_queue_rows(
        df=df,
        view="All",
        query=search,
        status_filter=status_filter,
    )

    filter_label = "" if status_filter == "All" else f" | Filter: {status_filter}"
    st.caption(f"Showing {len(filtered)} of {len(df)} documents{filter_label}")
    render_queue_section("Processing", sections["Processing"])
    render_ready_queue_band(sections["Ready"])
    section_cols = st.columns(2, gap="large")
    for col, view_name in zip(section_cols, ["Failed", "Reviewed"]):
        with col:
            render_queue_section(view_name, sections[view_name])

    if filtered.empty:
        st.info("No documents match this search.")


def dashboard_page(config, store):
    page_header(
        "Review",
        "Dashboard",
        "See what needs attention, monitor processing, and open documents for review.",
    )
    render_dashboard_live_content(config, store)


def detail_page(config, store):
    page_header(
        "Review",
        "Actions",
        "Work through documents that need approval, rejection, retry, or review follow-up.",
    )
    records = store.list_records()
    ordered_records = sort_action_records(records)
    ids = [record.document_id for record in ordered_records]
    if not ids:
        with st.container(border=True):
            st.info("No documents processed yet.")
            st.button(
                "Upload",
                type="primary",
                key="detail_empty_upload",
                on_click=open_page,
                args=(PAGE_UPLOAD,),
            )
        return

    ready_actions = sum(1 for record in records if requires_human_action(record))
    failed_actions = sum(1 for record in records if record.status.value == "FAILED")
    active_actions = sum(
        1 for record in records if record.status.value in ACTIVE_STATUSES
    )
    reviewed_actions = sum(
        1
        for record in records
        if record.review_status.value in {"APPROVED", "REJECTED"}
    )
    action_cols = st.columns(4)
    action_cols[0].metric("Needs decision", ready_actions)
    action_cols[1].metric("Needs fix", failed_actions)
    action_cols[2].metric("Processing", active_actions)
    action_cols[3].metric("Reviewed", reviewed_actions)

    pending_document_id = st.session_state.pop(PENDING_DETAIL_DOCUMENT_KEY, None)
    if pending_document_id in ids:
        st.session_state["selected_document_id"] = pending_document_id
        st.session_state[DETAIL_ACTION_PICKER_KEY] = pending_document_id

    default_id = st.session_state.get("selected_document_id", ids[0])
    index = ids.index(default_id) if default_id in ids else 0
    if st.session_state.get(DETAIL_ACTION_PICKER_KEY) not in ids:
        st.session_state[DETAIL_ACTION_PICKER_KEY] = ids[index]
    labels = {
        record.document_id: " - ".join(
            part
            for part in [
                record.document_name,
                f"Expense: {record.job_description}" if record.job_description else "",
                queue_stage(record),
                record.uploaded_at.strftime("%Y-%m-%d %H:%M"),
            ]
            if part
        )
        for record in records
    }
    picker_cols = st.columns([1.4, 0.3, 0.3])
    document_id = picker_cols[0].selectbox(
        "Action item",
        ids,
        index=index,
        format_func=lambda item: labels.get(item, item),
        key=DETAIL_ACTION_PICKER_KEY,
    )
    picker_cols[1].button(
        "Dashboard",
        width="stretch",
        key=f"detail_dashboard_{document_id}",
        on_click=open_page,
        args=(PAGE_DASHBOARD,),
    )
    picker_cols[2].button(
        "Upload",
        width="stretch",
        key=f"detail_upload_{document_id}",
        on_click=open_page,
        args=(PAGE_UPLOAD,),
    )

    record = store.load(document_id)
    st.session_state["selected_document_id"] = document_id

    st.subheader(record.document_name)
    if record.job_description:
        st.caption(f"Expense: {record.job_description}")
    render_status_strip(record)
    render_expense_reference_panel(records, record)

    decision_col, workflow_col = st.columns([0.95, 1.05], gap="large")
    with decision_col:
        with st.container(border=True):
            st.subheader("Decision")
            render_document_type_editor(config, store, record, "detail")
            render_review_action_panel(config, store, record, "detail")
            if record.review_comments:
                st.markdown("### Comments")
                st.write(record.review_comments)
    with workflow_col:
        with st.container(border=True):
            render_workflow_panel(config, store, record, "detail")

    with st.expander("Source document", expanded=True):
        render_source_document_download(config, record)

    render_analysis_overview(record)

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
            value=record.extracted_text_preview
            or "No extracted text preview available.",
            height=220,
            disabled=True,
            label_visibility="collapsed",
            key=f"extracted_preview_{document_id}",
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
            st.write(
                "Compliance knowledge base: "
                f"`{config.compliance_entities_object_name}`"
            )
            st.write(f"Max parallel jobs: `{config.max_parallel_jobs}`")
            st.write(f"Document AI timeout: `{config.document_ai_timeout_seconds}s`")
            st.info(
                "Run `python scripts/setup.py` to refresh GenAI region availability."
            )

    with health_col:
        with st.container(border=True):
            st.subheader("OCI Preflight")
            st.write(
                "Run this before processing customer documents. It performs real OCI API "
                "calls with the same runtime credentials used by document processing."
            )
            if st.button("Run OCI Preflight", type="primary", width="stretch"):
                with st.spinner(
                    "Checking Object Storage, Document Understanding, and GenAI"
                ):
                    results = run_preflight(config)
                for result in results:
                    detail = sanitize_provider_message(result.detail) or result.detail
                    if result.ok:
                        st.success(f"{result.name}: {detail}")
                    else:
                        st.error(f"{result.name}: {detail}")
                if all(result.ok for result in results):
                    st.success("All OCI runtime checks passed.")
                else:
                    st.warning(
                        "Fix the failed checks before processing customer documents."
                    )

    st.divider()
    st.caption(f"{CONTACT_TEXT}. {CONTACT_MESSAGE}")


def render_howto_step(number: int, title: str, body: str) -> str:
    return (
        '<div class="howto-step">'
        f'<div class="howto-number">{number}</div>'
        "<div>"
        f'<div class="howto-title">{escape(title)}</div>'
        f'<div class="howto-copy">{escape(body)}</div>'
        "</div>"
        "</div>"
    )


def render_howto_panel(
    title: str, intro: str, steps: list[tuple[str, str]]
) -> str:
    step_html = "".join(
        render_howto_step(index, step_title, body)
        for index, (step_title, body) in enumerate(steps, start=1)
    )
    return (
        '<div class="howto-panel">'
        f"<h3>{escape(title)}</h3>"
        f"<p>{escape(intro)}</p>"
        f"{step_html}"
        "</div>"
    )


def howto_page(config, store):
    page_header(
        "Guide",
        "How to Use",
        "A short path for submitting files and completing reviewer decisions.",
    )

    uploader_steps = [
        (
            "Choose the review type and context",
            "Start in Upload, choose a document type or Auto-detect, then add an optional reference, expense name or reference, and notes.",
        ),
        (
            "Attach one to five files",
            "Select PDFs, images, or text files. When you select more than one file, Expense name or reference is required so the set stays together.",
        ),
        (
            "Queue the submission",
            "Click Queue Document or Queue Documents. The browser can move on while workers process the files in the background.",
        ),
        (
            "Watch the queue",
            "Use Dashboard to see expense groups, compact Review cards, collapsed file details, active processing time, ready reviews, failures, and reviewed items.",
        ),
        (
            "Fix only failed items",
            "If processing fails or becomes stale, open the item from Dashboard or Actions, check the failure detail, and retry with a corrected file.",
        ),
    ]
    approver_steps = [
        (
            "Open Actions",
            "Use Actions for the review queue. The highest-priority item is selected first and the Decision panel appears near the top.",
        ),
        (
            "Read the source and linked files",
            "Download Doc for Review when needed, then use the linked-files panel to see other files from the same expense name or reference.",
        ),
        (
            "Check the AI review",
            "Review the summary, key points, items or services, extracted fields, risks, recommendations, and missing information.",
        ),
        (
            "Update workflow details",
            "Set the document type from the Decision panel, then update assignee, SLA, workflow status, or comments when the decision needs context.",
        ),
        (
            "Approve or reject",
            "Approve clean items or reject with comments. The page advances to the next action item automatically.",
        ),
    ]

    howto_html = (
        '<div class="howto-grid">'
        + render_howto_panel(
            "For uploaders",
            "Use this path when you are submitting one file or a small related file set for AI-assisted review.",
            uploader_steps,
        )
        + render_howto_panel(
            "For approvers",
            "Use this path when you are making the final human decision.",
            approver_steps,
        )
        + "</div>"
    )
    st.markdown(howto_html, unsafe_allow_html=True)

    st.markdown("### Queue states")
    st.markdown(
        '<div class="howto-status-grid">'
        '<div class="howto-status"><strong>Queued / Processing</strong><span>The file is waiting for or running through OCR, extraction, GenAI, and compliance checks. Dashboard shows active elapsed time.</span></div>'
        '<div class="howto-status"><strong>Ready</strong><span>The file needs a reviewer to inspect the results and approve, reject, or handle compliance review.</span></div>'
        '<div class="howto-status"><strong>Failed</strong><span>The file needs an operational fix or retry before review can continue. Stale active runs are marked failed automatically.</span></div>'
        '<div class="howto-status"><strong>Reviewed</strong><span>The file has already been approved or rejected and stays available for audit with its expense group.</span></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    records = store.list_records()
    pending_count = reviewer_action_count(records)
    ready_count = sum(1 for record in records if requires_human_action(record))
    failed_count = sum(1 for record in records if record.status.value == "FAILED")

    metric_cols = st.columns(3)
    metric_cols[0].metric("Needs action", pending_count)
    metric_cols[1].metric("Ready for decision", ready_count)
    metric_cols[2].metric("Needs retry", failed_count)

    nav_cols = st.columns(3)
    nav_cols[0].button(
        "Upload Document",
        type="primary",
        key="howto_upload",
        width="stretch",
        on_click=open_page,
        args=(PAGE_UPLOAD,),
    )
    nav_cols[1].button(
        "View Dashboard",
        key="howto_dashboard",
        width="stretch",
        on_click=open_page,
        args=(PAGE_DASHBOARD,),
    )
    nav_cols[2].button(
        "Open Actions",
        key="howto_actions",
        width="stretch",
        on_click=open_page,
        args=(PAGE_DETAIL,),
    )


def main():
    config = load_app_config()
    store = MetadataStore(config)
    st.set_page_config(page_title=config.app_title, layout="wide")
    apply_theme()
    stale_count = fail_stale_processing_runs(config, store)
    if stale_count:
        st.warning(f"{stale_count} stale processing run was marked as failed.")
    compliance_backfill_count = run_compliance_backfill_once(config, store)
    if compliance_backfill_count:
        st.info(
            f"{compliance_backfill_count} existing document"
            f"{'s were' if compliance_backfill_count != 1 else ' was'} flagged for compliance attention."
        )

    pages = [PAGE_UPLOAD, PAGE_DASHBOARD, PAGE_DETAIL, PAGE_HELP, PAGE_SETTINGS]
    nav_records = store.list_records()
    action_count = reviewer_action_count(nav_records)
    st.sidebar.title(config.app_title)
    st.sidebar.caption(f"AI document review on OCI | {VERSION_LABEL}")
    current_page = query_page() or (
        normalize_page(st.session_state.get("page", PAGE_UPLOAD)) or PAGE_UPLOAD
    )
    requested_page = normalize_page(st.session_state.get("requested_page"))
    if requested_page in pages:
        current_page = requested_page
    if current_page not in pages:
        current_page = PAGE_UPLOAD
    st.session_state["page"] = current_page
    sync_page_query(current_page)
    action_navigation = bool(st.session_state.pop("action_navigation", False))
    st.sidebar.markdown("Navigation")
    for nav_page in pages:
        nav_label = (
            f"{PAGE_DETAIL} ({action_count})"
            if nav_page == PAGE_DETAIL and action_count
            else nav_page
        )
        if (
            st.sidebar.button(
                nav_label,
                key=f"nav_{nav_page}",
                type="primary" if current_page == nav_page else "secondary",
                width="stretch",
            )
            and not action_navigation
        ):
            st.session_state["page"] = nav_page
            st.session_state.pop("requested_page", None)
            sync_page_query(nav_page)
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
    elif page == PAGE_HELP:
        howto_page(config, store)
    else:
        settings_page(config)


if __name__ == "__main__":
    main()
