"""
PHASE 2 — STOCK TICKERS (mapped to FDIC CERT) + DAILY PRICES
============================================================
Two jobs:
  1. Build bank_tickers.csv: largest listed US banks -> stock ticker -> the FDIC
     CERT of their LEAD BANK SUBSIDIARY (so it joins Phase 1). Every CERT is
     resolved against the live FDIC API; nothing is typed from memory except the
     three failed banks, which are looked up directly by their (Phase-1-verified) CERT.
     NOTE: listed banks trade as HOLDING COMPANIES (e.g. ticker JPM = "JPMorgan
     Chase & Co"), while the FDIC CERT belongs to the BANK SUBSIDIARY (CERT 628 =
     "JPMorgan Chase Bank NA"). This holdco<->subsidiary link ALWAYS needs human
     review, so every row is flagged needs_review=True with the authoritative FDIC
     name printed for you to eyeball.
  2. Download daily prices (yfinance) for those tickers + the S&P 500 (^GSPC),
     2021-06-01 to 2025-06-30, saved long-format (date, ticker, adj_close).

Sources: FDIC API (free) + Yahoo Finance via yfinance (free, no key).
"""

import re
import time
import requests
import pandas as pd
import yfinance as yf

H = {"User-Agent": "Mozilla/5.0 (MSc dissertation research; data collection)"}
INST = "https://api.fdic.gov/banks/institutions"

# ---------------------------------------------------------------------------
# Curated list of the largest listed US banks (money-center + major regionals).
# ticker  = stock symbol (holding company)
# company = holding-company name (what the ticker actually is)
# query   = the LEAD BANK SUBSIDIARY name, used to resolve the FDIC CERT
# mode    = 'active' (normal resolution) or 'failed' (delisted; look up by known CERT)
# cert    = only set for failed banks (verified live in Phase 1)
# ---------------------------------------------------------------------------
BANKS = [
    # --- money-center / universal / trust / brokerage ---
    {"ticker": "JPM",  "company": "JPMorgan Chase & Co",        "query": "JPMorgan Chase Bank, National Association"},
    {"ticker": "BAC",  "company": "Bank of America Corp",        "query": "Bank of America, National Association"},
    {"ticker": "WFC",  "company": "Wells Fargo & Co",            "query": "Wells Fargo Bank, National Association"},
    {"ticker": "C",    "company": "Citigroup Inc",               "query": "Citibank, National Association"},
    {"ticker": "USB",  "company": "U.S. Bancorp",                "query": "U.S. Bank National Association"},
    {"ticker": "PNC",  "company": "PNC Financial Services",      "query": "PNC Bank, National Association"},
    {"ticker": "TFC",  "company": "Truist Financial Corp",       "query": "Truist Bank"},
    {"ticker": "GS",   "company": "Goldman Sachs Group",         "query": "Goldman Sachs Bank USA"},
    {"ticker": "MS",   "company": "Morgan Stanley",              "query": "Morgan Stanley Bank, National Association"},
    {"ticker": "COF",  "company": "Capital One Financial",       "query": "Capital One, National Association"},
    {"ticker": "BK",   "company": "Bank of New York Mellon",     "query": "The Bank of New York Mellon"},
    {"ticker": "STT",  "company": "State Street Corp",           "query": "State Street Bank and Trust Company"},
    {"ticker": "NTRS", "company": "Northern Trust Corp",         "query": "The Northern Trust Company"},
    {"ticker": "SCHW", "company": "Charles Schwab Corp",         "query": "Charles Schwab Bank, SSB"},
    {"ticker": "ALLY", "company": "Ally Financial",              "query": "Ally Bank"},
    # --- super-regionals / major regionals ---
    {"ticker": "CFG",  "company": "Citizens Financial Group",    "query": "Citizens Bank, National Association"},
    {"ticker": "FITB", "company": "Fifth Third Bancorp",         "query": "Fifth Third Bank, National Association"},
    {"ticker": "KEY",  "company": "KeyCorp",                     "query": "KeyBank National Association"},
    {"ticker": "RF",   "company": "Regions Financial Corp",      "query": "Regions Bank"},
    {"ticker": "MTB",  "company": "M&T Bank Corp",               "query": "Manufacturers and Traders Trust Company"},
    {"ticker": "HBAN", "company": "Huntington Bancshares",       "query": "The Huntington National Bank"},
    {"ticker": "FCNCA","company": "First Citizens BancShares",   "query": "First-Citizens Bank & Trust Company"},
    {"ticker": "CMA",  "company": "Comerica Inc",                "query": "Comerica Bank"},
    {"ticker": "ZION", "company": "Zions Bancorporation",        "query": "Zions Bancorporation, N.A.", "cert": 2270},
    {"ticker": "WAL",  "company": "Western Alliance Bancorp",    "query": "Western Alliance Bank"},
    {"ticker": "EWBC", "company": "East West Bancorp",           "query": "East West Bank"},
    {"ticker": "WBS",  "company": "Webster Financial Corp",      "query": "Webster Bank, National Association"},
    {"ticker": "SNV",  "company": "Synovus Financial Corp",      "query": "Synovus Bank"},
    {"ticker": "VLY",  "company": "Valley National Bancorp",     "query": "Valley National Bank"},
    {"ticker": "COLB", "company": "Columbia Banking System",     "query": "Umpqua Bank"},
    {"ticker": "CFR",  "company": "Cullen/Frost Bankers",        "query": "Frost Bank", "cert": 5510},
    {"ticker": "WTFC", "company": "Wintrust Financial Corp",     "query": "Wintrust Bank, National Association"},
    {"ticker": "PNFP", "company": "Pinnacle Financial Partners", "query": "Pinnacle Bank"},
    {"ticker": "BOKF", "company": "BOK Financial Corp",          "query": "BOKF, National Association"},
    {"ticker": "PB",   "company": "Prosperity Bancshares",       "query": "Prosperity Bank"},
    {"ticker": "ONB",  "company": "Old National Bancorp",        "query": "Old National Bank"},
    {"ticker": "FLG",  "company": "Flagstar Financial (ex-NYCB)","query": "Flagstar Bank, National Association"},
    {"ticker": "BPOP", "company": "Popular Inc",                 "query": "Banco Popular de Puerto Rico"},
    {"ticker": "CBSH", "company": "Commerce Bancshares",         "query": "Commerce Bank"},
    {"ticker": "FNB",  "company": "F.N.B. Corp",                 "query": "First National Bank of Pennsylvania"},
    {"ticker": "ASB",  "company": "Associated Banc-Corp",        "query": "Associated Bank, National Association"},
    {"ticker": "HWC",  "company": "Hancock Whitney Corp",        "query": "Hancock Whitney Bank"},
    {"ticker": "OZK",  "company": "Bank OZK",                    "query": "Bank OZK"},
    {"ticker": "SSB",  "company": "SouthState Corp",             "query": "SouthState Bank, National Association"},
    {"ticker": "FHN",  "company": "First Horizon Corp",          "query": "First Horizon Bank"},
    {"ticker": "TCBI", "company": "Texas Capital Bancshares",    "query": "Texas Capital Bank", "cert": 34383},
    {"ticker": "UMBF", "company": "UMB Financial Corp",          "query": "UMB Bank, National Association"},
    {"ticker": "CADE", "company": "Cadence Bank",                "query": "Cadence Bank"},
    # --- failed / delisted 2023 (kept for the event study; resolved by verified CERT) ---
    {"ticker": "SIVB", "company": "SVB Financial Group",         "query": "Silicon Valley Bank", "mode": "failed", "cert": 24735},
    {"ticker": "SBNY", "company": "Signature Bank",              "query": "Signature Bank",       "mode": "failed", "cert": 57053},
    {"ticker": "FRC",  "company": "First Republic Bank (holdco)","query": "First Republic Bank",  "mode": "failed", "cert": 59017},
]

START, END = "2021-06-01", "2025-06-30"
OUT_TICKERS = "data/processed/bank_tickers.csv"
OUT_PRICES = "data/processed/stock_prices.csv"

# Tickers with NO usable FREE price data in this environment (verified directly
# against Yahoo Finance download/history AND Stooq before giving up). We log and
# skip them rather than invent or admit contaminated data. Reasons:
#   - failed 2023, series purged by Yahoo / ticker reused by another security
#   - acquired 2025-26, ticker delisted and history removed by Yahoo
NO_PRICE = {
    "SIVB": "SVB Financial failed Mar-2023; Yahoo purged the series (no free source found)",
    "SBNY": "Signature failed Mar-2023; 'SBNY' on Yahoo is now a REUSED ticker (2024+ data is a different company) -> excluded to avoid contamination",
    "FRC":  "First Republic failed May-2023; 'FRC'/'FRCB' give no clean series (purged/reused)",
    "CMA":  "Comerica acquired (2025-26); Yahoo delisted the ticker, history removed",
    "CADE": "Cadence Bank acquired (2025-26); Yahoo delisted the ticker, history removed",
    "SNV":  "Synovus acquired (2025-26); Yahoo delisted the ticker, history removed",
}


def norm(s):
    return re.sub(r"[^A-Z0-9 ]", "", (s or "").upper()).strip()


def get_by_cert(cert):
    """Authoritative single-record lookup by CERT (used for failed banks)."""
    r = requests.get(INST, params={"filters": f"CERT:{cert}",
        "fields": "NAME,CERT,STALP,CITY,ASSET,ACTIVE,BKCLASS", "limit": 1},
        headers=H, timeout=30)
    data = r.json().get("data", [])
    return data[0]["data"] if data else None


def resolve(query, mode):
    """Resolve a bank-subsidiary name to one FDIC record.
    Relevance search, then keep names that START WITH the query (kills loose
    token matches). For 'active' prefer ACTIVE then biggest; report #candidates."""
    r = requests.get(INST, params={"search": f'NAME:"{query}"',
        "fields": "NAME,CERT,STALP,CITY,ASSET,ACTIVE,BKCLASS", "limit": 10},
        headers=H, timeout=30)
    cands = [c["data"] for c in r.json().get("data", [])]
    q = norm(query)
    good = [d for d in cands if norm(d.get("NAME")).startswith(q)]
    pool = good or cands
    pool = sorted(pool, key=lambda d: (d.get("ACTIVE") == 1, d.get("ASSET") or 0), reverse=True)
    return (pool[0] if pool else None), len(good)


# ---------------------------------------------------------------------------
# 1. Resolve every ticker -> FDIC CERT
# ---------------------------------------------------------------------------
print("=" * 78)
print("STEP 1/2  Resolving tickers -> FDIC CERT (lead bank subsidiary)")
print("=" * 78)

rows = []
for b in BANKS:
    mode = b.get("mode", "active")
    if "cert" in b:                      # explicit CERT (failed banks + a few fixed ones)
        rec = get_by_cert(b["cert"])
        n_match, method = 1, "direct-cert-lookup"
    else:
        rec, n_match = resolve(b["query"], mode)
        method = "name-search"
    if rec is None:
        print(f"  !! {b['ticker']:<6} {b['query'][:40]:<40} -> NO FDIC MATCH (logged, review)")
        rows.append({"ticker": b["ticker"], "company_name": b["company"],
                     "lead_bank_query": b["query"], "fdic_cert": pd.NA,
                     "fdic_bank_name": "NO MATCH", "city": "", "state": "",
                     "asset_usd_thousands": pd.NA, "active": pd.NA,
                     "bkclass": "", "n_name_matches": 0, "resolution_method": method,
                     "needs_review": True})
        continue
    flag = "review" if (n_match != 1 or rec.get("ACTIVE") != 1) else "ok"
    print(f"  {b['ticker']:<6} -> CERT {str(rec['CERT']):>6} | {rec['NAME'][:38]:<38} | {rec.get('STALP')} | "
          f"${(rec.get('ASSET') or 0)/1e6:6.1f}bn | act={rec.get('ACTIVE')} | matches={n_match} [{flag}]")
    rows.append({"ticker": b["ticker"], "company_name": b["company"],
                 "lead_bank_query": b["query"], "fdic_cert": rec["CERT"],
                 "fdic_bank_name": rec["NAME"], "city": rec.get("CITY"), "state": rec.get("STALP"),
                 "asset_usd_thousands": rec.get("ASSET"), "active": rec.get("ACTIVE"),
                 "bkclass": rec.get("BKCLASS"), "n_name_matches": n_match,
                 "resolution_method": method, "needs_review": True})
    time.sleep(0.4)

tick = pd.DataFrame(rows)

# Cross-check: is each resolved CERT present in the Phase-1 commercial-bank panel?
try:
    panel_certs = set(pd.read_csv("data/processed/part1_panel.csv", usecols=["CERT"])["CERT"].dropna().astype(int))
    tick["in_phase1_panel"] = tick["fdic_cert"].apply(lambda c: int(c) in panel_certs if pd.notna(c) else False)
except Exception as e:
    print(f"  (could not cross-check Phase 1 panel: {e})")
    tick["in_phase1_panel"] = pd.NA

# Record whether free price data is available for each ticker (and why not)
tick["price_available"] = ~tick["ticker"].isin(NO_PRICE)
tick["price_note"] = tick["ticker"].map(NO_PRICE).fillna("")

tick.to_csv(OUT_TICKERS, index=False)
print(f"\n  Saved {OUT_TICKERS}  ({len(tick)} banks)")
dup = tick["fdic_cert"].dropna().duplicated().sum()
print(f"  Duplicate CERTs (should be 0): {dup}")
print(f"  Resolved CERTs found in Phase 1 panel: {tick['in_phase1_panel'].sum()} / {len(tick)}")
print(f"  Banks with usable free price data: {tick['price_available'].sum()} / {len(tick)}"
      f"  (skipped: {sorted(NO_PRICE)})")


# ---------------------------------------------------------------------------
# 2. Download daily prices (tickers + S&P 500), long format
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("STEP 2/2  Downloading daily prices from Yahoo Finance")
print("=" * 78)

tickers = tick.loc[tick["price_available"], "ticker"].tolist()   # only tickers with usable data
all_syms = tickers + ["^GSPC"]
print(f"  Downloading {len(all_syms)} symbols ({START} -> {END}) ...")
print(f"  (skipping {len(NO_PRICE)} tickers with no usable free data: {sorted(NO_PRICE)})")

raw = yf.download(all_syms, start=START, end=END, auto_adjust=False,
                  progress=False, group_by="column")

# Pull just the adjusted-close panel and reshape wide -> long
adj = raw["Adj Close"].copy()
adj.index.name = "date"
long = adj.reset_index().melt(id_vars="date", var_name="ticker", value_name="adj_close")
long = long.dropna(subset=["adj_close"]).sort_values(["ticker", "date"]).reset_index(drop=True)
long.to_csv(OUT_PRICES, index=False)
print(f"  Saved {OUT_PRICES}  ({len(long)} rows, long format)")

# ---------------------------------------------------------------------------
# 3. VERIFICATION — per-ticker coverage
# ---------------------------------------------------------------------------
print("\n=== Per-symbol price coverage ===")
cov = (long.groupby("ticker")
       .agg(n_days=("adj_close", "size"), first=("date", "min"), last=("date", "max"))
       .reset_index())
# Approx expected trading days over the full window (~252/yr * ~4.08yr)
EXP = 1025
gaps = []
for _, r in cov.sort_values("n_days").iterrows():
    flag = ""
    if r["n_days"] < 0.95 * EXP:
        flag = "  <-- GAP / partial (delisted or late listing)"
        gaps.append(r["ticker"])
    print(f"  {r['ticker']:<6} {r['n_days']:>5} days | {str(r['first'])[:10]} -> {str(r['last'])[:10]}{flag}")

missing = sorted(set(all_syms) - set(long["ticker"].unique()))
print(f"\n  Symbols with NO price data at all: {missing if missing else 'none'}")
print(f"  Symbols flagged with gaps/partial coverage: {gaps if gaps else 'none'}")
print("\nDONE — Phase 2 collection complete.")
