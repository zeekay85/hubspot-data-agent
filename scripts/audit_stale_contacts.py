import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import json
from urllib import request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hubspot_client import get_hubspot_client
from src.reporting import write_markdown_report

CONTACT_PROPERTIES = [
    "firstname",
    "lastname",
    "email",
    "createdate",
    "lifecyclestage",
    "hubspot_owner_id",
    "hs_lastmodifieddate",
    "lastactivitydate",
    "notes_last_updated",
    "recent_conversion_date",
    "num_conversion_events",
    "hs_analytics_last_visit_timestamp",
    "hs_analytics_num_visits",
    "hs_email_last_open_date",
    "hs_email_last_click_date",
    "recent_sales_email_open_date",
    "recent_sales_email_clicked_date",
    "last_engagement_date",
    "hs_marketable_status",
    "opted_in",
    "opt_in_source",
]

PROTECTED_LIFECYCLE_STAGES = {
    "customer",
    "evangelist",
    "opportunity",
}

STALE_DAYS = 730
ENGAGEMENT_DAYS = 365
PAGE_SIZE = 200
MAX_CONTACTS = 2000  # increase or lower as needed


def _get_access_token() -> str:
    client = get_hubspot_client()

    token = getattr(client, "access_token", None)
    if not token and getattr(client, "config", None):
        token = getattr(client.config, "access_token", None)

    if not token:
        raise RuntimeError("Unable to resolve HubSpot access token from get_hubspot_client().")

    return str(token)


def _hubspot_search_contacts(limit: int = MAX_CONTACTS) -> list[dict[str, Any]]:
    token = _get_access_token()
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"

    results: list[dict[str, Any]] = []
    after: str | None = None

    while len(results) < limit:
        payload: dict[str, Any] = {
            "limit": min(PAGE_SIZE, limit - len(results)),
            "properties": CONTACT_PROPERTIES,
            "sorts": [{"propertyName": "createdate", "direction": "ASCENDING"}],
        }
        if after is not None:
            payload["after"] = after

        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        batch = data.get("results", [])
        results.extend(batch)

        next_info = data.get("paging", {}).get("next", {})
        after = next_info.get("after")

        if not batch or not after:
            break

    return results[:limit]


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


def _latest_datetime(*values: str | None) -> datetime | None:
    parsed = [_parse_hubspot_datetime(v) for v in values]
    valid = [dt for dt in parsed if dt is not None]
    return max(valid) if valid else None


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _days_since(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return ""
    return str((now - dt).days)


def _classify_contact(contact: dict[str, Any], now: datetime) -> dict[str, Any]:
    props = contact.get("properties", {})

    createdate = _parse_hubspot_datetime(props.get("createdate"))
    last_modified = _parse_hubspot_datetime(props.get("hs_lastmodifieddate"))
    last_activity = _parse_hubspot_datetime(props.get("lastactivitydate"))
    notes_last_updated = _parse_hubspot_datetime(props.get("notes_last_updated"))
    recent_conversion_date = _parse_hubspot_datetime(props.get("recent_conversion_date"))
    last_visit = _parse_hubspot_datetime(props.get("hs_analytics_last_visit_timestamp"))
    email_open = _parse_hubspot_datetime(props.get("hs_email_last_open_date"))
    email_click = _parse_hubspot_datetime(props.get("hs_email_last_click_date"))
    sales_email_open = _parse_hubspot_datetime(props.get("recent_sales_email_open_date"))
    sales_email_click = _parse_hubspot_datetime(props.get("recent_sales_email_clicked_date"))
    last_engagement = _parse_hubspot_datetime(props.get("last_engagement_date"))

    meaningful_engagement = _latest_datetime(
        props.get("lastactivitydate"),
        props.get("recent_conversion_date"),
        props.get("hs_analytics_last_visit_timestamp"),
        props.get("hs_email_last_open_date"),
        props.get("hs_email_last_click_date"),
        props.get("recent_sales_email_open_date"),
        props.get("recent_sales_email_clicked_date"),
        props.get("last_engagement_date"),
    )

    record_touch = _latest_datetime(
        props.get("hs_lastmodifieddate"),
        props.get("notes_last_updated"),
    )

    lifecycle_stage = _safe_str(props.get("lifecyclestage")).lower()
    owner_id = _safe_str(props.get("hubspot_owner_id"))
    opted_in = _safe_str(props.get("opted_in")).lower()
    marketable_status = _safe_str(props.get("hs_marketable_status")).lower()
    num_conversion_events = _to_int(props.get("num_conversion_events"))
    num_visits = _to_int(props.get("hs_analytics_num_visits"))

    stale_cutoff = now - timedelta(days=STALE_DAYS)
    engagement_cutoff = now - timedelta(days=ENGAGEMENT_DAYS)

    score = 0
    reasons: list[str] = []
    protected_reasons: list[str] = []

    # Negative signals / stale indicators
    if meaningful_engagement is None or meaningful_engagement < stale_cutoff:
        score += 4
        reasons.append("no meaningful engagement in 24+ months")

    if record_touch is None or record_touch < stale_cutoff:
        score += 2
        reasons.append("no record updates in 24+ months")

    if createdate is not None and createdate < stale_cutoff:
        score += 1
        reasons.append("contact created 24+ months ago")

    if not owner_id:
        score += 2
        reasons.append("no owner assigned")

    if num_conversion_events == 0:
        score += 1
        reasons.append("no form conversions")

    if num_visits == 0:
        score += 1
        reasons.append("no tracked web visits")

    if last_visit is None or last_visit < engagement_cutoff:
        score += 1
        reasons.append("no recent web visit in 12+ months")

    if (
        email_open is None
        and email_click is None
        and sales_email_open is None
        and sales_email_click is None
    ):
        score += 1
        reasons.append("no recorded email engagement")

    # Protective signals / keep indicators
    if lifecycle_stage in PROTECTED_LIFECYCLE_STAGES:
        score -= 5
        protected_reasons.append(f"protected lifecycle stage: {lifecycle_stage}")

    if owner_id:
        score -= 1
        protected_reasons.append("has owner")

    if meaningful_engagement is not None and meaningful_engagement >= stale_cutoff:
        score -= 4
        protected_reasons.append("recent meaningful engagement")

    if record_touch is not None and record_touch >= stale_cutoff:
        score -= 1
        protected_reasons.append("recent record update")

    if num_conversion_events > 0:
        score -= 1
        protected_reasons.append("has form conversion history")

    if num_visits > 0:
        score -= 1
        protected_reasons.append("has website visit history")

    if opted_in in {"true", "yes", "1"}:
        score -= 1
        protected_reasons.append("opted in")

    if marketable_status in {"marketable", "eligible"}:
        score -= 1
        protected_reasons.append(f"marketable status: {marketable_status}")

    classification = "active"
    if score >= 8:
        classification = "cleanup_candidate"
    elif score >= 5:
        classification = "stale"

    return {
        "id": str(contact.get("id", "") or ""),
        "firstname": _safe_str(props.get("firstname")),
        "lastname": _safe_str(props.get("lastname")),
        "email": _safe_str(props.get("email")),
        "lifecyclestage": _safe_str(props.get("lifecyclestage")),
        "owner_id": owner_id,
        "opted_in": _safe_str(props.get("opted_in")),
        "opt_in_source": _safe_str(props.get("opt_in_source")),
        "marketable_status": _safe_str(props.get("hs_marketable_status")),
        "score": score,
        "classification": classification,
        "reasons": "; ".join(reasons),
        "protected_reasons": "; ".join(protected_reasons),
        "createdate": createdate,
        "meaningful_engagement": meaningful_engagement,
        "record_touch": record_touch,
        "last_modified_raw": _safe_str(props.get("hs_lastmodifieddate")),
        "last_activity_raw": _safe_str(props.get("lastactivitydate")),
        "recent_conversion_raw": _safe_str(props.get("recent_conversion_date")),
        "last_visit_raw": _safe_str(props.get("hs_analytics_last_visit_timestamp")),
        "days_since_engagement": _days_since(meaningful_engagement, now),
        "days_since_record_touch": _days_since(record_touch, now),
    }


def main() -> None:
    print("Running stale contacts audit...")
    contacts = _hubspot_search_contacts(limit=MAX_CONTACTS)
    now = datetime.now(timezone.utc)

    analyzed: list[dict[str, Any]] = []
    stale_contacts: list[dict[str, Any]] = []
    cleanup_candidates: list[dict[str, Any]] = []

    for contact in contacts:
        result = _classify_contact(contact, now)
        analyzed.append(result)

        if result["classification"] == "stale":
            stale_contacts.append(result)
        elif result["classification"] == "cleanup_candidate":
            cleanup_candidates.append(result)

    flagged_contacts = stale_contacts + cleanup_candidates
    flagged_contacts.sort(key=lambda x: x["score"], reverse=True)

    rows: list[list[str]] = []
    for contact in flagged_contacts:
        rows.append(
            [
                contact["id"],
                contact["firstname"],
                contact["lastname"],
                contact["email"],
                contact["lifecyclestage"],
                contact["classification"],
                str(contact["score"]),
                contact["owner_id"],
                contact["opted_in"],
                contact["marketable_status"],
                contact["days_since_engagement"],
                contact["days_since_record_touch"],
                contact["reasons"],
                contact["protected_reasons"],
            ]
        )

    report_path = write_markdown_report(
        report_name="stale_contacts",
        title="Stale Contacts",
        summary_lines=[
            f"- Total contacts reviewed: **{len(contacts)}**",
            f"- Total flagged as stale: **{len(stale_contacts)}**",
            f"- Total flagged as cleanup candidates: **{len(cleanup_candidates)}**",
            f"- Stale threshold: score **5-7**",
            f"- Cleanup candidate threshold: score **8+**",
            f"- Logic: score is based on inactivity, weak engagement, no owner, and age of record, with protective reductions for lifecycle stage, recent engagement, opt-in, and marketable status.",
        ],
        table_headers=[
            "id",
            "firstname",
            "lastname",
            "email",
            "lifecyclestage",
            "classification",
            "score",
            "owner_id",
            "opted_in",
            "marketable_status",
            "days_since_engagement",
            "days_since_record_touch",
            "reasons",
            "protected_reasons",
        ],
        rows=rows,
    )

    print(f"Total reviewed: {len(contacts)}")
    print(f"Total stale: {len(stale_contacts)}")
    print(f"Total cleanup candidates: {len(cleanup_candidates)}")
    print(f"Report path: {report_path}")


if __name__ == "__main__":
    main()