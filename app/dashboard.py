import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_companies_flagged_potential_duplicates import (
    main as run_company_duplicate_audit,
)
from scripts.audit_contacts_flagged_potential_duplicates import (
    main as run_contact_duplicate_audit,
)
from scripts.audit_contacts_missing_lead_source import (
    main as run_contacts_missing_lead_source_audit,
)
from scripts.audit_contacts_without_company import main as run_contacts_without_company_audit
from scripts.audit_duplicate_companies_by_domain import (
    main as run_duplicate_companies_by_domain_audit,
)
from scripts.build_data_quality_dashboard import build_dashboard
from scripts.audit_stale_contacts import main as run_stale_contacts_audit
from scripts.run_all_audits import main as run_all_audits
from src.audit_registry import AUDIT_DEFINITIONS_BY_KEY

REPORTS_DIR = PROJECT_ROOT / "reports"

AUDIT_FUNCTIONS: list[tuple[str, Callable[[], None]]] = [
    (
        AUDIT_DEFINITIONS_BY_KEY["contacts_without_company"].label,
        run_contacts_without_company_audit,
    ),
    (
        AUDIT_DEFINITIONS_BY_KEY["stale_contacts"].label,
        run_stale_contacts_audit,
    ),
    (
        AUDIT_DEFINITIONS_BY_KEY["contacts_flagged_potential_duplicates"].label,
        run_contact_duplicate_audit,
    ),
    (
        AUDIT_DEFINITIONS_BY_KEY["companies_flagged_potential_duplicates"].label,
        run_company_duplicate_audit,
    ),
    (
        AUDIT_DEFINITIONS_BY_KEY["contacts_missing_lead_source"].label,
        run_contacts_missing_lead_source_audit,
    ),
    (
        AUDIT_DEFINITIONS_BY_KEY["duplicate_companies_by_domain"].label,
        run_duplicate_companies_by_domain_audit,
    ),
]


def _apply_global_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --theme-blue: #0066ff;
            --theme-blue-dark: #0047b3;
            --theme-card: rgba(8, 19, 43, 0.68);
            --theme-card-border: rgba(255, 255, 255, 0.14);
            --theme-text: #ffffff;
            --theme-text-muted: rgba(255, 255, 255, 0.82);
            --theme-shadow: 0 18px 50px rgba(0, 27, 84, 0.28);
            --theme-radius: 18px;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 255, 255, 0.14), transparent 28%),
                linear-gradient(135deg, var(--theme-blue) 0%, var(--theme-blue-dark) 100%);
            color: var(--theme-text);
        }

        .stApp [data-testid="stAppViewContainer"] {
            background: transparent;
        }

        .stApp [data-testid="stHeader"],
        .stApp [data-testid="stToolbar"] {
            background: transparent;
        }

        .stApp [data-testid="stSidebar"] {
            background: rgba(3, 14, 36, 0.44);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        .stApp [data-testid="stSidebar"] * {
            color: var(--theme-text);
        }

        .stApp .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .stApp h1,
        .stApp h2,
        .stApp h3,
        .stApp h4,
        .stApp h5,
        .stApp h6,
        .stApp p,
        .stApp li,
        .stApp label,
        .stApp span,
        .stApp div {
            color: var(--theme-text);
        }

        .stApp a {
            color: #d9e8ff;
        }

        .stApp [data-testid="stCaptionContainer"],
        .stApp [data-testid="stMarkdownContainer"] p,
        .stApp [data-testid="stText"],
        .stApp small {
            color: var(--theme-text-muted);
        }

        .stApp [data-testid="stHorizontalBlock"] {
            gap: 1rem;
        }

        .stApp [data-testid="column"] {
            background: var(--theme-card);
            border: 1px solid var(--theme-card-border);
            border-radius: var(--theme-radius);
            box-shadow: var(--theme-shadow);
            padding: 1rem;
            backdrop-filter: blur(16px);
        }

        .stApp [data-testid="stAlert"],
        .stApp [data-testid="stMetric"],
        .stApp [data-testid="stFileUploader"],
        .stApp [data-testid="stDataFrame"],
        .stApp [data-testid="stTable"],
        .stApp [data-testid="stExpander"],
        .stApp div[data-baseweb="select"],
        .stApp div[data-baseweb="input"],
        .stApp textarea,
        .stApp input {
            background: var(--theme-card);
            border-radius: var(--theme-radius);
            border: 1px solid var(--theme-card-border);
            color: var(--theme-text);
        }

        .stApp [data-testid="stButton"] > button,
        .stApp [data-testid="stDownloadButton"] > button {
            background: linear-gradient(180deg, #2b84ff 0%, var(--theme-blue) 100%);
            color: var(--theme-text);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 12px;
            box-shadow: 0 10px 24px rgba(0, 41, 122, 0.24);
            transition: all 0.2s ease;
        }

        .stApp [data-testid="stButton"] > button:hover,
        .stApp [data-testid="stDownloadButton"] > button:hover {
            border-color: rgba(255, 255, 255, 0.28);
            transform: translateY(-1px);
        }

        .stApp [data-testid="stButton"] > button:focus,
        .stApp [data-testid="stDownloadButton"] > button:focus {
            box-shadow: 0 0 0 0.2rem rgba(217, 232, 255, 0.35);
        }

        .stApp [data-baseweb="slider"] [role="slider"] {
            background: var(--theme-blue);
            border-color: var(--theme-blue);
        }

        .stApp [data-baseweb="slider"] div[data-testid="stTickBarMin"],
        .stApp [data-baseweb="slider"] div[data-testid="stTickBarMax"] {
            background: rgba(255, 255, 255, 0.2);
        }

        .stApp [data-testid="stSliderTickBarMin"] {
            background: var(--theme-blue);
        }

        .stApp [data-testid="stCheckbox"] label,
        .stApp [data-testid="stRadio"] label {
            color: var(--theme-text);
        }

        .stApp [data-testid="stDivider"] {
            background-color: rgba(255, 255, 255, 0.16);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _run_audit(label: str, audit_func: Callable[[], None]) -> None:
    with st.spinner(f"Running {label}..."):
        audit_func()
        build_dashboard()
    st.success(f"{label} completed.")


def _run_dashboard_refresh() -> None:
    with st.spinner("Building dashboard summary..."):
        dashboard_path = build_dashboard()
    st.success(f"Dashboard summary updated: {dashboard_path.name}")


def _list_latest_reports(limit: int = 10) -> list[Path]:
    if not REPORTS_DIR.exists():
        return []

    files = [path for path in REPORTS_DIR.iterdir() if path.is_file()]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files[:limit]


def _format_timestamp(path: Path) -> str:
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return modified.strftime("%Y-%m-%d %H:%M:%S")


def _render_dashboard_summary() -> None:
    summary_candidates = sorted(REPORTS_DIR.glob("hubspot_data_quality_dashboard*"))
    if not summary_candidates:
        st.info("No dashboard summary report found in /reports yet.")
        return

    summary_file = max(summary_candidates, key=lambda path: path.stat().st_mtime)
    st.caption(f"Source: {summary_file.name}")
    st.markdown(summary_file.read_text(encoding="utf-8"))


def main() -> None:
    st.set_page_config(page_title="HubSpot Data Quality Agent", layout="wide")
    _apply_global_theme()
    st.title("HubSpot Data Quality Agent")

    st.subheader("Run Audits")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Run All Audits", use_container_width=True):
            _run_audit("Run All Audits", run_all_audits)

        for label, audit_func in AUDIT_FUNCTIONS[:2]:
            if st.button(label, use_container_width=True):
                _run_audit(label, audit_func)

    with col2:
        for label, audit_func in AUDIT_FUNCTIONS[2:]:
            if st.button(label, use_container_width=True):
                _run_audit(label, audit_func)

        if st.button("Refresh Dashboard Summary", use_container_width=True):
            _run_dashboard_refresh()

    st.divider()

    st.subheader("Latest Reports")
    latest_reports = _list_latest_reports(limit=10)
    if not latest_reports:
        st.info("No reports found in /reports.")
    else:
        for report_path in latest_reports:
            file_bytes = report_path.read_bytes()
            c1, c2, c3 = st.columns([4, 3, 2])
            c1.markdown(f"`{report_path.name}`")
            c2.write(_format_timestamp(report_path))
            c3.download_button(
                label="Download",
                data=file_bytes,
                file_name=report_path.name,
                mime="text/markdown",
                key=f"download-{report_path.name}",
                use_container_width=True,
            )

    st.divider()

    st.subheader("Summary")
    _render_dashboard_summary()


if __name__ == "__main__":
    main()
