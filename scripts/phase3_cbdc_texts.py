"""
PHASE 3 — FEDERAL RESERVE CBDC COMMUNICATION TEXTS
==================================================
Collect REAL Federal Reserve CBDC communications with FULL texts for later NLP.
We do NOT score or judge them. Every item keeps a working source URL.

Sources (both free, no key):
  PRIMARY  — BIS central bankers' speeches dataset (data/raw/speeches.csv, full texts).
             Filter: speaker's affiliation = Federal Reserve, date >= 2021-01-01,
             mentions a CBDC term.
  SECONDARY— Federal Reserve website, for items BIS misses (the 2022 "Money and
             Payments" discussion paper [PDF], its press release, and Brainard's
             2022-05-26 CBDC testimony).

De-duplication: an item is a duplicate if the same (date, speaker surname) already
came from BIS. Fed items already in BIS are skipped; only Fed-unique items are added.

Outputs:
  data/cbdc_texts/<date>_<speaker>.txt   — one full clean text per item
  data/processed/cbdc_events.csv         — index with an EMPTY 'threat_direction'
                                           column for YOU to fill manually.
"""

import csv, sys, re, io, time
from datetime import date
import requests
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd

csv.field_size_limit(sys.maxsize)
H = {"User-Agent": "Mozilla/5.0 (MSc dissertation research; data collection)"}

BIS_CSV = "data/raw/speeches.csv"
TXT_DIR = "data/cbdc_texts"
OUT_CSV = "data/processed/cbdc_events.csv"

STRONG = ["central bank digital currency", "cbdc", "digital dollar"]
WEAK = "digital currency"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def parse_date(s):
    try:
        return date.fromisoformat((s or "")[:10])
    except Exception:
        return None

def surname(author):
    parts = re.sub(r"[^A-Za-z ]", "", author or "").split()
    return parts[-1].lower() if parts else "unknown"

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")

def clean_text(t):
    """Normalise whitespace; drop empty lines; collapse blank runs."""
    lines = [ln.strip() for ln in (t or "").replace("\r", "\n").split("\n")]
    out = "\n".join(ln for ln in lines if ln)
    return re.sub(r"\n{3,}", "\n\n", out).strip()

def affiliation(desc):
    """Speaker institution = clause before the first ', at ' in the BIS description."""
    low = (desc or "").lower(); i = low.find(", at ")
    return desc[:i] if i != -1 else (desc or "")[:160]

def count_terms(text):
    h = (text or "").lower()
    return sum(h.count(t) for t in STRONG) + h.count(WEAK)

def fetch_html_body(url):
    r = requests.get(url, headers=H, timeout=40); r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    node = soup.find("div", id="article") or soup.find("div", id="content") or soup.find("main") or soup.body
    for t in node.find_all(["script", "style", "nav", "footer", "header"]):
        t.decompose()
    return clean_text(node.get_text("\n"))

def fetch_pdf_text(url):
    r = requests.get(url, headers=H, timeout=120); r.raise_for_status()
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        raw = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    # join words split across a line break by a hyphen ("pub-\nlic" -> "public")
    raw = re.sub(r"(?<=[a-z])-\n(?=[a-z])", "", raw)
    return clean_text(raw)


# ---------------------------------------------------------------------------
# 1. PRIMARY — pull Fed CBDC speeches out of the BIS dataset
# ---------------------------------------------------------------------------
print("=" * 78)
print("STEP 1/4  Filtering BIS dataset -> Federal Reserve CBDC speeches")
print("=" * 78)

bis_items = []
with open(BIS_CSV, newline="", encoding="utf-8", errors="replace") as f:
    for row in csv.DictReader(f):
        d = parse_date(row["date"])
        if d is None or d < date(2021, 1, 1):
            continue
        desc = row["description"] or ""
        # speaker must BE Federal Reserve (affiliation clause), not just mention it
        if "federal reserve" not in affiliation(desc).lower():
            continue
        hay = ((row["title"] or "") + " " + desc + " " + (row["text"] or "")).lower()
        if not any(t in hay for t in STRONG) and WEAK not in hay:
            continue
        # BIS titles are "Author Name: Real Title" -> keep the part after the first colon
        title = row["title"] or ""
        title = title.split(":", 1)[1].strip() if ":" in title else title
        bis_items.append({
            "date": d.isoformat(), "speaker": row["author"], "surname": surname(row["author"]),
            "title": title, "source": "BIS", "url": row["url"],
            "text": clean_text(row["text"]),
        })

print(f"  Federal Reserve CBDC speeches found in BIS: {len(bis_items)}")
bis_keys = {(i["date"], i["surname"]) for i in bis_items}


# ---------------------------------------------------------------------------
# 2. SECONDARY — Federal Reserve website candidates (added only if BIS lacks them)
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("STEP 2/4  Federal Reserve website — adding items BIS misses (with de-dup)")
print("=" * 78)

# Curated from federalreserve.gov/cbdc-speeches.htm + the CBDC landing page.
# kind: 'html' (speech/testimony/press release page) or 'pdf' (discussion paper).
FED_CANDIDATES = [
    {"date": "2021-05-24", "speaker": "Lael Brainard",          "title": "Private Money and Central Bank Money as Payments Go Digital: an Update on CBDCs", "url": "https://www.federalreserve.gov/newsevents/speech/brainard20210524a.htm", "kind": "html"},
    {"date": "2021-06-28", "speaker": "Randal K. Quarles",      "title": "Parachute Pants and Central Bank Money", "url": "https://www.federalreserve.gov/newsevents/speech/quarles20210628a.htm", "kind": "html"},
    {"date": "2021-08-05", "speaker": "Christopher J. Waller",  "title": "CBDC: A Solution in Search of a Problem?", "url": "https://www.federalreserve.gov/newsevents/speech/waller20210805a.htm", "kind": "html"},
    {"date": "2022-02-18", "speaker": "Lael Brainard",          "title": "Preparing for the Financial System of the Future", "url": "https://www.federalreserve.gov/newsevents/speech/brainard20220218a.htm", "kind": "html"},
    {"date": "2022-05-26", "speaker": "Lael Brainard",          "title": "Digital Assets and the Future of Finance: Examining the Benefits and Risks of a U.S. Central Bank Digital Currency (testimony)", "url": "https://www.federalreserve.gov/newsevents/testimony/brainard20220526a.htm", "kind": "html"},
    {"date": "2022-08-17", "speaker": "Michelle W. Bowman",     "title": "Technology, Innovation, and Financial Services", "url": "https://www.federalreserve.gov/newsevents/speech/bowman20220817a.htm", "kind": "html"},
    {"date": "2022-10-12", "speaker": "Michael S. Barr",        "title": "Managing the Promise and Risk of Financial Innovation", "url": "https://www.federalreserve.gov/newsevents/speech/barr20221012a.htm", "kind": "html"},
    {"date": "2022-10-14", "speaker": "Christopher J. Waller",  "title": "The U.S. Dollar and Central Bank Digital Currencies", "url": "https://www.federalreserve.gov/newsevents/speech/waller20221014a.htm", "kind": "html"},
    # publications that are NOT in the BIS speeches dataset:
    {"date": "2022-01-20", "speaker": "Federal Reserve Board",  "title": "Money and Payments: The U.S. Dollar in the Age of Digital Transformation (discussion paper)", "url": "https://www.federalreserve.gov/publications/files/money-and-payments-20220120.pdf", "kind": "pdf"},
    {"date": "2022-01-20", "speaker": "Federal Reserve Board (press release)", "title": "Federal Reserve Board releases discussion paper that examines pros and cons of a potential U.S. central bank digital currency", "url": "https://www.federalreserve.gov/newsevents/pressreleases/other20220120a.htm", "kind": "html"},
]

fed_added, failed = [], []
for c in FED_CANDIDATES:
    key = (c["date"], surname(c["speaker"]))
    if key in bis_keys:
        print(f"  dup (already in BIS): {c['date']} {c['speaker']}  -> skip")
        continue
    try:
        text = fetch_pdf_text(c["url"]) if c["kind"] == "pdf" else fetch_html_body(c["url"])
        if len(text.split()) < 50:
            raise ValueError(f"suspiciously short ({len(text.split())} words)")
        fed_added.append({**{k: c[k] for k in ("date", "speaker", "title", "url")},
                          "surname": surname(c["speaker"]), "source": "Fed", "text": text})
        print(f"  ADDED (Fed-unique): {c['date']} {c['speaker'][:28]:<28} {len(text.split()):>6} words")
    except Exception as e:
        failed.append({"url": c["url"], "error": f"{type(e).__name__}: {e}"})
        print(f"  !! FAILED {c['url']} -> {type(e).__name__}: {e}  (logged, skipped)")
    time.sleep(0.6)


# ---------------------------------------------------------------------------
# 3. Write one .txt per item + build the events index
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("STEP 3/4  Writing text files + cbdc_events.csv")
print("=" * 78)

import os, glob
os.makedirs(TXT_DIR, exist_ok=True)
# start clean so re-runs don't leave stale files behind
for old in glob.glob(os.path.join(TXT_DIR, "*.txt")):
    os.remove(old)

all_items = bis_items + fed_added
rows, used = [], set()
for it in sorted(all_items, key=lambda x: (x["date"], x["surname"])):
    fname = f"{it['date']}_{slug(it['surname']) or 'item'}.txt"
    base, k = fname[:-4], 1
    while fname in used:                      # only dedupe within THIS run
        fname = f"{base}-{k}.txt"; k += 1
    used.add(fname)
    with open(os.path.join(TXT_DIR, fname), "w", encoding="utf-8") as fh:
        fh.write(it["text"])
    wc = len(it["text"].split())
    rows.append({
        "date": it["date"], "speaker": it["speaker"], "title": it["title"],
        "source": it["source"], "url": it["url"], "word_count": wc,
        "txt_filename": fname, "cbdc_term_count": count_terms(it["text"]),
        "threat_direction": "",                 # <-- EMPTY: for YOU to fill manually
    })

events = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
events.to_csv(OUT_CSV, index=False)
print(f"  Wrote {len(rows)} text files to {TXT_DIR}/")
print(f"  Saved {OUT_CSV}")


# ---------------------------------------------------------------------------
# 4. VERIFICATION / SUMMARY
# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print("STEP 4/4  Summary")
print("=" * 78)
print(f"  Total CBDC items:      {len(events)}")
print(f"  From BIS:              {(events.source=='BIS').sum()}")
print(f"  From Fed (BIS missed): {(events.source=='Fed').sum()}")
print(f"  Date range:            {events.date.min()} -> {events.date.max()}")
print(f"  Word count: min {events.word_count.min()}, median {int(events.word_count.median())}, max {events.word_count.max()}")
print(f"  Failed URLs:           {len(failed)}")
for fl in failed:
    print(f"     - {fl['url']}  ({fl['error']})")
print("\n  FULL ITEM TABLE:")
print(f"  {'DATE':<11} {'SRC':<4} {'wc':>6} {'terms':>5}  {'SPEAKER':<28} TITLE")
for _, r in events.iterrows():
    print(f"  {r['date']:<11} {r['source']:<4} {r['word_count']:>6} {r['cbdc_term_count']:>5}  "
          f"{str(r['speaker'])[:28]:<28} {str(r['title'])[:50]}")
print("\nDONE — Phase 3 collection complete.")
