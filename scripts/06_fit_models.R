#!/usr/bin/env Rscript
# Step 06: fit the three GAMMs (mgcv::bam) and save them to outputs/models/.
#
#   iid_gamm.rds          primary formula with independent errors; only used to set the
#                         month-to-month carry-over (rho) and as the "no carry-over" robustness row
#   primary_gamm.rds      the reported model: drought curve + month curve + drought-month surface +
#                         unserved water curve + municipality baseline + year effect, AR(1) errors
#                         with rho = lag-1 correlation of the iid model's residuals (0.570)
#   interaction_gamm.rds  the second model: primary + drought-unserved water surface, same rho
#
# The repository ships these three files, so this step is skipped for any model that already
# exists. Pass --refit to fit all three again (about a minute).
#
# Usage (from the repository root):
#   Rscript scripts/06_fit_models.R [--refit]

file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
source(file.path(dirname(gsub("~+~", " ", sub("^--file=", "", file_arg), fixed = TRUE)), "_common.R"))

refit <- "--refit" %in% commandArgs(trailingOnly = TRUE)
need <- function(name) refit || !file.exists(file.path(MODELS, name))
if (!need("iid_gamm.rds") && !need("primary_gamm.rds") && !need("interaction_gamm.rds")) {
  message("All three models exist in outputs/models/; nothing to do (use --refit to fit again).")
  quit(save = "no")
}

df <- read_panel()
d <- model_data(df)
message(sprintf("Model data: %s municipality-months, %d municipalities, cap R$ %.0f",
                format(nrow(d), big.mark = ","), nlevels(d$IBGE_f), attr(d, "cap")))

if (need("iid_gamm.rds")) {
  message("Fitting the independent-errors model")
  iid <- fit_gamm(d, RHS_PRIMARY, rho = 0, seed = 20260724)
  save_model(iid, "iid_gamm.rds")
} else {
  iid <- readRDS(file.path(MODELS, "iid_gamm.rds"))
}
rho <- residual_rho(iid, d)
message(sprintf("Carry-over rho from the independent-errors residuals: %.4f", rho))

if (need("primary_gamm.rds")) {
  message("Fitting the primary GAMM")
  save_model(fit_gamm(d, RHS_PRIMARY, rho = rho, seed = 20260724), "primary_gamm.rds")
}
if (need("interaction_gamm.rds")) {
  message("Fitting the interaction GAMM")
  save_model(fit_gamm(d, RHS_INTERACTION, rho = rho, seed = 20260902), "interaction_gamm.rds")
}
