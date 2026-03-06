import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Ensure the project root is on the Python path so we can import from src
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.audit_registry import AUDIT_DEFINITIONS, AuditDefinition

COUNT_PATTERN_TEMPLATE = r"{marker}:\s*\*\*(\d+)\*\*"


@dataclass
class AuditReportSummary:
    definition: AuditDefinition
    latest_report_path: Path | None
    issue_count: int
    preview_lines: list[str]


def _find_latest_report(reports_dir: Path, report_prefix: str) -> Path | None:
    candidates = sorted(reports_dir.glob(f"{report_prefix}_*.md"))
    if not candidates:
        return None
    return candidates[-1]


def _extract_issue_count(report_text: str, count_markers: tuple[str, ...]) -> int:
    issue_count = 0
    for marker in count_markers:
        pattern = re.compile(COUNT_PATTERN_TEMPLATE.format(marker=re.escape(marker)))
        match = pattern.search(report_text)
        if match:
            issue_count += int(match.group(1))
    return issue_count


def _extract_table_preview(report_text: str, row_limit: int = 10) -> list[str]:
    lines = report_text.splitlines()

    header_index = None
    for index, line in enumerate(lines):
        if line.strip().startswith("|"):
            if index + 1 < len(lines) and lines[index + 1].strip().startswith("|"):
                header_index = index
                break

    if header_index is None:
        return ["_No table data available._"]

    table_lines: list[str] = [lines[header_index], lines[header_index + 1]]
    data_rows = 0

    for line in lines[header_index + 2 :]:
        if not line.strip().startswith("|"):
            break
        if data_rows >= row_limit:
            break
        table_lines.append(line)
        data_rows += 1

    return table_lines


def _collect_audit_summary(reports_dir: Path, definition: AuditDefinition) -> AuditReportSummary:
    latest_report_path = _find_latest_report(reports_dir, definition.report_prefix)
    if latest_report_path is None:
        return AuditReportSummary(
            definition=definition,
            latest_report_path=None,
            issue_count=0,
            preview_lines=["_No report found._"],
        )

    report_text = latest_report_path.read_text(encoding="utf-8")

    return AuditReportSummary(
        definition=definition,
        latest_report_path=latest_report_path,
        issue_count=_extract_issue_count(report_text, definition.count_markers),
        preview_lines=_extract_table_preview(report_text, row_limit=10),
    )


def _dashboard_report_path(reports_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return reports_dir / f"hubspot_data_quality_dashboard_{timestamp}.md"


def build_dashboard() -> Path:
    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    summaries = [_collect_audit_summary(reports_dir, definition) for definition in AUDIT_DEFINITIONS]

    generated_at = datetime.now().isoformat(timespec="seconds")
    lines: list[str] = [
        "# HubSpot Data Quality Dashboard",
        "",
        f"Generated timestamp: {generated_at}",
        "",
        "| Audit | Issue Count | Latest Report File |",
        "| --- | --- | --- |",
    ]

    for summary in summaries:
        latest = str(summary.latest_report_path) if summary.latest_report_path else "N/A"
        lines.append(f"| {summary.definition.label} | {summary.issue_count} | {latest} |")

    for summary in summaries:
        lines.extend(
            [
                "",
                f"## {summary.definition.label}",
                "",
                f"- Count: {summary.issue_count}",
                f"- Latest report: {summary.latest_report_path if summary.latest_report_path else 'N/A'}",
                "",
                "Preview (first 10 rows):",
                "",
            ]
        )
        lines.extend(summary.preview_lines)

    dashboard_path = _dashboard_report_path(reports_dir)
    dashboard_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dashboard_path


def main() -> None:
    dashboard_path = build_dashboard()
    print(f"Dashboard report path: {dashboard_path}")


if __name__ == "__main__":
    main()
