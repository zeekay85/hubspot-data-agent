from __future__ import annotations

from functools import lru_cache
from typing import Any

import requests
from hubspot import HubSpot
from hubspot.crm.companies import PublicObjectSearchRequest

from src.config import get_hubspot_token

COMPANY_SEARCH_LIMIT = 10
DEFAULT_COMPANY_PROPERTIES = ["name", "domain", "hubspot_owner_id"]
SEARCH_API_URL = "https://api.hubapi.com/crm/v3/objects/companies/search"


@lru_cache(maxsize=1)
def get_hubspot_client() -> HubSpot:
    """Return a cached HubSpot client configured from environment variables."""
    return HubSpot(access_token=get_hubspot_token())


class HubSpotCompanyReader:
    """Read-only helper for HubSpot company and owner lookups."""

    def __init__(self, client: HubSpot | None = None) -> None:
        self.client = client or get_hubspot_client()
        self._owner_cache: dict[str, dict[str, str]] = {}

    def search_companies_by_name(
        self,
        company_name: str,
        *,
        limit: int = COMPANY_SEARCH_LIMIT,
        properties: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        search_text = (company_name or "").strip()
        if not search_text:
            return []

        request = PublicObjectSearchRequest(
            query=search_text,
            limit=limit,
            properties=properties or DEFAULT_COMPANY_PROPERTIES,
        )
        response = self.client.crm.companies.search_api.do_search(
            public_object_search_request=request
        )
        return [record.to_dict() for record in (response.results or [])]

    def search_companies_by_domain_token(
        self,
        domain_token: str,
        *,
        limit: int = COMPANY_SEARCH_LIMIT,
        properties: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        token = (domain_token or "").strip().lower()
        if not token:
            return []

        payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "domain",
                            "operator": "CONTAINS_TOKEN",
                            "value": token,
                        }
                    ]
                }
            ],
            "properties": properties or DEFAULT_COMPANY_PROPERTIES,
            "limit": limit,
        }
        response = requests.post(
            SEARCH_API_URL,
            headers={
                "Authorization": f"Bearer {get_hubspot_token()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return list(data.get("results", []))

    def get_owner(self, owner_id: str | int | None) -> dict[str, str]:
        owner_key = str(owner_id or "").strip()
        if not owner_key:
            return {"name": "", "email": ""}

        if owner_key in self._owner_cache:
            return self._owner_cache[owner_key]

        try:
            owner = self.client.crm.owners.owners_api.get_by_id(owner_key)
        except Exception:
            owner_data = {"name": "", "email": ""}
            self._owner_cache[owner_key] = owner_data
            return owner_data

        first_name = str(getattr(owner, "first_name", "") or "").strip()
        last_name = str(getattr(owner, "last_name", "") or "").strip()
        full_name = " ".join(part for part in [first_name, last_name] if part).strip()
        owner_data = {
            "name": full_name,
            "email": str(getattr(owner, "email", "") or "").strip(),
        }
        self._owner_cache[owner_key] = owner_data
        return owner_data