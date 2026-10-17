"""Step 02: build the municipality-month panel, 2015-2019.

Each row is one municipality in one month, with its OCP spending, its SPEI and its unserved water.

1. OCP spending (federal transparency portal extract, December-2019 reais, deflated with the IPCA)
   is reshaped from one column per month to one row per municipality-month. The file covers 861
   municipalities. A blank cell is a month without a record (dropped later by the models); a zero
   is a month in which no trucks were paid.
2. An inner merge with the climate data keeps the 827 municipalities that match the IBGE 2025
   municipal mesh of the nine states (49,620 municipality-months).
3. IBGE 2025 population and the SINISA 2024 water indicators are added. Unserved water is
   100 minus IAG0001, the share of the population served by the public water network. Water loss
   (IAG2013, used only in a robustness check) is filled with the state median where missing.
   Eighty-one of the 827 municipalities have no SINISA value; the models leave them out, which
   gives the 746 analysed municipalities.

Inputs:  data/raw/ocp_spending/ocp_spending_real_dec2019.csv
         data/processed/spei_2015_2019.csv.gz
         data/raw/population/ibge_population_2025_municipalities.csv
         data/raw/sinisa/sinisa_2024_water_indicators_municipal.csv
Output:  data/processed/panel_2015_2019.csv.gz

Usage (from the repository root):
    python scripts/02_build_panel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import OCP_SPENDING, PANEL, POPULATION, SINISA, SPEI, SPEI_WINDOWS  # noqa: E402


def load_spending() -> pd.DataFrame:
    wide = pd.read_csv(OCP_SPENDING)
    month_cols = [c for c in wide.columns if "-" in c]
    long = wide.melt(
        id_vars=["IBGE", "UF", "Estado", "Municipio"], value_vars=month_cols,
        var_name="date", value_name="cost_real",
    )
    long[["year", "month"]] = long["date"].str.split("-", expand=True).astype(int)
    long["IBGE"] = long["IBGE"].astype(str).str.replace("IBGE:", "").astype(np.int64)
    return long.rename(columns={"UF": "uf", "Estado": "state", "Municipio": "municipality"})


def load_population() -> pd.DataFrame:
    pop = pd.read_csv(POPULATION, encoding="ISO-8859-1", skipinitialspace=True, usecols=[0, 1, 2, 3, 4])
    pop.columns = ["UF", "COD_UF", "COD_MUN", "NOME", "POP"]
    pop["IBGE"] = (pop["COD_UF"].astype(str) + pop["COD_MUN"].astype(str).str.zfill(5)).astype(np.int64)
    pop["population_2025"] = pd.to_numeric(
        pop["POP"].astype(str).str.replace("[^0-9]", "", regex=True), errors="coerce"
    )
    return pop[["IBGE", "population_2025"]]


def load_sinisa() -> pd.DataFrame:
    s = pd.read_csv(SINISA, encoding="ISO-8859-1", usecols=["cod_IBGE", "IAG0001", "IAG2013"])
    s = s.rename(columns={"cod_IBGE": "IBGE", "IAG0001": "water_coverage_pct", "IAG2013": "water_loss_pct"})
    s["IBGE"] = s["IBGE"].astype(np.int64)
    for col in ["water_coverage_pct", "water_loss_pct"]:
        s[col] = pd.to_numeric(s[col].astype(str).str.replace(",", "."), errors="coerce")
    return s


def main() -> None:
    spending = load_spending()
    spei = pd.read_csv(SPEI).rename(columns={"CD_MUN": "IBGE"})
    spei["IBGE"] = spei["IBGE"].astype(np.int64)

    print(f"OCP file: {spending['IBGE'].nunique()} municipalities")
    panel = spending.merge(spei, on=["IBGE", "year", "month"], how="inner")
    print(f"Matched with the municipal mesh: {panel['IBGE'].nunique()} municipalities, "
          f"{len(panel):,} municipality-months")

    panel = panel.merge(load_population(), on="IBGE", how="left")
    panel = panel.merge(load_sinisa(), on="IBGE", how="left")
    panel["water_unserved_pct"] = 100 - panel["water_coverage_pct"]
    panel["water_loss_pct"] = panel["water_loss_pct"].fillna(
        panel.groupby("state")["water_loss_pct"].transform("median")
    )
    n_sinisa = panel.loc[panel["water_unserved_pct"].notna(), "IBGE"].nunique()
    print(f"With a SINISA unserved-water value: {n_sinisa} municipalities")

    cols = [
        "IBGE", "uf", "state", "municipality", "year", "month", "cost_real", "population_2025",
        "water_coverage_pct", "water_unserved_pct", "water_loss_pct",
        "precip_mm", "eto_mm", "water_balance_mm",
    ] + [f"SPEI_{w}" for w in SPEI_WINDOWS]
    panel = panel[cols].sort_values(["IBGE", "year", "month"]).reset_index(drop=True)
    PANEL.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(PANEL, index=False, encoding="utf-8", compression={"method": "gzip", "mtime": 0})
    print(f"Wrote {PANEL.name}")


if __name__ == "__main__":
    main()
