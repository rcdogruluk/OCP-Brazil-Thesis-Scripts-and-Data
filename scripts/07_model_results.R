#!/usr/bin/env Rscript
# Step 07: every result of Chapter 3 from the saved models (no refitting).
#
# Outputs (outputs/tables/):
#   table_3_1_term_shares.csv           Table 3.1: mean |contribution| of the four terms, as shares
#   table_3_2_model_diagnostics.csv     Table 3.2: fit and error of the model and of each term
#   drought_month_response.csv          dry-to-wet difference of the combined drought-month
#                                       contribution in each calendar month
#   drought_month_surfaces.csv          the two surfaces of Figure 3.1 (blank = too far from data)
#   interaction_curves.csv              Figure 3.3: drought + unserved water contribution of the
#                                       second model at the 10th, 50th and 90th percentile
#   results_numbers.csv                 every other number Chapter 3 quotes
# Outputs (outputs/figures/):
#   fig_3_1_drought_and_month_terms.png, fig_3_2_unserved_water_term.png,
#   fig_3_3_drought_by_unserved.png
#
# Usage (from the repository root, about two minutes):
#   Rscript scripts/07_model_results.R

file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
source(file.path(dirname(gsub("~+~", " ", sub("^--file=", "", file_arg), fixed = TRUE)), "_common.R"))

m <- readRDS(file.path(MODELS, "primary_gamm.rds"))
mi <- readRDS(file.path(MODELS, "interaction_gamm.rds"))
dat <- m$model
nums <- list()
add <- function(quantity, value) nums[[length(nums) + 1]] <<- data.frame(quantity = quantity, value = value)

# ── Table 3.1: shares of the four terms ─────────────────────────────────────────────────────
s_d <- smooth_at(m, "s(drought)", data.frame(drought = dat$drought))
s_m <- smooth_at(m, "s(month)", data.frame(month = dat$month))
s_dm <- smooth_at(m, "ti(drought,month)", data.frame(drought = dat$drought, month = dat$month))
s_u <- smooth_at(m, "s(water_unserved_pct)", data.frame(water_unserved_pct = dat$water_unserved_pct))
mean_abs <- c(mean(abs(s_u)), mean(abs(s_d)), mean(abs(s_m)), mean(abs(s_dm)))
shares <- data.frame(
  term = c("Unserved water curve", "Drought curve", "Month curve", "Drought-month surface"),
  model_term = c("s(water_unserved_pct)", "s(drought)", "s(month)", "ti(drought,month)"),
  mean_abs_contribution = mean_abs,
  share = mean_abs / sum(mean_abs)
)
write_table(shares, "table_3_1_term_shares.csv")
share_of <- setNames(shares$share, shares$model_term)

# ── drought curve ───────────────────────────────────────────────────────────────────────────
dr <- drought_range(m, dat)
add("SPEI-12, 2nd percentile", dr$p02)
add("SPEI-12, 98th percentile", dr$p98)
add("drought curve at the 2nd percentile", dr$f_p02)
add("drought curve at the 98th percentile", dr$f_p98)
add("range of the drought curve, 2nd-98th percentile (log points)", dr$range)
add("same range as a factor on (1 + spending)", exp(dr$range))
add("driest observed SPEI-12", min(dat$drought))
add("drought curve at the driest observed SPEI-12", smooth_at(m, "s(drought)", data.frame(drought = min(dat$drought))))
add("drought curve at SPEI-12 = +2", smooth_at(m, "s(drought)", data.frame(drought = 2)))

# Dry-to-wet difference of drought curve + month curve + surface in each month (the month curve
# cancels): the drought response of one calendar month.
by_month <- do.call(rbind, lapply(1:12, function(mo) {
  g <- seq(dr$p02, dr$p98, length.out = 200)
  f <- smooth_at(m, "s(drought)", data.frame(drought = g)) +
    smooth_at(m, "ti(drought,month)", data.frame(drought = g, month = mo))
  data.frame(month = mo, dry_minus_wet = f[1] - f[length(f)], max_minus_min = max(f) - min(f))
}))
write_table(by_month, "drought_month_response.csv")

# ── standing difference and the model-free check ───────────────────────────────────────────
sd <- standing_difference(m, dat)
add("unserved water, 10th percentile (%)", sd$u_p10)
add("unserved water, 90th percentile (%)", sd$u_p90)
add("standing difference (times)", sd$factor)
add("standing difference, 95% interval low", sd$lo)
add("standing difference, 95% interval high", sd$hi)
mm <- aggregate(cbind(y, water_unserved_pct) ~ IBGE_f, data = dat, FUN = mean)
ols <- lm(y ~ water_unserved_pct, data = mm)
add("model-free check: municipality mean log spending on unserved water, p90 vs p10 (times)",
    exp(coef(ols)[["water_unserved_pct"]] * (sd$u_p90 - sd$u_p10)))
add("model-free check: R-squared", summary(ols)$r.squared)

# ── Table 3.2: diagnostics ──────────────────────────────────────────────────────────────────
s <- summary(m)
y <- dat$y
res <- y - as.numeric(fitted(m))
zero <- y == 0
worst <- abs(res) > quantile(abs(res), 0.9)
overall <- data.frame(
  quantity = c("municipality-months", "deviance explained", "adjusted R-squared",
               "median absolute error", "median absolute error, months with spending",
               "median absolute error, months without spending", "share of months with spending",
               "share of months without spending", "RMSE", "RMSE predicting the overall average",
               "month-to-month carry-over rho", "share of zero months among the worst tenth of errors",
               "share of squared error from zero months"),
  value = c(nrow(dat), s$dev.expl, s$r.sq, median(abs(res)), median(abs(res[!zero])),
            median(abs(res[zero])), mean(!zero), mean(zero), sqrt(mean(res^2)),
            sqrt(mean((y - mean(y))^2)), m$AR1.rho, mean(zero[worst]), sum(res[zero]^2) / sum(res^2))
)
terms <- c("s(drought)", "s(month)", "ti(drought,month)", "s(water_unserved_pct)")
pr <- predict(m, type = "terms", se.fit = TRUE)
per_term <- data.frame(
  quantity = paste(c("Drought curve", "Month curve", "Drought-month surface", "Unserved water curve"),
                   rep(c("EDF", "F", "p", "mean width of 95% band"), each = 4), sep = ": "),
  value = c(s$s.table[terms, "edf"], s$s.table[terms, "F"], s$s.table[terms, "p-value"],
            sapply(terms, function(t) 2 * 1.96 * mean(pr$se.fit[, t])))
)
write_table(rbind(overall, per_term), "table_3_2_model_diagnostics.csv")

# ── the second model (drought x unserved water) ─────────────────────────────────────────────
di <- mi$model
u_vals <- setNames(as.numeric(quantile(di$water_unserved_pct, c(0.10, 0.50, 0.90))), c("p10", "p50", "p90"))
d_seq <- seq(quantile(di$drought, 0.02), quantile(di$drought, 0.98), length.out = 40)
curves <- do.call(rbind, lapply(names(u_vals), function(p) {
  nd <- data.frame(drought = d_seq, water_unserved_pct = u_vals[[p]])
  data.frame(
    unserved_percentile = p, water_unserved_pct = u_vals[[p]], drought = d_seq,
    total_partial = smooth_at(mi, "s(drought)", nd) + smooth_at(mi, "s(water_unserved_pct)", nd[1, , drop = FALSE]) +
      smooth_at(mi, "ti(drought,water_unserved_pct)", nd)
  )
}))
write_table(curves, "interaction_curves.csv")
at <- function(p, i) curves$total_partial[curves$unserved_percentile == p][i]
i0 <- which.min(abs(d_seq))
si <- summary(mi)
add("second model: unserved water 10th / 50th / 90th percentile (%)", paste(round(u_vals, 1), collapse = " / "))
add("second model: gap p90 - p10 at SPEI = 0 (log points)", at("p90", i0) - at("p10", i0))
add("second model: same gap as a factor", exp(at("p90", i0) - at("p10", i0)))
add("second model: gap p90 - p10 at the 2nd percentile of SPEI (log points)", at("p90", 1) - at("p10", 1))
add("second model: same gap as a factor", exp(at("p90", 1) - at("p10", 1)))
for (p in names(u_vals)) {
  v <- curves$total_partial[curves$unserved_percentile == p]
  add(paste0("second model: range of the curve at ", p, " (log points)"), max(v) - min(v))
}
add("second model: deviance explained", si$dev.expl)
add("second model: AIC minus primary AIC", AIC(mi) - AIC(m))
add("second model: EDF of the drought-unserved surface", si$s.table["ti(drought,water_unserved_pct)", "edf"])

out <- do.call(rbind, nums)
write_table(out, "results_numbers.csv")
print(out, row.names = FALSE)
print(shares[, c("term", "share")], row.names = FALSE)

# ── figures ─────────────────────────────────────────────────────────────────────────────────
SE_MULT <- 2
pct <- function(x) sprintf("%.1f%%", 100 * x)

add_obs_rug <- function(x) {
  x <- as.numeric(x)
  x <- x[is.finite(x)]
  if (length(x) > 2000L) {
    set.seed(20260724L)
    x <- sample(x, 2000L)
  }
  rug(x, ticksize = 0.03, col = adjustcolor("grey20", alpha.f = 0.18), quiet = TRUE)
}
panel_header <- function(title, share, subtitle) {
  mtext(sprintf("%s (share %s)", title, pct(share)), side = 3, line = 2.35, font = 2, cex = 1.05)
  mtext(subtitle, side = 3, line = 0.75, cex = 0.95, col = "grey25")
}

# 1D curves as plot.gam draws them; one vertical range for all three
pd_1d <- lapply(c(1L, 2L, 4L), function(i) {
  pdf(file = NULL)
  on.exit(dev.off(), add = TRUE)
  plot(m, pages = 0, select = i, se = TRUE, seWithMean = FALSE, rug = FALSE)[[i]]
})
ylim_shared <- range(vapply(pd_1d, function(t) {
  yl <- range(c(t$fit - SE_MULT * t$se, t$fit + SE_MULT * t$se), finite = TRUE)
  yl + c(-1, 1) * 0.06 * diff(yl)
}, numeric(2)), finite = TRUE)

plot_1d <- function(select, xlab, rug_x, title, share, subtitle, month_ticks = FALSE) {
  par(mar = c(4.2, 4.2, 4.2, 1.0))
  plot(m, select = select, shade = TRUE, rug = FALSE, se = TRUE, seWithMean = FALSE,
       main = "", xlab = xlab, ylab = YLAB, ylim = ylim_shared,
       xaxt = if (month_ticks) "n" else "s")
  if (month_ticks) axis(1, at = 1:12)
  abline(h = 0, lty = 2, col = "grey50", lwd = 0.8)
  add_obs_rug(rug_x)
  panel_header(title, share, subtitle)
}

# drought-month surfaces on a 40 x 24 grid inside the observed combinations
d_grid <- seq(dr$p02, dr$p98, length.out = 40L)
m_grid <- seq(1, 12, length.out = 24)
grid <- expand.grid(drought = d_grid, month = m_grid)
too_far <- exclude.too.far(grid$drought, grid$month, dat$drought, dat$month, dist = 0.12)
surface <- function(labels) {
  X <- matrix(0, nrow = nrow(grid), ncol = length(coef(m)))
  for (l in labels) {
    sm <- find_smooth(m, l)
    X[, sm$first.para:sm$last.para] <- PredictMat(sm, grid)
  }
  fit <- as.numeric(X %*% coef(m))
  fit[too_far] <- NA_real_
  matrix(fit, nrow = length(d_grid))
}
add_colorbar <- function(zlim, cols, label) {
  usr <- par("usr")
  dx <- usr[2] - usr[1]
  dy <- usr[4] - usr[3]
  x0 <- usr[2] + 0.025 * dx
  x1 <- usr[2] + 0.06 * dx
  ys <- seq(usr[3], usr[4], length.out = length(cols) + 1)
  par(xpd = NA)
  rect(x0, ys[-length(ys)], x1, ys[-1], col = cols, border = NA)
  rect(x0, usr[3], x1, usr[4], border = "grey30")
  tk <- pretty(zlim, n = 5)
  tk <- tk[tk >= zlim[1] & tk <= zlim[2]]
  ty <- usr[3] + (tk - zlim[1]) / diff(zlim) * dy
  segments(x1, ty, x1 + 0.012 * dx, ty, col = "grey30")
  text(x1 + 0.018 * dx, ty, labels = format(tk), adj = 0, cex = 0.7)
  text((x0 + x1) / 2, usr[4] + 0.04 * dy, labels = label, cex = 0.7, adj = c(0.5, 0))
  par(xpd = FALSE)
}
plot_heat <- function(z, title, share, subtitle) {
  par(mar = c(4.2, 4.2, 4.2, 4.6))
  zlim <- c(-1, 1) * max(abs(range(z, finite = TRUE)))  # blue below, red above the average
  cols <- hcl.colors(100, "Blue-Red 3", rev = FALSE)
  zt <- t(z)  # month on the x axis, SPEI-12 on the y axis
  image(x = m_grid, y = d_grid, z = zt, col = cols, zlim = zlim, xlab = "Calendar month",
        ylab = "SPEI-12 (lag 0)", useRaster = TRUE, axes = FALSE)
  axis(1, at = 1:12)
  axis(2)
  box()
  suppressWarnings(contour(x = m_grid, y = d_grid, z = zt, add = TRUE, col = "blue", labcex = 0.7, lwd = 0.8))
  add_colorbar(zlim, cols, "log pts")
  panel_header(title, share, subtitle)
}
blank <- function() { par(mar = c(0, 0, 0, 0)); plot.new() }
plus_sign <- function() { blank(); text(0.5, 0.5, "+", cex = 6, font = 2, col = "grey35") }
right_arrow <- function() {
  par(mar = c(0, 0, 0, 0))
  plot(NA, xlim = c(0, 1), ylim = c(0, 1), axes = FALSE, xlab = "", ylab = "", xaxs = "i", yaxs = "i")
  polygon(x = c(0.02, 0.50, 0.50, 0.98, 0.50, 0.50, 0.02), y = c(0.56, 0.56, 0.68, 0.50, 0.32, 0.44, 0.44),
          col = "grey35", border = NA)
}

z_ti <- surface("ti(drought,month)")
z_comb <- surface(c("s(drought)", "s(month)", "ti(drought,month)"))
write_table(data.frame(drought = grid$drought, month = grid$month, interaction_only = as.numeric(z_ti),
                       combined = as.numeric(z_comb)), "drought_month_surfaces.csv")

# Figure 3.1: drought + month + surface = combined
png(file.path(FIGURES, "fig_3_1_drought_and_month_terms.png"), width = 1900, height = 1500, res = 150)
layout(matrix(1:8, nrow = 2, byrow = TRUE), widths = c(0.14, 1, 0.16, 1), heights = c(1, 1))
par(oma = c(0.3, 0.3, 0.3, 0.3))
blank()
plot_1d(1, "SPEI-12 (lag 0)", dat$drought, "Drought", share_of[["s(drought)"]], expression(f[1] * "(SPEI-12)"))
plus_sign()
plot_1d(2, "Calendar month", dat$month, "Month", share_of[["s(month)"]], expression(f[2] * "(month)"), month_ticks = TRUE)
plus_sign()
plot_heat(z_ti, "Drought × month", share_of[["ti(drought,month)"]],
          expression(f[list(1, 2)] * "(SPEI-12, month)"))
right_arrow()
plot_heat(z_comb, "Drought + month combined",
          sum(share_of[c("s(drought)", "s(month)", "ti(drought,month)")]), expression(f[1] + f[2] + f[list(1, 2)]))
invisible(dev.off())

# Figure 3.2: unserved water curve
png(file.path(FIGURES, "fig_3_2_unserved_water_term.png"), width = 1000, height = 800, res = 150)
plot_1d(4, "Water unserved (%)", dat$water_unserved_pct, "Unserved water",
        share_of[["s(water_unserved_pct)"]], expression(f[3] * "(unserved)"))
invisible(dev.off())

# Figure 3.3: second model, three levels of unserved water
cols_line <- c(p10 = "#2c7bb6", p50 = "#4d4d4d", p90 = "#d7191c")
ltys <- c(p10 = 1, p50 = 2, p90 = 1)
lwds <- c(p10 = 2.2, p50 = 2.0, p90 = 2.2)
yl <- range(curves$total_partial, finite = TRUE)
pad <- 0.06 * diff(yl)
png(file.path(FIGURES, "fig_3_3_drought_by_unserved.png"), width = 1400, height = 1000, res = 140)
par(mar = c(4.4, 4.6, 2.6, 1.2))
plot(NA, xlim = range(d_seq), ylim = yl + c(-pad, pad), xlab = "SPEI-12 (lag 0)", ylab = YLAB,
     main = "Drought + unserved water contribution at three levels of unserved water")
abline(h = 0, lty = 2, col = "grey50", lwd = 0.8)
for (p in names(u_vals)) {
  sub <- curves[curves$unserved_percentile == p, ]
  lines(sub$drought, sub$total_partial, col = cols_line[[p]], lty = ltys[[p]], lwd = lwds[[p]])
}
legend("topright", legend = sprintf("%s (unserved water %.1f%%)", names(u_vals), u_vals),
       col = unname(cols_line), lty = unname(ltys), lwd = unname(lwds), bty = "n", cex = 0.9)
invisible(dev.off())
message("Saved outputs/figures/fig_3_1_drought_and_month_terms.png, fig_3_2_unserved_water_term.png, ",
        "fig_3_3_drought_by_unserved.png")
