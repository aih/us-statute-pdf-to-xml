# Benchmark wp9a-cpu-easyocr

Date: 2026-09-08T16:50:05. Spec: `benchmark/sample-easyocr.yaml`. Rows: 72 (15 granules, profiles easyocr, rapidocr, tesseract:psm4, tesseract:psm6, textlayer). Judged: 0 ($0.00).

CER and WER are scored on the generated text clipped to the reference span (F3); `CER unclipped` is the score over the whole generated body. `Kept` is characters kept in the generated document over characters Docling produced (F2). Section recall matches sections by number and the first 40 characters.

## Profile by era

| Profile | Tier | Era | Granules | Mean CER | Median CER | Mean WER | Section recall | Id F1 | Clipped both | Min kept | XSD valid | s/page | Judge (n) | Judge mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| easyocr | B | scanned-1951-2002 | 6 | 0.762 | 0.770 | 0.846 | 0.18 | 0.17 | 0/6 | 1.01 | 6/6 | 43.7 | 0 | - |
| easyocr | B | scanned-pre-1951 | 6 | 0.799 | 0.781 | 0.895 | 0.17 | 0.17 | 0/6 | 1.00 | 6/6 | 83.0 | 0 | - |
| rapidocr | B | digital-2003+ | 3 | 0.073 | 0.084 | 0.093 | 1.00 | 0.00 | 3/3 | 1.02 | 3/3 | 3.0 | 0 | - |
| rapidocr | B | scanned-1951-2002 | 6 | 0.101 | 0.092 | 0.147 | 0.47 | 0.17 | 5/6 | 1.01 | 6/6 | 5.4 | 0 | - |
| rapidocr | B | scanned-pre-1951 | 6 | 0.092 | 0.089 | 0.138 | 0.17 | 0.17 | 6/6 | 1.01 | 6/6 | 9.5 | 0 | - |
| tesseract:psm4 | B | digital-2003+ | 3 | 0.043 | 0.053 | 0.062 | 1.00 | 0.00 | 3/3 | 1.02 | 3/3 | 2.3 | 0 | - |
| tesseract:psm4 | B | scanned-1951-2002 | 6 | 0.448 | 0.170 | 0.556 | 0.21 | 0.17 | 4/6 | 1.00 | 6/6 | 3.8 | 0 | - |
| tesseract:psm4 | B | scanned-pre-1951 | 6 | 0.067 | 0.068 | 0.130 | 0.17 | 0.17 | 6/6 | 1.02 | 6/6 | 7.4 | 0 | - |
| tesseract:psm6 | B | digital-2003+ | 3 | 0.044 | 0.053 | 0.063 | 1.00 | 0.00 | 3/3 | 1.02 | 3/3 | 2.3 | 0 | - |
| tesseract:psm6 | B | scanned-1951-2002 | 6 | 0.159 | 0.121 | 0.220 | 0.24 | 0.17 | 6/6 | 1.00 | 6/6 | 4.0 | 0 | - |
| tesseract:psm6 | B | scanned-pre-1951 | 6 | 0.175 | 0.112 | 0.251 | 0.17 | 0.17 | 6/6 | 1.02 | 6/6 | 8.3 | 0 | - |
| textlayer | B | digital-2003+ | 3 | 0.046 | 0.055 | 0.075 | 1.00 | 0.00 | 3/3 | 0.92 | 3/3 | 1.3 | 0 | - |
| textlayer | B | scanned-1951-2002 | 6 | 0.071 | 0.059 | 0.118 | 0.57 | 0.17 | 5/6 | 1.00 | 6/6 | 1.4 | 0 | - |
| textlayer | B | scanned-pre-1951 | 6 | 0.012 | 0.008 | 0.039 | 0.17 | 0.17 | 6/6 | 1.01 | 6/6 | 3.3 | 0 | - |

## By granule

| Granule | Class | Profile | Tier | Pages | CER | CER unclipped | Clip | WER | Sections ref/gen (matched) | Id F1 | Kept | Warn | XSD | Judge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| STATUTE-72-Pg1751 | PUBLICLAW | easyocr | B | 3 | 0.717 | 0.717 | none | 0.781 | 11/1 (1) | 0.00 | 1.03 | 2 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | easyocr | B | 1 | 0.757 | 0.757 | none | 0.866 | 2/0 (0) | 0.00 | 1.04 | 1 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | easyocr | B | 2 | 0.783 | 0.783 | none | 0.890 | 2/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | easyocr | B | 1 | 0.949 | 0.949 | none | 1.000 | 1/0 (0) | 0.00 | 1.06 | 2 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | easyocr | B | 1 | 0.845 | 0.845 | none | 0.885 | 2/1 (0) | 0.00 | 1.07 | 2 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | easyocr | B | 1 | 0.522 | 0.522 | head | 0.654 | 0/0 (0) | 1.00 | 1.07 | 0 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | easyocr | B | 1 | 0.894 | 0.894 | none | 0.961 | 1/0 (0) | 0.00 | 1.73 | 3 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | easyocr | B | 1 | 0.839 | 0.839 | none | 0.965 | 1/0 (0) | 0.00 | 1.50 | 3 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | easyocr | B | 1 | 0.941 | 0.942 | none | 0.969 | 1/0 (0) | 0.00 | 1.57 | 3 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | easyocr | B | 1 | 0.698 | 0.698 | none | 0.791 | 0/0 (0) | 1.00 | 1.06 | 1 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | easyocr | B | 1 | 0.723 | 0.723 | none | 0.811 | 1/0 (0) | 0.00 | 1.07 | 2 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | easyocr | B | 2 | 0.699 | 0.699 | none | 0.874 | 1/0 (0) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | rapidocr | B | 2 | 0.038 | 0.038 | both | 0.045 | 5/5 (5) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | rapidocr | B | 2 | 0.096 | 0.096 | both | 0.118 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | rapidocr | B | 2 | 0.084 | 0.084 | both | 0.115 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | rapidocr | B | 3 | 0.083 | 0.083 | both | 0.120 | 11/9 (9) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | rapidocr | B | 1 | 0.010 | 0.010 | both | 0.018 | 2/1 (1) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | rapidocr | B | 2 | 0.191 | 0.191 | head | 0.277 | 2/1 (1) | 0.00 | 1.01 | 3 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | rapidocr | B | 1 | 0.019 | 0.056 | both | 0.088 | 1/0 (0) | 0.00 | 1.02 | 3 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | rapidocr | B | 1 | 0.205 | 0.205 | both | 0.271 | 2/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | rapidocr | B | 1 | 0.100 | 0.114 | both | 0.105 | 0/0 (0) | 1.00 | 1.04 | 0 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | rapidocr | B | 1 | 0.222 | 0.228 | both | 0.320 | 1/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | rapidocr | B | 1 | 0.010 | 0.010 | both | 0.047 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | rapidocr | B | 1 | 0.131 | 0.131 | both | 0.167 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | rapidocr | B | 1 | 0.046 | 0.064 | both | 0.051 | 0/0 (0) | 1.00 | 1.02 | 0 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | rapidocr | B | 1 | 0.007 | 0.007 | both | 0.047 | 1/0 (0) | 0.00 | 1.01 | 3 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | rapidocr | B | 2 | 0.137 | 0.137 | both | 0.199 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | tesseract:psm4 | B | 2 | 0.019 | 0.019 | both | 0.035 | 5/5 (5) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | tesseract:psm4 | B | 2 | 0.053 | 0.053 | both | 0.070 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | tesseract:psm4 | B | 2 | 0.058 | 0.058 | both | 0.081 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | tesseract:psm4 | B | 3 | 0.185 | 0.185 | both | 0.271 | 11/3 (3) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | tesseract:psm4 | B | 1 | 0.116 | 0.116 | both | 0.170 | 2/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | tesseract:psm4 | B | 2 | 0.643 | 0.895 | head | 0.801 | 2/0 (0) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | tesseract:psm4 | B | 1 | 1.566 | 1.566 | head | 1.824 | 1/0 (0) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | tesseract:psm4 | B | 1 | 0.155 | 0.155 | both | 0.248 | 2/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | tesseract:psm4 | B | 1 | 0.021 | 0.034 | both | 0.019 | 0/0 (0) | 1.00 | 1.04 | 0 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | tesseract:psm4 | B | 1 | 0.092 | 1.216 | both | 0.175 | 1/0 (0) | 0.00 | 1.03 | 3 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | tesseract:psm4 | B | 1 | 0.026 | 0.055 | both | 0.105 | 1/0 (0) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | tesseract:psm4 | B | 1 | 0.041 | 0.790 | both | 0.080 | 1/0 (0) | 0.00 | 1.02 | 0 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | tesseract:psm4 | B | 1 | 0.090 | 0.300 | both | 0.121 | 0/0 (0) | 1.00 | 1.02 | 1 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | tesseract:psm4 | B | 1 | 0.106 | 0.288 | both | 0.209 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | tesseract:psm4 | B | 2 | 0.045 | 0.045 | both | 0.089 | 1/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | tesseract:psm6 | B | 2 | 0.019 | 0.019 | both | 0.035 | 5/5 (5) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | tesseract:psm6 | B | 2 | 0.053 | 0.053 | both | 0.070 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | tesseract:psm6 | B | 2 | 0.058 | 0.059 | both | 0.084 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | tesseract:psm6 | B | 3 | 0.134 | 0.134 | both | 0.203 | 11/5 (5) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | tesseract:psm6 | B | 1 | 0.319 | 1.700 | both | 0.482 | 2/0 (0) | 0.00 | 1.00 | 0 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | tesseract:psm6 | B | 2 | 0.313 | 0.313 | both | 0.349 | 2/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | tesseract:psm6 | B | 1 | 0.065 | 0.065 | both | 0.088 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | tesseract:psm6 | B | 1 | 0.107 | 0.107 | both | 0.169 | 2/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | tesseract:psm6 | B | 1 | 0.015 | 0.038 | both | 0.031 | 0/0 (0) | 1.00 | 1.03 | 0 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | tesseract:psm6 | B | 1 | 0.140 | 1.164 | both | 0.262 | 1/0 (0) | 0.00 | 1.03 | 2 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | tesseract:psm6 | B | 1 | 0.029 | 0.058 | both | 0.105 | 1/0 (0) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | tesseract:psm6 | B | 1 | 0.085 | 0.768 | both | 0.148 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | tesseract:psm6 | B | 1 | 0.558 | 0.672 | both | 0.582 | 0/0 (0) | 1.00 | 1.02 | 1 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | tesseract:psm6 | B | 1 | 0.160 | 0.371 | both | 0.276 | 1/0 (0) | 0.00 | 1.02 | 0 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | tesseract:psm6 | B | 2 | 0.077 | 0.077 | both | 0.132 | 1/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | textlayer | B | 2 | 0.022 | 0.022 | both | 0.058 | 5/5 (5) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | textlayer | B | 2 | 0.055 | 0.055 | both | 0.078 | 1/1 (1) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | textlayer | B | 2 | 0.060 | 0.060 | both | 0.090 | 1/1 (1) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | textlayer | B | 3 | 0.076 | 0.076 | both | 0.127 | 11/10 (10) | 0.00 | 1.00 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | textlayer | B | 1 | 0.016 | 0.016 | both | 0.054 | 2/1 (1) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | textlayer | B | 2 | 0.211 | 0.211 | head | 0.264 | 2/1 (1) | 0.00 | 1.01 | 3 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | textlayer | B | 1 | 0.063 | 2.315 | both | 0.165 | 1/0 (0) | 0.00 | 1.00 | 0 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | textlayer | B | 1 | 0.007 | 0.007 | both | 0.025 | 2/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | textlayer | B | 1 | 0.055 | 0.055 | both | 0.074 | 0/0 (0) | 1.00 | 1.04 | 0 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | textlayer | B | 1 | 0.008 | 4.842 | both | 0.039 | 1/1 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | textlayer | B | 1 | 0.002 | 0.002 | both | 0.023 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | textlayer | B | 1 | 0.003 | 0.807 | both | 0.019 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | textlayer | B | 1 | 0.010 | 0.231 | both | 0.025 | 0/0 (0) | 1.00 | 1.02 | 1 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | textlayer | B | 1 | 0.009 | 0.009 | both | 0.062 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | textlayer | B | 2 | 0.040 | 0.040 | both | 0.067 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |

## Failed

- STATUTE-124-Pg2256 [easyocr/B]: worker: A process in the process pool was terminated abruptly while the future was running or pending.
- STATUTE-124-Pg4523 [easyocr/B]: worker: A process in the process pool was terminated abruptly while the future was running or pending.
- STATUTE-124-Pg4525 [easyocr/B]: worker: A process in the process pool was terminated abruptly while the future was running or pending.

## Notes

- Spec: benchmark/sample-easyocr.yaml, 15 granules of sample.yaml (public and private laws from every era plus two proclamations), tier B only. The four other profiles are the wp9a-cpu conversions (2026-09-08-wp9a-cpu.md); their units were skipped and the rows recomputed under this run id so the five profiles are scored on the same granules.
- `easyocr` ran with one worker at 300 dpi (Docling `EasyOcrOptions`, lang en, CPU, full page, scale 300/72). The full sample was not attempted: 61 s/page per worker and a container peak above 5 GB per page.
- Twelve of 15 units converted (16 pages, 974 s, 60.9 s/page). A worker was killed on the second or third unit of every pass when the container passed about 5 GB during the detection pass on a 2,550 x 3,300 px page, with 1 GB of other containers on the host; the units were completed over ten `python -m pipeline.convert --spec benchmark/sample-easyocr.yaml --profile easyocr --workers 1` passes (each pass a fresh worker, finished units skipped), 20 minutes in total. The three STATUTE-124 units were killed on every pass (10 of 10), so there is no digital-era row. Tier A (`--tier A --dpi 96 --workers 1`): the worker was killed on the first unit in both attempts; no rows.
- `easyocr` text: CER 0.52 to 0.95; the clip anchors were found on 1 of 12 granules. Docling text volume per page is a fraction of the other engines': STATUTE-10-Pg764 gives 64 characters where tesseract:psm4 gives 3,536; page 1 of STATUTE-72-Pg1751 gives 1,148 characters where the PDF text layer has 3,416, and "Grand Portage" is read as "Grand Portuge". tests/test_ocr_engines.py::test_easyocr_reads_page_one fails on that output.
- `s/page` comes from the `conversions` rows (first pass, no `--rebuild`); for the four other profiles those are the wp9a-cpu timings restricted to these granules.
- Report command: `python -m benchmark.evaluate --spec benchmark/sample-easyocr.yaml --profiles textlayer,tesseract:psm4,tesseract:psm6,rapidocr,easyocr --tier B --no-judge --workers 1 --run-id wp9a-cpu-easyocr` (the three STATUTE-124 easyocr units are retried and fail in it).
