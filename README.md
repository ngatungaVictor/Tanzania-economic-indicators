# Tanzania Economic Indicators — Automated ETL Pipeline

An end-to-end, scheduled ETL pipeline that pulls economic and development
indicators for Tanzania from the [World Bank Open Data API](https://data.worldbank.org/),
cleans and transforms them in Python, loads them into SQLite, and hands off
to R for statistical analysis and an auto-generated report.

Built to demonstrate a full automation pipeline — not just a one-off script —
including scheduled execution via GitHub Actions.

## Architecture

```
World Bank API
      │
      ▼
┌─────────────┐     ┌───────────────┐     ┌────────────┐
│  extract.py │ ──▶ │ transform.py  │ ──▶ │  load.py   │
│  (fetch +   │     │ (clean, tidy, │     │ (SQLite +  │
│   retries)  │     │  derive YoY%) │     │  CSV)      │
└─────────────┘     └───────────────┘     └────────────┘
                                                  │
                                                  ▼
                                     data/tanzania_indicators.db
                                                  │
                                     ┌────────────┴────────────┐
                                     ▼                         ▼
                        r_analysis/analyze.R +        dashboard/app.py
                        report.Rmd                    (Streamlit + Plotly,
                        (summary stats, trend          interactive filters,
                         regressions, correlations,    KPIs, live charts)
                         auto-rendered report)
```

Orchestrated by `src/pipeline.py`, and scheduled weekly via
`.github/workflows/etl_schedule.yml`.

## Why this stack

- **Python for extraction/transformation**: robust HTTP handling,
  pandas for tidy-data manipulation, easy to schedule and test.
- **SQLite as the handoff layer**: no server to manage, a single portable
  file, and both Python and R can query it natively.
- **R for analysis/reporting**: R Markdown makes "data changes → report
  updates automatically" trivial, and it's a natural fit for the
  statistical side (trend regressions, correlation analysis).
- **GitHub Actions for scheduling**: free, version-controlled, and the
  commit history of `data/` becomes a visible audit trail of every run.
- **Streamlit + Plotly for the dashboard**: reads the same SQLite file the
  pipeline writes, so there's no separate data-prep step — refresh the
  pipeline, refresh the page, the dashboard updates.

## Project structure

```
tanzania-etl-pipeline/
├── config/indicators.yaml       # which indicators to track (edit this to add more)
├── src/
│   ├── extract.py                # World Bank API calls, with retry logic
│   ├── transform.py               # raw JSON -> tidy long-format DataFrame
│   ├── load.py                    # writes to SQLite + CSV
│   ├── pipeline.py                # orchestrates the full run
│   └── logger_config.py           # shared logging setup
├── r_analysis/
│   ├── analyze.R                  # summary stats, trend regressions, correlations
│   └── report.Rmd                 # auto-rendered HTML report with charts
├── dashboard/app.py                # Streamlit dashboard (filters, KPIs, live charts)
├── tests/test_transform.py        # offline unit tests (fixture-based)
├── .github/workflows/etl_schedule.yml   # weekly scheduled run
├── data/                          # generated: .db, .csv, analysis_results.rds
└── logs/pipeline.log              # generated: run history
```

## Setup

### Python side

```bash
pip install -r requirements.txt
python -m pytest tests/ -v      # run the offline unit tests
python -m src.pipeline           # run the full pipeline (fetches live data)
```

### R side

```r
install.packages(c("DBI", "RSQLite", "dplyr", "tidyr", "ggplot2", "purrr"))
```

```bash
Rscript r_analysis/analyze.R
Rscript -e "rmarkdown::render('r_analysis/report.Rmd')"
```

This produces `r_analysis/report.html` with charts and tables built from
whatever is currently in `data/tanzania_indicators.db`.

### Dashboard

```bash
streamlit run dashboard/app.py
```

Opens an interactive dashboard at `http://localhost:8501` with:
- KPI cards showing the latest value + YoY change for selected indicators
- A trend chart and a year-over-year change chart, filterable by indicator and year range
- A raw data table for the currently filtered selection

It reads directly from `data/tanzania_indicators.db`, so re-running the
pipeline and refreshing the page shows updated data with no extra steps.

## Automation

The pipeline runs automatically every Monday via GitHub Actions
(`.github/workflows/etl_schedule.yml`), re-fetches all indicators, re-runs
the tests, and commits the refreshed data back to the repo. You can also
trigger a run manually from the Actions tab (`workflow_dispatch`).

## Extending it

- Add indicators by editing `config/indicators.yaml` — no code changes needed.
- Swap the country code in the same file to point this at any World Bank
  member country.
- The tidy long-format schema (`country_code, year, indicator, value,
  yoy_change_pct`) is intentionally generic, so new indicators slot in
  without any pipeline changes.

## Data source

World Bank Open Data (CC BY-4.0): https://data.worldbank.org/country/tanzania
