# Phase 1 Summary — US Bank Panel (FDIC Call Reports)

**Date built:** 2026-06-23
**Source:** FDIC BankFind Suite API — `https://api.fdic.gov/banks/financials` (free, no key).
Note: the old host `banks.data.fdic.gov/api` now 301-redirects to `api.fdic.gov/banks`.

## What was collected
A bank-quarter panel of **all active US commercial banks** (charter classes
N = national, SM = state member, NM = state non-member) at six quarter-end dates:
2022-09-30, 2022-12-31, 2023-03-31, 2023-06-30, 2023-09-30, 2023-12-31.

Failed banks (SVB, Signature, First Republic) are **kept** because the panel is
pulled by report date, not by current "active" status.

### Field codes (confirmed against the live API + data dictionary before download)
| Concept | FDIC code | Note |
|---|---|---|
| Total assets | `ASSET` | $ thousands |
| Total deposits | `DEP` | $ thousands |
| Uninsured deposits — reported (RCON5597) | `DEPUNA` | **0 for banks < $1bn** |
| Uninsured deposits — FDIC estimate | `DEPUNINS` | **populated for all banks** |
| Total equity capital | `EQ` | |
| Cash & due from banks | `CHBAL` | used as "cash" |
| Securities | `SC` | |
| Total interest income | `INTINC` | year-to-date flow |
| Total noninterest income | `NONII` | year-to-date flow |

## Output files
- `data/processed/part1_panel.csv` — raw bank-quarter panel: **24,757 rows × 18 cols**.
- `data/processed/part1_features.csv` — one row per bank (base = 2022-12-31): **4,164 banks × 20 cols**.

### Rows per quarter
| REPDTE | banks |
|---|---|
| 2022-09-30 | 4,196 |
| 2022-12-31 | 4,164 |
| 2023-03-31 | 4,134 |
| 2023-06-30 | 4,110 |
| 2023-09-30 | 4,088 |
| 2023-12-31 | 4,065 |

Unique banks across all quarters: **4,216**. The gentle quarter-on-quarter
decline reflects ongoing mergers/failures (normal for US banking).

## Features & targets (in `part1_features.csv`)
**Targets:** `dep_chg_q4_to_q1`, `dep_chg_q4_to_q2` (% change in total deposits),
`uninsured_chg_q4_to_q1` (% change in FDIC-estimated uninsured deposits).
Flags `has_q1_2023_report` / `has_q2_2023_report` mark banks that failed before a quarter-end.

**Features as of 2022-12-31:** `deposits_to_assets`, `uninsured_to_deposits_est`,
`uninsured_to_deposits_reported`, `liquid_assets_to_assets` = (cash+securities)/assets,
`equity_to_assets`, `noninterest_income_share` = NONII/(INTINC+NONII), `log_assets`.

## Uninsured-deposit coverage (the key caveat)
- Banks at 2022-12-31: **4,164**; of which **848** have assets ≥ $1bn.
- `DEPUNA` (directly-reported RCON5597) populated > 0: **795 banks (19.1%)** — matches the
  rule that only ≥$1bn banks file RCON5597.
- `DEPUNINS` (FDIC estimate): **4,164 banks (100%)**.
- For JPMorgan, SVB, etc. the two are **identical** where both exist, so `DEPUNINS` is a
  clean superset. **Recommendation:** use `DEPUNINS` as the working uninsured measure
  (full coverage), and `DEPUNA` only if you want the strict reported-only subset.
  Because `DEPUNINS` already covers every bank, the FFIEC CDR bulk fallback is **not needed**.
  Caveat to state in the thesis: for <$1bn banks `DEPUNINS` is FDIC's estimate, not a bank-reported figure.

## Missing-value rates (features file)
| column | missing |
|---|---|
| dep_chg_q4_to_q1 | 0.8% |
| dep_chg_q4_to_q2 | 1.4% |
| uninsured_chg_q4_to_q1 | 1.0% |
| log_assets | 0.0% |
| deposits_to_assets | 0.0% |
| uninsured_to_deposits_est | 0.0% |
| uninsured_to_deposits_reported | 80.9% (expected — reported only for ≥$1bn) |
| liquid_assets_to_assets | 0.0% |
| equity_to_assets | 0.0% |
| noninterest_income_share | 0.0% |

The small missingness in the deposit-change columns is banks that did **not** file a
2023 report (failures/mergers) — flagged, not dropped.

## Sanity check — largest deposit outflows Q4-2022 → Q1-2023
| change | bank | state |
|---|---|---|
| −90.0% | Farmington State Bank (ex-Moonstone, FTX-linked) | WA |
| −76.3% | Silvergate Bank (crypto wind-down, Mar 2023) | CA |
| −72.2% | ANZ Guam Inc | GU |
| −48.4% | Bank of NY Mellon Trust Co NA | CA |
| **−40.8%** | **First Republic Bank** | CA |
| −36.8% | Independence Bank | RI |

**Failed-before-quarter-end (correctly have NO Q1 report, target = NaN, flagged):**
- Silicon Valley Bank (CERT 24735) — failed 2023-03-10. At 2022-12-31: $175bn deposits, **86% uninsured**.
- Signature Bank NY (CERT 57053) — failed 2023-03-12.

First Republic's −40.8% and Silvergate's −76.3% confirm the data captures the real 2023 outflow.

## Gaps / caveats
- SVB & Signature have no Q1-2023 deposit-change target (failed mid-March). Their pre-stress
  balance sheets are still in the panel for cross-sectional features.
- `uninsured_to_deposits_reported` is intentionally sparse (≥$1bn banks only); use the `_est` version for full coverage.
- "Commercial banks" excludes savings institutions by design; tell me if you want thrifts (SB/SA) added.
