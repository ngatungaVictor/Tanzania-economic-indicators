"""
Transform stage: converts raw World Bank JSON records into a single
tidy pandas DataFrame ready to load into the database.

Tidy shape:
    country_code | year | indicator | value

This "long" format is deliberate -- it's the easiest shape for both
SQL storage and downstream statistical work in R (one row per
observation, easy to pivot/filter/join).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.logger_config import get_logger

logger = get_logger(__name__)


def transform_indicator(
    indicator_name: str, raw_records: list[dict[str, Any]]
) -> pd.DataFrame:
    """Turn one indicator's raw records into a tidy long-format frame."""
    if not raw_records:
        logger.warning("No records to transform for %s", indicator_name)
        return pd.DataFrame(columns=["country_code", "year", "indicator", "value"])

    rows = []
    for rec in raw_records:
        value = rec.get("value")
        year = rec.get("date")
        country = rec.get("countryiso3code")

        if value is None or year is None:
            continue  # World Bank leaves gaps for years with no data

        rows.append(
            {
                "country_code": country,
                "year": int(year),
                "indicator": indicator_name,
                "value": float(value),
            }
        )

    df = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    logger.info("Transformed %s: %d clean rows (of %d raw)", indicator_name, len(df), len(raw_records))
    return df


def transform_all(raw_data: dict[str, list[dict[str, Any]]]) -> pd.DataFrame:
    """Combine every indicator's tidy frame into one long DataFrame."""
    frames = [
        transform_indicator(name, records) for name, records in raw_data.items()
    ]
    frames = [f for f in frames if not f.empty]

    if not frames:
        logger.error("Transform produced no data at all -- check the extract stage")
        return pd.DataFrame(columns=["country_code", "year", "indicator", "value"])

    combined = pd.concat(frames, ignore_index=True)
    combined = add_derived_metrics(combined)
    return combined


def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a year-over-year % change column per indicator.

    This is a small but genuinely useful derived metric: it's the
    kind of transform step that shows judgement rather than just
    passing data through untouched.
    """
    df = df.sort_values(["indicator", "year"]).copy()
    df["yoy_change_pct"] = (
        df.groupby("indicator")["value"].pct_change() * 100
    ).round(2)
    return df
