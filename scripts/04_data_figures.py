"""Step 04: draw the study-area and data figures of Chapters 1 and 2.

Outputs (outputs/figures/):
    fig_1_1_study_area.png              the nine states and the official semi-arid region
    fig_2_1_analysis_sample.png         analysed / OCP record without SINISA value / no record
    fig_2_2_spending_distribution.png   positive monthly spending (log scale) and monthly totals
    fig_2_3_map_mean_spei12.png         mean SPEI-12, 2015-2019, analysed municipalities
    fig_2_4_map_unserved_water.png      share without piped water, analysed municipalities

Usage (from the repository root):
    python scripts/04_data_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from matplotlib.ticker import FuncFormatter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    BRAZIL_OUTLINE, DPI, FIGURES, MUNICIPALITIES, PANEL, PLOT_CRS, SEMIARID_POLYGON, STATE_COLORS,
    STATE_NAMES, STATE_ORDER, WINSOR_Q, add_north_arrow, add_scale_bar, apply_style, save_fig,
)

# Small coastal states need a nudge so the state codes do not collide (kilometres).
LABEL_NUDGE_KM = {"AL": (39, -22), "SE": (44, -13), "RN": (17, 31), "PB": (44, 2), "PE": (28, -6)}
SAMPLE_COLORS = {"estimation": "#31708e", "fiscal_only": "#9ecae1", "outside": "#e2e2e2"}


def load_municipalities() -> gpd.GeoDataFrame:
    gdf = gpd.read_parquet(MUNICIPALITIES)
    gdf["CD_MUN"] = gdf["CD_MUN"].astype(str).str.zfill(7)
    return gdf


def frame_axes(ax: plt.Axes, bounds: tuple[float, float, float, float]) -> None:
    minx, miny, maxx, maxy = bounds
    pad = 0.03 * max(maxx - minx, maxy - miny)
    ax.set_xlim(minx - pad, maxx + pad)
    ax.set_ylim(miny - pad, maxy + pad)
    ax.set_aspect("equal")
    ax.axis("off")
    add_north_arrow(ax)
    add_scale_bar(ax)


def fig_study_area(mun: gpd.GeoDataFrame) -> None:
    states = mun.to_crs(PLOT_CRS).dissolve(by="SIGLA_UF", aggfunc="first").reset_index()[["SIGLA_UF", "geometry"]]
    states["SIGLA_UF"] = pd.Categorical(states["SIGLA_UF"], categories=STATE_ORDER, ordered=True)
    states = states.sort_values("SIGLA_UF").reset_index(drop=True)
    brazil = gpd.read_parquet(BRAZIL_OUTLINE).to_crs(PLOT_CRS)
    sab = gpd.read_file(SEMIARID_POLYGON)
    if sab.crs is None:
        sab = sab.set_crs(4674)
    semiarid = gpd.clip(sab.to_crs(PLOT_CRS).dissolve()[["geometry"]], states.dissolve())

    fig = plt.figure(figsize=(7.4, 6.6))
    ax = fig.add_axes([0.01, 0.28, 0.73, 0.70])
    for _, row in states.iterrows():
        states.loc[[row.name]].plot(ax=ax, color=STATE_COLORS[row["SIGLA_UF"]], edgecolor="white", linewidth=0.55)
    plt.rcParams["hatch.linewidth"] = 0.45
    semiarid.plot(ax=ax, facecolor="none", edgecolor="#2b2b2b", hatch="///", linewidth=0.0, alpha=0.75)
    semiarid.boundary.plot(ax=ax, color="#1f1f1f", linewidth=1.3)
    for _, row in states.iterrows():
        pt = row.geometry.representative_point()
        dx, dy = LABEL_NUDGE_KM.get(row["SIGLA_UF"], (0.0, 0.0))
        ax.annotate(row["SIGLA_UF"], xy=(pt.x + dx * 1000, pt.y + dy * 1000), ha="center", va="center",
                    fontsize=8.5, fontweight="bold", color="#1a1a1a")
    frame_axes(ax, tuple(states.total_bounds))

    handles = [mpatches.Patch(color=STATE_COLORS[uf], label=f"{uf}  {STATE_NAMES[uf]}") for uf in STATE_ORDER]
    handles.append(mpatches.Patch(facecolor="none", edgecolor="#1f1f1f", hatch="///", linewidth=1.1,
                                  label="Official semi-arid\nregion (SUDENE)"))
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.02, 0.52), frameon=False,
              borderaxespad=0.0, handlelength=0.9, handleheight=0.9, labelspacing=0.45)

    ax_inset = fig.add_axes([0.04, 0.02, 0.24, 0.24])
    brazil.plot(ax=ax_inset, color="#d9d9d9", edgecolor="#888888", linewidth=0.4)
    states.dissolve().plot(ax=ax_inset, color="#c9a227", edgecolor="#6b5420", linewidth=0.35)
    ax_inset.set_aspect("equal")
    ax_inset.axis("off")
    save_fig(fig, "fig_1_1_study_area.png")


def fig_analysis_sample(mun: gpd.GeoDataFrame, panel: pd.DataFrame) -> None:
    per_mun = panel.groupby("IBGE")["water_unserved_pct"].first()
    ids = per_mun.index.astype(str).str.zfill(7)
    gdf = mun.to_crs(PLOT_CRS)
    gdf["sample"] = "outside"
    gdf.loc[gdf["CD_MUN"].isin(ids), "sample"] = "fiscal_only"
    gdf.loc[gdf["CD_MUN"].isin(ids[per_mun.notna().to_numpy()]), "sample"] = "estimation"
    counts = gdf["sample"].value_counts()
    labels = {
        "estimation": f"In estimation sample ({counts.get('estimation', 0)})",
        "fiscal_only": f"OCP records, no SINISA value ({counts.get('fiscal_only', 0)})",
        "outside": f"No OCP spending record ({counts.get('outside', 0)})",
    }
    fig = plt.figure(figsize=(7.4, 6.4))
    ax = fig.add_axes([0.02, 0.16, 0.96, 0.82])
    for key in ("outside", "fiscal_only", "estimation"):
        gdf[gdf["sample"] == key].plot(ax=ax, color=SAMPLE_COLORS[key], edgecolor="white", linewidth=0.06)
    frame_axes(ax, tuple(gdf.total_bounds))
    handles = [mpatches.Patch(color=SAMPLE_COLORS[k], label=labels[k]) for k in ("estimation", "fiscal_only", "outside")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.50, -0.02), ncol=1, frameon=False,
              borderaxespad=0.0, handlelength=0.9, handleheight=0.9, labelspacing=0.40, fontsize=9)
    save_fig(fig, "fig_2_1_analysis_sample.png")


def fig_spending(panel: pd.DataFrame) -> None:
    cap = float(panel["cost_real"].quantile(WINSOR_Q))  # cap used in the model, from the 827 panel
    df = panel[panel["water_unserved_pct"].notna()].dropna(subset=["cost_real"]).copy()
    df["date"] = pd.to_datetime(df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2) + "-01")
    cost = df["cost_real"]
    positive = cost[cost > 0]

    fig, (ax_hist, ax_ts) = plt.subplots(2, 1, figsize=(7.2, 6.8),
                                         gridspec_kw={"height_ratios": [1.05, 0.95], "hspace": 0.42})
    bins = np.logspace(np.log10(max(float(positive.min()), 1.0)), np.log10(float(positive.max())), 40)
    ax_hist.hist(positive, bins=bins, color="#4c78a8", edgecolor="white", linewidth=0.3)
    ax_hist.set_xscale("log")
    ax_hist.axvline(cap, color="#c23b22", linestyle="--", linewidth=1.2)
    _, ymax = ax_hist.get_ylim()
    ax_hist.set_ylim(0, ymax * 1.08)
    ax_hist.text(cap * 1.25, ymax * 0.62, f"Cap used in the model\n(R$ {round(cap):,.0f})", color="#c23b22",
                 fontsize=8.5, va="bottom", ha="left")
    ax_hist.set_xlabel("Monthly municipal OCP spending (R$, log scale)")
    ax_hist.set_ylabel("Municipality–months")
    ax_hist.set_title(f"(a)  {(cost == 0).mean():.0%} of municipality–months are zero (not shown)",
                      loc="left", fontsize=10, fontweight="bold", pad=12)

    monthly = df.groupby("date", sort=True)["cost_real"].sum() / 1e6
    ax_ts.plot(monthly.index, monthly.to_numpy(), color="#4c78a8", linewidth=1.4)
    ax_ts.set_xlabel("Month")
    ax_ts.set_ylabel("Regional total (R$ million)")
    ax_ts.set_title("(b)", loc="left", fontsize=11, fontweight="bold", pad=6)
    ax_ts.yaxis.set_major_formatter(FuncFormatter(lambda x, _p: f"{x:.0f}"))
    ax_ts.set_xlim(monthly.index.min(), monthly.index.max())
    save_fig(fig, "fig_2_2_spending_distribution.png")


def choropleth(gdf: gpd.GeoDataFrame, column: str, name: str, title: str, cmap: str, cbar_label: str,
               center: float | None) -> None:
    """Municipality choropleth of the analysed municipalities; the rest of the study area is grey."""
    plot_gdf = gdf.to_crs(PLOT_CRS)
    vals = pd.to_numeric(plot_gdf[column], errors="coerce")
    plot_gdf["_v"] = vals
    vmin, vmax = float(vals.min()), float(vals.max())
    norm = None
    if center is not None:
        span = max(abs(vmin - center), abs(vmax - center))
        vmin, vmax = center - span, center + span
        norm = TwoSlopeNorm(vmin=vmin, vcenter=center, vmax=vmax)

    fig, ax = plt.subplots(figsize=(12, 14))
    plot_gdf[plot_gdf["_v"].isna()].plot(ax=ax, color="#d9d9d9", edgecolor="none", linewidth=0)
    plot_gdf[plot_gdf["_v"].notna()].plot(column="_v", ax=ax, cmap=cmap, vmin=vmin, vmax=vmax, norm=norm,
                                          edgecolor="white", linewidth=0.05, legend=False)
    ax.set_title(title, fontsize=13, pad=10)
    ax.set_aspect("equal")
    ax.axis("off")
    add_north_arrow(ax, fontsize=15, linewidth=1.8)
    add_scale_bar(ax, fontsize=13, linewidth=1.1)
    sm = plt.cm.ScalarMappable(cmap=plt.get_cmap(cmap), norm=norm or plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.035, pad=0.02)
    cbar.set_label(cbar_label)
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / name, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved outputs/figures/{name}")


def fig_input_maps(mun: gpd.GeoDataFrame, panel: pd.DataFrame) -> None:
    analysed = panel[panel["water_unserved_pct"].notna()]
    metrics = analysed.groupby("IBGE").agg(mean_spei12=("SPEI_12", "mean"),
                                           water_unserved_pct=("water_unserved_pct", "first"))
    metrics.index = metrics.index.astype(str).str.zfill(7)
    gdf = mun.to_crs(4326).merge(metrics, left_on="CD_MUN", right_index=True, how="left")
    # These two maps use matplotlib's default style, as in the thesis.
    with plt.style.context("default"):
        choropleth(gdf, "mean_spei12", "fig_2_3_map_mean_spei12.png", "Mean SPEI-12, 2015–2019", "RdBu",
                   "Mean SPEI-12 (negative = drier)", center=0.0)
        choropleth(gdf, "water_unserved_pct", "fig_2_4_map_unserved_water.png",
                   "Share of population without piped water", "Purples", "Water unserved (%)", center=None)


def main() -> None:
    mun = load_municipalities()
    panel = pd.read_csv(PANEL)
    fig_input_maps(mun, panel)
    apply_style()
    fig_study_area(mun)
    fig_analysis_sample(mun, panel)
    fig_spending(panel)


if __name__ == "__main__":
    main()
