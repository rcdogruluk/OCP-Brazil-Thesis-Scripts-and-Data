# Data

`raw/` holds the inputs of the analysis as they were used for the thesis. `processed/` holds the two
files that the scripts build from them (steps 01 and 02), so the later steps can be run without
rebuilding them.

All sources are public and aggregated to municipalities; none contains personal data. Files are
redistributed here so that the analysis can be reproduced. The terms of the original providers
apply, so please cite the sources below when you use the data.

## raw/

| Folder | Files | Source | Used for |
| :--- | :--- | :--- | :--- |
| `ocp_spending/` | `ocp_spending_real_dec2019.csv` (used), `ocp_spending_nominal.csv`, `ipca_deflators.csv`, `ocp_spending_2015_2019_original.xlsx` (the same three tables as one workbook) | Monthly Operação Carro-Pipa payments per municipality, January 2015 to December 2019, from the federal transparency portal (Controladoria-Geral da União, [Portal da Transparência](https://portaldatransparencia.gov.br/)). The real series is in December-2019 reais, deflated with the IPCA (factors in `ipca_deflators.csv`). 861 municipalities, one column per month. | Outcome (OCP spending) |
| `population/` | `ibge_population_2025_municipalities.csv` (used), `ibge_population_2025_original.xls`, `ibge_notes.txt` | IBGE, *Estimativas da população residente nos municípios brasileiros, 1 de julho de 2025* ([IBGE](https://www.ibge.gov.br/estatisticas/sociais/populacao/9103-estimativas-de-populacao.html)). The notes list court-ordered population figures for some municipalities. | Size of the sample; per-resident robustness check |
| `sinisa/` | `sinisa_2024_water_indicators_municipal.csv` (used), the original workbook, the indicator dictionary and the methodological note | Ministério das Cidades, SINISA, *Indicadores de abastecimento de água, base municipal, ano de referência 2024*, published 18 Dec 2025 ([SINISA](https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/saneamento/sinisa/resultados-sinisa)). Original file name: `Indicadores de Gestão.csv` (ISO-8859-1). | Unserved water = 100 − IAG0001 (share of residents served by the public network); water loss = IAG2013 (robustness only) |
| `climate/` | `br_dwgd_monthly_climate_1961_2020.csv.gz` | Brazilian Daily Weather Gridded Data (BR-DWGD; Xavier et al. 2022, [doi:10.1002/joc.7731](https://doi.org/10.1002/joc.7731)), extracted with Google Earth Engine by `scripts/00_extract_climate_gee.py`: monthly sums of daily precipitation (`pr`) and reference evapotranspiration (`ET`), averaged over each municipality polygon at 10 km. 1,794 municipalities × 720 months. Fernando de Noronha (PE), an island outside the grid, is empty. | SPEI (step 01) |
| `boundaries/` | `ne_municipalities_2025.parquet`, `brazil_outline_2025.parquet` | IBGE, *Malha municipal 2025* ([IBGE](https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/15774-malhas.html)). The first file is the 1,794 municipalities of the nine northeastern states with unchanged geometry; the second is all of Brazil dissolved into one outline. Both are made from the national shapefile by `scripts/00_prepare_boundaries.py`. SIRGAS 2000 (EPSG:4674). | Study area, climate extraction, maps |
| `semiarid/` | `LIM_Semiarido_OFICIAL_POLIGONAL.*`, `LIM_Semiarido_Municipal_OFICIAL.*` | Instituto Nacional do Semiárido, *Municípios, UF e Polígono do Semiárido Brasileiro (SAB/SUDENE)* ([INSA](https://www.gov.br/insa/pt-br/centrais-de-conteudo/mapas/mapas-em-shapefile/municipios_uf_poligono_sab_sudene.rar)). The official semi-arid polygon and its list of 1,262 municipalities. | Context only: Figure 1.1 and the count of analysed municipalities inside the polygon. It plays no part in selecting the sample. |

## processed/

| File | Made by | Contents |
| :--- | :--- | :--- |
| `spei_2015_2019.csv.gz` | `scripts/01_compute_spei.py` | SPEI-1 to SPEI-24, precipitation, reference evapotranspiration and water balance for the 1,794 municipalities, January 2015 to December 2019. Reference period 1990–2019. |
| `panel_2015_2019.csv.gz` | `scripts/02_build_panel.py` | The municipality-month panel: the 827 OCP municipalities that match the municipal mesh × 60 months (49,620 rows), with spending, population, SINISA indicators and SPEI. The 81 municipalities without a SINISA value have an empty `water_unserved_pct` and are left out of the models, which gives the 746 analysed municipalities. |

### Panel columns

| Column | Meaning |
| :--- | :--- |
| `IBGE` | 7-digit IBGE municipality code |
| `uf`, `state`, `municipality` | State code, state name and municipality name as in the OCP file |
| `year`, `month` | Calendar year and month |
| `cost_real` | OCP spending in the month, December-2019 reais. Empty = no record for that month (three calendar months are empty for every municipality: November 2016, December 2016, December 2017); 0 = no trucks paid. |
| `population_2025` | IBGE 2025 population estimate |
| `water_coverage_pct` | SINISA IAG0001: share of residents served by the public water network (%) |
| `water_unserved_pct` | 100 − `water_coverage_pct`: unserved water, the structural variable of the thesis |
| `water_loss_pct` | SINISA IAG2013: water lost in distribution (%), state median where missing; robustness only |
| `precip_mm`, `eto_mm`, `water_balance_mm` | BR-DWGD monthly precipitation, reference evapotranspiration and their difference |
| `SPEI_1` … `SPEI_24` | SPEI over trailing windows of 1–24 months. The thesis uses `SPEI_12`. SPEI = 0 is the municipality's 1990–2019 average, not the absence of water stress. |
