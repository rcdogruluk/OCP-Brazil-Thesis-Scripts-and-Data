"""Paths, constants and plotting helpers shared by the Python scripts."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
MODELS = ROOT / "outputs" / "models"

OCP_SPENDING = RAW / "ocp_spending" / "ocp_spending_real_dec2019.csv"
POPULATION = RAW / "population" / "ibge_population_2025_municipalities.csv"
SINISA = RAW / "sinisa" / "sinisa_2024_water_indicators_municipal.csv"
CLIMATE = RAW / "climate" / "br_dwgd_monthly_climate_1961_2020.csv.gz"
MUNICIPALITIES = RAW / "boundaries" / "ne_municipalities_2025.parquet"
BRAZIL_OUTLINE = RAW / "boundaries" / "brazil_outline_2025.parquet"
SEMIARID_POLYGON = RAW / "semiarid" / "LIM_Semiarido_OFICIAL_POLIGONAL.shp"
SEMIARID_MUNICIPALITIES = RAW / "semiarid" / "LIM_Semiarido_Municipal_OFICIAL.dbf"

SPEI = PROCESSED / "spei_2015_2019.csv.gz"
PANEL = PROCESSED / "panel_2015_2019.csv.gz"

YEARS = (2015, 2019)
SPEI_BASELINE = (1990, 2019)
SPEI_WINDOWS = list(range(1, 25))
WINSOR_Q = 0.99  # spending cap: 99th percentile of the 827-municipality panel

STATE_ORDER = ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]
STATE_NAMES = {
    "AL": "Alagoas",
    "BA": "Bahia",
    "CE": "Ceará",
    "MA": "Maranhão",
    "PB": "Paraíba",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RN": "Rio Grande do Norte",
    "SE": "Sergipe",
}
STATE_COLORS = {
    "AL": "#4c78a8",
    "BA": "#f58518",
    "CE": "#54a24b",
    "MA": "#b279a2",
    "PB": "#eeca3b",
    "PE": "#72b7b2",
    "PI": "#e45756",
    "RN": "#9d755d",
    "SE": "#6b6b6b",
}

# Maps are drawn in SIRGAS 2000 / Brazil Polyconic (metres), so the scale bar is real distance.
PLOT_CRS = 5880
DPI = 300


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["DejaVu Serif", "Liberation Serif", "Nimbus Roman"],
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "legend.fontsize": 8.5,
            "figure.dpi": DPI,
            "savefig.dpi": DPI,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def save_fig(fig: plt.Figure, name: str) -> Path:
    FIGURES.mkdir(parents=True, exist_ok=True)
    out = FIGURES / name
    fig.savefig(out, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved {out.relative_to(ROOT)}")
    return out


# Round lengths a reader can divide in their head, in kilometres.
NICE_LENGTHS_KM = [10, 25, 50, 100, 150, 200, 250, 300, 400, 500, 750, 1000]


def _nice_length_km(target_km: float) -> int:
    """Largest tidy bar length that does not exceed the target width."""
    candidates = [km for km in NICE_LENGTHS_KM if km <= target_km]
    return candidates[-1] if candidates else NICE_LENGTHS_KM[0]


def add_north_arrow(
    ax: plt.Axes,
    *,
    x: float = 0.90,
    y: float = 0.93,
    length: float = 0.075,
    fontsize: float = 9.0,
    linewidth: float = 1.1,
    color: str = "#1a1a1a",
) -> None:
    """Draw a north arrow in axes-fraction coordinates."""
    ax.annotate(
        "",
        xy=(x, y),
        xytext=(x, y - length),
        xycoords="axes fraction",
        textcoords="axes fraction",
        arrowprops={
            "arrowstyle": "-|>",
            "color": color,
            "linewidth": linewidth,
            "shrinkA": 0,
            "shrinkB": 0,
        },
        annotation_clip=False,
    )
    ax.annotate(
        "N",
        xy=(x, y + 0.012),
        xycoords="axes fraction",
        ha="center",
        va="bottom",
        fontsize=fontsize,
        fontweight="bold",
        color=color,
        annotation_clip=False,
    )


def add_scale_bar(
    ax: plt.Axes,
    *,
    target_fraction: float = 0.26,
    x_frac: float = 0.05,
    y_frac: float = 0.05,
    height_frac: float = 0.011,
    fontsize: float = 8.5,
    linewidth: float = 0.7,
    color: str = "#1a1a1a",
) -> int:
    """Draw a two-segment scale bar. Axes units must be metres.

    Returns the bar length in kilometres so callers can log or caption it.
    """
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x_span, y_span = x1 - x0, y1 - y0

    length_km = _nice_length_km(x_span * target_fraction / 1000.0)
    length_m = length_km * 1000.0

    bar_x = x0 + x_frac * x_span
    bar_y = y0 + y_frac * y_span
    bar_h = height_frac * y_span
    half = length_m / 2.0

    for i, fill in enumerate((color, "white")):
        ax.add_patch(
            Rectangle(
                (bar_x + i * half, bar_y),
                half,
                bar_h,
                facecolor=fill,
                edgecolor=color,
                linewidth=linewidth,
                zorder=5,
            )
        )

    for offset, label in ((0.0, "0"), (length_m, f"{length_km} km")):
        ax.annotate(
            label,
            xy=(bar_x + offset, bar_y + bar_h * 1.6),
            ha="center",
            va="bottom",
            fontsize=fontsize,
            color=color,
            zorder=5,
        )

    return length_km
