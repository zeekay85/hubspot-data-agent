from __future__ import annotations

import re
import string
import unicodedata

COMPANY_SUFFIXES = {
    "co",
    "company",
    "corp",
    "inc",
    "llc",
    "ltd",
}

PUNCTUATION_TABLE = str.maketrans({char: " " for char in string.punctuation})
MULTISPACE_PATTERN = re.compile(r"\s+")


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""

    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = text.translate(PUNCTUATION_TABLE)
    return MULTISPACE_PATTERN.sub(" ", text).strip()


def normalize_company_name(value: str | None) -> str:
    """Normalize a company name for more reliable matching."""
    normalized = normalize_text(value)
    tokens = [token for token in normalized.split() if token]

    while tokens and tokens[-1] in COMPANY_SUFFIXES:
        tokens.pop()

    return " ".join(tokens).strip()


def company_name_tokens(value: str | None) -> list[str]:
    normalized = normalize_company_name(value)
    return [token for token in normalized.split() if token]


def company_name_compact(value: str | None) -> str:
    return "".join(company_name_tokens(value))


def company_name_acronym(value: str | None) -> str:
    tokens = company_name_tokens(value)
    if len(tokens) <= 1:
        return ""
    return "".join(token[0] for token in tokens if token)


def build_search_queries(value: str | None) -> list[str]:
    variants = [
        str(value or "").strip(),
        normalize_company_name(value),
        company_name_compact(value),
        company_name_acronym(value),
    ]

    seen: set[str] = set()
    queries: list[str] = []
    for variant in variants:
        query = (variant or "").strip()
        if not query:
            continue
        lowered = query.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        queries.append(query)
    return queries
