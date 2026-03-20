from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from src.hubspot_client import HubSpotCompanyReader
from src.name_normalizer import build_search_queries, normalize_company_name, normalize_text

LOGGER = logging.getLogger(__name__)

OUTPUT_COLUMNS = [
    "Input Company Name",
    "Matched HubSpot Company Name",
    "Domain",
    "Owner Name",
    "Owner Email",
    "Match Score",
    "Match Confidence",
    "Match Type",
]


@dataclass(frozen=True)
class MatchConfig:
    score_threshold: int = 75
    high_confidence_threshold: int = 90
    medium_confidence_threshold: int = 75
    search_limit: int = 10
    include_top_candidates_in_logs: bool = True


class CompanyMatcher:
    def __init__(
        self,
        hubspot_reader: HubSpotCompanyReader | None = None,
        config: MatchConfig | None = None,
    ) -> None:
        self.hubspot_reader = hubspot_reader or HubSpotCompanyReader()
        self.config = config or MatchConfig()

    def match_companies(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        if "Company Name" not in dataframe.columns:
            raise ValueError('Input file must contain a "Company Name" column.')

        rows: list[dict[str, Any]] = []
        for row_number, (_, row) in enumerate(dataframe.iterrows(), start=2):
            try:
                rows.append(self._build_match_row(row))
            except Exception as exc:  # pragma: no cover - row-level safety
                LOGGER.exception(
                    "Failed to process row %s for company %r: %s",
                    row_number,
                    row.get("Company Name"),
                    exc,
                )
                rows.append(self._empty_match_row(row.get("Company Name")))

        return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)

    def _build_match_row(self, row: pd.Series) -> dict[str, Any]:
        input_name = "" if pd.isna(row.get("Company Name")) else str(row.get("Company Name")).strip()
        input_country = "" if pd.isna(row.get("Country")) else str(row.get("Country")).strip()
        if not input_name:
            LOGGER.warning("Encountered blank company name; returning no match.")
            return self._empty_match_row(input_name)

        candidates = self._fetch_candidates(input_name)
        if not candidates:
            LOGGER.info("No HubSpot candidates found for %r.", input_name)
            return self._empty_match_row(input_name)

        exact_name_matches = self._find_exact_name_matches(input_name, candidates)
        if exact_name_matches:
            country_exact_match = self._find_country_exact_match(exact_name_matches, input_country)
            if country_exact_match is not None:
                return self._matched_row(input_name, country_exact_match, 100, "High", "Exact")

            exact_match = self._pick_best_exact_match(exact_name_matches)
            return self._matched_row(input_name, exact_match, 100, "High", "Exact")

        scored_candidates = self._score_candidates(input_name, candidates)
        best_candidate, best_score = scored_candidates[0]
        if best_score < self.config.score_threshold:
            self._log_low_confidence_candidates(input_name, scored_candidates)
            return self._empty_match_row(input_name, score=best_score)

        return self._matched_row(
            input_name,
            best_candidate,
            best_score,
            self._determine_confidence(best_score),
            "Fuzzy",
        )

    def _fetch_candidates(self, input_name: str) -> list[dict[str, Any]]:
        deduped_candidates: dict[str, dict[str, Any]] = {}

        for query in build_search_queries(input_name):
            LOGGER.debug("Searching HubSpot for %r using query variant %r.", input_name, query)
            for candidate in self.hubspot_reader.search_companies_by_name(
                query,
                limit=self.config.search_limit,
            ):
                candidate_id = str(candidate.get("id", "") or "")
                if candidate_id:
                    deduped_candidates[candidate_id] = candidate

        return list(deduped_candidates.values())

    def _find_exact_name_matches(
        self,
        input_name: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized_input = normalize_company_name(input_name)
        if not normalized_input:
            return []

        exact_matches = []
        for candidate in candidates:
            candidate_name = str(candidate.get("properties", {}).get("name", "") or "").strip()
            if normalize_company_name(candidate_name) == normalized_input:
                exact_matches.append(candidate)
        return exact_matches

    def _find_country_exact_match(
        self,
        candidates: list[dict[str, Any]],
        input_country: str,
    ) -> dict[str, Any] | None:
        normalized_country = normalize_text(input_country)
        if not normalized_country:
            return None

        country_matches = []
        for candidate in candidates:
            candidate_country = str(candidate.get("properties", {}).get("country", "") or "").strip()
            if normalize_text(candidate_country) == normalized_country:
                country_matches.append(candidate)

        if not country_matches:
            return None
        return self._pick_best_exact_match(country_matches)

    def _pick_best_exact_match(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        return max(
            candidates,
            key=lambda candidate: self._parse_hubspot_datetime(
                candidate.get("properties", {}).get("hs_lastmodifieddate")
            ),
        )

    def _score_candidates(
        self,
        input_name: str,
        candidates: list[dict[str, Any]],
    ) -> list[tuple[dict[str, Any], int]]:
        normalized_input = normalize_company_name(input_name)
        scored_candidates: list[tuple[dict[str, Any], int]] = []

        for candidate in candidates:
            candidate_name = str(candidate.get("properties", {}).get("name", "") or "").strip()
            normalized_candidate = normalize_company_name(candidate_name)
            score = max(
                fuzz.ratio(normalized_input, normalized_candidate),
                fuzz.token_sort_ratio(normalized_input, normalized_candidate),
                fuzz.partial_ratio(normalized_input, normalized_candidate),
            )
            scored_candidates.append((candidate, int(round(score))))

        scored_candidates.sort(
            key=lambda item: (
                item[1],
                self._parse_hubspot_datetime(item[0].get("properties", {}).get("hs_lastmodifieddate")),
            ),
            reverse=True,
        )
        return scored_candidates

    def _matched_row(
        self,
        input_name: str,
        candidate: dict[str, Any],
        score: int,
        confidence: str,
        match_type: str,
    ) -> dict[str, Any]:
        properties = candidate.get("properties", {})
        owner = self.hubspot_reader.get_owner(properties.get("hubspot_owner_id"))
        return {
            "Input Company Name": input_name,
            "Matched HubSpot Company Name": str(properties.get("name", "") or "").strip(),
            "Domain": str(properties.get("domain", "") or "").strip(),
            "Owner Name": owner["name"],
            "Owner Email": owner["email"],
            "Match Score": score,
            "Match Confidence": confidence,
            "Match Type": match_type,
        }

    def _log_low_confidence_candidates(
        self,
        input_name: str,
        scored_candidates: list[tuple[dict[str, Any], int]],
    ) -> None:
        if not self.config.include_top_candidates_in_logs:
            return

        top_candidates = []
        for candidate, score in scored_candidates[:2]:
            properties = candidate.get("properties", {})
            top_candidates.append(
                {
                    "name": str(properties.get("name", "") or "").strip(),
                    "country": str(properties.get("country", "") or "").strip(),
                    "score": score,
                }
            )

        LOGGER.info(
            "No match returned for %r because best score %s is below threshold %s. Top candidates: %s",
            input_name,
            scored_candidates[0][1] if scored_candidates else 0,
            self.config.score_threshold,
            top_candidates,
        )

    def _determine_confidence(self, score: int) -> str:
        if score >= self.config.high_confidence_threshold:
            return "High"
        if score >= self.config.medium_confidence_threshold:
            return "Medium"
        return "Low"

    def _empty_match_row(self, company_name: Any, score: int = 0) -> dict[str, Any]:
        input_name = "" if pd.isna(company_name) else str(company_name).strip()
        return {
            "Input Company Name": input_name,
            "Matched HubSpot Company Name": "",
            "Domain": "",
            "Owner Name": "",
            "Owner Email": "",
            "Match Score": score,
            "Match Confidence": self._determine_confidence(score),
            "Match Type": "No Match",
        }

    def _parse_hubspot_datetime(self, value: Any) -> datetime:
        if value in (None, ""):
            return datetime.min.replace(tzinfo=timezone.utc)

        text = str(value).strip()
        if text.isdigit():
            raw = int(text)
            if raw > 10_000_000_000:
                return datetime.fromtimestamp(raw / 1000, tz=timezone.utc)
            return datetime.fromtimestamp(raw, tz=timezone.utc)

        normalized = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
