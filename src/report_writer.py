from __future__ import annotations

from pathlib import Path

import pandas as pd


class ReportWriteError(RuntimeError):
    """Raised when a report file cannot be written."""


def write_excel_report(dataframe: pd.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        dataframe.to_excel(output_path, index=False)
    except Exception as exc:  # pragma: no cover - defensive file I/O wrapper
        raise ReportWriteError(f"Failed to write report to {output_path}: {exc}") from exc
    return output_path
