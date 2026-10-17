# Shared paths and helpers for the R scripts. Sourced by 06_fit_models.R, 07_model_results.R and
# 08_robustness.R.

suppressPackageStartupMessages(library(mgcv))

script_root <- function() {
  file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(file_arg) == 1) {
    path <- gsub("~+~", " ", sub("^--file=", "", file_arg), fixed = TRUE)
    root <- normalizePath(file.path(dirname(path), ".."), winslash = "/")
    if (file.exists(file.path(root, "scripts", "_common.R"))) return(root)
  }
  root <- normalizePath(getwd(), winslash = "/")
  if (!file.exists(file.path(root, "scripts", "_common.R"))) stop("Run the scripts from the repository root.")
  root
}

ROOT <- script_root()
PANEL_CSV <- file.path(ROOT, "data", "processed", "panel_2015_2019.csv.gz")
MODELS <- file.path(ROOT, "outputs", "models")
TABLES <- file.path(ROOT, "outputs", "tables")
FIGURES <- file.path(ROOT, "outputs", "figures")
for (d in c(MODELS, TABLES, FIGURES)) dir.create(d, showWarnings = FALSE, recursive = TRUE)

WINSOR_Q <- 0.99  # spending cap: 99th percentile of the 827-municipality panel
YLAB <- "Partial effect on log(1 + spending)"

# The primary GAMM. ti() is the drought-month surface without the two main effects; the
# municipality baseline is a random intercept; the year enters as a factor.
RHS_PRIMARY <- c(
  "s(drought, k = 10, bs = 'tp')",
  "s(month, bs = 'cc', k = 12)",
  "ti(drought, month, bs = c('tp', 'cc'), k = c(6, 6))",
  "s(water_unserved_pct, k = 8, bs = 'tp')",
  "s(IBGE_f, bs = 're')",
  "year_f"
)
RHS_INTERACTION <- append(RHS_PRIMARY, "ti(drought, water_unserved_pct, bs = c('tp', 'tp'), k = c(6, 6))", after = 4)

read_panel <- function() {
  df <- read.csv(gzfile(PANEL_CSV), stringsAsFactors = FALSE)
  df$date <- as.Date(sprintf("%04d-%02d-01", df$year, df$month))
  df <- df[order(df$IBGE, df$date), ]
  rownames(df) <- NULL
  df$year_f <- factor(df$year)
  df$IBGE_f <- factor(df$IBGE)
  df$cost_per_1k <- df$cost_real / (df$population_2025 / 1000)
  df
}

# Lag a variable by `lag` months within each municipality (the panel has all 60 months per
# municipality, including the blank ones, so one row back is one calendar month back).
lag_within <- function(df, x, lag) {
  if (lag == 0L) return(as.numeric(x))
  out <- rep(NA_real_, nrow(df))
  for (ix in split(seq_len(nrow(df)), df$IBGE)) {
    v <- x[ix]
    out[ix] <- if (lag >= length(v)) NA_real_ else c(rep(NA_real_, lag), v[seq_len(length(v) - lag)])
  }
  out
}

# Model data: outcome log(1 + spending capped at quantile q of the whole 827-municipality panel),
# drought = SPEI-12 at the given lag; rows without spending, SPEI or unserved water are dropped,
# which leaves the 746 analysed municipalities.
model_data <- function(df, lag = 0L, outcome = "cost_real", q = WINSOR_Q, needs_loss = FALSE) {
  d <- df
  d$drought <- lag_within(d, d$SPEI_12, lag)
  x <- d[[outcome]]
  cap <- as.numeric(quantile(x, q, na.rm = TRUE))
  d$y <- log1p(pmin(x, cap))
  keep <- is.finite(d$y) & is.finite(d$drought) & is.finite(d$water_unserved_pct)
  if (needs_loss) keep <- keep & is.finite(d$water_loss_pct)
  d <- d[keep, ]
  d$year_f <- droplevels(d$year_f)
  d$IBGE_f <- droplevels(d$IBGE_f)
  # A new AR(1) segment starts at each municipality's first month and after every gap.
  same_mun <- c(FALSE, d$IBGE[-1] == d$IBGE[-nrow(d)])
  next_month <- c(FALSE, as.numeric(diff(d$date)) <= 32)
  d$ar_start <- !(same_mun & next_month)
  attr(d, "cap") <- cap
  d
}

fit_gamm <- function(d, rhs, rho = 0, seed = 20260724) {
  form <- as.formula(paste("y ~", paste(rhs, collapse = " + ")))
  set.seed(seed)
  fit <- function(discrete) {
    if (rho > 0) {
      bam(form, data = d, method = "fREML", discrete = discrete, select = TRUE,
          knots = list(month = c(0.5, 12.5)), rho = rho, AR.start = d$ar_start)
    } else {
      bam(form, data = d, method = "fREML", discrete = discrete, select = TRUE,
          knots = list(month = c(0.5, 12.5)))
    }
  }
  t0 <- Sys.time()
  m <- tryCatch(fit(TRUE), error = function(e) {
    message("  discrete fit failed (", conditionMessage(e), "); retrying with discrete = FALSE")
    fit(FALSE)
  })
  message(sprintf("  fitted on %s rows in %.1f min", format(nrow(d), big.mark = ","),
                  as.numeric(difftime(Sys.time(), t0, units = "mins"))))
  m
}

# Correlation between consecutive residuals of the same municipality (the AR(1) rho).
residual_rho <- function(m, d) {
  r <- as.numeric(residuals(m))
  same <- c(FALSE, d$IBGE[-1] == d$IBGE[-nrow(d)])
  lagged <- c(NA_real_, r[-length(r)])
  ok <- same & is.finite(r) & is.finite(lagged)
  cor(r[ok], lagged[ok])
}

# Formulas and functions inside a fitted bam keep a reference to the environment they were
# created in, which here holds the whole panel. Point them at the global environment so the
# saved file holds the model only (about 14 MB instead of about 100 MB).
strip_env <- function(x) {
  if (is.function(x) || inherits(x, "formula")) {
    environment(x) <- globalenv()
    return(x)
  }
  if (is.list(x) && !is.data.frame(x)) {
    a <- attributes(x)
    for (i in seq_along(x)) if (!is.null(x[[i]])) x[[i]] <- strip_env(x[[i]])
    attributes(x) <- a
  }
  if (!is.null(attr(x, ".Environment"))) attr(x, ".Environment") <- globalenv()
  x
}

save_model <- function(m, name) {
  m$call <- NULL
  m <- strip_env(m)
  attr(attr(m$model, "terms"), ".Environment") <- globalenv()
  path <- file.path(MODELS, name)
  saveRDS(m, path, compress = "xz")
  message("Saved ", sub(paste0(ROOT, "/"), "", path, fixed = TRUE))
}

find_smooth <- function(m, label) {
  i <- which(vapply(m$smooth, function(s) identical(s$label, label), logical(1)))
  if (length(i) != 1) stop("Smooth not found: ", label)
  m$smooth[[i]]
}

# Contribution of one smooth at new covariate values (PredictMat avoids predict.bam(newdata),
# which fails for discrete bam fits with ti() terms).
smooth_at <- function(m, label, nd) {
  sm <- find_smooth(m, label)
  as.numeric(PredictMat(sm, nd) %*% coef(m)[sm$first.para:sm$last.para])
}

# Standing difference: exp(f3(p90) - f3(p10)) of the unserved water curve, with a 95% interval
# from 2,000 draws of that curve's coefficients.
standing_difference <- function(m, d, n_sim = 2000L, seed = 20260903) {
  sm <- find_smooth(m, "s(water_unserved_pct)")
  u <- as.numeric(quantile(d$water_unserved_pct, c(0.10, 0.90)))
  dX <- PredictMat(sm, data.frame(water_unserved_pct = u[2])) -
    PredictMat(sm, data.frame(water_unserved_pct = u[1]))
  ix <- sm$first.para:sm$last.para
  b <- coef(m)[ix]
  V <- m$Vp[ix, ix, drop = FALSE]
  gap <- as.numeric(dX %*% b)
  set.seed(seed)
  L <- chol(V + diag(1e-10, ncol(V)))
  draws <- sweep(matrix(rnorm(n_sim * ncol(V)), nrow = n_sim) %*% L, 2, b, "+")
  q <- quantile(as.numeric(draws %*% as.numeric(dX)), c(0.025, 0.975), names = FALSE)
  list(u_p10 = u[1], u_p90 = u[2], log_gap = gap, factor = exp(gap),
       lo = exp(q[1]), hi = exp(q[2]))
}

# Range of the drought curve between the 2nd and 98th percentile of SPEI-12.
drought_range <- function(m, d, n = 200L) {
  p <- as.numeric(quantile(d$drought, c(0.02, 0.98)))
  f <- smooth_at(m, "s(drought)", data.frame(drought = seq(p[1], p[2], length.out = n)))
  list(p02 = p[1], p98 = p[2], f_p02 = f[1], f_p98 = f[n], range = max(f) - min(f))
}

write_table <- function(x, name) {
  write.csv(x, file.path(TABLES, name), row.names = FALSE, fileEncoding = "UTF-8")
  message("Saved outputs/tables/", name)
}
