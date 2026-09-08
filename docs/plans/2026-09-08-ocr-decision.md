# OCR pipeline decision

Date: 2026-09-08. Branch: `wp8-benchmark-repair` with `wp9-cpu-profiles`, `wp9-vlm-profiles`,
`wp9-claude-hybrid`, and `wp10-gold` merged. Inputs: the WP8 baseline
(`data/reports/2026-09-08-wp8-baseline.md`), the WP9 comparison (`data/reports/2026-09-08-wp9-comparison.md`
and the per-family reports `2026-09-08-wp9a-cpu.md`, `2026-09-08-wp9b-vlm.md`, `2026-09-08-wp9c-claude-hybrid.md`),
and the WP10 gold set (`benchmark/gold.py`, `data/reports/2026-09-08-wp10-gold.md`).

Follow-up on 2026-09-08 (branch `wp10-wp11-followup`, merged here): the Anthropic credits were purchased, so
the gold set (WP10, `data/reports/2026-09-08-wp10-gold.md`), the Claude transcription profile (C5,
`data/reports/2026-09-08-wp9c-claude.md`), and the judge pass (WP11, `data/reports/2026-09-08-wp11-judge.md`)
have measurements. The HF token in `.env` still lacks `job.write` on `dreamproit`, so no GPU job ran; the
VLM profiles ran on the Mac with MLX and the GPU throughput in section 5 remains an estimate.

## 1. Inputs

### Sample

`benchmark/sample.yaml`: 39 granules, 87 pages; volumes 10 and 39 (pre-1951), 72 and 85 (1951 to 2002),
124 and 132 (digital). The digital era holds public and private laws only (F4). Tier B scores the granule
PDF against the GPO USLM slice after clipping to the reference span (F3); tier A runs a profile on 300 dpi
page images of the five digital granules and scores against the exact USLM.

The VLM profiles ran on `benchmark/sample_vlm.yaml`: the 14 public and private laws of the sample with at
most three pages (10 scanned, 4 digital), 21 pages. EasyOCR ran on 12 granules. The comparison in section 2
therefore reports two views: every profile on the 14 laws it has in common with the VLM runs, and each
profile on all of its rows.

### Scanned-era size (packages table, volumes 1 to 116)

| Period | Volumes | Pages |
|---|---|---|
| 1789 to 1850 | 1 to 9 | 8,132 |
| 1851 to 1900 | 10 to 31 | 28,363 |
| 1901 to 1950 | 32 to 64 | 96,762 |
| 1951 to 1975 | 65 to 89 | 40,142 |
| 1976 to 2002 | 90 to 116 | 103,364 |
| Total | 116 | 276,763 |

The plan's cost table assumed 200,000 pages; the projections below use 276,763.

### Hosts and measured throughput

| Host | Capacity | Seconds per page |
|---|---|---|
| Container `app` (10 CPU, 8 GB, no GPU), 2 workers | Docling + Tesseract 300 dpi | 4.4 per worker (`scanned`), 3.9 (`tesseract:psm4`), 4.2 (`tesseract:psm6`) |
| same | Docling over the text layer (`textlayer`) | 1.5 per worker |
| same | Docling + RapidOCR | 5.7 per worker; 4.6 GB peak on a 4-page digital granule, so 1 worker there |
| same | Docling + EasyOCR | 60.9; over 5 GB per page; killed on most granules |
| Mac (M1 Pro, 16 GB), MLX, one model at a time | GLM-OCR | 9.6 to 13.4 |
| same | LightOnOCR-2-1B | 11.3 to 18.0 |
| same | GraniteDocling-258M | 4.3 to 23.2 (repetition loops on 2 of 21 pages) |
| HF Jobs (GPU) | not measured (token without `job.write`) | |
| Anthropic API, Batch API, 10 granule batches in flight | `claude-haiku-4-5` 2,320 image tokens per page | $0.0064 per page measured (87 pages, $0.55); batches took 1 to 90 minutes each |
| same | `claude-sonnet-5` | @@SONNET_COST@@ |
| same | `claude-opus-5` | $0.0376 per page measured (87 pages, $3.27); two of 39 batches failed on a lookup race and a connection error and were resubmitted |

## 2. Results matrix

Gold-set CER: median over the 150 gold pages (30 per period, 1789 to 2002; mean in parentheses) of the
Levenshtein distance on the text column against pages transcribed twice by `claude-opus-5` and adjudicated
(`benchmark/gold/`). Tier B columns: mean CER on the 14 laws common to every run (count in parentheses).
Section recall is the share of reference sections matched by number and first 40 characters.

| Profile | Candidate | Gold CER, 150 pages | pre-1951 laws | 1951 to 2002 laws | digital laws | Section recall (scanned) |
|---|---|---|---|---|---|---|
| `vlm:glm_ocr` | C4 GLM-OCR, MLX | 0.003 (0.025) | 0.002 (5) | 0.006 (5) | 0.029 (3) | 0.00 / 0.48 |
| `claude:claude-haiku-4-5` | C5, Batch API | not run on the gold granules | 0.016 (5) | 0.007 (5) | 0.032 (3) | 0.32 / 0.44 |
| `claude:claude-sonnet-5` | C5, Batch API | not run on the gold granules | @@SONNET_ROW@@ |
| `claude:claude-opus-5` | C5, Batch API | not run on the gold granules | 0.003 (5) | 0.006 (5) | 0.029 (3) | 0.32 / 0.44 |
| `textlayer` | C1 vendor text layer | 0.022 (0.064) | 0.012 (5) | 0.075 (5) | 0.046 (3) | 0.32 / 0.44 |
| `vlm:lightonocr` | C4 LightOnOCR, MLX | not run on the gold granules | 0.015 (5) | 0.053 (5) | 0.048 (3) | 0.00 / 0.48 |
| `tesseract:psm4` | C2 | not run on the gold granules | 0.062 (5) | 0.533 (5) | 0.043 (3) | 0.30 / 0.25 |
| `scanned` (Tesseract, automatic psm, WP8 baseline) | C2 | 0.143 (0.235) | 0.085 (5) | 0.189 (5) | (`digital`: 0.046) | 0.29 / 0.25 |
| `tesseract:psm6` | C2 | not run on the gold granules | 0.098 (5) | 0.188 (5) | 0.043 (3) | 0.29 / 0.30 |
| `rapidocr` | C3 | not run on the gold granules | 0.101 (5) | 0.102 (5) | 0.073 (3) | 0.31 / 0.40 |
| `vlm:granite_docling` | C4 | not run on the gold granules | 0.787 (5) | 0.257 (5) | 0.029 (3) | 0.00 / 0.28 |
| `easyocr` | C3 | not run on the gold granules | 0.819 (5) | 0.810 (5) | killed | 0.17 / 0.18 |
| `hybrid:vlm:glm_ocr` | C6 over GLM-OCR | | 0.002 (5) | 0.003 (5) | 0.034 (3) | 1.00 / 1.00 |
| `hybrid:claude:claude-opus-5` | C6 over C5 | | 0.005 (5) | 0.009 (5) | 0.035 (3) | 0.94 / 0.99 |
| `hybrid:textlayer` | C6 over the text layer | | 0.011 (5) | 0.061 (5) | 0.051 (3) | 0.94 / 0.98 |
| `hybrid:rapidocr` | C6 over RapidOCR | | 0.097 (5) | 0.097 (5) | 0.078 (3) | 0.94 / 0.99 |
| `hybrid:scanned` | C6 over Tesseract | | 0.067 (5) | 0.185 (5) | | 0.94 / 0.75 |
| C0 GPO USLM (the reference of tier B) | | 0.011 (0.143) | | | | |

The `vlm:lightonocr` and `vlm:granite_docling` rows are after the running-head fix of section 8 (before it:
0.022 / 0.242 / 0.100 and 0.787 / 0.257 / 0.057); no GLM-OCR row moved.

Gold-set CER per period (median; `data/reports/2026-09-08-wp10-gold.md` has the means and every page):

| Candidate | 1789-1850 | 1851-1900 | 1901-1950 | 1951-1975 | 1976-2002 | Sidenote CER, all |
|---|---|---|---|---|---|---|
| C0 GPO USLM | 0.012 | 0.010 | 0.002 | 0.023 | 0.091 | 0.050 |
| `vlm:glm_ocr` | 0.009 | 0.006 | 0.001 | 0.003 | 0.000 | 1.000 |
| `textlayer` | 0.040 | 0.027 | 0.011 | 0.023 | 0.010 | 0.240 |
| `scanned` | 0.069 | 0.055 | 0.035 | 0.225 | 0.567 | 0.674 |

Notes on the gold set: 136 of 150 pages had at least one differing run between the two transcriptions
(12.4 per page on average), resolved by a third call over the page image. The text column includes the
Peters-edition case-note footnotes, which fill most of some 1789 to 1850 pages. C0 scores above 0.5 on 12
pages (volumes 1, 2, 5, 77) where the volume USLM has no marker for the page and its text runs into the
next page; its 1976-2002 median of 0.091 is the digitization vendor's OCR of those volumes. GLM-OCR emits
almost none of the marginal notes (sidenote CER 1.000 on 144 pages): the hybrid takes sidenotes from the
GPO structure, the raw profile has none. GLM-OCR scores above 0.1 on 10 of the 150 pages and above 0.5 on
two (STATUTE-1-Pg96 p1, STATUTE-17-Pg466 p1, where the text layer scores 0.089 and 0.010): on those pages it
left out a region of the page (STATUTE-1-Pg448-2 p1 starts mid-page, 3,082 characters against 3,533 in the
gold). The 20 pages for human review are listed in `data/gold/review.md`.

Mean CER over every row of the sample (all classes; 18 pre-1951, 15 from 1951 to 2002, 5 digital):

| Profile | pre-1951 | 1951 to 2002 | digital B | digital A (rasters) |
|---|---|---|---|---|
| `scanned` / `digital` | 0.181 | 0.252 | 0.048 | |
| `textlayer` | 0.201 (median 0.039) | 0.060 | 0.048 | 1.000 (no text layer on a raster) |
| `tesseract:psm4` | 0.189 | 0.376 | 0.046 | 0.046 |
| `tesseract:psm6` | 0.263 | 0.240 | 0.046 | 0.046 |
| `rapidocr` | 0.245 | 0.097 | 0.079 | 0.076 |
| `vlm:glm_ocr` (5, 5, 3 rows) | 0.002 | 0.006 | 0.029 | 0.029 |
| `claude:claude-haiku-4-5` (18, 15, 5 rows) | 0.186 (median 0.048) | 0.019 | 0.039 | |
| `claude:claude-opus-5` (18, 15, 5 rows) | 0.152 (median 0.025) | 0.019 | 0.037 | |
| `hybrid:claude:claude-opus-5` | 0.101 (median 0.021) | 0.019 | 0.044 | |
| `hybrid:textlayer` | 0.140 | 0.054 | 0.052 | |
| `hybrid:scanned` | 0.111 | 0.238 | | |

Haiku's pre-1951 mean is four rows: the proclamation STATUTE-39-Pg1738 (0.77), the treaties STATUTE-39-Pg1645
(0.69) and STATUTE-10-Pg954 (0.17), and the concurrent resolutions STATUTE-39-Pg1600-3 and -1603-4 (0.62,
0.57), the same rows every profile fails on (bilingual columns, garbled headings); its public and private
laws score 0.019 to 0.023. Opus reads the same rows the same way (0.152 mean, 0.025 median); on the 14
common laws it matches GLM-OCR (0.003 and 0.006 against 0.002 and 0.006) at $0.0376 per page.

Checks made on the GLM-OCR result: on STATUTE-72-Pg1751 its text differs from the PDF text layer where the
text layer has OCR errors (`maintain` against the layer's `maintam`), and its CER against the text layer
is 0.037 while the text layer's own CER against the reference is 0.038. The output is not a copy of the
embedded text.

Rows above 0.5 in the sample are resolutions, treaties, and proclamations with garbled OCR of headings or
bilingual columns (listed in the WP8 report); the digital-era laws score 0.022 to 0.060 with every
profile that sees them.

## 3. Exclusions

Decision rule (plan section 4): rank by gold-set CER, then tier A CER, then section recall; exclude a
candidate whose projected cost for volumes 1 to 116 exceeds $5,000 or whose throughput exceeds two weeks
on the available hosts.

| Candidate | Projected cost | Projected wall time | Excluded |
|---|---|---|---|
| C5 `claude-opus-5` | $10,400 with the Batch API ($0.0376 per page measured), $20,800 streaming | | yes, cost; tier B CER equals GLM-OCR's (0.003 and 0.006 on the common laws) |
| C5 `claude-sonnet-5` | @@SONNET_PROJ@@ | | @@SONNET_EXCL@@ |
| C5 `claude-haiku-4-5` | $1,770 with the Batch API ($0.0064 per page measured), $3,500 streaming | Batch API turnaround 1 to 90 minutes per batch; no wall-time limit | not by cost; gold CER not measured, tier B behind GLM-OCR by an order of magnitude |
| C3 EasyOCR | $0 | 196 days at 61 s per page | yes, time and memory |
| C3 RapidOCR | $0 | 18 days with one worker (memory), 9 with two | borderline; CER behind the text layer in both eras |
| C4 GraniteDocling | $0 | | yes, repetition loops and CER 0.79 pre-1951 |
| C4 LightOnOCR | $0 | 36 to 58 days on the Mac | yes, time on the Mac; CER behind GLM-OCR |
| C4 GLM-OCR on the Mac alone | $0 | 35 days at 11 s per page | yes, time; see section 5 for the GPU route |

## 4. Decision

Chosen profile: `hybrid:vlm:glm_ocr`, the GPO USLM structure (C0) with body text from GLM-OCR through
Docling's VLM pipeline (C4), identifiers added by the rules in section 6. Ranking under the plan's rule with
the gold set in place: gold-set CER puts GLM-OCR first (median 0.003 against 0.022 for the text layer and
0.143 for Tesseract, and first in every period); tier A CER puts it first (0.029 against 0.043 to 0.100);
tier B on the scanned laws puts it first (0.002 and 0.006 against 0.012 and 0.075 for the text layer and
0.003 and 0.006 for the best Claude model); section recall puts the hybrid form of any candidate (0.94 to 1.00)
ahead of its raw form (0.00 to 0.48). The gold set does not reverse the order of GLM-OCR and the text layer.

Two measurements qualify the choice. GLM-OCR leaves out the marginal notes (gold sidenote CER 1.000), so the
sidenotes in the generated USLM come from the GPO structure and are only as good as the vendor's OCR of
them (C0 sidenote CER 0.050 over the gold set, 0.171 for 1789 to 1850). The judge pass (section 7) scores
structure 71.5 and tagging 68.4 on the hybrid; its findings are listed there and in section 8.

Fallback profile: `hybrid:textlayer`, the same structure with the vendor text layer as the text source
(CER 0.011 and 0.061 on the common laws; 0.140 mean pre-1951 over all classes because some pages carry a
garbage text layer), with `tesseract:psm6` per page where the text layer is empty or unreadable. It runs in
the container at 1.5 s per page per worker and costs nothing.

The DoclingDocument JSON is published for the chosen profile: the hybrid needs the candidate's page
geometry to place page markers, and the VLM output is the only record of the model's reading order.

The decision covers volumes 1 to 116: the sample has rows for volumes 10 to 132 and the gold set has 30
pages from volumes 1, 2, and 5 (1789 to 1845), where GLM-OCR scores a median CER of 0.009 against 0.040 for
the text layer. GLM-OCR also ran on the 25 sample granules the WP9 runs had skipped
(`data/reports/2026-09-08-wp9b-glm-all.md`, 21.4 s per page on the Mac): the 4- to 12-page laws score 0.039
to 0.057 (17 laws in all: mean 0.016 against 0.016 for `claude-opus-5` and 0.045 for the text layer), and
the resolutions, proclamations, and treaties score as they do for every profile (median 0.046), except five
rows where GLM-OCR left out part of a page (STATUTE-72-PgB14, -PgB23-3, STATUTE-10-Pg954, -Pg1177-2,
STATUTE-39-Pg1738: CER 0.65 to 3.2 unclipped, against 0.00 to 0.78 for Opus on the same rows).

## 5. Projection for volumes 1 to 116

276,763 pages.

| Route | Seconds per page | Wall time | Cost |
|---|---|---|---|
| GLM-OCR on the Mac, MLX | 11.7 (measured over the 247 gold pages; 9.6 to 13.4 on the sample) | 37 days continuous | $0 |
| GLM-OCR on one HF Jobs L4 (`benchmark/jobs.py`, $0.80 per hour) | 2 to 5 (estimate; not measured) | 6 to 16 days on one job, half on two | $125 to $310 per job-run |
| Hybrid assembly in the container | 0.1 to 0.3 (measured) | 1 day, overlapped | $0 |
| Fallback: text layer in the container, 2 workers | 1.5 per worker (measured) | 2.4 days | $0 |
| Fallback per-page Tesseract psm6, 2 workers | 4.2 per worker (measured) | 7 days if every page needed it | $0 |

Hosts to use: HF Jobs for GLM-OCR over volumes 65 to 116 first, then 1 to 64 (plan order), with the Mac
taking a volume at a time in parallel; the container for the hybrid assembly, the fallback profile, and the
ledger (`conversions`, `reconcile`). Unit of work stays one granule, cut from the Hub volume PDF by the MODS
page range (WP12).

The GPU figure is the one number the projection depends on. Section 8 lists what is needed to measure it.

## 6. Identifier rules for the generated USLM

From plan section 7; implemented in `pipeline/hybrid.py`.

| Document | Identifier | Example |
|---|---|---|
| Public law, 57th Congress (1901) onward | `/us/pl/{congress}/{number}` | `/us/pl/85/910` |
| Private law | `/us/pvtl/{congress}/{number}` | `/us/pvtl/85/12` |
| Act before public-law numbering, cited by chapter | `/us/act/{YYYY-MM-DD}/ch{chapter}` | `/us/act/1916-08-25/ch408` |
| Section and below | GPO PLAW scheme: `/s{n}`, `/s{n}/{a}`, `/s{n}/{a}/{1}`, with division and title segments when the law has them | `/us/pl/104/333/dI/tVIII/s814/e/1` |
| Page | `/us/stat/{volume}/{page}`; lettered pages lower case | `/us/stat/72/1751`, `/us/stat/64/b3` |

Laws from 1901 to 1957 carry both forms; the chapter form goes on `meta/property[@role='alternateIdentifier']`.

## 7. Judge pass

`claude-opus-5` judged the `hybrid:vlm:glm_ocr` output of @@JUDGE_N@@ sample granules against the granule PDF
and the GovInfo USLM (`data/reports/2026-09-08-wp11-judge.md`, run `wp11-judge`, @@JUDGE_COST@@):

| Score (0 to 100) | Mean | Range |
|---|---|---|
| Text | @@JUDGE_TEXT@@ |
| Structure | @@JUDGE_STRUCT@@ |
| Tagging | @@JUDGE_TAG@@ |

Findings that recur across granules:

1. The text of the neighbouring laws on the shared first and last pages is kept in `preface` and
   `appendix[@role='trailingMatter']` (plan defect F2: nothing Docling produced is dropped). The judge counts
   it as extra text on most granules; WP12 decides whether the shared-page text is dropped once the neighbour
   granule is converted.
2. The unnumbered first section ("That ...") carries no identifier; the judge expects `/us/pl/{c}/{n}/s1`.
3. Lost spaces at the hybrid's run replacements: "Congressassembled", "otherpurposes", "ProvidedProvided".
4. No `page` marker for the first page of the granule when the marker sits in the previous document.
5. In volumes 10 and 39 the chapter designator ("Chap. CXXI.—") is split from its long title across
   `preface` and `main`.

## 8. Open items

1. An HF token with `job.write` on `dreamproit`. Then `python -m benchmark.jobs submit --variant glm_ocr`
   on the 14-law subset to measure seconds per page and dollars per page on an L4, which fixes the wall time
   in section 5. The same run covers DeepSeek-OCR through Ollama.
2. Nanonets-OCR2 was not run (7.5 GB download stalled); `--repo-id mlx-community/Nanonets-OCR2-3B-4bit` is
   wired for a rerun.
3. The tier A rows for the VLM profiles were computed on wrapper PDFs with 1912 x 2476 pt pages (fixed in
   `benchmark/rasterize.py` after the runs); the text is unaffected, the per-page time for those rows is
   about three times too high.
4. Sidenotes: GLM-OCR emits none, so the hybrid's sidenotes are the GPO vendor's OCR (gold sidenote CER
   0.050; 0.171 for 1789 to 1850). A sidenote pass with a second model, or the Claude profile's sidenote
   lines, would replace them; not measured.
5. Judge findings 2 to 5 of section 7 are rule changes in `pipeline/hybrid.py` and `pipeline/uslm.py`
   (identifier on the unnumbered first section, spacing at run boundaries, the first page marker, the
   chapter designator).
6. The gold set's C0 column is undefined on the 12 pages whose volume USLM lacks a page marker; a page
   split by PDF page position instead of the marker would score them.
7. GLM-OCR drops a region of the page on about one page in fifteen (10 of 150 gold pages above CER 0.1,
   2 above 0.5; 5 of 21 non-law sample granules). A per-page guard in the hybrid, falling back to the text
   layer when the VLM page text is much shorter than the text layer's, would bound the damage; not built.

Resolved on 2026-09-08: Anthropic credits (gold set, C5, judge pass, all in this document); GLM-OCR on
volumes 1 to 9 (30 gold pages) and on the 25 sample granules the VLM runs had skipped; `pipeline/uslm.py`
treats page-top lines that match the running-head patterns as headers (commit `035bb80`, test on the
LightOnOCR output of STATUTE-72-Pg1751), which moved LightOnOCR's 1951 to 2002 tier B CER from 0.242 to 0.053
and left every GLM-OCR row unchanged.
