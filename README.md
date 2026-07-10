# Block 1 — Call Report panel for RQ1

Bank-quarter panel of US banks, 2019Q4–2023Q2 (15 quarters), built to test:

> **RQ1.** Which bank characteristics predict sensitivity to fast, CBDC-style deposit outflows, and can machine learning identify the most exposed banks?
>
> **H1a.** Reliance on retail and uninsured deposits, unrealised securities losses, and thin liquidity and capital predict the deposit outflows observed in the 2023 stress.
>
> **H1b.** Tree-based ML predicts outflow sensitivity more accurately than linear baselines, with vulnerability concentrating in smaller, less-diversified banks.

Window logic: 2019Q4 pre-COVID baseline → 2020–21 deposit surge and securities purchases → 2022 rate hikes and mark-to-market losses → **2022Q4 predictors** → **2023Q1 outcome (the run quarter)** → 2023Q2 robustness.

## Run

```bash
pip install -r requirements.txt
python 01_download.py      # 15 FFIEC archives, MDRM, FDIC panel/institutions/failures
python 02_build_panel.py   # diagnostics T1–T5, then the panel
python 03_filters.py       # funnel, outcome, coverage report
python test_svb.py         # golden checks
```

`01_download.py` is idempotent: an archive whose SHA-256 matches `manifest.json` is skipped.

## Sources

| What | Where | Auth |
|---|---|---|
| Call Reports | `cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx`, "Call Reports -- Single Period", tab delimited | none |
| MDRM dictionary | `federalreserve.gov/apps/mdrm/pdf/MDRM.zip` | none |
| DEPUNINS, establishment date, holding co., failures | `api.fdic.gov/banks/{financials,institutions,failures}` | none |

**Freeze the archives.** CDR serves the latest amended filings. Re-downloading months later returns different numbers than the ones written up. `manifest.json` records the download date and a SHA-256 per archive.

## The uninsured-deposit variable

Three columns sit side by side in the panel. They are not interchangeable.

| Column | Source | Coverage |
|---|---|---|
| `uninsured_from_m1` | RC-O Memorandum item 1, both branches | **~99% of all banks** |
| `uninsured_reported` | RC-O M.2, `RCON5597` | 92% of banks ≥$1bn, ~0% below |
| `DEPUNINS` | FDIC | all banks |

`RCON5597` is filed only by banks with ≥$1bn in assets. `DEPUNINS` looks like a clean full-coverage alternative, but diagnostic T3/T4 shows it is a **splice**: it equals `RCON5597` above $1bn (99.8% exact) and equals the M.1-derived figure below (99.6% exact).

That matters because the two underlying concepts differ. `RCON5597` is the bank's own estimate of uninsured deposits. The M.1 figure is an account-level approximation — the amount above the limit on large accounts. Deposit insurance applies per depositor per ownership category, not per account, so they answer different questions. Among banks ≥$1bn filing both, the median gap is ~0 but p10/p90 are −16%/+63%, and 86% of banks differ by more than 1%.

So `DEPUNINS` changes its meaning exactly at $1bn in assets. Diagnostic T5b measures the resulting jump in mean `uninsured_share`: +0.01pp and +0.09pp in the two bands below the threshold, then **−1.98pp** in the 1.0–1.2bn band. H1b is a hypothesis about bank size. A size-located measurement artefact would be read by SHAP as economics.

**Therefore the main regressor is `uninsured_share_m1`** — one methodology, continuous across the threshold. `DEPUNINS` and `RCON5597` are kept for robustness. Column `uninsured_source ∈ {reported, derived}` records which concept fills `DEPUNINS` for each bank.

The M.1 figure sums **both** branches of Memorandum item 1: ordinary accounts (`RCONF051`, `RCONF052`) and retirement accounts (`RCONF047`, `RCONF048`). Dropping the retirement branch understates uninsured deposits at retirement-heavy banks.

## The outcome, and what `-1.0` means

`dep_growth` = deposit growth 2022Q4 → 2023Q1.

A bank absent from 2023Q1 either **failed** or was **acquired**. Only the FDIC failure list separates them. Bank of the West vanished that quarter with $72bn in deposits — acquired by BMO. Coding absence as a −100% outflow would have fed the model a fictitious run larger than SVB's.

- absent **and** on the failure list → `dep_growth = -1.0`, `outcome_is_censored = 1`
- absent **and not** on the list → excluded, `exit_reason = "merger"` (31 banks)
- present → measured

**`-1.0` is an assumption, not a measurement.** SVB's deposits did not go to zero: the bank was closed on 10 March and its deposits moved to an FDIC bridge bank. The value is right-censoring — we know the outflow was extreme, we do not know its magnitude. Consequences:

1. No regression may touch `dep_growth` without reading `outcome_is_censored`.
2. **The run excluding failed banks belongs in the main results table**, not the appendix. If H1a's coefficients survive only on three censored observations, that must be visible.
3. `survived_q1` (binary) is free of the assumption — failure there is a measured fact. It is the second anchor.

Three specifications: censored continuous, failures excluded, binary. Agreement across all three is what makes the finding robust.

## Methodological limitation: 31 March is not the peak of the run

The run happened **9–13 March 2023**. Call Reports record the balance sheet on **31 March**. In between, the Fed's discount window and the BTFP (launched 12 March) were operating; some deposits returned, others moved to large banks.

Consequences that belong in the thesis, not in a code comment:

1. `dep_growth` measures the **net position at quarter end, not the peak outflow**. True run amplitude exceeds what we observe.
2. Safe-haven banks (JPMorgan and peers) may show deposit *growth* that quarter. The model will read them as unexposed. It is right about the fact and wrong about the reason: they gained from someone else's run.
3. **Robustness on 2023Q2 is therefore mandatory, not optional.** By June the emergency programmes are partly unwound, and Q2 shows what remained after the rebound.

## Traps this code handles (each one verified, not assumed)

1. **Two header lines.** Line 1 is MDRM codes, line 2 is descriptions. Reading line 2 as data turns every numeric column to `object` — silently, without raising.
2. **`RCON` vs `RCFD`.** FFIEC 031 filers report consolidated `RCFD*`. SVB's `RCON2170` is empty; its `RCFD2170` is 209,026,000. Scope is chosen **per filer**, never per column: `RCFD1773` = 25,976,000 vs `RCON1773` = 21,975,000, so coalescing each code independently would draw the two legs of `HTM cost − HTM fair value` from different scopes.
3. **Split files.** `RCO` arrives as 2 parts, `RCRII` as 4. Parts split *columns*, so they are joined on `IDRSSD`, not stacked.
4. **Drifting names.** RC-E exists as `RCE`, `RCEI` and `RCEII` in the same archive. Never hardcode; `ffiec.peek()` reports what is actually there.
5. **Opaque date ids.** The CDR date dropdown uses server-side ids (`12/31/2022` → `135`) that are neither stable nor contiguous — 123, 128 and 133 are absent. Always parsed.
6. **Never match banks by name.** Two banks are named exactly `SIGNATURE BANK`: CERT 57053 (New York, failed) and CERT 58264 (Illinois, alive). All joins key on `CERT` / `IDRSSD`.
7. **`DEPUNA` does not exist.** The FDIC field is `DEPUNINS`.
8. **`RCFD2200` does not exist.** Deposits split into domestic `RCON2200` and foreign `RCFN2200`.
9. **`CERT` dtype.** The failures endpoint returns `24735.0`; joins against the register silently return nothing unless normalised.

## Outputs

```
data/processed/
  rq1_panel.parquet              74,150 rows — all filers, all quarters
  rq1_sample.parquet             4,618 banks × 15 quarters — after filters
  crosswalk_rssd_cert.csv        IDRSSD ↔ CERT ↔ RSSDHCR/NAMEHCR (for RQ3)
  coverage.csv                   filter funnel
  predictors_without_outcome.csv 33 banks, named, with exit_reason
  zip_inventory.csv              actual contents of a quarterly archive
  manifest.json                  download date + SHA-256 per archive
```

`crosswalk_rssd_cert.csv` carries the holding-company identifiers because RQ3 needs to map each bank to its listed parent's stock. Collected here at no cost; expensive to reconstruct later.
