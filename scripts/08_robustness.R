#!/usr/bin/env Rscript
# Step 08: robustness checks (Annex B, Table B.1).
#
# The primary GAMM is refitted with one choice changed at a time, keeping the formula and the
# month-to-month carry-over of the reported model. For each version the table gives the standing
# difference (unserved water p90 vs p10, with a 95% interval from 2,000 draws) and the range of
# the drought curve between the 2nd and 98th percentile of SPEI-12. The SPEI reference period is
# not varied.
#
#   None (reported model)            primary_gamm.rds, no refit
#   Drought one month earlier        SPEI-12 at lag 1
#   Cap at 95th / 99.5th percentile  spending capped at another quantile
#   Spending per 1,000 residents     outcome log(1 + capped spending per 1,000 residents)
#   Water loss added                 extra term s(water_loss_pct)
#   No carry-over                    iid_gamm.rds, no refit
#
# Output: outputs/tables/table_B_1_robustness.csv
#
# Usage (from the repository root, five refits, about a minute):
#   Rscript scripts/08_robustness.R

file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
source(file.path(dirname(gsub("~+~", " ", sub("^--file=", "", file_arg), fixed = TRUE)), "_common.R"))

primary <- readRDS(file.path(MODELS, "primary_gamm.rds"))
rho <- primary$AR1.rho
df <- read_panel()

summarise <- function(change, m, d) {
  sd <- standing_difference(m, d)
  dr <- drought_range(m, d)
  data.frame(change = change, municipality_months = nrow(d),
             standing_difference = sd$factor, interval_low = sd$lo, interval_high = sd$hi,
             drought_range = dr$range, dry_minus_wet = dr$f_p02 - dr$f_p98)
}
refit <- function(change, rhs = RHS_PRIMARY, ...) {
  message("Refitting: ", change)
  d <- model_data(df, ...)
  summarise(change, fit_gamm(d, rhs, rho = rho, seed = 20260903), d)
}

rows <- list(
  summarise("None (reported model)", primary, primary$model),
  refit("Drought one month earlier", lag = 1L),
  refit("Cap at 95th percentile", q = 0.95),
  refit("Cap at 99.5th percentile", q = 0.995),
  refit("Spending per 1,000 residents", outcome = "cost_per_1k"),
  refit("Water loss added", rhs = append(RHS_PRIMARY, "s(water_loss_pct, k = 8, bs = 'tp')", after = 4),
        needs_loss = TRUE),
  { iid <- readRDS(file.path(MODELS, "iid_gamm.rds")); summarise("No carry-over", iid, iid$model) }
)
out <- do.call(rbind, rows)
write_table(out, "table_B_1_robustness.csv")
print(out, row.names = FALSE, digits = 3)
