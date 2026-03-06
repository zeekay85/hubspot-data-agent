import sys
from pathlib import Path

# Ensure the project root is on the Python path so we can import from src
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from src.hubspot_client import get_hubspot_client
from src.reporting import write_markdown_report

MAX_COMPANIES = 500
PAGE_SIZE = 100  # HubSpot basic_api max is 100


def _fetch_companies(limit_total: int = MAX_COMPANIES) -> list[dict[str, Any]]:
    client = get_hubspot_client()
    properties = [
        "name",
        "domain",
        "icp_priority",
        "current_hcm_system_company_",
        "number_of_countries",
        "numberofemployees",
        "hs_lastmodifieddate",
        "potential_duplicate",
        "campaign_new",
        "createdate",
        "hubspot_owner_id",
    ]

    companies: list[dict[str, Any]] = []
    after: str | None = None

    while len(companies) < limit_total:
        limit = min(PAGE_SIZE, limit_total - len(companies))
        response = client.crm.companies.basic_api.get_page(
            limit=limit,
            after=after,
            properties=properties,
            archived=False,
        )

        batch = [item.to_dict() for item in (response.results or [])]
        companies.extend(batch)

        next_page = getattr(getattr(response, "paging", None), "next", None)
        after = str(getattr(next_page, "after", "")) if next_page else None

        if not after or not batch:
            break

    return companies[:limit_total]


def _normalize_domain(value: str) -> str:
    domain = (value or "").strip().lower()
    if not domain:
        return ""

    if "://" in domain:
        parsed = urlparse(domain)
        domain = parsed.netloc or parsed.path

    domain = domain.strip().strip("/")
    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def _parse_hubspot_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.isdigit():
        raw = int(text)
        if raw > 10_000_000_000:
            return datetime.fromtimestamp(raw / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(raw, tz=timezone.utc)

    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _to_int(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _completeness_score(properties: dict[str, Any]) -> int:
    score = 0
    important_fields = [
        "name",
        "domain",
        "icp_priority",
        "current_hcm_system_company_",
        "number_of_countries",
        "numberofemployees",
        "hubspot_owner_id",
        "campaign_new",
    ]
    for field in important_fields:
        if _safe_str(properties.get(field)):
            score += 1
    return score


def _pick_primary_record(group: list[dict[str, Any]]) -> str:
    """
    Picks a likely 'best' record to keep based on:
    1. Most complete record
    2. Most recently modified
    3. Lowest company ID as tie-breaker
    """
    ranked = []

    for company in group:
        props = company.get("properties", {})
        completeness = _completeness_score(props)
        last_modified = _parse_hubspot_datetime(props.get("hs_lastmodifieddate"))
        company_id = str(company.get("id", "") or "")

        ranked.append(
            (
                completeness,
                last_modified.timestamp() if last_modified else 0,
                -int(company_id) if company_id.isdigit() else 0,
                company_id,
            )
        )

    ranked.sort(reverse=True)
    return ranked[0][3] if ranked else ""


def main() -> None:
    print("Running duplicate companies by domain audit...")
    companies = _fetch_companies(limit_total=MAX_COMPANIES)

    companies_by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for company in companies:
        properties = company.get("properties", {})
        domain = _normalize_domain(_safe_str(properties.get("domain")))
        if not domain:
            continue
        companies_by_domain[domain].append(company)

    duplicate_groups = {
        domain: grouped
        for domain, grouped in companies_by_domain.items()
        if len(grouped) > 1
    }

    sorted_duplicate_domains = sorted(
        duplicate_groups.keys(),
        key=lambda d: (len(duplicate_groups[d]), d),
        reverse=True,
    )

    rows: list[list[str]] = []
    for domain in sorted_duplicate_domains:
        group = duplicate_groups[domain]
        group_size = len(group)
        primary_id = _pick_primary_record(group)

        group_sorted = sorted(
            group,
            key=lambda company: (
                _completeness_score(company.get("properties", {})),
                _parse_hubspot_datetime(
                    company.get("properties", {}).get("hs_lastmodifieddate")
                ).timestamp()
                if _parse_hubspot_datetime(company.get("properties", {}).get("hs_lastmodifieddate"))
                else 0,
            ),
            reverse=True,
        )

        for company in group_sorted:
            properties = company.get("properties", {})
            company_id = str(company.get("id", "") or "")
            rows.append(
                [
                    domain,
                    str(group_size),
                    company_id,
                    "yes" if company_id == primary_id else "",
                    _safe_str(properties.get("name")),
                    _safe_str(properties.get("icp_priority")),
                    _safe_str(properties.get("current_hcm_system_company_")),
                    _safe_str(properties.get("number_of_countries")),
                    _safe_str(properties.get("numberofemployees")),
                    _safe_str(properties.get("hubspot_owner_id")),
                    _safe_str(properties.get("potential_duplicate")),
                    _safe_str(properties.get("campaign_new")),
                    _safe_str(properties.get("hs_lastmodifieddate")),
                    str(_completeness_score(properties)),
                ]
            )

    total_companies_in_duplicate_groups = sum(len(group) for group in duplicate_groups.values())

    report_path = write_markdown_report(
        report_name="duplicate_companies_by_domain",
        title="Duplicate Companies by Domain",
        summary_lines=[
            f"- Total companies reviewed: **{len(companies)}**",
            f"- Total duplicate domains: **{len(duplicate_groups)}**",
            f"- Total companies in duplicate groups: **{total_companies_in_duplicate_groups}**",
            f"- Primary record recommendation logic: most complete record, then most recently modified.",
        ],
        table_headers=[
            "domain",
            "group_size",
            "id",
            "recommended_primary",
            "name",
            "icp_priority",
            "current_hcm_system_company_",
            "number_of_countries",
            "numberofemployees",
            "hubspot_owner_id",
            "potential_duplicate",
            "campaign_new",
            "hs_lastmodifieddate",
            "completeness_score",
        ],
        rows=rows,
    )

    print(f"Total companies reviewed: {len(companies)}")
    print(f"Total duplicate domains: {len(duplicate_groups)}")
    print(f"Total companies in duplicate groups: {total_companies_in_duplicate_groups}")
    print(f"Report path: {report_path}")


if __name__ == "__main__":
    main()