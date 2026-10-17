"""Optional step 00: build the two boundary files in data/raw/boundaries/ from the IBGE download.

The repository already contains both outputs, so this step only needs to be run to rebuild them.

Input: the IBGE 2025 municipal mesh for all of Brazil (shapefile "BR_Municipios_2025", about 320 MB),
downloaded from https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/
15774-malhas.html and passed as the first argument.

Outputs:
    data/raw/boundaries/ne_municipalities_2025.parquet  the 1,794 municipalities of the nine
                                                        northeastern states, geometry unchanged
    data/raw/boundaries/brazil_outline_2025.parquet      all municipalities dissolved into one
                                                        outline (used for the inset of Figure 1.1)

Usage (from the repository root):
    python scripts/00_prepare_boundaries.py path/to/BR_Municipios_2025.shp
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import BRAZIL_OUTLINE, MUNICIPALITIES, STATE_ORDER  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    brazil = gpd.read_file(sys.argv[1])
    if brazil.crs is None:
        brazil = brazil.set_crs(4674)  # SIRGAS 2000, the CRS of the IBGE mesh

    ne = brazil[brazil["SIGLA_UF"].isin(STATE_ORDER)].copy()
    if len(ne) != 1794:
        raise ValueError(f"Expected 1,794 municipalities in the nine states, found {len(ne)}")
    MUNICIPALITIES.parent.mkdir(parents=True, exist_ok=True)
    ne.to_parquet(MUNICIPALITIES)
    print(f"Wrote {MUNICIPALITIES.name}: {len(ne)} municipalities")

    outline = brazil[["geometry"]].dissolve()
    outline.to_parquet(BRAZIL_OUTLINE)
    print(f"Wrote {BRAZIL_OUTLINE.name}")


if __name__ == "__main__":
    main()
