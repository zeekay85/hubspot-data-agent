import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_contacts_flagged_potential_duplicates import main as run_contact_duplicate_audit
from scripts.audit_companies_flagged_potential_duplicates import main as run_company_duplicate_audit


def main() -> None:
    print("HubSpot Data Quality Agent")
    print("--------------------------")

    audits = [
        ("Contacts Potential Duplicates", run_contact_duplicate_audit),
        ("Companies Potential Duplicates", run_company_duplicate_audit),
    ]

    for label, fn in audits:
        try:
            print(f"\nRunning audit: {label}")
            fn()
        except Exception as exc:
            print(f"❌ Audit failed: {label} — {exc}")

    print("\nAll audits completed.")


if __name__ == "__main__":
    main()