import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
from typing import Any

import requests

from src.config import get_contact_lead_source_property
from src.hubspot_client import get_hubspot_client
from src.reporting import write_markdown_report


CONTACT_PROPERTIES = [
    "firstname",
    "lastname",
    "email",
    "lifecyclestage",
    "campaign",
    "opted_in",
    "opt_in_source",
    "hs_lastmodifieddate",
]


def _get_access_token() -> str:
    client = get_hubspot_client()

    token = getattr(client, "access_token", None)
    if not token and getattr(client, "config", None):
        token = getattr(client.config, "access_token", None)
    if not token:
        token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")

    if not token:
        raise RuntimeError("Unable to resolve HubSpot access token from get_hubspot_client().")

    return token


def _hubspot_request(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = _get_access_token()
    response = requests.post(
        f"https://api.hubapi.com{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _fetch_contacts(limit_total: int, properties: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    after: str | None = None

    while len(results) < limit_total:
        limit = min(200, limit_total - len(results))
        payload: dict[str, Any] = {
            "properties": properties,
            "limit": limit,
        }
        if after is not None:
            payload["after"] = after

        data = _hubspot_request("/crm/v3/objects/contacts/search", payload)
        batch = data.get("results", [])
        results.extend(batch)

        paging = data.get("paging", {})
        next_info = paging.get("next", {})
        after = next_info.get("after")

        if not after or not batch:
            break

    return results[:limit_total]


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def main() -> None:
    print("Running contacts missing lead source audit...")
    lead_source_property = get_contact_lead_source_property()

    contacts = _fetch_contacts(
        limit_total=500,
        properties=CONTACT_PROPERTIES + [lead_source_property],
    )

    contacts_missing_lead_source: list[dict[str, Any]] = []
    for contact in contacts:
        properties = contact.get("properties", {})
        if _is_blank(properties.get(lead_source_property)):
            contacts_missing_lead_source.append(contact)

    rows: list[list[str]] = []
    for contact in contacts_missing_lead_source:
        properties = contact.get("properties", {})
        rows.append(
            [
                str(contact.get("id", "") or ""),
                str(properties.get("firstname", "") or ""),
                str(properties.get("lastname", "") or ""),
                str(properties.get("email", "") or ""),
                str(properties.get("lifecyclestage", "") or ""),
                str(properties.get("campaign", "") or ""),
                str(properties.get("opted_in", "") or ""),
                str(properties.get("opt_in_source", "") or ""),
                str(properties.get("hs_lastmodifieddate", "") or ""),
            ]
        )

    report_path = write_markdown_report(
        report_name="contacts_missing_lead_source",
        title="Contacts Missing Lead Source",
        summary_lines=[
            f"- Total contacts reviewed: **{len(contacts)}**",
            f"- Total contacts missing lead source: **{len(contacts_missing_lead_source)}**",
        ],
        table_headers=[
            "id",
            "firstname",
            "lastname",
            "email",
            "lifecyclestage",
            "campaign",
            "opted_in",
            "opt_in_source",
            "hs_lastmodifieddate",
        ],
        rows=rows,
    )

    print(f"Total contacts reviewed: {len(contacts)}")
    print(f"Total contacts missing lead source: {len(contacts_missing_lead_source)}")
    print(f"Report path: {report_path}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        raise SystemExit(1)
    except Exception as exc:
        print(f"Failed to audit contacts missing lead source: {exc}")
        raise
