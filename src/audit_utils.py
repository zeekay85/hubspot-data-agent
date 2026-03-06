from __future__ import annotations

import os
from typing import Any, Iterable

import requests


_SEARCHABLE_OBJECT_TYPES = {"contacts", "companies"}
_SEARCH_PAGE_SIZE = 200
_ASSOCIATIONS_BATCH_SIZE = 100


def _get_access_token(client: Any) -> str:
    token = getattr(client, "access_token", None)
    if not token and getattr(client, "config", None):
        token = getattr(client.config, "access_token", None)
    if not token:
        token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")
    if not token:
        raise RuntimeError("Unable to resolve HubSpot access token from the HubSpot client.")
    return token


def _hubspot_post(client: Any, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"https://api.hubapi.com{path}",
        headers={
            "Authorization": f"Bearer {_get_access_token(client)}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _chunked(values: Iterable[str], size: int) -> Iterable[list[str]]:
    batch: list[str] = []
    for value in values:
        if not value:
            continue
        batch.append(value)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def search_objects(
    client: Any,
    object_type: str,
    properties: list[str],
    limit: int = 500,
) -> list[dict[str, Any]]:
    if object_type not in _SEARCHABLE_OBJECT_TYPES:
        raise ValueError(f"Unsupported object type for search: {object_type!r}")
    if limit <= 0:
        return []

    records: list[dict[str, Any]] = []
    after: str | None = None

    while len(records) < limit:
        page_limit = min(_SEARCH_PAGE_SIZE, limit - len(records))
        payload: dict[str, Any] = {
            "properties": properties,
            "limit": page_limit,
        }
        if after is not None:
            payload["after"] = after

        data = _hubspot_post(client, f"/crm/v3/objects/{object_type}/search", payload)
        batch = data.get("results", [])
        records.extend(batch)

        paging = data.get("paging", {})
        next_info = paging.get("next", {})
        after = str(next_info.get("after", "") or "") or None

        if not after or not batch:
            break

    return records[:limit]


def get_contact_company_association_ids(
    client: Any,
    contact_ids: list[str] | Iterable[str],
) -> dict[str, list[str]]:
    association_map: dict[str, list[str]] = {}
    normalized_contact_ids = [str(contact_id) for contact_id in contact_ids if str(contact_id)]

    for batch in _chunked(normalized_contact_ids, _ASSOCIATIONS_BATCH_SIZE):
        data = _hubspot_post(
            client,
            "/crm/v4/associations/contacts/companies/batch/read",
            {"inputs": [{"id": contact_id} for contact_id in batch]},
        )

        for result in data.get("results", []):
            from_info = result.get("from", {})
            contact_id = str(from_info.get("id", "") or "")
            company_ids = [
                str(item.get("toObjectId", "") or "")
                for item in result.get("to", [])
                if str(item.get("toObjectId", "") or "")
            ]
            if contact_id and company_ids:
                association_map[contact_id] = company_ids

    return association_map
