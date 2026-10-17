"""Step 03: describe the study area, the sample and the panel (Chapter 2).

Outputs (outputs/tables/):
    table_2_2_enrolment_groups.csv   Table 2.2: analysed / OCP record without SINISA value / no record
    table_2_3_panel_summary.csv      Table 2.3: spending, SPEI-12 and unserved water, 746 analysed
    enrolment_by_state.csv           share of each state's municipalities with an OCP record
    data_numbers.csv                 every other number Chapter 2 quotes about the data

Usage (from the repository root):
    python scripts/03_describe_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    MUNICIPALITIES, OCP_SPENDING, PANEL, SEMIARID_MUNICIPALITIES, SINISA, SPEI, STATE_ORDER, TABLES,
    WINSOR_Q,
)


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(PANEL)
    spei = pd.read_csv(SPEI).rename(columns={"CD_MUN": "IBGE"})
    area = pd.DataFrame(gpd.read_parquet(MUNICIPALITIES)[["CD_MUN", "SIGLA_UF"]])
    area["IBGE"] = area["CD_MUN"].astype(np.int64)

    ocp_file = pd.read_csv(OCP_SPENDING, usecols=["IBGE"])
    n_ocp_file = ocp_file["IBGE"].astype(str).str.replace("IBGE:", "").nunique()

    per_mun = panel.groupby("IBGE").agg(
        uf=("uf", "first"), unserved=("water_unserved_pct", "first"),
        population=("population_2025", "first"),
    )
    in_panel = set(per_mun.index)
    analysed = set(per_mun.index[per_mun["unserved"].notna()])
    no_sinisa = in_panel - analysed
    no_record = set(area["IBGE"]) - in_panel

    sinisa = pd.read_csv(SINISA, encoding="ISO-8859-1", usecols=["cod_IBGE", "IAG0001"])
    sinisa["unserved"] = 100 - pd.to_numeric(sinisa["IAG0001"].astype(str).str.replace(",", "."), errors="coerce")
    sinisa = sinisa.set_index("cod_IBGE")["unserved"]
    mean_spei12 = spei.groupby("IBGE")["SPEI_12"].mean()

    # Table 2.2
    groups = [("Analysed", analysed), ("OCP record, no SINISA value", no_sinisa), ("No OCP record", no_record)]
    rows = []
    for name, ids in groups:
        u = sinisa.reindex(sorted(ids)).dropna()
        rows.append({
            "group": name,
            "municipalities": len(ids),
            "with_sinisa_value": len(u),
            "mean_unserved_pct": round(u.mean(), 1) if len(u) else np.nan,
            "mean_spei12_2015_2019": round(mean_spei12.reindex(sorted(ids)).mean(), 2),
        })
    pd.DataFrame(rows).to_csv(TABLES / "table_2_2_enrolment_groups.csv", index=False, encoding="utf-8")

    # Enrolment by state
    area["has_ocp_record"] = area["IBGE"].isin(in_panel)
    by_state = area.groupby("SIGLA_UF").agg(municipalities=("IBGE", "size"), with_ocp_record=("has_ocp_record", "sum"))
    by_state["share_with_record"] = (by_state["with_ocp_record"] / by_state["municipalities"]).round(3)
    by_state.reindex(STATE_ORDER).rename_axis("state").to_csv(TABLES / "enrolment_by_state.csv", encoding="utf-8")

    # Blank months and the 42,008 municipality-months
    blank_all = panel.groupby(["year", "month"])["cost_real"].apply(lambda s: s.isna().all())
    blank_months = [f"{y}-{m:02d}" for (y, m), b in blank_all.items() if b]
    a = panel[panel["IBGE"].isin(analysed)].copy()
    a["ym"] = a["year"].astype(str) + "-" + a["month"].map("{:02d}".format)
    in_blank = a["ym"].isin(blank_months)
    n_blank_calendar = int(in_blank.sum())
    n_late = int((a["cost_real"].isna() & ~in_blank).sum())
    spend = a["cost_real"].dropna()

    # Table 2.3
    u746 = per_mun.loc[sorted(analysed), "unserved"]
    def describe(s: pd.Series, name: str, digits: int) -> dict:
        return {"variable": name, "N": int(s.count()), "mean": round(s.mean(), digits),
                "SD": round(s.std(), digits), "min": round(s.min(), digits), "max": round(s.max(), digits)}
    pd.DataFrame([
        describe(spend, "OCP spending (R$)", 0),
        describe(a["SPEI_12"], "SPEI-12", 2),
        describe(u746, "Unserved water (%)", 1),
    ]).to_csv(TABLES / "table_2_3_panel_summary.csv", index=False, encoding="utf-8")

    # Cap, correlation, semi-arid membership
    cap = float(panel["cost_real"].quantile(WINSOR_Q))
    m746 = mean_spei12.reindex(sorted(analysed))
    semiarid = pyogrio.read_dataframe(SEMIARID_MUNICIPALITIES, read_geometry=False)
    semiarid_ids = set(semiarid["CD_GEOCMU"].astype(np.int64))

    numbers = [
        ("municipalities in the nine-state study area", len(area)),
        ("municipalities in the OCP file", n_ocp_file),
        ("OCP municipalities matching the municipal mesh", len(in_panel)),
        ("municipality-months in the matched panel", len(panel)),
        ("matched municipalities without a SINISA value", len(no_sinisa)),
        ("analysed municipalities", len(analysed)),
        ("municipalities without an OCP record", len(no_record)),
        ("residents of the analysed municipalities (IBGE 2025)", int(per_mun.loc[sorted(analysed), "population"].sum())),
        ("calendar months blank for every municipality", ", ".join(blank_months)),
        ("analysed municipality-months in those blank months", n_blank_calendar),
        ("analysed municipality-months blank because of late entry", n_late),
        ("analysed municipality-months", len(spend)),
        ("share of analysed municipality-months with zero spending", round((spend == 0).mean(), 4)),
        ("median monthly spending (R$)", round(spend.median(), 0)),
        ("SD / mean of monthly spending", round(spend.std() / spend.mean(), 2)),
        ("spending cap: 99th percentile in the 827-municipality panel (R$)", round(cap, 0)),
        ("analysed municipality-months above the cap", int((spend > cap).sum())),
        ("correlation of mean SPEI-12 and unserved water (Pearson, 746)", round(m746.corr(u746), 3)),
        ("correlation of mean SPEI-12 and unserved water (Spearman, 746)", round(m746.corr(u746, method="spearman"), 3)),
        ("municipalities in the official semi-arid list (SUDENE)", len(semiarid_ids)),
        ("analysed municipalities in the semi-arid list", len(analysed & semiarid_ids)),
        ("matched (827) municipalities in the semi-arid list", len(in_panel & semiarid_ids)),
        ("municipalities without an OCP record in the semi-arid list", len(no_record & semiarid_ids)),
    ]
    out = pd.DataFrame(numbers, columns=["quantity", "value"])
    out.to_csv(TABLES / "data_numbers.csv", index=False, encoding="utf-8")
    print(out.to_string(index=False))
    print(pd.read_csv(TABLES / "table_2_2_enrolment_groups.csv").to_string(index=False))
    print(pd.read_csv(TABLES / "table_2_3_panel_summary.csv").to_string(index=False))


if __name__ == "__main__":
    main()
