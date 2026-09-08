# OCR pipeline decision

Date: 2026-09-08. Branch: `wp8-benchmark-repair` with `wp9-cpu-profiles`, `wp9-vlm-profiles`,
`wp9-claude-hybrid`, and `wp10-gold` merged. Inputs: the WP8 baseline
(`data/reports/2026-09-08-wp8-baseline.md`), the WP9 comparison (`data/reports/2026-09-08-wp9-comparison.md`
and the per-family reports `2026-09-08-wp9a-cpu.md`, `2026-09-08-wp9b-vlm.md`, `2026-09-08-wp9c-claude-hybrid.md`),
and the WP10 gold set (`benchmark/gold.py`, `data/reports/2026-09-08-wp10-gold.md`).

Two inputs the plan calls for are missing. The Anthropic organization's credit balance was too low for
every request made on 2026-09-08 (HTTP 400, request ids in the WP9c and WP10 reports), so the Claude
transcription profile (C5), the gold set (WP10), and the judge pass (WP11) have no measurements. The
HF token in `.env` lacks `job.write` on `dreamproit`, so no GPU job ran; the VLM profiles ran on the Mac
with MLX. The decision below is therefore provisional on the two measurements in section 8.

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
| Anthropic API | not measured (credit balance) | offline token count: 2,070 image tokens per page |

## 2. Results matrix

Mean CER, tier B, on the 14 laws common to every run (count in parentheses). Section recall is the share of
reference sections matched by number and first 40 characters.

| Profile | Candidate | pre-1951 laws | 1951 to 2002 laws | digital laws | Section recall (scanned) |
|---|---|---|---|---|---|
| `vlm:glm_ocr` | C4 GLM-OCR, MLX | 0.002 (5) | 0.006 (5) | 0.029 (3) | 0.00 / 0.48 |
| `textlayer` | C1 vendor text layer | 0.012 (5) | 0.075 (5) | 0.046 (3) | 0.32 / 0.44 |
| `vlm:lightonocr` | C4 LightOnOCR, MLX | 0.022 (5) | 0.242 (5) | 0.100 (3) | 0.00 / 0.20 |
| `tesseract:psm4` | C2 | 0.062 (5) | 0.533 (5) | 0.043 (3) | 0.30 / 0.25 |
| `scanned` (Tesseract, automatic psm, WP8 baseline) | C2 | 0.085 (5) | 0.189 (5) | (`digital`: 0.046) | 0.29 / 0.25 |
| `tesseract:psm6` | C2 | 0.098 (5) | 0.188 (5) | 0.043 (3) | 0.29 / 0.30 |
| `rapidocr` | C3 | 0.101 (5) | 0.102 (5) | 0.073 (3) | 0.31 / 0.40 |
| `vlm:granite_docling` | C4 | 0.787 (5) | 0.257 (5) | 0.057 (3) | 0.00 / 0.28 |
| `easyocr` | C3 | 0.819 (5) | 0.810 (5) | killed | 0.17 / 0.18 |
| `hybrid:vlm:glm_ocr` | C6 over GLM-OCR | 0.002 (5) | 0.003 (5) | 0.034 (3) | 1.00 / 1.00 |
| `hybrid:textlayer` | C6 over the text layer | 0.011 (5) | 0.061 (5) | 0.051 (3) | 0.94 / 0.98 |
| `hybrid:rapidocr` | C6 over RapidOCR | 0.097 (5) | 0.097 (5) | 0.078 (3) | 0.94 / 0.99 |
| `hybrid:scanned` | C6 over Tesseract | 0.067 (5) | 0.185 (5) | | 0.94 / 0.75 |
| `claude:*` | C5 | not run | not run | not run | |

Mean CER over every row of the sample (all classes; 18 pre-1951, 15 from 1951 to 2002, 5 digital):

| Profile | pre-1951 | 1951 to 2002 | digital B | digital A (rasters) |
|---|---|---|---|---|
| `scanned` / `digital` | 0.181 | 0.252 | 0.048 | |
| `textlayer` | 0.201 (median 0.039) | 0.060 | 0.048 | 1.000 (no text layer on a raster) |
| `tesseract:psm4` | 0.189 | 0.376 | 0.046 | 0.046 |
| `tesseract:psm6` | 0.263 | 0.240 | 0.046 | 0.046 |
| `rapidocr` | 0.245 | 0.097 | 0.079 | 0.076 |
| `vlm:glm_ocr` (5, 5, 3 rows) | 0.002 | 0.006 | 0.029 | 0.029 |
| `hybrid:textlayer` | 0.140 | 0.054 | 0.052 | |
| `hybrid:scanned` | 0.111 | 0.238 | | |

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
| C5 `claude-opus-5` | $22,400 streaming, $11,200 with the Batch API ($0.081 per page measured offline) | | yes, cost |
| C5 `claude-sonnet-5` | $9,000, $4,500 batch | | yes above $5,000 without the Batch API; quality unmeasured |
| C5 `claude-haiku-4-5` | $4,480, $2,240 batch | | not by cost; quality unmeasured |
| C3 EasyOCR | $0 | 196 days at 61 s per page | yes, time and memory |
| C3 RapidOCR | $0 | 18 days with one worker (memory), 9 with two | borderline; CER behind the text layer in both eras |
| C4 GraniteDocling | $0 | | yes, repetition loops and CER 0.79 pre-1951 |
| C4 LightOnOCR | $0 | 36 to 58 days on the Mac | yes, time on the Mac; CER behind GLM-OCR |
| C4 GLM-OCR on the Mac alone | $0 | 35 days at 11 s per page | yes, time; see section 5 for the GPU route |

## 4. Decision

Chosen profile: `hybrid:vlm:glm_ocr`, the GPO USLM structure (C0) with body text from GLM-OCR through
Docling's VLM pipeline (C4), identifiers added by the rules in section 6. Ranking under the plan's rule with
the gold-set CER missing: tier A CER puts GLM-OCR first (0.029 against 0.043 to 0.100 for the others that
ran on rasters); tier B on the scanned laws puts it first by an order of magnitude (0.002 and 0.006 against
0.012 and 0.075 for the next candidate); section recall puts the hybrid form of any candidate (0.94 to 1.00)
ahead of its raw form (0.00 to 0.48).

Fallback profile: `hybrid:textlayer`, the same structure with the vendor text layer as the text source
(CER 0.011 and 0.061 on the common laws; 0.140 mean pre-1951 over all classes because some pages carry a
garbage text layer), with `tesseract:psm6` per page where the text layer is empty or unreadable. It runs in
the container at 1.5 s per page per worker and costs nothing.

The DoclingDocument JSON is published for the chosen profile: the hybrid needs the candidate's page
geometry to place page markers, and the VLM output is the only record of the model's reading order.

The decision holds for volumes 10 to 116 (1855 onward), where the sample has measurements. Volumes 1 to 9
(1789 to 1850) have no rows yet; the gold set samples 30 pages from them (`benchmark/gold_sample.yaml`).

## 5. Projection for volumes 1 to 116

276,763 pages.

| Route | Seconds per page | Wall time | Cost |
|---|---|---|---|
| GLM-OCR on the Mac, MLX | 11 (measured, mean of 9.6 to 13.4) | 35 days continuous | $0 |
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

Not run: every Anthropic request on 2026-09-08 returned "credit balance is too low". Command once credits
are available, on 20 granules of the chosen profile:

```
docker compose exec app python -m benchmark.evaluate --spec benchmark/sample.yaml \
    --profiles hybrid:vlm:glm_ocr --tier B --rebuild --judge --judge-limit 20 --run-id wp11-judge
```

## 8. Open items

1. Anthropic credits. Then: `python -m benchmark.gold build --pages 150` (about $25 with `claude-opus-5`),
   `python -m benchmark.gold score --profile vlm:glm_ocr` and `--profile textlayer`, the C5 sample runs
   (`python -m pipeline.claude_ocr --spec benchmark/sample.yaml --model claude-haiku-4-5 --batch`), and the
   judge pass above. The gold-set CER is the first key of the decision rule; if it reverses the order of
   GLM-OCR and the text layer, section 4 changes.
2. An HF token with `job.write` on `dreamproit`. Then `python -m benchmark.jobs submit --variant glm_ocr`
   on the 14-law subset to measure seconds per page and dollars per page on an L4, which fixes the wall time
   in section 5. The same run covers DeepSeek-OCR through Ollama.
3. GLM-OCR on the remaining 25 sample granules (resolutions, proclamations, treaties, and the 4- to 12-page
   laws) and on volumes 1 to 9, which no profile has seen.
4. Nanonets-OCR2 was not run (7.5 GB download stalled); `--repo-id mlx-community/Nanonets-OCR2-3B-4bit` is
   wired for a rerun.
5. The tier A rows for the VLM profiles were computed on wrapper PDFs with 1912 x 2476 pt pages (fixed in
   `benchmark/rasterize.py` after the runs); the text is unaffected, the per-page time for those rows is
   about three times too high.
6. `pipeline/uslm.py`: with markdown VLM output, running heads reach the body layer and the document
   boundary rule moved later pages of STATUTE-72-Pg1751 and STATUTE-72-PgA13 into trailing matter for
   LightOnOCR. Filtering page-top lines that match the running-head patterns before boundary detection
   recovers them.
