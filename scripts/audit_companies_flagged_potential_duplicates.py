import sys
from pathlib import Path

# Ensure the project root is on the Python path so we can import from src
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Any
import requests

from src.config import (
    get_company_duplicate_flag_property,
    get_hubspot_token,
)
from src.reporting import write_markdown_report


def _get_access_token() -> str:
    return get_hubspot_token()


def _hubspot_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    token = _get_access_token()
    url = f"https://api.hubapi.com{path}"
    response = requests.request(
        method,
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _resolve_flag_mode(property_name: str) -> str:
    data = _hubspot_request("GET", f"/crm/v3/properties/companies/{property_name}")

    property_type = str(data.get("type", "")).lower()
    field_type = str(data.get("fieldType", "")).lower()

    if property_type in {"bool", "boolean"} or field_type == "booleancheckbox":
        return "boolean"
    if property_type in {"enumeration", "string"}:
        return "textual"

    raise RuntimeError(
        "Could not determine flag property type for companies. "
        f"Property internal name: '{property_name}'. "
        "Please confirm this property type and flagged values in HubSpot Settings > Properties."
    )


def _fetch_flagged_companies(property_name: str, flag_mode: str) -> list[dict[str, Any]]:
    requested_properties = [
        "name",
        "domain",
        "hs_lastmodifieddate",
        property_name,
    ]

    if flag_mode == "boolean":
        filter_groups = [
            {
                "filters": [
                    {
                        "propertyName": property_name,
                        "operator": "EQ",
                        "value": "true",
                    }
                ]
            }
        ]
    else:
        filter_groups = [
            {
                "filters": [
                    {
                        "propertyName": property_name,
                        "operator": "EQ",
                        "value": value,
                    }
                ]
            }
            for value in ["true", "True", "yes", "Yes", "1"]
        ]

    results: list[dict[str, Any]] = []
    after: str | None = None

    while len(results) < 500:
        limit = min(200, 500 - len(results))
        payload: dict[str, Any] = {
            "filterGroups": filter_groups,
            "properties": requested_properties,
            "limit": limit,
        }
        if after is not None:
            payload["after"] = after

        data = _hubspot_request("POST", "/crm/v3/objects/companies/search", payload)
        batch = data.get("results", [])
        results.extend(batch)

        paging = data.get("paging", {})
        next_info = paging.get("next", {})
        after = next_info.get("after")
        if not after or not batch:
            break

    return results[:500]


def main() -> None:
    flag_property = get_company_duplicate_flag_property()
    flag_mode = _resolve_flag_mode(flag_property)
    companies = _fetch_flagged_companies(flag_property, flag_mode)

    rows: list[list[str]] = []
    for company in companies:
        properties = company.get("properties", {})
        rows.append(
            [
                str(company.get("id", "")),
                str(properties.get("name", "") or ""),
                str(properties.get("domain", "") or ""),
                str(properties.get(flag_property, "") or ""),
                str(properties.get("hs_lastmodifieddate", "") or ""),
            ]
        )

    report_path = write_markdown_report(
        report_name="companies_flagged_potential_duplicates",
        title="Companies Flagged as Potential Duplicates",
        summary_lines=[
            f"- Flag property: `{flag_property}`",
            f"- Total flagged companies: **{len(companies)}**",
        ],
        table_headers=[
            "id",
            "name",
            "domain",
            "flag_value",
            "hs_lastmodifieddate",
        ],
        rows=rows,
    )

    print(f"Total flagged companies: {len(companies)}")
    print(f"Report path: {report_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Failed to audit companies flagged as potential duplicates: {exc}")
        raise
