import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import streamlit as st

# Ensure the project root is on the Python path so we can import from src and scripts
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_companies_flagged_potential_duplicates import (
    main as run_company_duplicate_audit,
)
from scripts.audit_contacts_flagged_potential_duplicates import (
    main as run_contact_duplicate_audit,
)
from scripts.run_all_audits import main as run_all_audits

REPORTS_DIR = PROJECT_ROOT / "reports"


def _run_audit(label: str, audit_func: Callable[[], None]) -> None:
    with st.spinner(f"Running {label}..."):
        audit_func()
    st.success(f"{label} completed.")


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
    st.title("HubSpot Data Quality Agent")

    st.subheader("Run Audits")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Run All Audits", use_container_width=True):
            _run_audit("Run All Audits", run_all_audits)
        
    with col2:
        if st.button("Run Contact Duplicate Audit", use_container_width=True):
            _run_audit("Run Contact Duplicate Audit", run_contact_duplicate_audit)
        if st.button("Run Company Duplicate Audit", use_container_width=True):
            _run_audit("Run Company Duplicate Audit", run_company_duplicate_audit)

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
