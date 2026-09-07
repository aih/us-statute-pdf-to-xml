# Downloader, pipeline, and benchmark plan

Date: 2026-09-05. Branch at time of writing: `fix-fetch-idempotency`.

## 1. Status of the running downloader

Process: `python -m downloader.fetch_historical`, PID 7 inside `statute-pdf-to-xml-app-1`, started 2026-09-05 05:06 UTC, attached to an interactive `docker compose exec` terminal (`/dev/pts/0`).

Observed on 2026-09-05 15:45 UTC:

| Item | Value |
|---|---|
| Volumes completed | STATUTE-1 through STATUTE-100 (PDF + USLM XML) |
| In flight | STATUTE-101 |
| Local data | 37 GB in `data/historical/` |
| Host disk free | 29 GB of 926 GB (97% used) |
| Throughput | ~1 MB/s, one connection at a time |
| Elapsed | 10.6 h for 100 volumes |
| Uploaded to HuggingFace | Nothing. `dreamproit/us-statutes-at-large` does not exist on the Hub. |
| DB rows written by this run | None (the historical fetcher does not touch Postgres) |

The process is running in local-only mode. `docker-compose.yml` passes `POSTGRES_URL`, `ANTHROPIC_API_KEY`, and `GOVINFO_API_KEY` into the container and nothing else, so `HF_TOKEN` and `HF_REPO_ID` from `.env` never reach the process. `fetch_historical.py` checks `os.getenv("HF_TOKEN")`, finds nothing, sets `api = None`, and silently skips the upload and the local delete.

Remaining work for the current process: volumes 101 to 137. Volumes 101 to 116 are scanned image PDFs of 540 MB to 990 MB each (about 13.5 GB total). Volumes 117 to 137 are born-digital PDFs of 8 MB to 45 MB each. STATUTE-138 returns 404, so the loop ends after 137 plus five 404 probes. At the current 1 MB/s the remaining scanned volumes take about four hours.

### Determination

Do not kill the process for its own sake. Every completed file is reusable: the new downloader (section 6, WP2) skips files whose size matches the GovInfo `Content-Length`, and the files can be uploaded from the host now.

Two actions are required:

1. **Upload the completed volumes now, from the host, to free disk.** Move completed volumes out of the directory the downloader writes to, then upload the staging directory. `upload_large_folder` is resumable and creates the repo if it does not exist.

   ```bash
   cd /Users/arihershowitz/Documents/workspace/aih/statute-pdf-to-xml
   set -a; . ./.env; set +a
   mkdir -p data/hf_staging/pdfs data/hf_staging/xmls
   # Move every volume except the one currently being written (the newest .pdf).
   INFLIGHT=$(ls -t data/historical/pdfs/*.pdf | head -1)
   for f in data/historical/pdfs/*.pdf; do [ "$f" = "$INFLIGHT" ] || mv "$f" data/hf_staging/pdfs/; done
   mv data/historical/xmls/*.xml data/hf_staging/xmls/
   hf upload-large-folder "$HF_REPO_ID" data/hf_staging --repo-type dataset --num-workers 4
   ```

   After the upload finishes, compare the Hub tree against the staging directory (name and byte size) before deleting the staging files. WP3 automates this check.

2. **Stop the process when WP2 is ready to run.** Press Ctrl-C in its terminal, delete the newest `.pdf` in `data/historical/pdfs/` (a partial file passes the current "exists and non-empty" check and would be uploaded as-is), then start the new downloader. It resumes from the Hub listing and local files.

If the disk drops below 10 GB before WP2 is ready, stop the process and delete the in-flight PDF. macOS degrades below that point.

## 2. Facts established about the sources

GovInfo, verified 2026-09-05 with the project API key:

- The `STATUTE` collection holds volumes 1 to 137. Every volume has a package-level `pdfLink` and `uslmLink`. Package USLM XML files are 2 MB to 68 MB.
- Volumes 1 to 116 are scanned. PDF sizes: 45 MB to 1.1 GB, typically 150 MB to 950 MB. Volumes 117 to 137 are born-digital, 8 MB to 45 MB.
- Granules exist per law, resolution, proclamation, and treaty (STATUTE-64 has 1,393). Each granule has its own `pdfLink` (about 5 MB for a treaty in vol. 64) and `modsLink`. There is no granule-level USLM link; the volume USLM is the only XML.
- The `PLAW` collection from 2013 onward holds 2,551 packages, each with a per-law PDF and USLM XML.
- Download endpoints throttle at about 1 MB/s per connection. HTTP `Range` requests return 206. Four parallel range requests on one file ran at 2.7 MB/s aggregate while the container's single-connection download was also running.
- The API key's rate limit is 36,000 requests per hour (`x-ratelimit-limit` header).
- Package titles for granules exceed 500 characters. The `statutes.title` column is `VARCHAR(255)`.

HuggingFace:

- `HF_REPO_ID` in `.env` is `dreamproit/us-statutes-at-large`. The repo does not exist.
- The token is fine-grained with `repo.write` on the `dreamproit` org and on the `arihers` user. The user is an org admin. The org is on the free plan.
- The full dataset is about 52 GB of PDFs plus about 2 GB of XML. Public dataset repos have no storage quota; private repos on a free plan are capped at 100 GB.

Container: 10 CPUs, 8 GB RAM, no GPU. Docling 2.126.0, huggingface_hub 1.30.0, httpx 0.28.1.

## 3. Issues

### 3.1 Downloader (`downloader/fetch_historical.py`, `downloader/fetch.py`, `downloader/hf_package.py`)

| # | Issue | Effect | Fix |
|---|---|---|---|
| D1 | `HF_TOKEN`, `HF_REPO_ID` not passed through `docker-compose.yml` | No uploads, no local cleanup, disk fills | `env_file: .env` in compose; fail fast at startup when upload is requested and the token is missing |
| D2 | Serial single-connection download | 1 MB/s; 52 GB takes 14+ hours | Ranged parallel chunk download per file, two files in flight |
| D3 | Idempotency check is "exists and size > 0" | Truncated file after an interrupt is treated as complete and uploaded | Download to `<name>.part`, compare byte count to `Content-Length`, rename atomically; on restart compare existing file size to `Content-Length` |
| D4 | Two Hub commits per volume, `metadata.jsonl` re-uploaded every time | ~280 commits for the collection, slow, and the Hub applies per-repo commit rate limits | One commit per volume containing PDF + XML; regenerate `metadata.jsonl` from state and commit it every N volumes and at the end |
| D5 | Any non-404 HTTP error on the summary call (`429`, `5xx`, `400`) breaks out of the loop | Whole run stops on a transient error | Retry with exponential backoff on 429/5xx/timeouts; treat 400 as not-found for probing; log and continue |
| D6 | Upload failure is logged and the loop moves on; local file kept, no state record | Silent gaps in the dataset | Persist per-package state (downloaded, uploaded, sha256, bytes); reconcile against the Hub tree at startup |
| D7 | Local copy deleted immediately after `upload_file` returns, without verifying the Hub entry | Corrupt or missing Hub file cannot be recovered without re-download | Verify name and size in the Hub tree (`get_paths_info`) before deleting |
| D8 | GovInfo API key hard-coded in `docker-compose.yml` and as a default in both fetch scripts, committed to git and pushed to GitHub | Key is public | Remove from source; read from `.env` only; rotate the key at govinfo.gov |
| D9 | `fetch.py` outer loop increments `congress` forever once the inner loop hits three 404s | Never terminates when `limit` exceeds available laws; burns API quota | Stop at the current Congress; use the `collections/PLAW` listing instead of probing package IDs |
| D10 | `fetch.py` sets `volume`, `start_page`, `end_page` to `None` | Metadata the schema was designed for is never populated | Read `volume`/`pages` from the package summary; for granules read `pagePosition` |
| D11 | No file logging; output goes to the interactive terminal | No record of what happened after the terminal closes | Log to `data/logs/<script>-<date>.log` plus stdout |
| D12 | `hf_package.py` writes `metadata.jsonl` from local files only and uses `upload_folder` (single commit) | 50 GB in one commit fails; metadata drifts from what is on the Hub | Replace with the reconciler in WP3 |
| D13 | `datasets` is a declared dependency but unused; `pypdf` unused | Longer image build | Remove until needed |

### 3.2 Infrastructure

| # | Issue | Fix |
|---|---|---|
| I1 | `version: '3.8'` in compose (obsolete, warns on every command) | Remove |
| I2 | No `env_file`; secrets duplicated in compose | `env_file: .env` |
| I3 | Docling downloads its layout and OCR models on first use inside a container with no persistent cache | Pre-fetch in the Dockerfile (`docling-tools models download`) and mount a named volume at `/root/.cache/huggingface` |
| I4 | `COPY . .` in the Dockerfile copies `data/` (37 GB) into the build context | Add `.dockerignore` with `data/`, `.git/`, `.venv/` |
| I5 | `schema.sql` runs only on first DB init; schema changes are not applied to the existing volume | Add a migrations directory applied by `downloader/db.py init_db` on startup (idempotent `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) |
| I6 | `statutes.title VARCHAR(255)` | `TEXT` |
| I7 | No tests, no CI | `pytest` with unit tests for chunked download, state reconciliation, USLM splitter, and metrics; GitHub Actions running them |

### 3.3 Pipeline (`pipeline/convert.py`, `pipeline/transform.py`)

| # | Issue | Effect | Fix |
|---|---|---|---|
| P1 | New `DocumentConverter()` per PDF | Layout and OCR models reload for every file (tens of seconds each) | One converter per worker process, created once |
| P2 | Converts whole files with no `page_range` and no memory bound | A 3,000-page 900 MB scanned volume exhausts the 8 GB container | Unit of work is a granule PDF (single law) or a page range; `page_range` on `convert()`; cap workers by RAM |
| P3 | Default pipeline options; OCR always on with the default engine | Slow on born-digital PDFs; wrong engine choice for scanned volumes | Two profiles: `scanned` (OCR on, Tesseract CLI, image scale tuned) and `digital` (OCR off, text layer used). Select by volume number (<=116 scanned) |
| P4 | Output written as indented JSON of the full `DoclingDocument` | Large files, slow writes | Compact JSON; keep page images out of the export |
| P5 | `transform.py` emits `<law xmlns="http://xml.house.gov/schemas/uslm/1.0"><main><p>...` | Wrong namespace (GovInfo uses `http://schemas.gpo.gov/xml/uslm`), wrong root (`statutesAtLarge` for volumes, per-law roots for PLAW), no sections, headings, notes, or page breaks. The judge compares a flat paragraph list to a structured document | Rebuild with `lxml`: map Docling labels (`section_header`, `text`, `list_item`, `table`, `page_header`, `page_footer`, marginal notes) to USLM `<section>`, `<heading>`, `<content>`, `<p>`, `<note>`, `<page>`; validate against the USLM 2.0.17 XSD referenced by GovInfo's files |
| P6 | Sequential processing | One core of ten in use | `ProcessPoolExecutor`, one converter per worker |
| P7 | No skip-if-exists, no record in `conversions` | Reruns redo everything; failures invisible | Skip when output exists and input hash unchanged; write a `conversions` row per unit with status and error |

### 3.4 Benchmark (`benchmark/evaluate.py`, `benchmark/judge.py`)

| # | Issue | Effect | Fix |
|---|---|---|---|
| B1 | Model `claude-3-opus-20240229` | Retired model; every call fails and returns score 0 | `claude-opus-5` (configurable via `JUDGE_MODEL`), adaptive thinking, streaming, `fallbacks: "default"` |
| B2 | Both full XML documents pasted into one prompt, `max_tokens=1000`, non-streaming | A single PLAW pair is ~140k tokens; a volume pair is millions and cannot be sent | Judge at granule level on a sample; send aligned segments, not whole documents |
| B3 | Score parsed by scanning for `SCORE:` in free text | Fragile; a missing line scores 0 | Structured output (`output_config.format`) with a schema: `text_score`, `structure_score`, `tagging_score`, `issues[]` |
| B4 | Called a "VLM judge" but never sees the PDF | Cannot detect OCR errors the ground truth XML shares or omits | Deterministic text metrics first (below); the LLM judge receives the PDF page(s) as a document block plus the generated XML segment for a sampled subset |
| B5 | No deterministic metrics | Scores are not reproducible and cost money to recompute | Character error rate and word error rate on normalized text extracted from both XMLs (`rapidfuzz`); structural counts (sections, headings, notes, tables); alignment via difflib opcodes |
| B6 | Results not stored (`TODO`), errors swallowed | No history, no per-era breakdown | Write `benchmarks` rows; report by era (scanned pre-1951, scanned 1951-2002, digital 2003+) |
| B7 | README states ground truth exists only for post-2012 laws | GovInfo publishes USLM for all 137 volumes | Use volume USLM as ground truth for every era; document the provenance of the pre-1951 XML in the README |

## 4. Decision: Python with concurrency, not Go

Determination: keep Python. Add concurrency with threads for network work and processes for Docling.

The workload is bound by GovInfo's per-connection throttle (about 1 MB/s) and by HuggingFace upload bandwidth. Python threads over `httpx` reach the same aggregate ceiling as a Go program: the measured limit scales with connection count, not with client CPU. A 4-chunk-per-file, 2-files-in-flight configuration is 8 connections, which the sample above puts at roughly 5 MB/s, a 3x to 5x reduction in wall-clock time.

`huggingface_hub` supplies chunked LFS upload, resumable large-folder upload, commit batching, and Hub tree queries. HuggingFace maintains no Go client with those features.

Docling, the Anthropic SDK, and `datasets` are Python. A Go downloader would be a second toolchain, a second Docker image, and a second set of tests for a component that spends its time waiting on sockets.

Concurrency model:

- Downloader: `ThreadPoolExecutor` for ranged chunks within a file; a second small pool for files; a bounded queue (max 3 volumes on disk awaiting upload) between the download stage and the upload stage; one uploader thread issuing one `create_commit` per volume.
- Pipeline: `ProcessPoolExecutor` with `workers = min(4, cpu_count // 2)` on the 8 GB container; one `DocumentConverter` per process, created in the initializer.
- Benchmark: `ThreadPoolExecutor` for judge calls, bounded to 4 in flight.

## 5. Target architecture

```
downloader/
  govinfo.py        httpx client: retries, rate-limit headers, summary/collection/granule iterators,
                    ranged parallel download to .part with size verification
  state.py          Postgres tables `packages` and `granules`; reconcile with Hub tree
  hf_upload.py      one commit per package (pdf + xml); verify; delete local; metadata.jsonl
  fetch_historical.py  CLI: --volumes 1-137 --parts 4 --files 2 --no-upload --keep-local
  fetch_plaw.py     CLI over collections/PLAW: per-law pdf + uslm, writes `statutes`
  fetch_granules.py CLI: granule PDFs for a sample spec (benchmark input)
pipeline/
  profiles.py       scanned / digital Docling pipeline options
  convert.py        pool of converters; unit = granule pdf or page range; writes conversions rows
  uslm.py           DoclingDocument -> USLM (lxml), XSD validation
  split_uslm.py     volume USLM -> per-granule USLM using page markers and granule pagePosition
benchmark/
  sample.py         stratified sample spec (era x document class) -> granule list
  metrics.py        CER/WER/structure counts on normalized text
  judge.py          Claude judge with structured output, PDF pages as document blocks
  evaluate.py       orchestrates convert -> transform -> metrics -> judge; writes benchmarks; report
db/
  migrations/       001_initial.sql (existing), 002_packages_granules.sql, 003_title_text.sql
tests/
```

Dataset layout on the Hub (`dreamproit/us-statutes-at-large`, public):

```
README.md              dataset card: source, license (public domain, 17 USC 105), volumes, eras, fields
metadata.jsonl         one row per volume: file_name, volume, congress, session, date_issued, pages,
                       scanned, pdf_bytes, pdf_sha256, xml_file, xml_bytes, xml_sha256, source_package_url
pdfs/STATUTE-{n}.pdf
xmls/STATUTE-{n}.xml
granules/STATUTE-{n}/{granuleId}.pdf     benchmark sample only, added by WP6
granules/metadata.jsonl
```

## 6. Work packages

Each package is a separate commit on a branch off `main`. Acceptance criteria are checked by tests or by the listed command.

### WP1: Secrets and infrastructure

- Remove the API key from `docker-compose.yml`, `downloader/fetch.py`, `downloader/fetch_historical.py`, and `.env.example`. Read `GOVINFO_API_KEY` from the environment only; exit with a message if missing.
- `env_file: .env` in compose. Remove `version:`. Add `.dockerignore`.
- Dockerfile: pre-fetch Docling models; named volume for `/root/.cache/huggingface`.
- Migrations directory; `db.py init_db` applies them in order; `statutes.title` to `TEXT`; new `packages` and `granules` tables.
- `pytest` scaffold; GitHub Actions workflow running `pytest`.
- README: state that the key must be rotated; describe the new env vars.

Acceptance: `docker compose config` shows no literal key; `git grep` for the leaked key prefix returns nothing on the branch; `pytest` passes.

### WP2: Downloader rewrite

- `govinfo.py` with retry (429, 5xx, timeouts; exponential backoff with jitter; honor `Retry-After`), rate-limit header logging, and `download_ranged(url, dest, parts)`.
- `.part` files, `Content-Length` verification, atomic rename, sha256 computed during write.
- Startup reconcile: list the Hub tree; for each volume decide `skip` (on Hub with matching size), `upload-only` (complete local file), or `download`.
- Bounded pipeline: download pool -> queue (max 3) -> uploader thread.
- CLI flags: `--volumes`, `--parts`, `--files`, `--no-upload`, `--keep-local`, `--log-dir`.
- File logging.

Acceptance: unit tests for range planning, `.part` verification, and reconcile decisions with a fake Hub tree; `python -m downloader.fetch_historical --volumes 118-119 --no-upload` completes in under two minutes and leaves two verified PDF+XML pairs; rerunning skips both.

### WP3: Hub uploader and metadata

- `hf_upload.py`: one `create_commit` per volume with `CommitOperationAdd` for PDF and XML; after commit, `get_paths_info` confirms both paths and sizes; then delete local files unless `--keep-local`.
- `metadata.jsonl` regenerated from the `packages` table; committed every 10 volumes and at the end.
- Dataset card `README.md` committed with the first upload.
- `reconcile` subcommand: prints local-only, hub-only, size-mismatch entries; `--fix` uploads or re-downloads.

Acceptance: `python -m downloader.fetch_historical --volumes 118-119` uploads to the real repo and deletes local copies; `reconcile` reports no differences; `metadata.jsonl` on the Hub has rows for 118 and 119 with correct sizes and hashes.

### WP4: PLAW and granule fetchers

- `fetch_plaw.py` iterates `collections/PLAW/{since}` with pagination; downloads per-law PDF and USLM; writes `statutes` rows with `volume` and `pages` from the summary; concurrency 4.
- `fetch_granules.py` takes a sample spec (WP6) and downloads granule PDFs with MODS metadata into `data/granules/STATUTE-{n}/`; writes `granules` rows.

Acceptance: `fetch_plaw.py --since 2023-01-01 --limit 20` populates 20 rows with non-null volume and pages; `fetch_granules.py --spec benchmark/sample.yaml` downloads the listed granules and is idempotent.

### WP5: Pipeline

- `profiles.py` with `scanned` and `digital` options; `convert.py` with a process pool, one converter per worker, `page_range` support, skip-if-exists, `conversions` rows.
- `uslm.py`: lxml builder producing GovInfo-namespace USLM with sections, headings, content, notes, and page breaks; XSD validation against uslm-2.0.17.
- `split_uslm.py`: per-granule USLM slices from the volume USLM using page markers and granule `pagePosition`. First task in this package: inspect `STATUTE-64.xml` and one PLAW USLM to confirm the element and page-marker structure before writing the splitter.

Acceptance: converting a 20-page granule PDF from vol. 64 and one 2023 PLAW produces XML that validates against the XSD; a second run skips both; `split_uslm.py` on STATUTE-64 yields one file per granule with the expected count (1,393).

### WP6: Benchmark

- `sample.py`: stratified sample, e.g. 10 granules per era per document class, seeded; writes `benchmark/sample.yaml`.
- `metrics.py`: text normalization (whitespace, hyphenation at line ends, quotes), CER, WER, structure counts, alignment report.
- `judge.py`: `claude-opus-5`, adaptive thinking, streaming, `fallbacks: "default"`, structured output schema, PDF pages as document blocks, aligned XML segments; cost logged from `usage`.
- `evaluate.py`: runs the stages with skip-if-done, writes `benchmarks` rows, prints a per-era table and writes `data/reports/<date>.md`.

Acceptance: `python -m benchmark.evaluate --spec benchmark/sample.yaml --no-judge` produces CER/WER for every sampled granule; `--judge` on two granules writes two `benchmarks` rows with structured details.

### WP7: Documentation

- README rewritten for the new commands and env vars; era table; ground truth provenance note; dataset card link.
- `docs/architecture.md` with the module diagram and data flow.

## 7. Order

1. WP1 (secrets, compose, migrations, tests scaffold).
2. WP2 and WP3 together; test on volumes 118 to 119; then run the full backfill with the current downloader stopped and the in-flight PDF deleted.
3. WP4.
4. WP5, then WP6.
5. WP7.

## 8. Out of scope for this plan

- Full conversion of all 137 volumes through Docling. On 10 CPU cores the scanned era (roughly 200,000 pages) is a multi-week job. The benchmark runs on the sample; a full run needs GPU hosts and is a separate plan.
- Rewriting git history to purge the leaked key. Rotating the key is sufficient; history rewriting on a repository with a merged PR is the owner's call.
