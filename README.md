# What drives Operação Carro-Pipa? Scripts and data

This repository holds the data, scripts and outputs behind the MSc thesis *What drives Operação
Carro-Pipa? Drought, structural water scarcity, and the allocation of emergency water spending in
the Brazilian Sertão* (Robin Dogruluk, Water Resources Management, Wageningen University &
Research, 2026).

The thesis asks to what extent spending on Operação Carro-Pipa (OCP), the federal water-truck
programme, is driven by drought and to what extent by structural water scarcity, and how that
spending is spread across municipalities and months. It combines monthly OCP spending for
2015–2019 with a drought index (SPEI-12, built from BR-DWGD weather data) and the share of
residents without piped water (SINISA 2024), for 746 municipalities in the nine northeastern
states, and fits a generalised additive mixed model (GAMM) with `mgcv`.

Everything the thesis reports can be rebuilt from `data/raw/` with the scripts in `scripts/`. The
fitted models, tables and figures are already in `outputs/`, so nothing has to be recomputed to
use them.

## Contents

```
data/
  raw/          inputs as used for the thesis (OCP spending, IBGE population, SINISA, BR-DWGD
                climate extract, municipal boundaries, SUDENE semi-arid polygon)
  processed/    SPEI 2015-2019 and the municipality-month panel, built by steps 01 and 02
scripts/        the analysis, numbered in the order it runs
outputs/
  models/       the three fitted GAMMs (R .rds files)
  tables/       every table and number of the thesis, as CSV
  figures/      every data figure of the thesis, named by its number in the thesis
run_all.py      runs steps 01-08 in order
```

`data/README.md` describes each data source, its origin and the panel columns.

## The analysis, step by step

| Step | Script | What it does | Thesis |
| :--- | :--- | :--- | :--- |
| 00 | `00_prepare_boundaries.py` | Optional. Cuts the nine northeastern states out of the IBGE 2025 national municipal mesh. | – |
| 00 | `00_extract_climate_gee.py` | Optional. Extracts monthly precipitation and reference evapotranspiration per municipality from BR-DWGD in Google Earth Engine (needs an Earth Engine account, about six hours). | – |
| 01 | `01_compute_spei.py` | Computes SPEI-1 to SPEI-24 per municipality: water balance summed over the window, generalised logistic distribution fitted to the 1990–2019 reference period with unbiased probability-weighted moments, converted to a standard normal score. | §2.3 |
| 02 | `02_build_panel.py` | Builds the municipality-month panel: 861 municipalities in the OCP file → 827 matching the municipal mesh → 746 with a SINISA value. | §2.4 |
| 03 | `03_describe_data.py` | Sample counts, enrolment groups, panel summary, spending cap, correlation of drought and unserved water. | Tables 2.2, 2.3 |
| 04 | `04_data_figures.py` | Study-area map, sample map, spending distribution, maps of mean SPEI-12 and unserved water. | Figures 1.1, 2.1–2.4 |
| 05 | `05_window_lag_test.py` | Tests SPEI windows of 1–24 months and lags of 0–12 months on month-to-month changes (train 2015–2017, test 2018–2019). | Annex A, Figure A.1 |
| 06 | `06_fit_models.R` | Fits the GAMMs: the independent-errors version (to set the month-to-month carry-over, ρ = 0.570), the primary model and the second model with a drought–unserved water surface. Skipped when the models already exist; `--refit` fits them again. | §2.5 |
| 07 | `07_model_results.R` | All Chapter 3 results from the saved models: drought and month curves, standing difference, model-free check, second model, term shares, error diagnostics, Figures 3.1–3.3. | Chapter 3, Tables 3.1, 3.2 |
| 08 | `08_robustness.R` | Refits the primary model with one choice changed at a time. | Annex B, Table B.1 |

Figure 2.5 (the flow from sources to results) is drawn in LaTeX in the thesis and has no script
here.

## Running it

Requirements: Python 3.12 and R 4.5 with `mgcv` (1.9.3 was used; it ships with R).

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
Rscript install_r_packages.R

python run_all.py                 # steps 01-08, using the models in outputs/models/
python run_all.py --refit         # the same, but fit the three GAMMs again
python run_all.py --only 07       # one step
```

Run everything from the repository root. Each script can also be run on its own, for example
`python scripts/03_describe_data.py` or `Rscript scripts/07_model_results.R`. Every step
overwrites its own outputs; nothing is versioned by date.

Run times on a laptop: step 01 (SPEI) about ten minutes; every other step, including refitting
the models, takes between a few seconds and two minutes.

## Where each thesis result comes from

| In the thesis | File |
| :--- | :--- |
| Sample counts, blank months, cap, correlation (Chapter 2) | `outputs/tables/data_numbers.csv` |
| Table 2.2 Enrolment groups; enrolment by state | `table_2_2_enrolment_groups.csv`, `enrolment_by_state.csv` |
| Table 2.3 Panel summary statistics | `table_2_3_panel_summary.csv` |
| Drought curve, standing difference and its interval, model-free check, second model (Chapter 3) | `results_numbers.csv` |
| Drought response by calendar month (§3.1) | `drought_month_response.csv` |
| Table 3.1 Shares of the four terms | `table_3_1_term_shares.csv` |
| Table 3.2 Error diagnostics | `table_3_2_model_diagnostics.csv` |
| Figure 3.1 surfaces; Figure 3.3 curves | `drought_month_surfaces.csv`; `interaction_curves.csv` |
| Annex A window and lag test | `window_lag_test.csv`, `window_lag_selection.csv` |
| Table B.1 Robustness checks | `table_B_1_robustness.csv` |
| SPEI check: reference-period mean ≈ 0 and SD ≈ 1 for every window | `spei_validation.csv` |
| Figures 1.1, 2.1–2.4, 3.1–3.3, A.1 | `outputs/figures/fig_*.png` |

## The models

`outputs/models/` holds the three fitted `mgcv::bam` objects used in the thesis:

- `primary_gamm.rds`: the reported model. log(1 + capped spending) on a drought curve (SPEI-12,
  lag 0), a cyclic month curve, a drought–month surface, an unserved water curve, a random
  intercept per municipality and a year effect, with AR(1) errors (ρ = 0.570).
- `interaction_gamm.rds`: the same plus a drought–unserved water surface.
- `iid_gamm.rds`: the primary formula with independent errors. It sets ρ and is the "no carry-over"
  row of the robustness table.

Load one in R with `m <- readRDS("outputs/models/primary_gamm.rds")`; `summary(m)`, `plot(m)` and
`predict(m, type = "terms")` work as usual. The data each model was fitted on is in `m$model`.
Spending is capped at R$ 703,321, the 99th percentile of the 827-municipality panel, before the
log is taken.

Running `python run_all.py --refit` from the raw data gives the same models (coefficients equal to
within 10⁻⁹) and the same tables and figures as the thesis. One small difference with the thesis
text: Chapter 3 gives the 95% interval of the standing difference as 2.69 to 6.04, while this code
gives 2.69 to 6.05 (Annex B, at one decimal, shows 2.7 to 6.0 for both). The interval comes from
random draws of the model coefficients, and the thesis figure was taken from an earlier run.

## Reading the results

- The outcome is spending, a measure of where and when the government sends trucks. It says
  nothing about whether people received enough water.
- SPEI = 0 is each municipality's own 1990–2019 average, not the absence of water stress.
- Municipalities without an OCP record are not in the panel. The results describe how spending is
  divided among the municipalities the programme reaches.
- Unserved water is a single 2024 snapshot, so its curve compares municipalities with each other.

## Licence and citation

The code is released under the MIT licence (`LICENSE`). The tables, figures and fitted models in
`outputs/` may be reused under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) with a
reference to the thesis. The data in `data/raw/` come from the public sources listed in
`data/README.md`, whose terms apply.

Please cite the thesis as: Dogruluk, R. (2026). *What drives Operação Carro-Pipa? Drought,
structural water scarcity, and the allocation of emergency water spending in the Brazilian
Sertão*. MSc thesis, Wageningen University & Research.
