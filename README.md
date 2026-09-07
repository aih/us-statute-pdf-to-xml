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
| [docs/plans/2026-09-07-statutes-api-design.md](docs/plans/2026-09-07-statutes-api-design.md) | API for statutes.linkedlegislation.org: identifiers, enacted and compiled views, currency notes, storage |
| [docs/prompts/](docs/prompts/) | kickoff prompts for each plan |

## License

MIT. The statutes are works of the United States Government (17 U.S.C. 105).
