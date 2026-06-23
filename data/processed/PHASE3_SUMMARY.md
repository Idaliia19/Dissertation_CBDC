# Phase 3 Summary — Federal Reserve CBDC Communication Texts

**Date built:** 2026-06-23
**Sources (both free, no key):**
- **PRIMARY — BIS central bankers' speeches dataset** (`https://www.bis.org/speeches/speeches.zip`,
  122MB → `speeches.csv`, 20,365 speeches with full texts). Columns: `url, title, description, date, text, author`.
- **SECONDARY — federalreserve.gov** (`/cbdc-speeches.htm`, the Money & Payments paper, its press release).

## Output files
- `data/cbdc_texts/<date>_<speaker>.txt` — **27 files**, one full clean body text per item.
- `data/processed/cbdc_events.csv` — **27 rows**. Columns:
  `date, speaker, title, source, url, word_count, txt_filename, cbdc_term_count, threat_direction`.
  **`threat_direction` is intentionally EMPTY — for you to fill in manually** (I did not guess it).
  `cbdc_term_count` is an extra helper column (CBDC-term hits) to help you prune; not required by the brief.

## How items were selected (no fabrication)
**BIS:** kept a speech only if (1) `date >= 2021-01-01`, (2) the **speaker's affiliation**
(the clause before ", at " in `description`) contains "Federal Reserve" — this correctly
**excludes 3 non-Fed speakers** (Andrew Hauser/Bank of England, Gerardo Esquivel/Banco de México,
Jon Cunliffe/Bank of England) whose speeches only *mentioned* the Fed in the event context, and
(3) the text mentions a CBDC term ("central bank digital currency", "cbdc", "digital dollar", or
"digital currency"). → **24 BIS items.**

**Fed website:** 10 curated candidates checked against BIS. **7 were duplicates** (same date+speaker
already in BIS) and skipped. **3 were Fed-unique and added:**
| date | item | why BIS missed it |
|---|---|---|
| 2022-01-20 | "Money and Payments" discussion paper (PDF, 10,779 words) | a publication, not a speech |
| 2022-01-20 | Press release announcing the paper | a press release, not a speech |
| 2022-05-26 | Brainard testimony to the House Financial Services Committee | testimony not in the BIS speeches set |

**De-duplication key:** `(date, speaker surname)`. Final set has **0 duplicate (date, speaker)** rows.

## Result
- **27 items total** — 24 from BIS, 3 from Fed.
- **Date range:** 2021-03-18 → 2025-08-20.
- **Word counts:** min 400 (press release), median 2,277, max 10,779 (the discussion paper).
- **Failed URLs: 0.** Every item kept a working source URL.
- **9 distinct speakers** (Powell, Brainard, Quarles, Waller, Bowman, Barr, Williams, Neal, + the Board).

## Quality notes
- BIS texts come straight from the dataset's `text` field (already clean full bodies).
- The discussion-paper **PDF** was extracted with `pdfplumber` (cleaner word spacing than pypdf) and
  de-hyphenated at line breaks. Minor PDF artifacts may remain (table-of-contents lines, page numbers).
- BIS `date` is the dataset's recorded date; for the 3 Fed-sourced items the date is the exact
  Fed publication date. For an event study, treat the Fed-sourced dates as authoritative.

## ⚠️ Borderline items for your manual review (low CBDC-term count)
6 of 27 items mention CBDC only in passing (`cbdc_term_count <= 3`). They are genuine Fed speeches but
may not be "CBDC communications" in substance — consider excluding when you fill `threat_direction`:
| date | speaker | terms | title |
|---|---|---|---|
| 2022-06-01 | Williams | 3 | The song remains the same |
| 2022-10-12 | Barr | 3 | Managing the promise and risk of financial innovation |
| 2024-02-15 | Bowman | 2 | Advancing cross-border payments and financial inclusion |
| 2024-05-15 | Bowman | 2 | Innovation and the evolving financial landscape |
| 2024-10-18 | Waller | 1 | Centralized and decentralized finance |
| 2025-08-20 | Waller | 1 | Technological advancements in payments |

The strongest, unambiguous CBDC items (high term counts): the Jan-2022 discussion paper (198),
Bowman "Considerations for a CBDC" Apr-2023 (107), Quarles (80), Waller "Solution in Search of a
Problem" (74), Waller "US dollar and CBDCs" Oct-2022 (58), Brainard May-2021 (47), Bowman Oct-2023 (46).

## Caveats
- The BIS dataset is updated periodically; this snapshot was downloaded 2026-06-23.
- "digital currency" is a broad term; combined with the strict Fed-affiliation filter it mainly
  catches CBDC-adjacent speeches, but see the borderline list above.
- The raw 366MB `speeches.csv` is kept in `data/raw/` (not committed-friendly); the 122MB zip is in `data/raw/bis_speeches.zip`.
