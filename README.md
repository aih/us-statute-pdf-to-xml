# US Statutes at Large: PDF to USLM XML

Downloads the United States Statutes at Large from GovInfo, publishes the volumes as a HuggingFace
dataset, converts law PDFs to USLM XML with [Docling](https://github.com/docling-project/docling),
and benchmarks the conversion against the XML that the Government Publishing Office publishes.

Module layout and data flow: [docs/architecture.md](docs/architecture.md). Dataset:
[dreamproit/us-statutes-at-large](https://huggingface.co/datasets/dreamproit/us-statutes-at-large).

## Setup

Requirements: Docker with Compose v2.24 or later.

1. Copy `.env.example` to `.env` and fill in every value. `docker-compose.yml` loads `.env` with
   `env_file`; no secret appears in compose or in source.

   | Variable | Used by |
   |---|---|
   | `GOVINFO_API_KEY` | every downloader script. Request one at https://api.govinfo.gov/docs/ |
   | `HF_TOKEN` | uploads to the HuggingFace dataset. Fine-grained token with `repo.write` on `HF_REPO_ID` |
   | `HF_REPO_ID` | dataset repository, `dreamproit/us-statutes-at-large` |
   | `ANTHROPIC_API_KEY` | benchmark judge |
   | `JUDGE_MODEL` | optional; defaults to `claude-opus-5` |
   | `ANTHROPIC_WORKSPACE_ID` | required when the Anthropic key is not scoped to a workspace |

   Scripts exit with status 2 and name the variable when a required one is missing.

   **Key rotation.** A GovInfo API key was committed to this repository in earlier revisions
   (`docker-compose.yml` and the downloader scripts) and pushed to GitHub. That key is compromised.
   Revoke it and request a new one before running the downloader.

2. Build and start the containers. The image pre-fetches the Docling layout and table models; a
   named volume keeps them across container restarts.

   ```bash
   docker compose up -d --build
   ```

3. Run the tests.

   ```bash
   docker compose exec app pytest
   ```

   Tests marked `integration` use the compose Postgres and local data files; the rest run offline.

All commands below run inside the `app` container: `docker compose exec app <command>`.

## Database

Postgres 15. Migrations live in `db/migrations/NNN_name.sql` and are applied in order by
`downloader/db.py init_db`, which every CLI calls at startup. Applied versions are recorded in
`schema_migrations`.

| Table | Rows |
|---|---|
| `packages` | one per GovInfo package (STATUTE volume or PLAW law): sizes, sha256, download and upload status, Hub commit |
| `granules` | one per STATUTE granule (law, resolution, proclamation, treaty): class, page range, MODS metadata |
| `statutes` | one per public law from the PLAW collection: PL number, volume, Stat. pages |
| `conversions` | one per conversion unit: profile, pages, seconds, XSD validity, input sha256 |
| `benchmarks` | one per benchmarked granule and run: CER, WER, structure metrics, judge result |

## Downloader

### Volumes (STATUTE collection, 1 to 137)

```bash
python -m downloader.fetch_historical --volumes 1-137 --parts 4 --files 2
python -m downloader.fetch_historical --volumes 118-119 --no-upload      # download only
python -m downloader.fetch_historical reconcile [--fix]                  # compare local, Hub, GovInfo
```

For each volume the script reads the GovInfo summary and the `Content-Length` of the PDF and USLM
XML, lists the Hub tree once, and decides `skip` (on the Hub with matching sizes), `upload-only`
(complete local files) or `download`. Downloads use `--parts` parallel range requests per file,
written to `.part.N` files that resume after an interruption; the assembled file is checked against
`Content-Length`, hashed, and renamed into place. `--files` volumes download at a time; a queue of
`--queue-size` volumes feeds one uploader thread that commits PDF and XML together, verifies both on
the Hub (`get_paths_info`: size and LFS sha256), then deletes the local copies unless `--keep-local`.
`metadata.jsonl` is regenerated from the `packages` table every `--metadata-every` uploads and at
the end. Logs go to stdout and `data/logs/fetch_historical-<date>.log`.

`reconcile` prints local-only, hub-only, size-mismatch and missing files for the requested volumes.
`--fix` uploads local-only volumes and re-downloads mismatches.

### Public laws (PLAW collection)

```bash
python -m downloader.fetch_plaw --since 2023-01-01 --limit 20 [--congress 118] [--congress-gov]
python -m downloader.fetch_plaw --package PLAW-118publ5
```

Downloads the per-law PDF and USLM into `data/pdfs/` and `data/xmls/` and writes `statutes` rows.
`--since` is GovInfo's lastModified filter and is also applied to `dateIssued` (disable with
`--any-date`). Volume and Stat. pages come from the USLM (`citableAs`, `page` markers).
`--congress-gov` also fetches the congress.gov copy of the USLM and reports whether it is
byte-identical to GovInfo's; for every law checked so far it was.

### Granules

```bash
python -m downloader.fetch_granules --spec benchmark/sample.yaml
```

Downloads the granule PDF and MODS record for each granule in a sample spec into
`data/granules/STATUTE-{n}/` and writes `granules` rows with the page range from MODS. Rerunning
skips PDFs whose size matches GovInfo.

## Pipeline

```bash
python -m pipeline.convert --spec benchmark/sample.yaml [--workers 4]
python -m pipeline.convert --plaw PLAW-118publ5
python -m pipeline.convert --pdf some.pdf --profile scanned --volume 64 --start-page 371 --page-range 1-20
python -m pipeline.split_uslm data/historical/xmls/STATUTE-64.xml
```

`convert` runs Docling in a process pool (default `min(2, cpu_count // 2)` workers, one converter per
worker; four OCR workers exceeded the 8 GB container, so raise `--workers` only with more memory). Volumes 1 to 116 use the `scanned` profile (Tesseract OCR, English, 2x render); later
volumes and PLAW files use `digital` (text layer, no OCR). Output is `data/doclang/{id}.json` and
`data/generated_xmls/{id}.xml`; the XML is validated against `uslm-2.0.17.xsd`
(`pipeline/schemas/`) and a `conversions` row records profile, pages, seconds, and validity. A unit
is skipped when its outputs exist and the input sha256 is unchanged.

The USLM builder emits the GovInfo namespace with the identifier scheme of GPO's PLAW files:
`section identifier="/us/pl/{congress}/{law}/s{n}"`, `subsection .../s{n}/{a}`, `paragraph
.../s{n}/{a}/{1}`, page markers `page identifier="/us/stat/{volume}/{page}"`, plus `meta`,
`preface`, `longTitle`, `enactingFormula`, `sidenote`, `action`, and `legislativeHistory`.

`split_uslm` cuts a volume USLM into one document per GovInfo granule (`data/granules/STATUTE-{n}/uslm/`),
which is the ground truth for each benchmarked granule. On volume 64 it produces 1,393 documents for
1,393 granules with 1,385 ids identical to GovInfo's.

## Benchmark

```bash
python -m benchmark.sample --per-cell 3 --volumes-per-era 2 --max-pages 12      # writes benchmark/sample.yaml
python -m benchmark.evaluate --spec benchmark/sample.yaml --no-judge
python -m benchmark.evaluate --spec benchmark/sample.yaml --judge --judge-limit 2
```

`sample` picks volumes per era at random (seeded), fetches their granule listings, and samples
`--per-cell` granules per era and document class, skipping granules longer than `--max-pages`.

`evaluate` fetches missing granules, downloads and splits the volume USLM, converts, and computes
for every granule: character error rate and word error rate on normalized body text, structure
counts (sections, subsections, paragraphs, headings, notes, tables, pages), identifier precision
and recall against GovInfo's `/us/pl/...` and `/us/stat/...` identifiers, and a token-level
alignment of the largest differences. Results go to `benchmarks` and to `data/reports/<date>-<run>.md`
with a per-era table.

`--judge` sends each granule's PDF (as a document block), the generated XML, and the alignment
differences to Claude (`claude-opus-5`, adaptive thinking, streaming, structured output, server-side
refusal fallbacks) and stores `text_score`, `structure_score`, `tagging_score`, and a list of located
issues, with token usage and cost.

### Eras

| Era | Volumes | Years | Source PDF | Ground truth |
|---|---|---|---|---|
| scanned-pre-1951 | 1 to 64 | 1789 to 1951 | scanned images | GPO USLM produced from OCR and editorial markup; sections carry no identifiers |
| scanned-1951-2002 | 65 to 116 | 1951 to 2002 | scanned images | GPO USLM, as above |
| digital-2003+ | 117 to 137 | 2003 to 2023 | born digital | GPO USLM from the typesetting source; PLAW files (2013 on) carry section identifiers |

GovInfo publishes USLM for all 137 volumes. For laws from the 113th Congress on, the per-law
USLM in the PLAW collection is the reference with full identifiers; the copy served by congress.gov
is the same file.

## Benchmark results and the chosen pipeline

Measured on 2026-09-08 and 2026-09-09. The decision and every number below are in
[docs/plans/2026-09-08-ocr-decision.md](docs/plans/2026-09-08-ocr-decision.md); the reports it cites are
under `data/reports/` and are listed at the end of this section.

Chosen pipeline: `hybrid:vlm:glm_ocr`. The GPO USLM for the granule supplies the document structure,
sidenotes, and page markers; the body text comes from GLM-OCR (Zhipu, 0.9B parameters) run through
Docling's VLM pipeline on page images; `pipeline/hybrid.py` aligns the two and adds the identifiers of
the PLAW scheme. Fallback: `hybrid:textlayer`, the same assembly over the PDF's own text layer, with
Tesseract per page where the text layer is empty.

```bash
python -m pipeline.vlm run --spec benchmark/sample.yaml --variant glm_ocr          # Mac (MLX) or GPU
python -m pipeline.convert --spec benchmark/sample.yaml --profile hybrid:vlm:glm_ocr   # container
```

### How the pipelines were scored

**Character error rate (CER)** is the Levenshtein edit distance between a pipeline's text and the
reference text, divided by the length of the reference (`benchmark/metrics.py`). Both texts are
normalized first: Unicode NFKC, quotation marks and dashes unified, words hyphenated at a line end
joined, whitespace collapsed. A CER of 0.003 means three characters inserted, deleted, or substituted
per thousand characters of reference. A gold page holds about 3,200 characters, so 0.003 is roughly ten
wrong characters on the page. A CER above 1 is possible: it means the pipeline produced far more text
than the reference span (a page that was not clipped, or a repetition loop). **Word error rate (WER)** is
the same distance over words and punctuation tokens. **Section recall** is the share of the reference's
sections found in the output with the same number and the same first 40 characters. Reports give the
mean and the median over pages or granules; the median is the figure to compare, because a single page
with a missing region has a CER of 0.3 to 1.0 and moves the mean by itself.

Three references:

- **Gold set** (`benchmark/gold/`, 150 pages, 30 per period from 1789 to 2002, sampled from public
  laws with a fixed seed). Each page image was transcribed twice by `claude-opus-5` under two different
  prompts; where the two transcriptions differ, a third call sees both and the image and returns the
  printed lines for each differing run. CER is measured on the text column (body and footnote lines);
  marginal notes are scored separately as sidenote CER. The 20 pages in `data/gold/review.md` are for a
  human spot check. Report: `data/reports/2026-09-08-wp10-gold.md`, with the CER of every page.
- **Tier B**: the granule's text against the GPO USLM slice for the same granule, on a 39-granule
  sample (`benchmark/sample.yaml`: volumes 10, 39, 72, 85, 124, 132; laws, resolutions, proclamations,
  treaties). The generated text is clipped to the span of the reference before scoring, because a
  granule PDF holds whole pages and the neighbouring laws on them. The GPO text is itself the
  digitization vendor's OCR for volumes 1 to 116: scored against the gold set it has a median CER of
  0.011, so tier B cannot separate pipelines below that level and rewards agreement with the vendor's
  errors. Tier B also measures section recall, identifier precision and recall, and XSD validity.
- **Tier A**: the same on page rasters of the five born-digital granules, where the USLM is exact.

A **judge pass** sends the granule PDF, the generated USLM, and the largest text differences to
`claude-opus-5`, which returns text, structure, and tagging scores from 0 to 100 and a list of located
issues (`benchmark/judge.py`). It is the only measurement of structure quality beyond section counts.

### Results

| Text source | Gold CER, median (mean) | Tier B CER, laws 1855 to 1950 | Tier B CER, laws 1951 to 2002 | Sidenotes | Cost per page | Seconds per page |
|---|---|---|---|---|---|---|
| GLM-OCR (`vlm:glm_ocr`) | 0.003 (0.025) | 0.002 | 0.006 | none emitted | $0 on the Mac, $0.0019 on an L4 | 11.7 on an M1 Pro (MLX), 8.5 on an L4 |
| `claude-opus-5` (`claude:claude-opus-5`) | not run | 0.003 | 0.006 | emitted | $0.038 (Batch API) | API |
| `claude-sonnet-5` | not run | 0.003 | 0.006 | emitted | $0.031 streaming | API |
| `claude-haiku-4-5` | not run | 0.016 | 0.007 | emitted | $0.0064 (Batch API) | API |
| PDF text layer (`textlayer`) | 0.022 (0.064) | 0.012 | 0.075 | 0.240 CER | $0 | 1.5 in the container |
| LightOnOCR-2-1B (`vlm:lightonocr`) | not run | 0.015 | 0.053 | none emitted | $0 | 11 to 18, MLX |
| Tesseract (`scanned`) | 0.143 (0.235) | 0.085 | 0.189 | 0.674 CER | $0 | 4.4 in the container |
| RapidOCR | not run | 0.101 | 0.102 | | $0 | 5.7 |
| GraniteDocling-258M | not run | 0.787 | 0.257 | | $0 | 4 to 23, repetition loops |
| EasyOCR | not run | 0.819 | 0.810 | | $0 | 61, over 5 GB per page |
| GPO USLM text (the tier B reference) | 0.011 (0.143) | | | 0.050 CER | | |

The tier B columns are means over the 14 laws every pipeline ran on; the gold column covers 150 pages.
GLM-OCR is first on the gold set in every period, including 1789 to 1850 (0.009 against 0.040 for the
text layer), and ties the Claude models on tier B. The Claude models project to $8,700 to $20,800 for the
276,763 scanned pages and are excluded by the plan's $5,000 limit; Haiku fits the limit and trails GLM-OCR
by an order of magnitude on tier B. GLM-OCR takes 11.7 seconds per page on the Mac (37 days for the scanned
volumes) and 8.5 on an HF Jobs L4 through Docling's transformers engine ($0.0019 per page, 27 days on one
card); two L4s and the Mac together take about 10 days.

### What the accuracy of the chosen pipeline is

Per page, on the gold set (character errors per page for GLM-OCR: median 8, mean 89, 90th percentile
240, worst page 2,552):

| Text source | Pages at or under 0.5% CER | At or under 1% | At or under 5% | Between 10% and 50% | Over 50% |
|---|---|---|---|---|---|
| GLM-OCR | 88 of 150 | 116 | 132 | 8 | 2 |
| PDF text layer | 23 | 38 | 102 | 26 | 2 |
| Tesseract | 0 | 0 | 41 | 67 | 21 |
| GPO USLM text | 42 of 148 | 70 | 106 | 18 | 16 |

The GPO row's 16 pages over 50% are pages where the volume USLM has no page marker and the reference
text runs into the next page; they say nothing about the vendor's OCR.

Per granule, on the 17 public and private laws of the sample: GLM-OCR has a mean WER of 0.020 (one word
in 50), the same as `claude-opus-5` (0.023); the text layer 0.289. The assembled output
(`hybrid:vlm:glm_ocr`) keeps the text source's error rate (WER 0.022) and recovers 0.86 to 1.00 of the
reference sections against 0.00 to 0.48 for any raw OCR output. The judge scored 20 granules of the
assembled output: text 75.1, structure 64.7, tagging 62.6 out of 100; on the 13 laws alone 83.5 / 71.5 /
68.4, on the seven resolutions, proclamations, and treaties lower (STATUTE-39-Pg1738: 18 / 15 / 22).

### Failure modes and how to fix them

1. **Dropped regions.** GLM-OCR leaves out part of a page on 10 of the 150 gold pages (CER over 0.1),
   two of them most of the page (STATUTE-1-Pg96 p1 and STATUTE-17-Pg466 p1 score 0.55 and 0.66 where
   the text layer scores 0.089 and 0.010), and on 5 of the 21 non-law sample granules (STATUTE-72-PgB14,
   -PgB23-3, STATUTE-10-Pg954, -Pg1177-2, STATUTE-39-Pg1738). The model stops early or skips a block; the
   page STATUTE-1-Pg448-2 p1 starts mid-page with 3,082 characters where the gold has 3,533. Fix: a
   per-page guard in `pipeline/hybrid.py` that compares the VLM page text with the text layer (length
   ratio and alignment) and takes the text layer, or a second VLM pass at another resolution, for pages
   that disagree. Not built. Where: `2026-09-08-wp10-gold.md` per-page table; decision document section 2
   notes and section 8 item 8.
2. **Invented text and repetition loops.** On STATUTE-39-Pg1738 page 1739, a map printed over the text,
   GLM-OCR produced paragraphs that are not on the page; on the treaty STATUTE-10-Pg954 one phrase repeats
   about 150 times; on STATUTE-39-Pg1645 Spanish column text is spliced into the English articles. CER
   catches the loop and the splice, not the invention. Fix: a repetition cap on the generated tokens and
   the same agreement check against the text layer. Not built. Where: `2026-09-08-wp11-judge.md` judge
   summaries; decision document section 7 finding 6 and section 8 item 7.
3. **Marginal notes.** GLM-OCR emits almost none (sidenote CER 1.000 on the gold set). The assembled
   output takes them from the GPO USLM, whose sidenotes score 0.050 against the gold (0.171 for 1789 to
   1850). Fix options: the Claude profile's sidenote lines, or a second model on the margin crop. Not
   measured. Where: `2026-09-08-wp10-gold.md` sidenote columns; decision document section 8 item 4.
4. **Structure and tagging** (from the judge): the text of neighbouring laws on the shared first and
   last pages is kept in `preface` and `appendix[@role='trailingMatter']`; the unnumbered first section
   carries no identifier; spaces are lost where the hybrid replaces a run ("Congressassembled"); the
   first page's marker is missing when it sits in the previous document. These are rule changes in
   `pipeline/hybrid.py` and `pipeline/uslm.py`. Where: decision document section 7 findings 1 to 5.
5. **Engine differences.** The same model through Docling's transformers engine on an L4 scores
   slightly worse than through MLX on the Mac (tier B 0.003 / 0.013 / 0.032 against 0.002 / 0.006 /
   0.029 on the same 14 laws). Where: `2026-09-09-wp9b-vlm-gpu.md` against `2026-09-08-wp9b-vlm-rebuild.md`.

### Reports

| Report | Content |
|---|---|
| `data/reports/2026-09-08-wp8-baseline.md` | the baseline after the benchmark repair (F1 to F4 of the plan) |
| `data/reports/2026-09-08-wp9-comparison.md` | every profile on the 39-granule sample, by era and by granule |
| `data/reports/2026-09-08-wp9a-cpu.md`, `-wp9b-vlm.md`, `-wp9c-claude-hybrid.md` | per-family runs with timing, memory, and what did not run |
| `data/reports/2026-09-08-wp9b-vlm-rebuild.md` | the VLM profiles after the running-head fix |
| `data/reports/2026-09-08-wp9b-glm-all.md` | GLM-OCR and its hybrid on all 39 granules, including the resolutions and treaties |
| `data/reports/2026-09-08-wp9c-claude.md` | Claude Haiku, Sonnet, Opus, and the Opus hybrid |
| `data/reports/2026-09-08-wp10-gold.md` | the gold set: build cost, CER per period, and every page |
| `data/reports/2026-09-08-wp11-judge.md` | the judge pass: scores per granule and the located issues |
| `data/reports/2026-09-09-wp9b-vlm-gpu.md` | GLM-OCR on the HF Jobs L4 |

## Data directories

```
data/historical/{pdfs,xmls}/   volumes in transit to the Hub (deleted after a verified upload)
data/pdfs/, data/xmls/         PLAW per-law files
data/granules/STATUTE-{n}/     granule PDFs, MODS, granules.json listing, uslm/ ground-truth slices
data/doclang/, data/generated_xmls/   conversion output
data/reports/                  benchmark reports
data/logs/                     one log per script per day
```

## Plans

| Document | Content |
|---|---|
| [docs/plans/2026-09-05-downloader-and-pipeline-plan.md](docs/plans/2026-09-05-downloader-and-pipeline-plan.md) | downloader rewrite, pipeline, benchmark (WP1 to WP7, implemented) |
| [docs/plans/2026-09-07-ocr-pipeline-evaluation-plan.md](docs/plans/2026-09-07-ocr-pipeline-evaluation-plan.md) | benchmark defects found on 2026-09-07, two-tier ground truth, OCR candidates, reprocessing run (WP8 to WP12) |
| [docs/plans/2026-09-08-ocr-decision.md](docs/plans/2026-09-08-ocr-decision.md) | results matrix, gold-set CER, exclusions, the chosen profile, projection for volumes 1 to 116, judge pass, open items (WP11) |
| [docs/plans/2026-09-07-statutes-api-design.md](docs/plans/2026-09-07-statutes-api-design.md) | API for statutes.linkedlegislation.org: identifiers, enacted and compiled views, currency notes, storage |
| [docs/prompts/](docs/prompts/) | kickoff prompts for each plan |

## License

MIT. The statutes are works of the United States Government (17 U.S.C. 105).
