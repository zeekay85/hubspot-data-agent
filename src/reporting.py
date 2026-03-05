from datetime import datetime
from pathlib import Path


def write_markdown_report(
    report_name: str,
    title: str,
    summary_lines: list[str],
    table_headers: list[str],
    rows: list[list[str]],
) -> Path:
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"{report_name}_{timestamp}.md"

    lines: list[str] = [f"# {title}", ""]

    if summary_lines:
        lines.extend(summary_lines)
        lines.append("")

    if table_headers:
        lines.append("| " + " | ".join(table_headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(table_headers)) + " |")
        for row in rows:
            lines.append("| " + " | ".join(row) + " |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path