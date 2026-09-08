# WP9 C5 (Claude transcription) and C6 (hybrid): implementation and first results

Date: 2026-09-08. Branch `wp9-claude-hybrid` (worktree `wt-wp9c`, based on `wp8-benchmark-repair`). Benchmark run
`wp9c-hybrid` (report `2026-09-08-wp9c-hybrid.md`); baseline `wp8-baseline` (2026-09-08).

## Summary

- C6 `pipeline/hybrid.py` is implemented and scored on the full tier B sample with the WP8 candidates
  (`hybrid:scanned` on 33 scanned granules, `hybrid:digital` on 5 digital granules). Every output validates
  against uslm-2.0.17.xsd.
- C5 `pipeline/claude_ocr.py` is implemented and unit-tested with a fake client. No page was transcribed:
  the first request (Haiku 4.5, page 1 of STATUTE-10-Pg764, request id `req_011CerGhkXLCEmrbWtrpNxJy`)
  returned HTTP 400 `Your credit balance is too low to access the Anthropic API`, the module raised
  `CreditError` without retrying, and no further request was sent. Token and dollar figures for C5 below
  are projections from the rendered images, not measurements.

## C6: hybrid rows (tier B, `--no-judge`)

| Profile | Era | Granules | Mean CER | Median CER | Mean WER | Section recall | XSD valid | Baseline mean CER | Baseline section recall |
|---|---|---|---|---|---|---|---|---|---|
| hybrid:scanned | scanned-pre-1951 | 18 | 0.111 | 0.050 | 0.169 | 0.94 | 18/18 | 0.181 | 0.29 |
| hybrid:scanned | scanned-1951-2002 | 15 | 0.238 | 0.160 | 0.354 | 0.75 | 15/15 | 0.252 | 0.25 |
| hybrid:digital | digital-2003+ | 5 | 0.052 | 0.063 | 0.075 | 1.00 | 5/5 | 0.048 | 1.00 |

Wall time: 0.0 to 0.3 s per page (difflib alignment; the 12-page STATUTE-39-Pg1058 takes 0.5 s).

How to read the CER: the hybrid body is the candidate's words placed into the GPO structure, so its CER
against the GPO slice can only differ from the candidate's through (a) text the builder keeps from GPO
(`num`, `action`, `toc`, and runs whose candidate span is empty) and (b) the clip and alignment. Column
`Candidate share` is the share of body tokens that come from the candidate; where it is low the CER is
mostly the GPO text scored against itself. 15 granules score better than the baseline by more than
0.005, 2 worse, 21 within 0.005.

### By granule

| Granule | Class | Baseline CER | Hybrid CER | Delta | Candidate share | Runs kept from GPO | Sections matched (baseline) | Sections matched (hybrid) | Identifier |
|---|---|---|---|---|---|---|---|---|---|
| STATUTE-10-Pg1177-2 | PROCLAMATION | 0.180 | 0.180 | +0.000 | 1.0 | 0 | 0/0 | 0/0 | - |
| STATUTE-10-Pg764 | PRIVATELAW | 0.138 | 0.090 | -0.048 | 0.9444 | 0 | 0/1 | 1/1 | /us/act/1853-03-03/ch121 |
| STATUTE-10-Pg826-5 | PRIVATELAW | 0.036 | 0.034 | -0.002 | 0.9333 | 0 | 0/1 | 1/1 | /us/act/1854-08-05/ch265 |
| STATUTE-10-Pg840-3 | PRIVATELAW | 0.053 | 0.028 | -0.025 | 0.964 | 0 | 0/1 | 1/1 | /us/act/1855-01-12/ch33 |
| STATUTE-10-Pg954 | TREATY | 0.190 | 0.130 | -0.059 | 0.9118 | 46 | 0/1 | 1/1 | - |
| STATUTE-10-Pg972 | TREATY | 0.086 | 0.050 | -0.036 | 0.9604 | 1 | 0/0 | 0/0 | - |
| STATUTE-39-Pg1058 | PUBLICLAW | 0.134 | 0.104 | -0.029 | 0.957 | 31 | 1/5 | 5/5 | /us/pl/64/380 (+/us/act/1917-03-03/ch162) |
| STATUTE-39-Pg1599-4 | HCONRES | 0.044 | 0.047 | +0.002 | 0.9474 | 0 | 0/1 | 1/1 | - |
| STATUTE-39-Pg1600-3 | SCONRES | 0.069 | 0.070 | +0.001 | 0.9675 | 0 | 0/1 | 1/1 | - |
| STATUTE-39-Pg1603-4 | SCONRES | 0.038 | 0.040 | +0.001 | 0.9675 | 0 | 0/1 | 1/1 | - |
| STATUTE-39-Pg1604-3 | HCONRES | 0.558 | 0.522 | -0.037 | 0.9153 | 1 | 0/1 | 0/1 | - |
| STATUTE-39-Pg1606 | SCONRES | 0.032 | 0.032 | +0.001 | 0.9851 | 0 | 0/1 | 1/1 | - |
| STATUTE-39-Pg1606-4 | HCONRES | 0.040 | 0.042 | +0.002 | 0.9588 | 0 | 0/1 | 1/1 | - |
| STATUTE-39-Pg1645 | TREATY | 0.627 | 0.390 | -0.237 | 0.6791 | 26 | 0/0 | 0/0 | - |
| STATUTE-39-Pg1738 | PROCLAMATION | 0.789 | 0.010 | -0.779 | 0.2129 | 25 | 0/0 | 0/0 | - |
| STATUTE-39-Pg1782 | PROCLAMATION | 0.048 | 0.049 | +0.001 | 1.0 | 0 | 0/0 | 0/0 | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | 0.147 | 0.134 | -0.012 | 0.988 | 0 | 0/1 | 1/1 | /us/pl/64/138 (+/us/act/1916-07-03/ch216) |
| STATUTE-39-Pg354-4 | PUBLICLAW | 0.049 | 0.051 | +0.001 | 0.9818 | 1 | 0/1 | 1/1 | /us/pl/64/154 (+/us/act/1916-07-08/ch236) |
| STATUTE-72-Pg1572 | PUBLICLAW | 0.316 | 0.318 | +0.002 | 0.9816 | 17 | 3/6 | 3/6 | /us/pl/85/863 |
| STATUTE-72-Pg1751 | PUBLICLAW | 0.171 | 0.170 | -0.001 | 0.9775 | 2 | 3/11 | 9/11 | /us/pl/85/910 |
| STATUTE-72-Pg983-2 | PUBLICLAW | 0.148 | 0.139 | -0.009 | 0.9216 | 1 | 0/2 | 2/2 | /us/pl/85/822 |
| STATUTE-72-PgA13 | PRIVATELAW | 0.259 | 0.252 | -0.007 | 0.9706 | 0 | 0/2 | 2/2 | /us/pvtl/85/360 |
| STATUTE-72-PgA144-2 | PRIVATELAW | 0.210 | 0.207 | -0.002 | 0.9275 | 1 | 0/1 | 1/1 | /us/pvtl/85/668 |
| STATUTE-72-PgB14 | HCONRES | 1.227 | 1.154 | -0.073 | 0.9686 | 1 | 0/1 | 0/1 | - |
| STATUTE-72-PgB21 | SCONRES | 0.117 | 0.117 | +0.000 | 0.9468 | 0 | 0/1 | 0/1 | - |
| STATUTE-72-PgB23-3 | SCONRES | 0.384 | 0.386 | +0.002 | 0.9254 | 0 | 0/1 | 1/1 | - |
| STATUTE-72-PgB5 | HCONRES | 0.079 | 0.075 | -0.004 | 0.9487 | 0 | 0/1 | 1/1 | - |
| STATUTE-72-PgC40 | PROCLAMATION | 0.123 | 0.125 | +0.003 | 0.9508 | 2 | 0/0 | 0/0 | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | 0.155 | 0.156 | +0.001 | 0.9656 | 0 | 0/2 | 2/2 | /us/pvtl/92/26 |
| STATUTE-85-Pg864 | HCONRES | 0.157 | 0.160 | +0.003 | 0.9344 | 0 | 0/1 | 0/1 | - |
| STATUTE-85-Pg868-5 | SCONRES | 0.400 | 0.311 | -0.089 | 0.8779 | 1 | 0/2 | 2/2 | - |
| STATUTE-85-Pg906 | PROCLAMATION | 0.018 | 0.005 | -0.013 | 0.9952 | 1 | 0/0 | 0/0 | - |
| STATUTE-85-Pg943 | PROCLAMATION | 0.021 | 0.001 | -0.020 | 0.9909 | 1 | 0/0 | 0/0 | - |
| STATUTE-124-Pg2256 | PUBLICLAW | 0.022 | 0.026 | +0.003 | 0.9388 | 2 | 5/5 | 5/5 | /us/pl/111/210 |
| STATUTE-124-Pg4523 | PRIVATELAW | 0.055 | 0.063 | +0.008 | 0.9698 | 1 | 1/1 | 1/1 | /us/pvtl/111/1 |
| STATUTE-124-Pg4525 | PRIVATELAW | 0.060 | 0.064 | +0.004 | 0.9692 | 1 | 1/1 | 1/1 | /us/pvtl/111/2 |
| STATUTE-132-Pg2888 | PUBLICLAW | 0.059 | 0.065 | +0.006 | 0.9457 | 7 | 2/2 | 2/2 | /us/pl/115/240 |
| STATUTE-132-Pg5019 | PUBLICLAW | 0.042 | 0.043 | +0.002 | 0.9189 | 11 | 11/11 | 11/11 | /us/pl/115/335 |

Identifier column: `/us/pl/...` and `/us/pvtl/...` from the MODS congress and law number; `/us/act/{date}/ch{n}`
for 1853 (volume 10) from the approval date and the MODS chapter; both forms for 1917 (volume 39) with the
chapter form on `meta/property[@role='alternateIdentifier']`. Proclamations, treaties, and resolutions get no
document identifier (section 7 of the plan covers laws). `Id F1` in the evaluate report is 0 for laws because
the STATUTE-era GPO slices carry no identifiers to compare with.

### Observations

- Section recall rises from 0.25 to 0.29 (baseline) to 0.75 to 0.94 because the sections are the GPO's;
  the candidate's section detection only decides where its text is cut. STATUTE-72-Pg1751: 9 of 11
  sections matched by the metric (the candidate recognized 3).
- STATUTE-39-Pg1738 (proclamation, land-description tables): the candidate has 1,008 of 4,658 reference
  characters, 25 of 29 runs keep the GPO text, candidate share 0.21, CER 0.010. This is the GPO text scoring
  itself; the tier B reference cannot say whether the hybrid is right there.
- STATUTE-39-Pg1645 (bilingual treaty in a two-column `layout`): the candidate's reading order interleaves the
  columns; the hybrid keeps the 26 runs that difflib could not fill and scores 0.39 against 0.627.
- STATUTE-72-PgB14 (resolution): the clip anchors are not found on either side and the candidate text is
  garbled (baseline 1.227); the hybrid scores 1.154.
- Digital era: 0.002 to 0.008 worse than the candidate. The `digital` candidate lists the table of contents
  as sections with the same numbers as the real ones; the weighted section matcher pairs the real ones
  (STATUTE-132-Pg5019: 11/11) and the TOC tokens are dropped against the GPO `toc` (`substituted_tokens`).
- `Kept` in the evaluate report is `kept_chars / docling_chars` where `docling_chars` is the candidate's main
  text and `kept_chars` includes the GPO sidenotes and the candidate's preface and trailing paragraphs, so it
  exceeds 1 (up to 7.5 on one-page granules whose neighbours' text is long).
- The evaluate report lists 39 failures: `hybrid:digital` on the 33 scanned granules and `hybrid:scanned` on
  the 6 digital ones, where the named candidate profile has no output. STATUTE-132-Pg5595 has no GPO slice
  (F4) and is skipped.

## C5: state

Implemented: family `claude` with variants `claude-opus-5` (default), `claude-sonnet-5`, `claude-haiku-4-5`;
one request per page image (JPEG, longest side 1,500 px, quality 85); cached system prompt (about
993 tokens; below the 1,024-token cache minimum of Sonnet 5 and the 4,096 of Haiku 4.5, above
the 512 of Opus 5); adaptive thinking with `output_config.effort` (default `medium`, `--effort`) on Opus 5
and Sonnet 5, no thinking on Haiku 4.5; structured output with the line schema (`role`, `text`,
`starts_paragraph`); `fallbacks="default"` with the `server-side-fallback-2026-07-01` beta, dropped and
retried without when the API rejects it for a model; 4 requests in flight; retries with backoff on 429,
529, 5xx, and connection errors; `CreditError` on the 400 credit message; `--batch` through the Message
Batches API (polled every 30 s, results keyed by `custom_id`, priced at half). Per page the usage sidecar
records input, output, cache read, cache write tokens, estimated image tokens, cost, seconds, attempts,
stop reason, serving model, and request id.

Adapter: `to_docling` gives every line group synthetic geometry (body column x = 0.12 to 0.72 of the page
width, sidenotes at x = 0.75 to 0.97 at the height of the body line before them, running heads and page
numbers in the top 5 percent, footnotes at 6.5 to 12.5 percent from the foot); `pipeline.uslm.load_pages`
classifies them as header, sidenote, body, and footnote (tested). Lines whose `starts_paragraph` is false
are joined with a newline to the most recent item of the same role, which is the paragraph shape Docling
produces; `--line-items` keeps one item per line. Empty lines are skipped; every other line's text is in
exactly one item.

Measured without the API (`--dry-run`): 87 pages, 180,112 image tokens, mean 2,070 per page (letter pages
1,160 x 1,500 px, 2,320 tokens; volume 10 and 39 pages 977 x 1,500 px, 1,954 tokens), JPEG 29 to 268 KB.

Projection per page: input 2240 tokens (image, user text, and the system prompt at the cached rate);
output 2800 tokens (about 55 lines of JSON at 40 tokens each plus thinking at medium effort; the plan
assumed 1,200 because it did not count the per-line JSON overhead).

| Model | Price in / out per MTok | Per page | 87 pages | 87 pages, batch | 200,000 pages | 200,000 pages, batch |
|---|---|---|---|---|---|---|
| `claude-opus-5` | $5.00 / $25.00 | $0.0812 | $7.06 | $3.53 | $16,240 | $8,120 |
| `claude-sonnet-5` | $2.00 / $10.00 | $0.0325 | $2.83 | $1.41 | $6,496 | $3,248 |
| `claude-haiku-4-5` | $1.00 / $5.00 | $0.0162 | $1.41 | $0.71 | $3,248 | $1,624 |

All three models on the sample project to $11.3 streaming or $5.7 with `--batch`, so the $8 budget holds
only with `--batch`. Seconds per page: not measured.

Not run: `claude:<model>` on the sample, `hybrid:claude:<model>`, the judge.

## Reproduce

Mac (no database; `DATA_DIR` points at the shared data directory):

    cd wt-wp9c && set -a && . ./.env && set +a
    export DATA_DIR=/Users/arihershowitz/Documents/workspace/aih/statute-pdf-to-xml/data
    python -m pipeline.claude_ocr --spec benchmark/sample.yaml --model claude-haiku-4-5 --dry-run
    python -m pipeline.claude_ocr --spec benchmark/sample.yaml --model claude-haiku-4-5 --limit 5
    python -m pipeline.claude_ocr --spec benchmark/sample.yaml --model claude-opus-5 --batch
    python -m pytest -q

Container (database, evaluate):

    docker compose -p statute-pdf-to-xml run -d --name wp9c -v "$PWD":/app \
        -v /Users/arihershowitz/Documents/workspace/aih/statute-pdf-to-xml/data:/app/data app tail -f /dev/null
    docker exec wp9c sh -c 'cd /app && python -m pytest -q'
    docker exec wp9c sh -c 'cd /app && python -m benchmark.evaluate --spec benchmark/sample.yaml \
        --profiles hybrid:scanned,hybrid:digital --tier B --no-judge --run-id wp9c-hybrid'
    docker exec wp9c sh -c 'cd /app && python -m benchmark.evaluate --spec benchmark/sample.yaml \
        --profiles claude:claude-haiku-4-5 --tier B --no-judge --limit 5 --run-id wp9c-claude'
    docker exec wp9c sh -c 'cd /app && python -m benchmark.evaluate --spec benchmark/sample.yaml \
        --profiles claude:claude-opus-5 --tier B --no-judge --rebuild --run-id wp9c-claude'   # scores JSON written on the Mac
    docker exec wp9c sh -c 'cd /app && python -m benchmark.evaluate --spec benchmark/sample.yaml \
        --profiles hybrid:claude:claude-opus-5 --tier B --no-judge --run-id wp9c-hybrid-claude'
    docker rm -f wp9c
