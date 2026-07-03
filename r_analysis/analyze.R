# ==============================================================================
# analyze.R
#
# Reads the SQLite database produced by the Python ETL pipeline and runs
# a statistical analysis pass: summary stats, correlation between
# indicators, and simple trend regressions (value ~ year) per indicator.
#
# Run from the project root:
#   Rscript r_analysis/analyze.R
#
# Requires: DBI, RSQLite, dplyr, tidyr, ggplot2, purrr
# Install once with:
#   install.packages(c("DBI", "RSQLite", "dplyr", "tidyr", "ggplot2", "purrr"))
# ==============================================================================

suppressMessages({
  library(DBI)
  library(RSQLite)
  library(dplyr)
  library(tidyr)
  library(purrr)
})

DB_PATH <- file.path("data", "tanzania_indicators.db")

if (!file.exists(DB_PATH)) {
  stop(
    "Database not found at ", DB_PATH,
    ". Run the Python pipeline first: python -m src.pipeline"
  )
}

con <- dbConnect(RSQLite::SQLite(), DB_PATH)
indicators_df <- dbReadTable(con, "indicators")
dbDisconnect(con)

cat("Loaded", nrow(indicators_df), "rows across",
    length(unique(indicators_df$indicator)), "indicators\n\n")

# ---- 1. Summary statistics per indicator -----------------------------------
summary_stats <- indicators_df %>%
  group_by(indicator) %>%
  summarise(
    n_years       = n(),
    first_year    = min(year),
    last_year     = max(year),
    mean_value    = mean(value, na.rm = TRUE),
    sd_value      = sd(value, na.rm = TRUE),
    min_value     = min(value, na.rm = TRUE),
    max_value     = max(value, na.rm = TRUE),
    mean_yoy_pct  = mean(yoy_change_pct, na.rm = TRUE),
    .groups = "drop"
  )

cat("=== Summary statistics ===\n")
print(summary_stats)

# ---- 2. Trend regression per indicator (value ~ year) -----------------------
# A simple linear trend gives an easily-interpretable "average annual
# change" figure per indicator, and the R^2 tells us how linear that
# trend really is (useful for flagging volatile indicators like inflation).
trend_results <- indicators_df %>%
  group_by(indicator) %>%
  group_modify(~ {
    if (nrow(.x) < 3) {
      return(tibble(slope = NA_real_, r_squared = NA_real_, p_value = NA_real_))
    }
    model <- lm(value ~ year, data = .x)
    s <- summary(model)
    tibble(
      slope     = round(unname(coef(model)["year"]), 4),
      r_squared = round(s$r.squared, 4),
      p_value   = round(coef(s)["year", "Pr(>|t|)"], 4)
    )
  }) %>%
  ungroup()

cat("\n=== Trend regressions (value ~ year) ===\n")
print(trend_results)

# ---- 3. Correlation matrix across indicators (wide pivot on year) ----------
wide_df <- indicators_df %>%
  select(year, indicator, value) %>%
  pivot_wider(names_from = indicator, values_from = value)

numeric_cols <- wide_df %>% select(-year)
cor_matrix <- cor(numeric_cols, use = "pairwise.complete.obs")

cat("\n=== Correlation matrix ===\n")
print(round(cor_matrix, 2))

# ---- 4. Persist results for the report to reuse -----------------------------
dir.create("data", showWarnings = FALSE)
saveRDS(
  list(
    raw = indicators_df,
    summary_stats = summary_stats,
    trend_results = trend_results,
    cor_matrix = cor_matrix
  ),
  file.path("data", "analysis_results.rds")
)

cat("\nSaved analysis results to data/analysis_results.rds\n")
cat("Next: render the report with r_analysis/report.Rmd\n")
