"""
Pipeline orchestrator: the single entry point that runs
extract -> transform -> load end to end.

Run it with:
    python -m src.pipeline

Or import run_pipeline() from another script / a scheduler.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import yaml

from src.extract import fetch_all_indicators
from src.load import load_all
from src.logger_config import get_logger
from src.transform import transform_all

logger = get_logger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "indicators.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_pipeline() -> int:
    """Run the full ETL pipeline. Returns an exit code (0 = success)."""
    start = time.time()
    logger.info("=== Pipeline run started ===")

    try:
        config = load_config()
    except Exception:
        logger.exception("Failed to load config -- aborting")
        return 1

    country = config["country_code"]
    start_year = config["start_year"]
    end_year = config["end_year"]
    indicators = config["indicators"]

    logger.info(
        "Fetching %d indicators for %s (%d-%d)",
        len(indicators), country, start_year, end_year,
    )

    raw_data = fetch_all_indicators(country, indicators, start_year, end_year)

    if not raw_data:
        logger.error("No indicators were successfully fetched -- aborting")
        return 1

    tidy_df = transform_all(raw_data)

    if tidy_df.empty:
        logger.error("Transform stage produced no usable data -- aborting")
        return 1

    load_all(tidy_df)

    elapsed = time.time() - start
    logger.info(
        "=== Pipeline run finished in %.1fs | %d rows | %d/%d indicators succeeded ===",
        elapsed, len(tidy_df), len(raw_data), len(indicators),
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_pipeline())
