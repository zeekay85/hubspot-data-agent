import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime, timezone
from pathlib import Path

# Ensure the project root is on the Python path so we can import from src
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging

import pandas as pd

from src.company_matcher import CompanyMatcher, MatchConfig
from src.report_writer import write_excel_report

DEFAULT_INPUT_PATH = PROJECT_ROOT / "reports" / "company_input.xlsx"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports"
LOGGER = logging.getLogger(__name__)


def parse_args() -> Namespace:
    parser = ArgumentParser(
        description="Read company names from Excel, search HubSpot, and write match results to a new Excel file.",
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default=str(DEFAULT_INPUT_PATH),
        help=f"Path to the input Excel file. Defaults to {DEFAULT_INPUT_PATH}",
    )
    parser.add_argument(
        "--output-path",
        default="",
        help="Optional explicit path for the output Excel file. Defaults to reports/company_owner_lookup_<timestamp>.xlsx",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=75,
        help="Minimum fuzzy match score required to accept a match.",
    )
    parser.add_argument(
        "--search-limit",
        type=int,
        default=10,
        help="Maximum number of HubSpot candidates to fetch per company name.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args()


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def resolve_output_path(output_path_arg: str) -> Path:
    if output_path_arg:
        return Path(output_path_arg).expanduser().resolve()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return (DEFAULT_OUTPUT_DIR / f"company_owner_lookup_{timestamp}.xlsx").resolve()


def read_input_excel(input_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    dataframe = pd.read_excel(input_path)
    if "Company Name" not in dataframe.columns:
        raise ValueError('Input file must contain a "Company Name" column.')
    return dataframe


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level)

    input_path = Path(args.input_path).expanduser().resolve()
    output_path = resolve_output_path(args.output_path)

    LOGGER.info("Reading input Excel file from %s", input_path)
    dataframe = read_input_excel(input_path)

    matcher = CompanyMatcher(
        config=MatchConfig(
            score_threshold=args.threshold,
            medium_confidence_threshold=args.threshold,
            search_limit=args.search_limit,
        )
    )
    result_dataframe = matcher.match_companies(dataframe)

    LOGGER.info("Writing %s matched rows to %s", len(result_dataframe), output_path)
    write_excel_report(result_dataframe, output_path)
    LOGGER.info("Done. Output saved to %s", output_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        LOGGER.exception("Company owner lookup failed: %s", exc)
        raise SystemExit(1) from exc
