# CBDC deposit-outflow vulnerability — dissertation data & code

Empirical machinery for a dissertation on how a CBDC-style, fast digital-deposit
outflow would stress US banks, anchored on the March 2023 run (SVB, Signature,
First Republic). Three data blocks feed the research questions:

- **Block 1 — Call Reports (FFIEC).** Bank balance-sheet characteristics → **RQ1**.
- **Block 2 — CRSP stock prices (WRDS).** Listed-bank equity returns → **RQ3**.
- **Block 3 — Fed communications.** A curated CBDC-signal corpus → later block.

The blocks are joined by an identifier crosswalk (bank RSSD ↔ CRSP permno) built
from FFIEC NIC relationships and the CRSP–FRB link.

## Research questions

> **RQ1.** Which bank characteristics predict sensitivity to fast, CBDC-style
> deposit outflows, and can machine learning identify the most exposed banks?
>
> **H1a.** Reliance on retail and uninsured deposits, unrealised securities
> losses, and thin liquidity and capital predict the deposit outflows observed
> in the 2023 stress.
>
> **H1b.** Tree-based ML predicts outflow sensitivity more accurately than linear
> baselines, with vulnerability concentrating in smaller, less-diversified banks.

**RQ3** (planned) links each bank's out-of-sample vulnerability score to its
holding company's stock reaction during the 2023 stress. Block 3 supports a later
question on Fed CBDC-design signalling.

## Status (what is actually built)

| Stage | Script | Output | State |
|---|---|---|---|
| Identifier crosswalk (RSSD→holder→permco→permno) | *not yet in `scripts/`* † | `data/processed/crosswalk_rssd_permno.csv`, `sample_banks.csv` | ✅ built |
| Block-1 panel (2022Q4 cross-section) | `scripts/build_panel.py` | `data/processed/panel_2022Q4.csv` | ✅ built |
| RQ1 Model 1 (supervised ML) | `scripts/run_rq1.py` | `vulnerability_scores.csv`, `rq1_shap_summary.png`, `rq1_results.txt` | ✅ built |
| Block-2 CRSP extraction | *not committed* † | `data/raw/wrds/*.parquet` | ✅ data on disk |
| Block-3 processing | — | — | ⏳ raw only |
| RQ3 event study | — | — | ⏳ pending |

† Two generating scripts (WRDS pull, crosswalk build) were run but are **not yet
saved under `scripts/`** — a known reproducibility gap; their outputs are on disk.
The MDRM/Call-Report downloads were done manually (no downloader script).

**The panel is a single 2022Q4 cross-section (one row per bank), not the
15-quarter bank-quarter panel described in earlier drafts.** Predictors are
measured at 2022Q4; the outcome uses 2023Q1 deposits.

## Repository layout

```
data/
  raw/                          # READ-ONLY source data (never modified)
    call_MMDDYYYY.zip           # 15 FFIEC Call Report archives, 2019Q4–2023Q2
    mdrm/MDRM_CSV.csv           # MDRM data dictionary (decodes 8-char codes)
    wrds/                       # CRSP (from WRDS), 440-bank listed universe
      dsf.parquet  dsi.parquet  stocknames.parquet  dsedelist.parquet
  crsp_20240930 (1).csv         # CRSP–FRB link: holding-company RSSD → permco
  CSV_RELATIONSHIPS.CSV         # FFIEC NIC parent→offspring RSSD relationships
  CSV_ATTRIBUTES_ACTIVE.CSV     # FFIEC NIC entity attributes (name, type, cert)
  fdic_failures.csv             # FDIC failed-bank list (SVB, Signature, FRC, …)
  Fed_Communications_Block3.xlsx# Block 3 corpus (11 Fed CBDC communications)
  processed/                    # WRITE target — all generated here
    crosswalk_rssd_permno.csv   # bank_IDRSSD, holder_RSSD, permco, permno, dates
    sample_banks.csv            # 278 sample banks + failed flag
    panel_2022Q4.csv            # 278 banks × constructed variables + outcome
    vulnerability_scores.csv    # out-of-sample predicted outflow per bank (RQ3)
    rq1_results.txt             # CV metrics, OLS table, SHAP ranking
    rq1_shap_summary.png        # SHAP beeswarm
scripts/
  build_panel.py                # Step 1: extract + construct + clean the panel
  run_rq1.py                    # Model 1: OLS + RF + GB, CV, SHAP, scores
```

`data/` is git-ignored. Python deps: `pandas, pyarrow, numpy, scikit-learn,
statsmodels, shap, matplotlib, openpyxl` (plus `wrds` for the CRSP pull).

## Reproduce

```bash
# prerequisites on disk: data/processed/sample_banks.csv (the 278-bank sample)
python scripts/build_panel.py    # -> data/processed/panel_2022Q4.csv
python scripts/run_rq1.py        # -> vulnerability_scores.csv, rq1_*.{txt,png}
```

Both scripts are read-only on `data/raw/`, write only to `data/processed/`, use a
fixed seed, and are re-runnable with no manual edits.

## Data sources

| What | Source | Auth |
|---|---|---|
| Call Reports (bulk, tab-delimited) | `cdr.ffiec.gov` "Call Reports — Single Period" | none |
| MDRM dictionary | `federalreserve.gov/apps/mdrm` | none |
| CRSP daily stock/index/delist/names | WRDS (`crsp` library) | WRDS login |
| CRSP–FRB link (RSSD→permco) | NY Fed / WRDS | none |
| FFIEC NIC relationships & attributes | `ffiec.gov/npw` bulk CSV | none |
| FDIC failed-bank list | FDIC (saved CSV on disk) | none |

**Freeze the archives.** CDR serves the latest *amended* filings; the Call Report
zips on disk are the May-2026 vintage. Re-downloading later returns different
numbers. There is currently **no `manifest.json` / SHA-256 freeze** — a gap worth
closing before write-up.

## The identifier crosswalk — the grain problem

RQ1 (Call Reports) is keyed on the **bank** RSSD (`IDRSSD`); CRSP is keyed on
**permno** at the listed **holding-company** level. They share no common key, and
the naive link fails:

- The CRSP–FRB link maps `entity` = **holding-company** RSSD → permco. Matching it
  directly to Call Report `IDRSSD` (a **bank** RSSD) matched only **9** banks and
  dropped SVB (holding RSSD 1031449 ≠ bank IDRSSD 802866).
- **Fix:** the FFIEC NIC relationships file gives bank→parent edges. Walking each
  filer up its control chain to the top holder that appears in the CRSP–FRB link
  yields **bank-IDRSSD → holder-RSSD → permco → permno**, recovering **278** banks
  including SVB. Signature and First Republic are linked because CRSP maps them at
  bank grain (entity RSSD = IDRSSD).
- Where a holder owns several filing banks (30 cases, usually bank + trust
  company), the largest subsidiary by total assets is kept and flagged.

## Variable construction (Section 3.3)

Built in `scripts/build_panel.py` for the 278 banks at 2022Q4. Filer mix:
**199 × FFIEC 041, 45 × 051, 34 × 031.**

**Filer-aware scope (critical — see traps below).** For 031 filers the domestic
`RCON` balance-sheet cells are empty; the consolidated figure is under `RCFD` /
`RCFA` / `RCFN`. Scope is chosen **per filer** across all balance-sheet fields:
031 → consolidated, 041/051 → `RCON`/`RCOA`. RC-O Memorandum item 1 is
domestic-office-only on all forms (always `RCON`); income statement is single-scope
`RIAD`.

Variables (one column each): `uninsured_share`, `unrealised_losses`,
`deposit_reliance`, `liquidity`, `capital` (tier-1 leverage ratio, **percent
units**), `size` (ln assets), and controls `ROA`, `NPL_ratio`, `equity_ratio`,
`int_inc_ratio`.

**Uninsured deposits** use RC-O Memorandum item 1 — the amount above the $250k
limit on large accounts, summing **both** the ordinary (`RCONF051/F052`) and
retirement (`RCONF047/F048`) branches. Call Report dollar amounts are in
**thousands**, so the per-account limit is coded `250` (not `250,000`); using the
raw dollar figure drove `uninsured_share` to ≈ −100 (a unit bug, now fixed and
commented). `RCON5597` (bank's own estimate, ≥$1bn filers only) and FDIC
`DEPUNINS` remain as robustness variants but are **not yet built** (they need FDIC
financials, not currently on disk).

## The outcome, and what `-1.0` means

`dep_growth` = deposit growth 2022Q4 → 2023Q1 (base is always 2022Q4).

A bank absent from 2023Q1 either **failed** or was **acquired**; only the FDIC
failure list separates them.

- absent **and** on the failure list → `dep_growth = -1.0`, `censored = True`
- absent **and not** on the list → excluded (merger exit). In this sample that is
  **one** bank, Farmers National Bank of Emlenton (IDRSSD 119528).
- present → measured.

**`-1.0` is an assumption, not a measurement.** SVB's deposits did not go to zero:
the bank was closed on 10 March and moved to an FDIC bridge bank. The value is
right-censoring — we know the outflow was extreme, not its magnitude. Consequences:

1. No analysis may touch `dep_growth` without reading `censored`.
2. **The run excluding failed banks belongs in the main results**, not the
   appendix — if H1a survives only on the three censored points, that must be
   visible. (In RQ1, RMSE is in fact dominated by these three −1.0 observations.)
3. `survived_q1` (binary) is free of the assumption and is the natural second
   anchor — not yet run.

The three censored failures **stay in training** — dropping them reintroduces
survivorship bias.

## Methodological limitations

1. **31 March is not the peak of the run** (9–13 March). Call Reports record the
   quarter-end balance sheet, after the discount window and the BTFP (12 March) had
   partly reversed flows. `dep_growth` is the net quarter-end position, not peak
   outflow; safe-haven banks (JPMorgan) show *inflows* and read as unexposed.
   Robustness on 2023Q2 is therefore mandatory (not yet built).
2. **CRSP price data ends 2024-12-31** in this WRDS subscription (both daily and
   monthly; `crspq` unavailable). The intended 2026 horizon is unreachable; the
   2023 events are fully covered.
3. **The panel is a single 2022Q4 cross-section**, not the multi-quarter panel —
   no pre-trend / dynamics yet.

## Data traps handled (verified, not assumed)

1. **Two header lines.** Row 1 = MDRM codes (kept as header), row 2 = descriptions
   (dropped). Reading row 2 as data silently turns numeric columns to `object`.
2. **`RCON` vs `RCFD`, per filer.** SVB's `RCON2170` is empty; `RCFD2170` =
   209,026,000. Scope is chosen per filer, never per column, so the two legs of a
   difference (e.g. HTM cost − fair value) are never drawn from different scopes.
3. **Split schedules.** `RCO` arrives in 2 parts, `RCRII` in 4. Parts split
   *columns* → joined on `IDRSSD`, not stacked (`read_schedule` handles this).
4. **Never match banks by name.** Two banks are named exactly `SIGNATURE BANK`
   (CERT 57053 New York, failed; a live Illinois bank). All joins key on RSSD /
   CERT; the NY failure is picked by RSSD 2942690.
5. **`RCFD2200` does not exist.** Deposits split into domestic `RCON2200` and
   foreign `RCFN2200`; consolidated deposits = their sum.
6. **`CERT` dtype.** FDIC certs arrive as floats (`24735.0`); normalise before
   joining or matches silently vanish. Cert↔IDRSSD is bridged via the POR.
7. **MDRM `%` and unit quirks.** The tier-1 leverage ratio is filed as a string
   with `%` (`'8.2978%'`); amounts are in $thousands (see uninsured note).

## RQ1 findings so far (honest)

From `rq1_results.txt` (N = 277, 10 features, 5-fold CV, seed 42):

- **H1a — partially supported (in-sample).** OLS R² = 0.14; `uninsured_share`
  (t = −4.08, p < 0.001) and `unrealised_losses` (t = +2.81, p = 0.005) are
  significant with the economically correct sign. The other eight features are not
  significant. SHAP agrees: `uninsured_share` is the dominant driver.
- **H1b — not supported.** Random forest does **not** beat OLS out-of-sample
  (oos-RMSE 0.1326 vs 0.1320); all three models have **negative out-of-sample R²**
  (worse than the mean); gradient boosting badly overfits. No genuine OOS
  predictive power on this cross-section.
- **Face validity is weak.** SVB ranks 8/277 by vulnerability, but the top of the
  list is dominated by high-uninsured custody banks (State Street, BoNY Mellon,
  Northern Trust) that did not run; Signature (30), First Republic (74), Comerica
  (43), Western Alliance (57), PacWest (141) are not near the top. The score
  largely proxies `uninsured_share`.

Likely causes: only ~3 extreme events (the censored −1.0 failures dominate RMSE),
thin signal (277 banks, most near 0), the 31-March-vs-peak issue, and custody banks
inflating the top feature.

## Known gaps / next steps

- Save the WRDS-pull and crosswalk-build scripts into `scripts/` (reproducibility).
- Add a `manifest.json` with SHA-256 to freeze the Call Report vintage.
- RQ1 robustness: the binary `survived_q1` target, the failures-excluded spec, and
  2023Q2; consider dropping custody banks / winsorising.
- Build Block 2 → RQ3 (vulnerability score → holding-company stock reaction) and
  Block 3 processing.
