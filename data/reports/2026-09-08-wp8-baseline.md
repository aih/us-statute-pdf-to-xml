# Benchmark wp8-baseline

Date: 2026-09-08T15:46:45. Spec: `benchmark/sample.yaml`. Rows: 38 (38 granules, profiles digital, scanned). Judged: 0 ($0.00).

CER and WER are scored on the generated text clipped to the reference span (F3); `CER unclipped` is the score over the whole generated body. `Kept` is characters kept in the generated document over characters Docling produced (F2). Section recall matches sections by number and the first 40 characters.

## Profile by era

| Profile | Tier | Era | Granules | Mean CER | Median CER | Mean WER | Section recall | Id F1 | Clipped both | Min kept | XSD valid | s/page | Judge (n) | Judge mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| digital | B | digital-2003+ | 5 | 0.048 | 0.055 | 0.073 | 1.00 | 0.00 | 5/5 | 0.92 | 5/5 | 0.0 | 0 | - |
| scanned | B | scanned-1951-2002 | 15 | 0.252 | 0.157 | 0.374 | 0.25 | 0.60 | 12/15 | 1.01 | 15/15 | 0.0 | 0 | - |
| scanned | B | scanned-pre-1951 | 18 | 0.181 | 0.078 | 0.248 | 0.29 | 0.67 | 15/18 | 1.01 | 18/18 | 0.1 | 0 | - |

## By granule

| Granule | Class | Profile | Tier | Pages | CER | CER unclipped | Clip | WER | Sections ref/gen (matched) | Id F1 | Kept | Warn | XSD | Judge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| STATUTE-124-Pg2256 | PUBLICLAW | digital | B | 2 | 0.022 | 0.022 | both | 0.058 | 5/5 (5) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | digital | B | 2 | 0.055 | 0.055 | both | 0.078 | 1/1 (1) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | digital | B | 2 | 0.060 | 0.060 | both | 0.090 | 1/1 (1) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | digital | B | 4 | 0.059 | 0.059 | both | 0.083 | 2/2 (2) | 0.00 | 0.94 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | digital | B | 6 | 0.042 | 0.042 | both | 0.054 | 11/22 (11) | 0.00 | 0.96 | 2 | yes | - |
| STATUTE-72-Pg1572 | PUBLICLAW | scanned | B | 8 | 0.316 | 0.305 | both | 0.414 | 6/4 (3) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | scanned | B | 3 | 0.171 | 0.171 | both | 0.258 | 11/3 (3) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | scanned | B | 1 | 0.148 | 0.148 | both | 0.205 | 2/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | scanned | B | 2 | 0.259 | 0.259 | both | 0.325 | 2/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | scanned | B | 1 | 0.210 | 0.210 | both | 0.330 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-PgB14 | HCONRES | scanned | B | 1 | 1.227 | 1.227 | none | 2.080 | 1/0 (0) | 1.00 | 1.03 | 1 | yes | - |
| STATUTE-72-PgB21 | SCONRES | scanned | B | 1 | 0.117 | 0.117 | both | 0.136 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-72-PgB23-3 | SCONRES | scanned | B | 1 | 0.384 | 0.385 | both | 0.500 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgB5 | HCONRES | scanned | B | 1 | 0.079 | 1.052 | both | 0.122 | 1/0 (0) | 1.00 | 1.01 | 3 | yes | - |
| STATUTE-72-PgC40 | PROCLAMATION | scanned | B | 1 | 0.123 | 0.139 | tail | 0.142 | 0/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | scanned | B | 1 | 0.155 | 0.155 | both | 0.248 | 2/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-85-Pg864 | HCONRES | scanned | B | 1 | 0.157 | 0.157 | both | 0.279 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg868-5 | SCONRES | scanned | B | 2 | 0.400 | 0.400 | head | 0.527 | 2/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-85-Pg906 | PROCLAMATION | scanned | B | 2 | 0.018 | 0.025 | both | 0.021 | 0/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | scanned | B | 1 | 0.021 | 0.034 | both | 0.019 | 0/0 (0) | 1.00 | 1.04 | 0 | yes | - |
| STATUTE-10-Pg1177-2 | PROCLAMATION | scanned | B | 2 | 0.180 | 0.224 | both | 0.306 | 0/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | scanned | B | 1 | 0.138 | 1.152 | both | 0.252 | 1/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | scanned | B | 1 | 0.036 | 0.065 | both | 0.116 | 1/0 (0) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | scanned | B | 1 | 0.053 | 0.768 | both | 0.105 | 1/0 (0) | 0.00 | 1.02 | 0 | yes | - |
| STATUTE-10-Pg954 | TREATY | scanned | B | 6 | 0.190 | 0.190 | tail | 0.301 | 1/0 (0) | 1.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg972 | TREATY | scanned | B | 1 | 0.086 | 0.086 | both | 0.165 | 0/0 (0) | 1.00 | 1.02 | 0 | yes | - |
| STATUTE-39-Pg1058 | PUBLICLAW | scanned | B | 12 | 0.134 | 0.134 | both | 0.174 | 5/1 (1) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-39-Pg1599-4 | HCONRES | scanned | B | 1 | 0.044 | 0.044 | both | 0.058 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-39-Pg1600-3 | SCONRES | scanned | B | 1 | 0.069 | 0.892 | both | 0.109 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-39-Pg1603-4 | SCONRES | scanned | B | 1 | 0.038 | 0.038 | both | 0.065 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1604-3 | HCONRES | scanned | B | 1 | 0.558 | 0.558 | head | 0.690 | 1/0 (0) | 1.00 | 1.03 | 1 | yes | - |
| STATUTE-39-Pg1606 | SCONRES | scanned | B | 1 | 0.032 | 0.292 | both | 0.043 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1606-4 | HCONRES | scanned | B | 2 | 0.040 | 2.713 | both | 0.044 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1645 | TREATY | scanned | B | 5 | 0.627 | 0.652 | both | 0.795 | 0/0 (0) | 1.00 | 1.01 | 0 | yes | - |
| STATUTE-39-Pg1738 | PROCLAMATION | scanned | B | 3 | 0.789 | 0.789 | head | 0.798 | 0/0 (0) | 1.00 | 1.03 | 0 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | scanned | B | 1 | 0.048 | 0.258 | both | 0.090 | 0/0 (0) | 1.00 | 1.02 | 1 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | scanned | B | 1 | 0.147 | 0.290 | both | 0.258 | 1/0 (0) | 0.00 | 1.01 | 0 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | scanned | B | 2 | 0.049 | 0.049 | both | 0.089 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |

## Skipped

- STATUTE-132-Pg5595 [digital/B]: no one-to-one reference (PRIVATELAW: no slice; F4)

## Notes

- Conversion timings in this report come from the `--rebuild` pass (USLM rebuilt from stored Docling output). OCR timings from the first pass of this run (Docling + Tesseract at 300 dpi, two workers, 10-CPU container): digital: 17 pages in 27 s wall (1.6 s/page per worker); scanned: 70 pages in 307 s wall (4.4 s/page per worker).
- Defects F1 to F4 of docs/plans/2026-09-07-ocr-pipeline-evaluation-plan.md are fixed in this run: orientation detection off (pipeline/tesseract.py), no body text dropped (kept ratio 0.92 to 1.07), CER on the clipped span, digital era limited to laws.
- Granules above CER 0.5 are not laws: STATUTE-72-PgB14 and STATUTE-39-Pg1604-3 (resolution pages with garbled OCR of the heading and end lines, so the document start is mislocated), STATUTE-39-Pg1645 (bilingual treaty, two columns), STATUTE-39-Pg1738 (proclamation with land-description tables over three pages; Docling produced 1,008 characters for 4,658 in the reference).
- STATUTE-132-Pg5595 is skipped: the volume USLM places Private Law 115-1 at 132 Stat. 5592, GovInfo's granule at page 5595.
- The WP6 report (2026-09-05-wp6-metrics.md) scored the same scanned granules at mean CER 0.99 to 1.04.
