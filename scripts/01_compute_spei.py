"""Step 01: compute SPEI-1 to SPEI-24 for every municipality of the nine states.

For each municipality, the monthly water balance (precipitation minus reference evapotranspiration,
from BR-DWGD) is summed over trailing windows of 1 to 24 months. For each window and calendar
month, a generalised logistic distribution (the "log-logistic" of the R SPEI package) is fitted to
the 1990-2019 sums with unbiased probability-weighted moments, and every sum is converted to a
standard normal score (Vicente-Serrano et al. 2010). SPEI = 0 is the municipality's own 1990-2019
average for that window and month, not the absence of water stress.

Input:  data/raw/climate/br_dwgd_monthly_climate_1961_2020.csv.gz
Output: data/processed/spei_2015_2019.csv.gz   SPEI-1..24 and the water balance, 2015-2019,
                                               1,794 municipalities x 60 months
        outputs/tables/spei_validation.csv     baseline mean and SD per window (about 0 and 1)

One municipality (Fernando de Noronha, an island outside the BR-DWGD grid) has no climate data;
its fits fail and its SPEI is empty. It has no OCP record, so it does not enter the analysis.

Usage (from the repository root, about ten minutes):
    python scripts/01_compute_spei.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CLIMATE, SPEI, SPEI_BASELINE, SPEI_WINDOWS, TABLES, YEARS  # noqa: E402

BASELINE_YEARS = range(SPEI_BASELINE[0], SPEI_BASELINE[1] + 1)
SPEI_SCALES = SPEI_WINDOWS
MIN_BASELINE_OBS = 20
PROBABILITY_EPS = 1e-6
SHAPE_ZERO_TOL = 1e-6


def fit_glo_unbiased_pwm(values: np.ndarray) -> tuple[float, float, float]:
    """
    Fit Hosking's generalized logistic distribution with unbiased PWMs.

    This matches the default estimator used by the R SPEI package
    (distribution = "log-Logistic", fit = "ub-pwm"). Returned parameters are
    location xi, scale alpha, and shape k. SciPy's unconstrained fisk.fit() is
    deliberately not used: with only ~30 observations per seasonal baseline,
    its free location MLE can collapse toward the sample minimum and compress
    nearly all transformed values into one narrow positive SPEI band.
    """
    x = np.sort(np.asarray(values, dtype=float))
    x = x[np.isfinite(x)]
    n = len(x)
    if n < MIN_BASELINE_OBS:
        raise ValueError(
            f"Only {n} finite baseline observations; need {MIN_BASELINE_OBS}."
        )
    if n < 3 or not np.isfinite(np.std(x, ddof=1)) or np.std(x, ddof=1) == 0:
        raise ValueError("Baseline has insufficient finite variation.")

    ranks = np.arange(n, dtype=float)
    b0 = float(np.mean(x))
    b1 = float(np.sum((ranks / (n - 1)) * x) / n)
    b2 = float(
        np.sum(
            (ranks * (ranks - 1) / ((n - 1) * (n - 2))) * x
        )
        / n
    )

    lambda1 = b0
    lambda2 = 2 * b1 - b0
    lambda3 = 6 * b2 - 6 * b1 + b0
    if not np.isfinite(lambda1) or not np.isfinite(lambda2) or lambda2 <= 0:
        raise ValueError(
            f"Invalid L-moments: lambda1={lambda1}, lambda2={lambda2}."
        )

    tau3 = lambda3 / lambda2
    if not np.isfinite(tau3) or abs(tau3) >= 1:
        raise ValueError(f"Invalid L-skewness tau3={tau3}; require |tau3| < 1.")

    k = -tau3
    if abs(k) <= SHAPE_ZERO_TOL:
        alpha = lambda2
        xi = lambda1
        k = 0.0
    else:
        g = np.pi * k / np.sin(np.pi * k)
        alpha = lambda2 / g
        xi = lambda1 - alpha * (1 - g) / k

    if not np.isfinite(alpha) or alpha <= 0 or not np.isfinite(xi):
        raise ValueError(f"Invalid GLO parameters: xi={xi}, alpha={alpha}, k={k}.")
    return float(xi), float(alpha), float(k)


def glo_cdf(values: np.ndarray, xi: float, alpha: float, k: float) -> np.ndarray:
    """Evaluate the lower-tail generalized-logistic CDF used by SPEI."""
    x = np.asarray(values, dtype=float)
    probs = np.full(len(x), np.nan)
    valid = np.isfinite(x)
    if not valid.any():
        return probs

    xv = x[valid]
    if k == 0:
        y = (xv - xi) / alpha
        probs[valid] = stats.logistic.cdf(y)
        return probs

    support = 1 - k * (xv - xi) / alpha
    inside = support > 0
    pv = np.empty(len(xv), dtype=float)
    pv[inside] = stats.logistic.cdf(-np.log(support[inside]) / k)
    # k > 0 has an upper endpoint; k < 0 has a lower endpoint.
    pv[~inside] = 1.0 if k > 0 else 0.0
    probs[valid] = pv
    return probs


def compute_spei_ub_pwm(
    baseline_values: np.ndarray,
    target_values: np.ndarray,
    min_baseline_obs: int = MIN_BASELINE_OBS,
) -> tuple[np.ndarray, dict]:
    """
    Compute SPEI with the standard unbiased-PWM generalized logistic fit.

    Returns the SPEI vector and compact diagnostics for this seasonal fit.
    """
    spei = np.full(len(target_values), np.nan)

    baseline = baseline_values[np.isfinite(baseline_values)]
    if len(baseline) < min_baseline_obs:
        raise ValueError(
            f"Only {len(baseline)} finite baseline observations; "
            f"need {min_baseline_obs}."
        )

    xi, alpha, k = fit_glo_unbiased_pwm(baseline)
    probs_raw = glo_cdf(target_values, xi, alpha, k)
    valid = np.isfinite(probs_raw)
    lower_clipped = int(np.sum(valid & (probs_raw < PROBABILITY_EPS)))
    upper_clipped = int(np.sum(valid & (probs_raw > 1 - PROBABILITY_EPS)))
    probs = np.where(
        valid,
        np.clip(probs_raw, PROBABILITY_EPS, 1 - PROBABILITY_EPS),
        np.nan,
    )
    spei[valid] = stats.norm.ppf(probs[valid])
    return spei, {
        "xi": xi,
        "alpha": alpha,
        "k": k,
        "n_baseline": int(len(baseline)),
        "lower_clipped": lower_clipped,
        "upper_clipped": upper_clipped,
    }



def build_validation_summary(
    df: pd.DataFrame,
    fit_counts: dict[int, dict[str, int]],
) -> pd.DataFrame:
    """Summarize baseline standardization and analysis-period support by scale."""
    rows = []
    baseline_mask = df["year"].isin(BASELINE_YEARS)
    analysis_mask = df["year"].between(2015, 2019)

    for scale in SPEI_SCALES:
        col = f"SPEI_{scale}"
        baseline = df.loc[baseline_mask, col].dropna()
        analysis = df.loc[analysis_mask, col].dropna()
        counts = fit_counts[scale]
        n_transformed = counts["n_transformed"]
        n_clipped = counts["lower_clipped"] + counts["upper_clipped"]

        baseline_mean = float(baseline.mean()) if len(baseline) else np.nan
        baseline_sd = float(baseline.std(ddof=1)) if len(baseline) > 1 else np.nan
        clip_pct = 100 * n_clipped / n_transformed if n_transformed else np.nan

        issues = []
        if not np.isfinite(baseline_mean) or abs(baseline_mean) > 0.15:
            issues.append("baseline_mean_outside_±0.15")
        if not np.isfinite(baseline_sd) or not 0.8 <= baseline_sd <= 1.2:
            issues.append("baseline_sd_outside_0.8_1.2")
        if np.isfinite(clip_pct) and clip_pct > 0.5:
            issues.append("more_than_0.5pct_probability_clipped")
        has_fit_gaps = counts["fit_failures"] > 0

        quantiles = (
            analysis.quantile([0.01, 0.05, 0.5, 0.95, 0.99])
            if len(analysis)
            else pd.Series(dtype=float)
        )
        rows.append(
            {
                "scale": scale,
                "baseline_n": int(len(baseline)),
                "baseline_mean": baseline_mean,
                "baseline_sd": baseline_sd,
                "analysis_2015_2019_n": int(len(analysis)),
                "analysis_p01": quantiles.get(0.01, np.nan),
                "analysis_p05": quantiles.get(0.05, np.nan),
                "analysis_median": quantiles.get(0.5, np.nan),
                "analysis_p95": quantiles.get(0.95, np.nan),
                "analysis_p99": quantiles.get(0.99, np.nan),
                "seasonal_fits": counts["fits"],
                "fit_failures": counts["fit_failures"],
                "lower_probability_clips": counts["lower_clipped"],
                "upper_probability_clips": counts["upper_clipped"],
                "probability_clipped_pct": clip_pct,
                "status": (
                    "REVIEW"
                    if issues
                    else ("PASS_WITH_GAPS" if has_fit_gaps else "PASS")
                ),
                "issues": ";".join(
                    issues
                    + (["seasonal_fit_failures"] if has_fit_gaps else [])
                ),
            }
        )
    return pd.DataFrame(rows)




def main() -> None:
    df = pd.read_csv(CLIMATE)
    df = df.sort_values(["CD_MUN", "year", "month"]).reset_index(drop=True)
    fit_counts = {
        s: {"fits": 0, "fit_failures": 0, "lower_clipped": 0, "upper_clipped": 0, "n_transformed": 0}
        for s in SPEI_SCALES
    }
    results = []
    for idx, (_, group) in enumerate(df.groupby("CD_MUN")):
        group = group.sort_values(["year", "month"]).copy()
        baseline_mask = group["year"].isin(BASELINE_YEARS)
        for scale in SPEI_SCALES:
            rolled = group["water_balance_mm"].rolling(window=scale, min_periods=scale).sum()
            col = f"SPEI_{scale}"
            group[col] = np.nan
            for month in range(1, 13):
                target_mask = group["month"] == month
                baseline_values = rolled[baseline_mask & target_mask].values
                target_values = rolled[target_mask].values
                try:
                    values, diag = compute_spei_ub_pwm(baseline_values, target_values)
                except Exception:
                    fit_counts[scale]["fit_failures"] += 1
                    continue
                group.loc[target_mask, col] = values
                c = fit_counts[scale]
                c["fits"] += 1
                c["lower_clipped"] += diag["lower_clipped"]
                c["upper_clipped"] += diag["upper_clipped"]
                c["n_transformed"] += int(np.isfinite(target_values).sum())
        results.append(group)
        if (idx + 1) % 300 == 0:
            print(f"  {idx + 1} municipalities done", flush=True)

    full = pd.concat(results, ignore_index=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    validation = build_validation_summary(full, fit_counts)
    validation.to_csv(TABLES / "spei_validation.csv", index=False, encoding="utf-8")

    keep = ["CD_MUN", "year", "month", "precip_mm", "eto_mm", "water_balance_mm"]
    keep += [f"SPEI_{s}" for s in SPEI_SCALES]
    out = full.loc[full["year"].between(*YEARS), keep]
    SPEI.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(SPEI, index=False, encoding="utf-8", compression={"method": "gzip", "mtime": 0})
    print(f"Wrote {SPEI.name}: {len(out):,} rows, {out['CD_MUN'].nunique()} municipalities")
    print(validation[["scale", "baseline_mean", "baseline_sd", "fit_failures", "status"]].to_string(index=False))


if __name__ == "__main__":
    main()
