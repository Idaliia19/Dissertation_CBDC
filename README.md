# CBDC deposit-outflow vulnerability — dissertation data & code

Empirical machinery for a dissertation on how a CBDC-style, fast digital-deposit outflow would stress US banks, anchored on the March 2023 run (SVB, Signature, First Republic). Three data blocks — FFIEC Call Reports, CRSP stock prices (WRDS), and a corpus of Fed CBDC communications — are joined by an identifier crosswalk (bank RSSD ↔ CRSP permno). Methodology, hypotheses and limitations live in the dissertation (Chapter 3); this README covers what runs.

## Research questions

- **RQ1** — which bank characteristics predict sensitivity to fast, CBDC-style deposit outflows, and can ML identify the most exposed banks? (Call Reports)
- **RQ2** — event study of listed-bank stock reactions to Fed CBDC communications: do protective design signals (Safeguard signal) produce less negative reactions?
- **RQ3** — bridge regression linking each bank's RQ1 vulnerability score to its RQ2 abnormal return.

## Status

| Stage | Script | Output | State |
|---|---|---|---|
| Identifier crosswalk (bank RSSD→holder→permco→permno) | *not yet in `scripts/`* † | `crosswalk_rssd_permno.csv`, `sample_banks.csv` | Built |
| Block-1 panel (2022Q4 cross-section) | `scripts/build_panel.py` | `panel_2022Q4.csv` | Built |
| RQ1 model (OLS + RF + GB, CV, SHAP) | `scripts/run_rq1.py` | `vulnerability_scores.csv`, `rq1_results.txt`, `rq1_shap_summary.png` | Built |
| Block-2 CRSP extraction | *not yet in `scripts/`* † | `data/raw/wrds/*.parquet` | Built (data on disk) |
| RQ2 event study | — | — | Pending |
| RQ3 bridge regression | — | — | Pending |

† The WRDS-pull and crosswalk-build scripts were run but are **not yet saved under `scripts/`** — a known reproducibility gap; their outputs are on disk. Call Report and MDRM downloads were manual.

Sample: **278 linked / 277 modelled** — one merger exit (Farmers National Bank of Emlenton, IDRSSD 119528) is dropped for lack of a 2023Q1 outcome. Filer mix: 199 × FFIEC 041, 45 × 051, 34 × 031 (balance-sheet scope is chosen per filer). The panel is a single 2022Q4 cross-section: predictors at 2022Q4, outcome from 2023Q1 deposits.
Failed banks are right-censored at `dep_growth = -1.0` with `censored = True`, so no analysis may read the outcome without reading the flag. The three censored failures **stay in training** — dropping them reintroduces survivorship bias.

## Repository layout

```
data/                             # git-ignored
  raw/                            # READ-ONLY sources
    call_MMDDYYYY.zip             # 15 FFIEC Call Report archives, 2019Q4–2023Q2
    mdrm/MDRM_CSV.csv             # MDRM data dictionary
    wrds/                         # CRSP: dsf, dsi, stocknames, dsedelist (parquet)
  crsp_20240930 (1).csv           # CRSP–FRB link: holder RSSD → permco
  CSV_RELATIONSHIPS.CSV  CSV_ATTRIBUTES_ACTIVE.CSV   # FFIEC NIC edges + attributes
  fdic_failures.csv  Fed_Communications_Block3.xlsx  # failures; RQ2 corpus (11 items)
  processed/                      # WRITE target — all generated here
    crosswalk_rssd_permno.csv   sample_banks.csv   panel_2022Q4.csv
    vulnerability_scores.csv    rq1_results.txt    rq1_shap_summary.png
scripts/
  build_panel.py                  # extract + construct + clean the panel
  run_rq1.py                      # OLS + RF + GB, CV, SHAP, vulnerability scores
```

Python deps: `pandas, pyarrow, numpy, scikit-learn, statsmodels, shap, matplotlib, openpyxl` (plus `wrds` for the CRSP pull).

## Reproduce

```bash
# prerequisite on disk: data/processed/sample_banks.csv
python scripts/build_panel.py    # -> data/processed/panel_2022Q4.csv
python scripts/run_rq1.py        # -> vulnerability_scores.csv, rq1_*.{txt,png}
```
Both scripts read only from `data/raw/`, write only to `data/processed/`, use a fixed seed, and re-run with no manual edits.

## Data sources

| What | Source | Auth |
|---|---|---|
| Call Reports (bulk, tab-delimited) | `cdr.ffiec.gov` "Call Reports — Single Period" | none |
| MDRM dictionary | `federalreserve.gov/apps/mdrm` | none |
| CRSP daily stock/index/delist/names | WRDS (`crsp` library) | WRDS login |
| CRSP–FRB link (RSSD→permco) | NY Fed / WRDS | none |
| FFIEC NIC relationships & attributes | `ffiec.gov/npw` bulk CSV | none |
| FDIC failed-bank list | FDIC (saved CSV on disk) | none |

CDR serves the latest *amended* filings, so the zips on disk are a fixed vintage; there is no `manifest.json` / SHA-256 freeze yet.

## Identifier crosswalk — the grain fix

Call Reports are keyed on the **bank** RSSD (`IDRSSD`); the CRSP–FRB link maps **holding-company** RSSD → permco, so matching the two directly linked only 9 banks and dropped SVB. Walking each filer up its FFIEC NIC control chain to the top holder present in the CRSP–FRB link gives **bank-IDRSSD → holder-RSSD → permco → permno**, recovering **278** banks including SVB. Where one holder owns several filing banks (30 cases), the largest subsidiary by assets is kept and flagged.
