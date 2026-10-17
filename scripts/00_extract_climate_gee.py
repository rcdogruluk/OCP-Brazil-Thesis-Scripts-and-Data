"""Optional step 00: extract monthly precipitation and reference evapotranspiration from BR-DWGD.

The repository already contains the result (data/raw/climate/br_dwgd_monthly_climate_1961_2020.csv.gz),
so this step only needs to be run to rebuild it. It needs a Google Earth Engine account and takes
about six hours (8,640 requests).

For every municipality of the nine states and every month of 1961-2020, the daily BR-DWGD grids
(Xavier et al. 2022) are rescaled with the published factors, summed over the month and averaged
over the municipality polygon at a 10 km scale:

    precip_mm         monthly precipitation (band pr)
    eto_mm            monthly reference evapotranspiration (band ET)
    water_balance_mm  precip_mm - eto_mm, the input of the SPEI

Usage (from the repository root):
    set GEE_PROJECT=<your Earth Engine cloud project>      (Windows; export GEE_PROJECT=... elsewhere)
    python scripts/00_extract_climate_gee.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import ee
import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CLIMATE, MUNICIPALITIES  # noqa: E402

BR_DWGD_ASSET = "projects/ee-alexandrexavier/assets/BR-DWGD"
YEARS = list(range(1961, 2021))
BATCH_SIZE = 150
PR_SCALE, PR_OFFSET = 0.00686666, 225.0  # BR-DWGD published scaling
ET_SCALE, ET_OFFSET = 0.051181102, 0.0


def rescale(image: ee.Image, band: str, scale: float, offset: float) -> ee.Image:
    return (
        image.select(band).multiply(scale).add(offset).max(0).rename(band)
        .copyProperties(image, image.propertyNames())
    )


def monthly_image(year: int, month: int) -> ee.Image:
    start = ee.Date.fromYMD(year, month, 1)
    days = ee.ImageCollection(BR_DWGD_ASSET).filterDate(start, start.advance(1, "month"))
    precip = days.map(lambda im: rescale(im, "pr", PR_SCALE, PR_OFFSET)).sum().rename("precip_mm")
    eto = days.map(lambda im: rescale(im, "ET", ET_SCALE, ET_OFFSET)).sum().rename("eto_mm")
    return precip.addBands(eto).addBands(precip.subtract(eto).rename("water_balance_mm"))


def main() -> None:
    project = os.environ.get("GEE_PROJECT")
    if not project:
        sys.exit("Set GEE_PROJECT to your Earth Engine cloud project first.")
    try:
        ee.Initialize(project=project)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project)

    gdf = gpd.read_parquet(MUNICIPALITIES)[["CD_MUN", "geometry"]]
    gdf["geometry"] = gdf["geometry"].simplify(0.005)
    rows, start = [], datetime.now()
    for b in range(0, len(gdf), BATCH_SIZE):
        fc = ee.FeatureCollection(json.loads(gdf.iloc[b : b + BATCH_SIZE].to_json()))
        print(f"Batch {b // BATCH_SIZE + 1}/{(len(gdf) + BATCH_SIZE - 1) // BATCH_SIZE}", flush=True)
        for year in YEARS:
            for month in range(1, 13):
                result = monthly_image(year, month).reduceRegions(
                    collection=fc, reducer=ee.Reducer.mean(), scale=10000
                )
                for feat in result.getInfo()["features"]:
                    p = feat["properties"]
                    rows.append({
                        "CD_MUN": p.get("CD_MUN"), "year": year, "month": month,
                        "precip_mm": p.get("precip_mm"), "eto_mm": p.get("eto_mm"),
                        "water_balance_mm": p.get("water_balance_mm"),
                    })
    out = pd.DataFrame(rows)
    CLIMATE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(CLIMATE, index=False, encoding="utf-8")
    print(f"Wrote {len(out):,} rows to {CLIMATE.name} in {datetime.now() - start}")


if __name__ == "__main__":
    main()
