from dataclasses import dataclass


@dataclass(frozen=True)
class AuditDefinition:
    key: str
    label: str
    report_prefix: str
    count_markers: tuple[str, ...]


AUDIT_DEFINITIONS: tuple[AuditDefinition, ...] = (
    AuditDefinition(
        key="contacts_flagged_potential_duplicates",
        label="Contacts Potential Duplicates",
        report_prefix="contacts_flagged_potential_duplicates",
        count_markers=("Total flagged contacts",),
    ),
    AuditDefinition(
        key="companies_flagged_potential_duplicates",
        label="Companies Potential Duplicates",
        report_prefix="companies_flagged_potential_duplicates",
        count_markers=("Total flagged companies",),
    ),
    AuditDefinition(
        key="contacts_without_company",
        label="Contacts Without Company",
        report_prefix="contacts_without_company",
        count_markers=("Total contacts without company",),
    ),
    AuditDefinition(
        key="contacts_missing_lead_source",
        label="Contacts Missing Lead Source",
        report_prefix="contacts_missing_lead_source",
        count_markers=("Total contacts missing lead source",),
    ),
    AuditDefinition(
        key="stale_contacts",
        label="Stale Contacts",
        report_prefix="stale_contacts",
        count_markers=(
            "Total flagged as stale",
            "Total flagged as cleanup candidates",
        ),
    ),
    AuditDefinition(
        key="duplicate_companies_by_domain",
        label="Duplicate Companies by Domain",
        report_prefix="duplicate_companies_by_domain",
        count_markers=("Total companies in duplicate groups",),
    ),
)


AUDIT_DEFINITIONS_BY_KEY = {definition.key: definition for definition in AUDIT_DEFINITIONS}
