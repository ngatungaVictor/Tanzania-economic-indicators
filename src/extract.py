"""
Extract stage: pulls raw indicator data from the World Bank API.

The API is public and needs no key:
https://api.worldbank.org/v2/country/{country}/indicator/{code}?format=json

We wrap each call with retries because public APIs occasionally
time out or rate-limit, and a real pipeline should not fall over
because of one flaky request.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from src.logger_config import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.worldbank.org/v2/country/{country}/indicator/{code}"
MAX_RETRIES = 3
BACKOFF_SECONDS = 2
TIMEOUT_SECONDS = 15


class ExtractionError(Exception):
    """Raised when an indicator cannot be fetched after all retries."""


def fetch_indicator(
    country_code: str,
    indicator_code: str,
    start_year: int,
    end_year: int,
) -> list[dict[str, Any]]:
    """
    Fetch a single indicator's full time series for a country.

    Returns the list of raw per-year records exactly as the API
    provides them (this is the "raw" layer -- transformation happens
    later in transform.py, deliberately kept separate).
    """
    url = BASE_URL.format(country=country_code, code=indicator_code)
    params = {
        "format": "json",
        "date": f"{start_year}:{end_year}",
        "per_page": 1000,
    }

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Fetching %s (attempt %d/%d)", indicator_code, attempt, MAX_RETRIES
            )
            response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()

            # World Bank API quirk: errors come back as HTTP 200 with
            # a message payload instead of the usual [metadata, data] list.
            if isinstance(payload, dict) or len(payload) < 2 or payload[1] is None:
                raise ExtractionError(
                    f"Unexpected/empty payload for {indicator_code}: {payload}"
                )

            records = payload[1]
            logger.info("Fetched %d records for %s", len(records), indicator_code)
            return records

        except (requests.RequestException, ExtractionError, ValueError) as exc:
            last_error = exc
            logger.warning("Attempt %d for %s failed: %s", attempt, indicator_code, exc)
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_SECONDS * attempt)  # simple linear backoff

    raise ExtractionError(
        f"Failed to fetch {indicator_code} after {MAX_RETRIES} attempts"
    ) from last_error


def fetch_all_indicators(
    country_code: str,
    indicators: list[dict[str, str]],
    start_year: int,
    end_year: int,
) -> dict[str, list[dict[str, Any]]]:
    """
    Fetch every indicator in the config, skipping (not crashing on)
    any single indicator that fails, so one bad indicator code
    doesn't take down the whole pipeline run.
    """
    results: dict[str, list[dict[str, Any]]] = {}

    for ind in indicators:
        code = ind["code"]
        name = ind["name"]
        try:
            records = fetch_indicator(country_code, code, start_year, end_year)
            results[name] = records
        except ExtractionError as exc:
            logger.error("Skipping indicator %s (%s): %s", name, code, exc)

    return results
