"""
Interactive dashboard for the Tanzania economic indicators pipeline.

Reads straight from data/tanzania_indicators.db -- the exact file the
Python ETL pipeline produces -- so the dashboard always reflects
whatever the most recent pipeline run loaded, with no separate data
prep step.

Run with:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tanzania_indicators.db"

st.set_page_config(
    page_title="Tanzania Economic Indicators",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(ttl=3600)
def load_data(db_path: Path) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM indicators ORDER BY indicator, year", conn)
    conn.close()
    return df


def indicator_label(name: str) -> str:
    """Turn a snake_case indicator name into a readable label."""
    return name.replace("_", " ").replace("pct", "%").title()


# ---- Load data ---------------------------------------------------------------
if not DB_PATH.exists():
    st.error(
        f"No database found at `{DB_PATH}`.\n\n"
        "Run the pipeline first: `python -m src.pipeline`"
    )
    st.stop()

df = load_data(DB_PATH)

# ---- Header ---------------------------------------------------------------
st.title("🇹🇿 Tanzania Economic Indicators")
st.caption(
    "Live from the automated ETL pipeline · Source: World Bank Open Data · "
    f"Data covers {df['year'].min()}–{df['year'].max()}"
)

# ---- Sidebar controls ---------------------------------------------------------------
st.sidebar.header("Filters")

all_indicators = sorted(df["indicator"].unique())
default_selection = [i for i in ["gdp_growth_pct", "inflation_pct"] if i in all_indicators] or all_indicators[:2]

selected_indicators = st.sidebar.multiselect(
    "Indicators to compare",
    options=all_indicators,
    default=default_selection,
    format_func=indicator_label,
)

year_min, year_max = int(df["year"].min()), int(df["year"].max())
year_range = st.sidebar.slider(
    "Year range",
    min_value=year_min,
    max_value=year_max,
    value=(year_min, year_max),
)

filtered = df[
    (df["indicator"].isin(selected_indicators))
    & (df["year"].between(*year_range))
]

# ---- KPI row: latest value per selected indicator ------------------------------
if selected_indicators:
    cols = st.columns(len(selected_indicators))
    for col, ind in zip(cols, selected_indicators):
        ind_df = df[df["indicator"] == ind].sort_values("year")
        if ind_df.empty:
            continue
        latest = ind_df.iloc[-1]
        delta = latest["yoy_change_pct"]
        col.metric(
            label=f"{indicator_label(ind)} ({int(latest['year'])})",
            value=f"{latest['value']:,.2f}",
            delta=f"{delta:+.2f}% YoY" if pd.notna(delta) else None,
        )

st.divider()

# ---- Main trend chart ---------------------------------------------------------------
if filtered.empty:
    st.info("Select at least one indicator from the sidebar to see charts.")
else:
    fig = px.line(
        filtered,
        x="year",
        y="value",
        color="indicator",
        markers=True,
        labels={"value": "Value", "year": "Year", "indicator": "Indicator"},
        title="Indicator trends over time",
    )
    fig.for_each_trace(lambda t: t.update(name=indicator_label(t.name)))
    fig.update_layout(legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

    # ---- Year-over-year change chart ---------------------------------------
    yoy_fig = px.bar(
        filtered.dropna(subset=["yoy_change_pct"]),
        x="year",
        y="yoy_change_pct",
        color="indicator",
        barmode="group",
        labels={"yoy_change_pct": "YoY change (%)", "year": "Year"},
        title="Year-over-year change (%)",
    )
    yoy_fig.for_each_trace(lambda t: t.update(name=indicator_label(t.name)))
    yoy_fig.update_layout(legend_title_text="")
    st.plotly_chart(yoy_fig, use_container_width=True)

    # ---- Raw data table ---------------------------------------------------------------
    with st.expander("View underlying data"):
        display_df = filtered.copy()
        display_df["indicator"] = display_df["indicator"].map(indicator_label)
        st.dataframe(
            display_df.sort_values(["indicator", "year"]),
            use_container_width=True,
            hide_index=True,
        )

st.divider()
st.caption(
    "Dashboard reads directly from the pipeline's SQLite output. "
    "Re-run the pipeline and refresh this page to see updated data."
)
