import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_companies_flagged_potential_duplicates import (
    main as run_company_duplicate_audit,
)
from scripts.audit_contacts_flagged_potential_duplicates import (
    main as run_contact_duplicate_audit,
)
from scripts.audit_contacts_missing_lead_source import (
    main as run_contacts_missing_lead_source_audit,
)
from scripts.audit_contacts_without_company import main as run_contacts_without_company_audit
from scripts.audit_duplicate_companies_by_domain import (
    main as run_duplicate_companies_by_domain_audit,
)
from scripts.audit_stale_contacts import main as run_stale_contacts_audit
from scripts.build_data_quality_dashboard import build_dashboard


def main() -> None:
    print("HubSpot Data Quality Agent")
    print("--------------------------")

    audits = [
        ("Contacts Potential Duplicates", run_contact_duplicate_audit),
        ("Companies Potential Duplicates", run_company_duplicate_audit),
        ("Contacts Without Company", run_contacts_without_company_audit),
        ("Contacts Missing Lead Source", run_contacts_missing_lead_source_audit),
        ("Stale Contacts", run_stale_contacts_audit),
        ("Duplicate Companies by Domain", run_duplicate_companies_by_domain_audit),
    ]

    for index, (label, fn) in enumerate(audits, start=1):
        try:
            print(f"\n[{index}/{len(audits)}] Running audit: {label}")
            fn()
            print(f"[{index}/{len(audits)}] Completed audit: {label}")
        except Exception as exc:
            print(f"[{index}/{len(audits)}] Audit failed: {label} - {exc}")

    dashboard_path = build_dashboard()
    print(f"\nAll audits completed. Dashboard report path: {dashboard_path}")


if __name__ == "__main__":
    main()
