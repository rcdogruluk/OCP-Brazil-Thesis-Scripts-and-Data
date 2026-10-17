"""Step 05: choose the SPEI window and lag (Annex A).

For every SPEI window (1-24 months) and lag (0-12 months), a ridge regression of the month-to-month
change in log(1 + capped spending) on the change in the lagged SPEI, plus calendar-month dummies,
is trained on 2015-2017 and scored on 2018-2019 (root mean square error). Changes are used rather
than levels so that the programme-wide fall in spending in 2018 does not dominate the test. Lags are
taken within each municipality's 2015-2019 series. All 827 matched municipalities are used.

Outputs:
    outputs/tables/window_lag_test.csv        one row per window and lag
    outputs/tables/window_lag_selection.csv   best cell, SPEI-12 lag 0, range of the 9-14 x 0-1 band
    outputs/figures/fig_A_1_window_lag_test.png

Usage (from the repository root, about a minute):
    python scripts/05_window_lag_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import FIGURES, PANEL, SPEI_WINDOWS, TABLES, WINSOR_Q  # noqa: E402

LAGS = list(range(0, 13))
TRAIN_YEARS, TEST_YEARS = {2015, 2016, 2017}, {2018, 2019}
RIDGE_ALPHA = 1.0


def month_dummies(month: pd.Series) -> np.ndarray:
    d = pd.get_dummies(month.astype(int), prefix="m")
    cols = [f"m_{m}" for m in range(2, 13)]
    for c in cols:
        if c not in d.columns:
            d[c] = 0
    return d[cols].to_numpy(dtype=float)


def score(df: pd.DataFrame, x: pd.Series, train_mask: np.ndarray, test_mask: np.ndarray) -> dict:
    work = pd.DataFrame({"y": df["y"].to_numpy(), "x": x.to_numpy(), "IBGE": df["IBGE"].to_numpy(),
                         "month": df["month"].to_numpy()})
    work["dy"] = work.groupby("IBGE", sort=False)["y"].diff()
    work["dx"] = work.groupby("IBGE", sort=False)["x"].diff()
    valid = work["dy"].notna() & work["dx"].notna()
    out = {}
    model = None
    for part, mask in (("train", valid & train_mask), ("test", valid & test_mask)):
        sub = work.loc[mask]
        X = np.column_stack([sub["dx"].to_numpy(), month_dummies(sub["month"])])
        if model is None:
            model = Ridge(alpha=RIDGE_ALPHA, fit_intercept=True).fit(X, sub["dy"].to_numpy())
        hat = model.predict(X)
        out[f"n_{part}"] = int(mask.sum())
        out[f"{part}_rmse"] = float(np.sqrt(mean_squared_error(sub["dy"], hat)))
        out[f"{part}_r2"] = float(r2_score(sub["dy"], hat))
    out["coef_drought"] = float(model.coef_[0])
    return out


def main() -> None:
    df = pd.read_csv(PANEL).sort_values(["IBGE", "year", "month"]).reset_index(drop=True)
    cap = df["cost_real"].quantile(WINSOR_Q)
    df["y"] = np.log1p(df["cost_real"].clip(upper=cap))
    train_mask = df["year"].isin(TRAIN_YEARS).to_numpy()
    test_mask = df["year"].isin(TEST_YEARS).to_numpy()

    rows = []
    for w in SPEI_WINDOWS:
        col = f"SPEI_{w}"
        grouped = df.groupby("IBGE", sort=False)[col]
        for lag in LAGS:
            x = df[col] if lag == 0 else grouped.shift(lag)
            rows.append({"spei_window": w, "lag": lag, **score(df, x, train_mask, test_mask)})
    res = pd.DataFrame(rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    res.to_csv(TABLES / "window_lag_test.csv", index=False, encoding="utf-8")

    best = res.loc[res["test_rmse"].idxmin()]
    band = res[res["spei_window"].between(9, 14) & res["lag"].isin([0, 1])]
    s12 = res[(res["spei_window"] == 12) & (res["lag"] == 0)].iloc[0]
    sel = pd.DataFrame([
        ("lowest test RMSE: window", int(best["spei_window"])),
        ("lowest test RMSE: lag", int(best["lag"])),
        ("lowest test RMSE", round(best["test_rmse"], 3)),
        ("SPEI-12 lag 0 test RMSE (used)", round(s12["test_rmse"], 3)),
        ("SPEI-12 lag 0 test R2", round(s12["test_r2"], 3)),
        ("band windows 9-14, lags 0-1: lowest RMSE", round(band["test_rmse"].min(), 3)),
        ("band windows 9-14, lags 0-1: highest RMSE", round(band["test_rmse"].max(), 3)),
    ], columns=["quantity", "value"])
    sel.to_csv(TABLES / "window_lag_selection.csv", index=False, encoding="utf-8")
    print(sel.to_string(index=False))

    pivot = res.pivot_table(index="lag", columns="spei_window", values="test_rmse", aggfunc="first")
    pivot = pivot.reindex(index=LAGS, columns=SPEI_WINDOWS)
    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(pivot, ax=ax, cmap="viridis_r", annot=False,
                cbar_kws={"label": "Test RMSE (change in log(1 + spending))"})
    ax.set_xlabel("SPEI window (months)")
    ax.set_ylabel("Lag (months)")
    ax.set_title("First-difference SPEI window × lag search: test RMSE (train 2015–2017, test 2018–2019)")
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "fig_A_1_window_lag_test.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved outputs/figures/fig_A_1_window_lag_test.png")


if __name__ == "__main__":
    main()
