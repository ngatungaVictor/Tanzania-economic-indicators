"""
Unit tests for src/transform.py.

These run entirely offline against fixture data shaped like real
World Bank API responses, so they can run in CI without network access.
"""

import pandas as pd
import pytest

from src.transform import add_derived_metrics, transform_all, transform_indicator

SAMPLE_RAW_RECORDS = [
    {"countryiso3code": "TZA", "date": "2022", "value": 71.4},
    {"countryiso3code": "TZA", "date": "2021", "value": 67.8},
    {"countryiso3code": "TZA", "date": "2020", "value": None},  # gap: should be dropped
    {"countryiso3code": "TZA", "date": "2019", "value": 63.2},
]


def test_transform_indicator_drops_null_values():
    df = transform_indicator("gdp_current_usd", SAMPLE_RAW_RECORDS)
    assert len(df) == 3  # the None-value record must be dropped
    assert df["value"].isnull().sum() == 0


def test_transform_indicator_sorts_by_year_ascending():
    df = transform_indicator("gdp_current_usd", SAMPLE_RAW_RECORDS)
    assert list(df["year"]) == [2019, 2021, 2022]


def test_transform_indicator_empty_input_returns_empty_frame():
    df = transform_indicator("gdp_current_usd", [])
    assert df.empty
    assert list(df.columns) == ["country_code", "year", "indicator", "value"]


def test_transform_all_combines_multiple_indicators():
    raw_data = {
        "gdp_current_usd": SAMPLE_RAW_RECORDS,
        "inflation_pct": [
            {"countryiso3code": "TZA", "date": "2022", "value": 4.3},
            {"countryiso3code": "TZA", "date": "2021", "value": 3.7},
        ],
    }
    df = transform_all(raw_data)
    assert set(df["indicator"].unique()) == {"gdp_current_usd", "inflation_pct"}
    assert len(df) == 5  # 3 gdp rows + 2 inflation rows
    assert "yoy_change_pct" in df.columns


def test_add_derived_metrics_computes_yoy_change():
    df = pd.DataFrame(
        {
            "indicator": ["x", "x", "x"],
            "year": [2020, 2021, 2022],
            "value": [100.0, 110.0, 121.0],
        }
    )
    result = add_derived_metrics(df)
    # first year in each indicator group has no prior year -> NaN
    assert pd.isna(result.iloc[0]["yoy_change_pct"])
    assert result.iloc[1]["yoy_change_pct"] == pytest.approx(10.0)
    assert result.iloc[2]["yoy_change_pct"] == pytest.approx(10.0)


def test_add_derived_metrics_does_not_leak_across_indicators():
    df = pd.DataFrame(
        {
            "indicator": ["x", "x", "y", "y"],
            "year": [2020, 2021, 2020, 2021],
            "value": [100.0, 200.0, 50.0, 50.0],
        }
    )
    result = add_derived_metrics(df)
    y_2021 = result[(result["indicator"] == "y") & (result["year"] == 2021)]
    assert y_2021["yoy_change_pct"].iloc[0] == pytest.approx(0.0)
