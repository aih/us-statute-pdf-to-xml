# OCR pipeline evaluation and reprocessing plan

Date: 2026-09-07. Branch at time of writing: `downloader-rewrite` (WP1 to WP7 of the
[2026-09-05 plan](2026-09-05-downloader-and-pipeline-plan.md) implemented, unmerged).

Goal: choose the conversion pipeline for the scanned volumes (1 to 116), using the born-digital
volumes (117 to 137) as exact ground truth, then reprocess the scanned volumes into USLM with
section identifiers and page markers, and publish the result on the Hub.

## 1. State on 2026-09-07

### Dataset

| Item | Value |
|---|---|
| On the Hub (`dreamproit/us-statutes-at-large`) | volumes 1 to 38 and 93 to 137, PDF and USLM each (83 pairs) |
| Local, complete, queued for upload | volumes 39 to 92 in `data/historical/` (22 GB) |
| Uploader | `fetch_historical` running in `statute-pdf-to-xml-app-1`, one volume every 7 to 10 minutes; about 6.5 hours left at 20:11 UTC |
| Host disk free | 25 GB |

The backfill is complete once the uploader reaches volume 92. `reconcile` must report no
differences before anything below uses the Hub as its source.

### Benchmark baseline (run `wp6-metrics`, 44 granules)

The [WP6 report](../../data/reports/2026-09-05-wp6-metrics.md) shows mean CER 0.99 to 1.04 on the
scanned eras and 0.67 on the digital era. Inspection of individual granules shows that these
numbers measure four defects in the pipeline and the benchmark, not OCR quality:

| # | Defect | Evidence |
|---|---|---|
| F1 | Docling's Tesseract CLI model runs orientation detection (`tesseract --psm 0`) on every page and rotates the image by the result before OCR. On these scans the detection is wrong (`STATUTE-72-Pg1751` page 1: "Orientation 270, confidence 0.61" on an upright page), so the OCR output is rotated gibberish. | Docling text for that page: `O16-SB "eT ONG`, `LOV NY` (mirrored "PUBLIC LAW 85-910", "AN ACT"). `STATUTE-10-Pg764` is the same. `STATUTE-72-Pg1572` was detected correctly and scored CER 0.37. |
| F2 | `pipeline/uslm.py` `_ingest` skips every body item on a STATUTE granule until it matches a "CHAPTER", "Public Law", or "AN ACT" line. When OCR mangles those lines, the whole body is dropped. | `STATUTE-39-Pg1058`: Docling produced 45,746 characters of text; the generated USLM body has 172. `STATUTE-72-Pg1751`: 9,085 in, 124 out. |
| F3 | A granule PDF contains whole pages, and the first and last pages carry text of the neighbouring laws. The reference slice contains only the granule's own text. | Every granule whose page is shared. |
| F4 | For volumes 117 onward GovInfo groups all concurrent resolutions of a session into one or two granules and proclamations differently from the XML, so the splitter produces no one-to-one reference for `HCONRES`, `SCONRES`, and `PROCLAMATION` granules. | `STATUTE-132-Pg5600` reference 353 characters, generated 13, because the reference is a different document. The digital-era public and private laws score CER 0.02 to 0.06. |

Two further facts change the candidate list:

- **The scanned granule PDFs carry a text layer.** `STATUTE-72-Pg1751` page 1 has 3,416
  characters of embedded text from GovInfo's digitization vendor. Its quality is below the GPO
  USLM (`maintam`, `Ame7'ica`, `contaming` where the USLM reads `maintain`, `America`,
  `containing`) but it is free and upright.
- **The GPO USLM for the scanned era has structure but noisy text.** Sections, sidenotes, page
  markers, `citableAs`, and `approvedDate` are present; `processedBy` is "Digitization Vendor",
  `processedDate` 2025-12-22. Text errors remain (`Howe of Representatives`, `lie is hereby`).
  Sections carry no `identifier`.

### Compute

| Host | CPU | Memory | GPU |
|---|---|---|---|
| Container `app` | 10 | 8 GB | none |
| Mac (M1 Pro) | 10 | 16 GB | Apple silicon; Docling ships MLX variants of GraniteDocling, GLM-OCR, LightOnOCR, Nanonets-OCR2 |
| HuggingFace Jobs (`hf jobs run`, `hf jobs hardware`) | rented | | GPU per job; billed to the `dreamproit` org |

Docling 2.126.0 in the container exposes OCR engines `TesseractCliOcrOptions` (with `psm`),
`TesseractOcrOptions`, `RapidOcrOptions`, `EasyOcrOptions`, `NemotronOcrOptions`, and the VLM
pipeline (`VlmPipelineOptions`) with the model specs listed above plus DeepSeek-OCR, Dolphin,
GOT2, and Granite Vision.

## 2. Ground truth: two tiers

### Tier A: exact truth from born-digital volumes

Volumes 117 to 137 have an exact USLM, and PLAW files from the 113th Congress carry section
identifiers. Rasterize their PDF pages to images (300 dpi PNG; a second variant with JPEG
quality 60, 0.5 degree skew, and Gaussian noise to approximate a scan) and run every candidate on
the images only, never on the PDF text layer. The comparison is against the GPO USLM, so text,
structure, and identifier scores are exact.

Limit: modern typography and layout. A candidate that scores well here can still fail on
eighteenth-century type. Tier B covers that.

### Tier B: scanned era

Reference is the GPO USLM slice from `split_uslm`, restricted to `PUBLICLAW` and `PRIVATELAW`
granules (F4). Its text is noisy, so a candidate can beat the reference; tier B alone cannot say
so. A gold set decides ties:

- 150 pages, stratified: 30 per period (1789 to 1850, 1851 to 1900, 1901 to 1950, 1951 to 1975,
  1976 to 2002), drawn from public laws only, each page a full page image.
- Transcribed twice with `claude-opus-5` (adaptive thinking, image input, structured output:
  lines with roles `running-head`, `sidenote`, `body`, `footnote`, `page-number`), from
  independent prompts; disagreements adjudicated by a third call that sees both transcriptions
  and the image; 20 pages spot-checked by a person. Stored in `benchmark/gold/{granule}/p{n}.json`
  with the image sha256.
- Every candidate, and the GPO USLM itself, is scored against the gold set on those pages.

## 3. Candidates

| Id | Pipeline | Runs on | Cost per page |
|---|---|---|---|
| C0 | GPO USLM as published (text and structure) | none | 0 |
| C1 | Embedded PDF text layer through Docling layout (`digital` profile on scanned PDFs, `force_backend_text`) | CPU | 0 |
| C2 | Docling + Tesseract CLI, orientation detection disabled, 300 dpi, `psm` 4 and 6 compared | CPU | 0 |
| C3 | Docling + RapidOCR; Docling + EasyOCR | CPU | 0 |
| C4 | Docling VLM pipeline: GraniteDocling, LightOnOCR, Nanonets-OCR2, GLM-OCR, DeepSeek-OCR | MLX on the Mac for the small models; HF Jobs GPU for the rest | GPU time |
| C5 | Claude page transcription to structured lines (same schema as the gold set) | API | see below |
| C6 | Hybrid: GPO USLM structure (C0) with body text replaced per section by the best of C1 to C5, aligned with `difflib` on the section boundaries; identifiers added by rule | wherever the text candidate runs | that candidate's cost |

C5 cost, assuming 2,000 input tokens per page image, 1,000 tokens of cached prompt, 1,200 output
tokens, and 200,000 scanned-era pages:

| Model | Per page | 200,000 pages | With the Batch API (50%) |
|---|---|---|---|
| `claude-opus-5` ($5 / $25 per MTok) | $0.040 | $8,000 | $4,000 |
| `claude-sonnet-5` ($2 / $10) | $0.016 | $3,200 | $1,600 |
| `claude-haiku-4-5` ($1 / $5) | $0.008 | $1,600 | $800 |

The benchmark runs C5 with all three models on the sample; the judge stays on `claude-opus-5`.

Docling adds value only through layout: sidenote and running-head separation, tables, and
reading order. C5 and C6 do not need it. The decision in section 6 records whether the DoclingDocument
JSON is published.

## 4. Metrics

Per granule and per candidate, in `benchmarks` and the report:

- CER and WER on normalized body text, after clipping (section 5, WP8).
- Section detection precision and recall: a generated section matches a reference section when
  their `num` values agree and the first 40 characters of content align.
- Identifier F1 (tier A, PLAW era only).
- Sidenote recall (tier A only; the reference marks them).
- XSD validity.
- Seconds per page and dollars per page.
- Gold-set CER, for the 150 pages, per candidate and for C0.

Decision rule: rank by gold-set CER, then tier A CER, then section recall; a candidate whose
projected cost for the full run exceeds $5,000 or whose throughput exceeds two weeks on the
available hosts is excluded before ranking.

## 5. Work packages

Each is one commit or one small PR on a branch off `downloader-rewrite`; the acceptance line is
checked by tests or the named command.

### WP8: Benchmark repair

- F1: Docling's `TesseractCliOcrModel` (`models/stages/ocr/tesseract_ocr_cli_model.py`) runs
  `_perform_osd` on every OCR rectangle whatever the language setting and rotates the image
  when the result is not 0; no option turns this off. `pipeline/tesseract.py` subclasses the
  model with `_perform_osd` returning orientation 0 and registers it through Docling's OCR
  factory (`allow_external_plugins` or a direct `ocr_options` subclass). `profiles.py` gets a
  `dpi` setting; the scanned profile renders at 300 dpi.
- F2: `pipeline/uslm.py` never discards a body item. Items before the recognized document start
  go into `preface` as `p` elements; items that match nothing go into the current level as
  `content`/`p`. Add a builder warning count per document and store it in `conversions`.
- F3: `benchmark/metrics.py` clips the generated text to the reference: anchor the first and
  last 30 tokens of the reference in the generated text with `rapidfuzz.fuzz.partial_ratio_alignment`
  (threshold 70) and score the span between them; record `clip_found` and score unclipped when an
  anchor is missing.
- F4: `benchmark/sample.py` restricts the digital era to `PUBLICLAW` and `PRIVATELAW`; the
  splitter reports the granules it cannot pair.
- Tier A rasterizer: `benchmark/rasterize.py` writes page images for a PLAW or STATUTE granule
  into `data/raster/{id}/p{n}.png` (clean and degraded variants) and a PDF wrapper Docling can
  read (`img2pdf`).
- Rerun the baseline. Acceptance: digital-era public laws stay at CER 0.02 to 0.06; scanned
  granules with a correct orientation report CER below 0.5; no generated USLM has fewer body
  characters than 80% of the Docling text it was built from.

### WP9: Candidate profiles and the comparison run

- `pipeline/profiles.py`: profiles `textlayer` (C1), `tesseract` (C2, both `psm` values),
  `rapidocr`, `easyocr` (C3), `vlm:<spec>` (C4), `claude:<model>` (C5). Each profile writes
  `data/doclang/{profile}/{id}.json` and `data/generated_xmls/{profile}/{id}.xml`;
  `conversions.module_used` carries the profile.
- `pipeline/claude_ocr.py` (C5): one request per page image with `claude-opus-5` by default and
  `--model` for the others, adaptive thinking, structured output with the line schema, `fallbacks`
  as in `benchmark/judge.py`, the Batch API when `--batch`. Output feeds the same builder as
  Docling through an adapter that produces `Page`/`Item` records with geometry from the
  model's line order.
- `pipeline/hybrid.py` (C6): takes the GPO slice and a text candidate's output, aligns section by
  section, replaces `content` text, keeps GPO's `sidenote`, `page`, `meta`, and `action`, adds
  identifiers (section 7).
- `benchmark/evaluate.py --profiles a,b,c` runs every profile on the spec and writes one report
  with a profile-by-era matrix. `--tier A` uses rasterized inputs.
- GPU profiles run on HF Jobs: `benchmark/jobs.py` submits `hf jobs run` with the project image,
  the sample granules pulled from the Hub, and results written back to a `benchmark-runs/` folder
  in the dataset repo.
- Acceptance: `evaluate --profiles textlayer,tesseract,rapidocr --tier A,B --no-judge` completes
  on the sample and the report has one row per profile and era; at least one VLM profile and one
  Claude profile have rows.

### WP10: Gold set

- `benchmark/gold.py build --pages 150`: samples pages, calls Claude twice and adjudicates,
  writes `benchmark/gold/`, prints the 20 pages for human review with their images.
- `benchmark/gold.py score --profile X`: CER of a profile's output and of the GPO slice against
  the gold pages.
- Acceptance: 150 gold pages committed; C0's gold-set CER reported per period.

### WP11: Decision and full-run plan

- `docs/plans/2026-09-XX-ocr-decision.md`: the matrix, the chosen profile, projected cost and wall
  time for volumes 1 to 116, the hosts to use, and the identifier rules of section 7.
- Judge pass (`--judge`) on 20 granules of the chosen profile for a structure and tagging score.

### WP12: Reprocessing run

- Unit of work: one law (granule). Inputs come from the Hub volume PDFs, cut by the MODS page
  range of each granule (`fetch_granules` already parses MODS; add a `cut` step with `pypdfium2`
  so no per-granule download is needed).
- Output on the Hub: `uslm/STATUTE-{n}/{granuleId}.xml`, `uslm/metadata.jsonl` (granule id, law
  identifier, pages, profile, pipeline version, sha256, CER against the GPO slice), and
  `doclang/` only if the decision keeps it.
- Resumable: the `conversions` table is the ledger; a nightly `reconcile` compares Hub and
  ledger.
- Order: volumes 65 to 116 first (post-1951 type, where the pipeline will do best), then 1 to 64.

## 6. Out of scope

- Reprocessing the born-digital volumes 117 to 137. Their GPO USLM is the text of record; WP9's
  identifier rule (section 7) is applied to that XML directly, without OCR.
- Treaties, proclamations, and concurrent resolutions in the reprocessing run. They are
  benchmarked only where a reference exists.

## 7. Identifier rules for generated USLM

The identifiers must match the forms the Office of the Law Revision Counsel writes in US Code
source credits, so that a US Code reference resolves to the generated document. Counted in
`usc16.xml` at release point 119-102not101: 23,000 `/us/pl/` refs, 18,571 `/us/stat/`, 4,026
`/us/act/`.

| Document | Identifier | Example |
|---|---|---|
| Public law, 57th Congress (1901) onward | `/us/pl/{congress}/{number}` | `/us/pl/85/910` |
| Private law | `/us/pvtl/{congress}/{number}` | `/us/pvtl/85/12` |
| Act before public-law numbering, cited by chapter | `/us/act/{YYYY-MM-DD}/ch{chapter}` | `/us/act/1916-08-25/ch408` |
| Section and below | GPO PLAW scheme: `/s{n}`, `/s{n}/{a}`, `/s{n}/{a}/{1}`, with division and title segments when the law has them (`/dA/tI/s101`) | `/us/pl/104/333/dI/tVIII/s814/e/1` |
| Page | `/us/stat/{volume}/{page}`; lettered pages lower case | `/us/stat/72/1751`, `/us/stat/64/b3` |

Laws from 1901 to 1957 have both a public-law number and a chapter number; both identifiers are
emitted, the chapter form on `meta/property[@role='alternateIdentifier']`, because OLRC cites
those years by chapter (`/us/act/1947-07-26/ch343`).
