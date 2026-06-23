# Phase 2 Summary — Stock Tickers (→ FDIC CERT) + Daily Prices

**Date built:** 2026-06-23
**Sources (both free, no key):**
- FDIC BankFind API — to resolve each listed bank's lead **bank subsidiary** CERT.
- Yahoo Finance via `yfinance` — daily prices.

## Output files
- `data/processed/bank_tickers.csv` — **51 banks**, ticker ↔ FDIC CERT mapping.
- `data/processed/stock_prices.csv` — **47,104 rows**, long format (`date, ticker, adj_close`),
  **45 bank tickers + ^GSPC**, 2021-06-01 → 2025-06-27.

## The holding-company vs. bank-subsidiary issue (READ THIS)
Listed banks trade as **holding companies** (ticker `JPM` = "JPMorgan Chase & Co"),
but the FDIC CERT belongs to the **bank subsidiary** (CERT 628 = "JPMorgan Chase Bank NA").
I resolved every CERT against the live FDIC API and **flagged every row `needs_review=True`**.
The authoritative FDIC bank name is in `fdic_bank_name` for you to eyeball.

**Validation:** all **51/51** resolved CERTs are present in the Phase-1 commercial-bank
panel — i.e. every ticker mapped to a real operating bank that joins Phase 1.
`n_name_matches` and `needs_review` tell you where to look hardest (multiple FDIC
name matches, or a now-inactive bank). Two resolutions were auto-corrected after the
in-panel check caught them (Frost Bank, Texas Capital Bank); Zions was fixed because
FDIC stores it as "Zions Bancorporation, N.A.".

`bank_tickers.csv` columns: `ticker, company_name, lead_bank_query, fdic_cert,
fdic_bank_name, city, state, asset_usd_thousands, active, bkclass, n_name_matches,
resolution_method, needs_review, in_phase1_panel, price_available, price_note`.

## Banks covered (51)
Money-center / universal / trust / brokerage: JPM, BAC, WFC, C, USB, PNC, TFC, GS, MS,
COF, BK, STT, NTRS, SCHW, ALLY. Super-regionals & regionals: CFG, FITB, KEY, RF, MTB,
HBAN, FCNCA, CMA, ZION, WAL, EWBC, WBS, SNV, VLY, COLB, CFR, WTFC, PNFP, BOKF, PB, ONB,
FLG, BPOP, CBSH, FNB, ASB, HWC, OZK, SSB, FHN, TCBI, UMBF, CADE. Failed 2023 (mapping
kept, no usable prices): SIVB, SBNY, FRC.

## Price coverage
- **45 of 51** tickers have usable free price data: **all 1,024 trading days, no gaps**,
  2021-06-01 → 2025-06-27 (the 2025-06-30 close is excluded because yfinance's `end` is
  exclusive — immaterial for the event study).
- `^GSPC` (S&P 500 market index) downloaded with full coverage.
- Prices are **`Adj Close`** (split- and dividend-adjusted) via `auto_adjust=False`.

## Gap: 6 banks have NO usable free price data (logged, not faked)
| ticker | bank | reason |
|---|---|---|
| SIVB | SVB Financial | failed Mar-2023; Yahoo purged the series; no clean free source |
| SBNY | Signature Bank | failed Mar-2023; **"SBNY" is now a REUSED ticker** (2024+ data is a *different* company) → excluded to avoid contamination |
| FRC | First Republic | failed May-2023; `FRC`/`FRCB` give no clean series (purged/reused) |
| CMA | Comerica | acquired 2025–26; Yahoo delisted the ticker, history removed |
| CADE | Cadence Bank | acquired 2025–26; Yahoo delisted the ticker, history removed |
| SNV | Synovus | acquired 2025–26; Yahoo delisted the ticker, history removed |

These are recorded in `bank_tickers.csv` (`price_available=False`, with `price_note`).
I verified each against Yahoo (`download` + `Ticker.history`) and Stooq before skipping.

### Why this is mostly OK for the event study
- The three **failed** banks (SVB/Signature/First Republic) delisted in 2023; their idiosyncratic
  bank-run collapse would contaminate any CBDC-event reaction anyway.
- The three **acquired** banks (Comerica/Cadence/Synovus) *did* trade through 2021–2025 — losing
  them is a genuine cost, but they are 3 of ~48 regionals, so the cross-section stays strong.
- If you want them, the standard route is a paid/academic source (CRSP via WRDS, or
  Bloomberg/Refinitiv) for the delisted series — outside the "free, no key" scope.

## Caveats for your manual review
- Every CERT match needs your sign-off (`needs_review=True`); pay special attention where
  `n_name_matches > 1`.
- `active=0` for CMA, SNV, CADE (and the 3 failed banks) is **correct** — they merged/failed
  *after* the 2022–23 study window; their CERTs are right for Phase 1's pre-stress balance sheets.
- `FLG` = Flagstar Financial (formerly New York Community Bancorp / NYCB); Yahoo serves the
  continuous series under `FLG`.
