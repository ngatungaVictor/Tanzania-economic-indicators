"""
Load stage: persists the tidy DataFrame to SQLite (for R / SQL
consumers) and to CSV (for quick inspection / spreadsheet users).

SQLite is chosen over a CSV-only approach on purpose: it lets R
connect with a normal DBI connection, supports simple querying,
and is a single portable file -- no server setup needed, which
matters for a portfolio project someone else has to be able to run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.logger_config import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "tanzania_indicators.db"
CSV_PATH = DATA_DIR / "tanzania_indicators.csv"
TABLE_NAME = "indicators"


def load_to_sqlite(df: pd.DataFrame, db_path: Path = DB_PATH) -> None:
    if df.empty:
        logger.warning("Skipping SQLite load -- DataFrame is empty")
        return

    conn = sqlite3.connect(db_path)
    try:
        df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_indicator_year "
            f"ON {TABLE_NAME}(indicator, year)"
        )
        conn.commit()
        logger.info("Loaded %d rows into %s (table: %s)", len(df), db_path, TABLE_NAME)
    finally:
        conn.close()


def load_to_csv(df: pd.DataFrame, csv_path: Path = CSV_PATH) -> None:
    if df.empty:
        logger.warning("Skipping CSV load -- DataFrame is empty")
        return

    df.to_csv(csv_path, index=False)
    logger.info("Wrote %d rows to %s", len(df), csv_path)


def load_all(df: pd.DataFrame) -> None:
    load_to_sqlite(df)
    load_to_csv(df)
