import os
from dotenv import load_dotenv

load_dotenv()


def get_hubspot_token() -> str:
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")
    if not token:
        raise ValueError(
            "HUBSPOT_PRIVATE_APP_TOKEN is not set. Please set it in your .env file."
        )
    return token


def get_contact_duplicate_flag_property() -> str:
    prop = os.getenv("HS_POTENTIAL_DUPLICATE_CONTACT_PROP") or os.getenv(
        "CONTACT_DUPLICATE_FLAG_PROPERTY", "potential_duplicate"
    )
    if not prop:
        raise ValueError(
            "Contact duplicate property not set. "
            "Set HS_POTENTIAL_DUPLICATE_CONTACT_PROP in your .env file."
        )
    return prop


def get_company_duplicate_flag_property() -> str:
    prop = os.getenv("HS_POTENTIAL_DUPLICATE_COMPANY_PROP") or os.getenv(
        "COMPANY_DUPLICATE_FLAG_PROPERTY", "potential_duplicate"
    )
    if not prop:
        raise ValueError(
            "Company duplicate property not set. "
            "Set HS_POTENTIAL_DUPLICATE_COMPANY_PROP in your .env file."
        )
    return prop


def get_contact_lead_source_property() -> str:
    prop = os.getenv("HS_CONTACT_LEAD_SOURCE_PROPERTY") or os.getenv(
        "CONTACT_LEAD_SOURCE_PROPERTY", ""
    )
    if not prop:
        raise ValueError(
            "Contact lead source property is not configured. "
            "Set HS_CONTACT_LEAD_SOURCE_PROPERTY (or CONTACT_LEAD_SOURCE_PROPERTY) in your .env file."
        )
    return prop