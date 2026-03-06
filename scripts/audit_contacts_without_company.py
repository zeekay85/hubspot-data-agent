import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Any

from src.hubspot_client import get_hubspot_client
from src.reporting import write_markdown_report

CONTACT_PROPERTIES = [
    "firstname",
    "lastname",
    "email",
    "lifecyclestage",
    "opted_in",
    "opted_in_source",
    "campaign",
    "hs_lastmodifieddate",
]


def _hubspot_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    client = get_hubspot_client()
    response = client.api_request(
        {
            "method": "GET",
            "path": path,
            "query_params": params,
        }
    )
    return response.json()


def _hubspot_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    client = get_hubspot_client()
    response = client.api_request(
        {
            "method": "POST",
            "path": path,
            "body": body,
        }
    )
    return response.json()


def _fetch_contacts(limit: int = 500) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    after: str | None = None

    while len(contacts) < limit:
        page_size = min(100, limit - len(contacts))
        params: dict[str, Any] = {
            "limit": page_size,
            "properties": CONTACT_PROPERTIES,
        }
        if after is not None:
            params["after"] = after

        data = _hubspot_get("/crm/v3/objects/contacts", params)
        batch = data.get("results", [])
        contacts.extend(batch)

        paging = data.get("paging", {})
        next_page = paging.get("next", {})
        after = next_page.get("after")
        if not after or not batch:
            break

    return contacts[:limit]


def _get_contact_company_association_ids(contact_ids: list[str]) -> set[str]:
    associated_contact_ids: set[str] = set()

    if not contact_ids:
        return associated_contact_ids

    # HubSpot batch association read works more reliably in chunks
    chunk_size = 100

    for i in range(0, len(contact_ids), chunk_size):
        chunk = contact_ids[i:i + chunk_size]
        body = {"inputs": [{"id": contact_id} for contact_id in chunk]}

        data = _hubspot_post(
            "/crm/v4/associations/contacts/companies/batch/read",
            body,
        )

        for result in data.get("results", []):
            from_id = str(result.get("from", {}).get("id", "") or "")
            to_list = result.get("to", []) or []
            if from_id and len(to_list) > 0:
                associated_contact_ids.add(from_id)

    return associated_contact_ids


def main() -> None:
    print("Running contacts without associated company audit...")

    contacts = _fetch_contacts(limit=500)
    contact_ids = [str(contact.get("id", "") or "") for contact in contacts]
    associated_contact_ids = _get_contact_company_association_ids(contact_ids)

    print(f"Total contacts reviewed: {len(contacts)}")
    print(f"Contacts with associated company: {len(associated_contact_ids)}")

    print("Sample reviewed contacts:")
    for contact in contacts[:5]:
        props = contact.get("properties", {}) or {}
        cid = str(contact.get("id", "") or "")
        print(
            {
                "id": cid,
                "firstname": props.get("firstname"),
                "lastname": props.get("lastname"),
                "email": props.get("email"),
                "has_company": cid in associated_contact_ids,
            }
        )

    contacts_without_company = []
    for contact in contacts:
        cid = str(contact.get("id", "") or "")
        if cid not in associated_contact_ids:
            contacts_without_company.append(contact)

    print(f"Contacts without company: {len(contacts_without_company)}")

    rows: list[list[str]] = []
    for contact in contacts_without_company:
        properties = contact.get("properties", {}) or {}
        rows.append(
            [
                str(contact.get("id", "") or ""),
                str(properties.get("firstname", "") or ""),
                str(properties.get("lastname", "") or ""),
                str(properties.get("email", "") or ""),
                str(properties.get("lifecyclestage", "") or ""),
                str(properties.get("opted_in", "") or ""),
                str(properties.get("opted_in_source", "") or ""),
                str(properties.get("campaign", "") or ""),
                str(properties.get("hs_lastmodifieddate", "") or ""),
            ]
        )

    report_path = write_markdown_report(
        report_name="contacts_without_company",
        title="Contacts Without Associated Company",
        summary_lines=[
            f"- Total contacts reviewed: **{len(contacts)}**",
            f"- Contacts with associated company: **{len(associated_contact_ids)}**",
            f"- Total contacts without company: **{len(contacts_without_company)}**",
        ],
        table_headers=[
            "id",
            "firstname",
            "lastname",
            "email",
            "lifecyclestage",
            "opted_in",
            "opted_in_source",
            "campaign",
            "hs_lastmodifieddate",
        ],
        rows=rows,
    )

    print(f"Report path: {report_path}")


if __name__ == "__main__":
    main()