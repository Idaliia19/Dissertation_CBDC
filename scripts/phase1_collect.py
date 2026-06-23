"""
PHASE 1 — US BANK PANEL FROM FDIC CALL REPORTS
===============================================
Goal (plain language):
  Download balance-sheet data for ALL active US commercial banks at six
  quarter-end dates around the 2023 banking stress, then build:
    (a) part1_panel.csv     -> raw bank-quarter panel (one row per bank per date)
    (b) part1_features.csv  -> one row per bank: 2022-12-31 features + 2023 deposit-change targets

Source: FDIC BankFind Suite API (free, no key).
  Base URL: https://api.fdic.gov/banks   (the old banks.data.fdic.gov host now redirects here)
  Endpoint used: /financials  (quarterly Call Report figures)

All dollar values from the FDIC are in THOUSANDS of US dollars.
Field codes below were confirmed against the live API and the official data
dictionary (risview_properties.yaml) before writing this script.
"""

import time
import requests
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# 0. Configuration
# ---------------------------------------------------------------------------
BASE = "https://api.fdic.gov/banks/financials"
HEADERS = {"User-Agent": "Mozilla/5.0 (MSc dissertation research; data collection)"}

# The six quarter-end report dates we need (FDIC stores them as YYYYMMDD strings)
REPDTES = ["20220930", "20221231", "20230331", "20230630", "20230930", "20231231"]

# "Commercial banks" = FDIC charter classes N (national), SM (state member),
# NM (state non-member). This deliberately EXCLUDES savings institutions
# (SB/SA/OI). SVB is SM, First Republic and Signature are NM, so all three
# stress-test banks are inside this universe.
COMMERCIAL_BKCLASS = "(N OR SM OR NM)"

# Fields to pull. Left = our friendly meaning; right = exact FDIC field code.
FIELDS = [
    "CERT",      # FDIC certificate number (the bank's permanent ID; joins to Phase 2)
    "REPDTE",    # report date (quarter end)
    "NAME",      # bank legal name
    "CITY",      # city
    "STNAME",    # state name
    "BKCLASS",   # charter class
    "ASSET",     # total assets
    "DEP",       # total deposits
    "DEPDOM",    # deposits in domestic offices (context for the uninsured figures)
    "DEPUNA",    # estimated uninsured deposits AS DIRECTLY REPORTED (RCON5597); 0 for <$1bn banks
    "DEPUNINS",  # estimated uninsured deposits, FDIC estimate (populated for ALL banks)
    "EQ",        # total equity capital
    "SC",        # securities
    "CHBAL",     # cash & due from depository institutions ("cash")
    "NONII",     # total noninterest income (year-to-date flow)
    "INTINC",    # total interest income (year-to-date flow)
]

OUT_PANEL = "data/processed/part1_panel.csv"
OUT_FEATURES = "data/processed/part1_features.csv"
PAGE = 1000          # rows per API request (polite chunk size; API max is larger)
PAUSE = 0.5          # seconds between requests (be polite: one request at a time)


# ---------------------------------------------------------------------------
# 1. A small, robust download helper (pages through results for one date)
# ---------------------------------------------------------------------------
def fetch_quarter(repdte):
    """Return a list of bank records (dicts) for one report date.
    Pages through the API using offset until we have everything."""
    filt = f"REPDTE:{repdte} AND BKCLASS:{COMMERCIAL_BKCLASS}"
    out, offset, total = [], 0, None
    while True:
        params = {
            "filters": filt,
            "fields": ",".join(FIELDS),
            "limit": PAGE,
            "offset": offset,
            "sort_by": "CERT",
            "sort_order": "ASC",
        }
        for attempt in range(4):                      # retry on transient failures
            try:
                r = requests.get(BASE, params=params, headers=HEADERS, timeout=40)
                r.raise_for_status()
                j = r.json()
                break
            except Exception as e:
                wait = 2 * (attempt + 1)
                print(f"    ! request failed ({e}); retry in {wait}s")
                time.sleep(wait)
        else:
            raise RuntimeError(f"Gave up fetching {repdte} at offset {offset}")

        if total is None:
            total = j["meta"]["total"]
        rows = [rec["data"] for rec in j["data"]]
        out.extend(rows)
        offset += PAGE
        time.sleep(PAUSE)
        if offset >= total:
            break
    return out, total


# ---------------------------------------------------------------------------
# 2. Download every quarter and stack into one raw panel
# ---------------------------------------------------------------------------
print("=" * 70)
print("STEP 1/3  Downloading bank-quarter panel from FDIC")
print("=" * 70)

frames = []
for d in REPDTES:
    rows, total = fetch_quarter(d)
    print(f"  {d}: fetched {len(rows):>5} / {total} commercial banks")
    frames.append(pd.DataFrame(rows))

panel = pd.concat(frames, ignore_index=True)

# Make sure numeric columns are numeric (the API returns numbers already, but be safe)
num_cols = ["ASSET", "DEP", "DEPDOM", "DEPUNA", "DEPUNINS", "EQ", "SC", "CHBAL", "NONII", "INTINC"]
for c in num_cols:
    panel[c] = pd.to_numeric(panel[c], errors="coerce")
panel["CERT"] = pd.to_numeric(panel["CERT"], errors="coerce").astype("Int64")
# REPDTE as a real date for readability + a clean string key
panel["REPDTE"] = panel["REPDTE"].astype(str)
panel["DATE"] = pd.to_datetime(panel["REPDTE"], format="%Y%m%d")

panel = panel.sort_values(["CERT", "REPDTE"]).reset_index(drop=True)
panel.to_csv(OUT_PANEL, index=False)

print(f"\n  Saved {OUT_PANEL}")
print(f"  Panel shape: {panel.shape[0]} rows x {panel.shape[1]} cols")
print("  Rows per quarter:")
print(panel["REPDTE"].value_counts().sort_index().to_string())
print(f"  Unique banks (CERT) across all quarters: {panel['CERT'].nunique()}")


# ---------------------------------------------------------------------------
# 3. Build the one-row-per-bank features + targets table (as of 2022-12-31)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 2/3  Building features (as of 2022-12-31) + 2023 targets")
print("=" * 70)

# Pivot deposits & uninsured deposits across dates so we can compute changes.
def wide(col):
    w = panel.pivot_table(index="CERT", columns="REPDTE", values=col, aggfunc="first")
    return w

dep = wide("DEP")
unins = wide("DEPUNINS")     # full-coverage FDIC estimate
unina = wide("DEPUNA")       # strictly-reported RCON5597 (0 for small banks)

# Base universe for features = banks that filed at 2022-12-31
base = panel[panel["REPDTE"] == "20221231"].copy().set_index("CERT")

feat = pd.DataFrame(index=base.index)
feat["NAME"] = base["NAME"]
feat["CITY"] = base["CITY"]
feat["STNAME"] = base["STNAME"]
feat["BKCLASS"] = base["BKCLASS"]

# --- helper for safe percentage change a->b = (b-a)/a  (NaN if a missing/zero)
def pct_change(a, b):
    a = a.replace(0, np.nan)
    return (b - a) / a

# ---- TARGETS (the thing the dissertation will predict) --------------------
# % change in total deposits 2022-12-31 -> 2023-03-31
feat["dep_chg_q4_to_q1"] = pct_change(dep.get("20221231"), dep.get("20230331"))
# % change in total deposits 2022-12-31 -> 2023-06-30
feat["dep_chg_q4_to_q2"] = pct_change(dep.get("20221231"), dep.get("20230630"))
# % change in uninsured deposits (FDIC estimate) 2022-12-31 -> 2023-03-31
feat["uninsured_chg_q4_to_q1"] = pct_change(unins.get("20221231"), unins.get("20230331"))

# Flags so we NEVER silently drop a failed/merged bank
feat["has_q1_2023_report"] = dep.get("20230331").notna().reindex(feat.index).fillna(False)
feat["has_q2_2023_report"] = dep.get("20230630").notna().reindex(feat.index).fillna(False)

# ---- FEATURES as of 2022-12-31 --------------------------------------------
A = base["ASSET"]
D = base["DEP"]
feat["log_assets"] = np.log(A.replace(0, np.nan))
feat["deposits_to_assets"] = D / A.replace(0, np.nan)
# uninsured/deposits — two versions: full-coverage estimate and strict-reported
feat["uninsured_to_deposits_est"] = base["DEPUNINS"] / D.replace(0, np.nan)
feat["uninsured_to_deposits_reported"] = base["DEPUNA"].replace(0, np.nan) / D.replace(0, np.nan)
feat["liquid_assets_to_assets"] = (base["CHBAL"] + base["SC"]) / A.replace(0, np.nan)
feat["equity_to_assets"] = base["EQ"] / A.replace(0, np.nan)
# noninterest income / total income, where total income = interest + noninterest income
tot_income = (base["INTINC"] + base["NONII"]).replace(0, np.nan)
feat["noninterest_income_share"] = base["NONII"] / tot_income

# Keep the raw 2022-12-31 levels too (handy for sanity checks)
feat["assets_2022Q4"] = A
feat["deposits_2022Q4"] = D
feat["uninsured_est_2022Q4"] = base["DEPUNINS"]

feat = feat.reset_index()  # CERT becomes a column
feat.to_csv(OUT_FEATURES, index=False)
print(f"  Saved {OUT_FEATURES}")
print(f"  Features shape: {feat.shape[0]} banks x {feat.shape[1]} cols")


# ---------------------------------------------------------------------------
# 4. VERIFICATION — print coverage, missingness, sanity checks
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 3/3  Verification")
print("=" * 70)

print("\n[A] Uninsured-deposit coverage at 2022-12-31 (non-zero, non-missing):")
n = len(base)
rep_cov = (base["DEPUNA"].fillna(0) > 0).sum()
est_cov = base["DEPUNINS"].notna().sum()
big = (base["ASSET"] >= 1_000_000).sum()   # >= $1bn (assets are in $thousands)
print(f"    banks at 2022-12-31:                         {n}")
print(f"    banks with ASSET >= $1bn:                    {big}")
print(f"    DEPUNA  (reported RCON5597) populated > 0:    {rep_cov}  ({rep_cov/n:.1%})")
print(f"    DEPUNINS (FDIC estimate) populated:           {est_cov}  ({est_cov/n:.1%})")

print("\n[B] Missing-value rate per feature column:")
fcols = ["dep_chg_q4_to_q1", "dep_chg_q4_to_q2", "uninsured_chg_q4_to_q1",
         "log_assets", "deposits_to_assets", "uninsured_to_deposits_est",
         "uninsured_to_deposits_reported", "liquid_assets_to_assets",
         "equity_to_assets", "noninterest_income_share"]
for c in fcols:
    miss = feat[c].isna().mean()
    print(f"    {c:<32} missing {miss:6.1%}")

print("\n[C] SANITY CHECK — 12 most negative deposit changes Q4-2022 -> Q1-2023:")
sc = feat.dropna(subset=["dep_chg_q4_to_q1"]).nsmallest(12, "dep_chg_q4_to_q1")
for _, r in sc.iterrows():
    print(f"    {r['dep_chg_q4_to_q1']:+7.1%}  CERT {int(r['CERT']):>6}  {str(r['NAME'])[:42]:<42} ({r['STNAME']})")

print("\n[D] Stress-test banks (did they show up / drop out as expected?):")
for cert, label in [(24735, "Silicon Valley Bank"), (57053, "Signature Bank (NY)"),
                    (59017, "First Republic Bank")]:
    if cert in feat["CERT"].values:
        r = feat.set_index("CERT").loc[cert]
        q1 = f"{r['dep_chg_q4_to_q1']:+.1%}" if pd.notna(r["dep_chg_q4_to_q1"]) else "NO Q1 REPORT (failed before quarter-end)"
        print(f"    CERT {cert} {label:<22} dep chg Q4->Q1: {q1}")
    else:
        print(f"    CERT {cert} {label}: not in 2022-12-31 universe")

print("\nDONE — Phase 1 collection complete.")
