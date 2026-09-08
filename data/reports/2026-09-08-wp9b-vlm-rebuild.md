# Benchmark wp9b-vlm-rebuild

Date: 2026-09-08T18:06:34. Spec: `benchmark/sample_vlm.yaml`. Rows: 48 (13 granules, profiles vlm:glm_ocr, vlm:granite_docling, vlm:lightonocr). Judged: 0 ($0.00).

CER and WER are scored on the generated text clipped to the reference span (F3); `CER unclipped` is the score over the whole generated body. `Kept` is characters kept in the generated document over characters Docling produced (F2). Section recall matches sections by number and the first 40 characters.

## Profile by era

| Profile | Tier | Era | Granules | Mean CER | Median CER | Mean WER | Section recall | Id F1 | Clipped both | Min kept | XSD valid | s/page | Judge (n) | Judge mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vlm:glm_ocr | A | digital-2003+ | 3 | 0.029 | 0.034 | 0.036 | 1.00 | 0.00 | 3/3 | 1.02 | 3/3 | 1.1 | 0 | - |
| vlm:glm_ocr | B | digital-2003+ | 3 | 0.029 | 0.034 | 0.037 | 1.00 | 0.00 | 3/3 | 1.02 | 3/3 | 0.0 | 0 | - |
| vlm:glm_ocr | B | scanned-1951-2002 | 5 | 0.006 | 0.005 | 0.010 | 0.48 | 0.00 | 5/5 | 1.01 | 5/5 | 0.0 | 0 | - |
| vlm:glm_ocr | B | scanned-pre-1951 | 5 | 0.002 | 0.002 | 0.008 | 0.00 | 0.00 | 5/5 | 1.01 | 5/5 | 1.2 | 0 | - |
| vlm:granite_docling | A | digital-2003+ | 3 | 0.029 | 0.034 | 0.035 | 1.00 | 0.00 | 3/3 | 1.01 | 3/3 | 1.8 | 0 | - |
| vlm:granite_docling | B | digital-2003+ | 3 | 0.025 | 0.034 | 0.031 | 1.00 | 0.00 | 3/3 | 1.01 | 3/3 | 0.0 | 0 | - |
| vlm:granite_docling | B | scanned-1951-2002 | 5 | 0.257 | 0.133 | 0.294 | 0.28 | 0.00 | 4/5 | 0.09 | 5/5 | 0.0 | 0 | - |
| vlm:granite_docling | B | scanned-pre-1951 | 5 | 0.787 | 0.071 | 0.835 | 0.00 | 0.00 | 4/5 | 1.01 | 5/5 | 1.2 | 0 | - |
| vlm:lightonocr | A | digital-2003+ | 3 | 0.048 | 0.048 | 0.068 | 0.93 | 0.00 | 3/3 | 1.00 | 3/3 | 1.0 | 0 | - |
| vlm:lightonocr | B | digital-2003+ | 3 | 0.048 | 0.048 | 0.068 | 0.93 | 0.00 | 3/3 | 1.00 | 3/3 | 0.0 | 0 | - |
| vlm:lightonocr | B | scanned-1951-2002 | 5 | 0.053 | 0.022 | 0.082 | 0.48 | 0.00 | 5/5 | 1.00 | 5/5 | 0.0 | 0 | - |
| vlm:lightonocr | B | scanned-pre-1951 | 5 | 0.015 | 0.002 | 0.031 | 0.00 | 0.00 | 5/5 | 1.00 | 5/5 | 1.1 | 0 | - |

## By granule

| Granule | Class | Profile | Tier | Pages | CER | CER unclipped | Clip | WER | Sections ref/gen (matched) | Id F1 | Kept | Warn | XSD | Judge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| STATUTE-124-Pg2256 | PUBLICLAW | vlm:glm_ocr | A | 2 | 0.016 | 0.016 | both | 0.018 | 5/5 (5) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | vlm:glm_ocr | A | 2 | 0.034 | 0.034 | both | 0.042 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | vlm:glm_ocr | A | 2 | 0.038 | 0.038 | both | 0.048 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | vlm:glm_ocr | B | 2 | 0.016 | 0.016 | both | 0.018 | 5/5 (5) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | vlm:glm_ocr | B | 2 | 0.034 | 0.034 | both | 0.042 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | vlm:glm_ocr | B | 2 | 0.038 | 0.038 | both | 0.051 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | vlm:glm_ocr | B | 3 | 0.011 | 0.011 | both | 0.014 | 11/10 (10) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | vlm:glm_ocr | B | 1 | 0.010 | 0.010 | both | 0.018 | 2/1 (1) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | vlm:glm_ocr | B | 2 | 0.005 | 0.005 | both | 0.010 | 2/1 (1) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | vlm:glm_ocr | B | 1 | 0.000 | 0.000 | both | 0.000 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | vlm:glm_ocr | B | 1 | 0.004 | 0.004 | both | 0.010 | 2/1 (1) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | vlm:glm_ocr | B | 1 | 0.006 | 0.006 | both | 0.019 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | vlm:glm_ocr | B | 1 | 0.002 | 0.002 | both | 0.012 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | vlm:glm_ocr | B | 1 | 0.000 | 0.000 | both | 0.000 | 1/0 (0) | 0.00 | 1.01 | 3 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | vlm:glm_ocr | B | 1 | 0.002 | 0.002 | both | 0.005 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | vlm:glm_ocr | B | 2 | 0.001 | 0.001 | both | 0.003 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | vlm:granite_docling | A | 2 | 0.016 | 0.016 | both | 0.018 | 5/5 (5) | 0.00 | 1.03 | 2 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | vlm:granite_docling | A | 2 | 0.034 | 0.034 | both | 0.042 | 1/1 (1) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | vlm:granite_docling | A | 2 | 0.036 | 0.036 | both | 0.044 | 1/1 (1) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | vlm:granite_docling | B | 2 | 0.003 | 0.003 | both | 0.000 | 5/5 (5) | 0.00 | 1.03 | 2 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | vlm:granite_docling | B | 2 | 0.034 | 0.034 | both | 0.042 | 1/1 (1) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | vlm:granite_docling | B | 2 | 0.039 | 0.039 | both | 0.051 | 1/1 (1) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | vlm:granite_docling | B | 3 | 0.133 | 0.133 | both | 0.158 | 11/10 (10) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | vlm:granite_docling | B | 1 | 0.092 | 0.092 | both | 0.143 | 2/1 (1) | 0.00 | 1.05 | 3 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | vlm:granite_docling | B | 2 | 0.222 | 0.223 | both | 0.226 | 2/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | vlm:granite_docling | B | 1 | 0.021 | 0.930 | both | 0.044 | 1/0 (0) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | vlm:granite_docling | B | 1 | 0.817 | 0.817 | none | 0.898 | 2/0 (0) | 0.00 | 0.09 | 3 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | vlm:granite_docling | B | 1 | 3.248 | 4.505 | head | 3.311 | 1/0 (0) | 0.00 | 1.01 | 3 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | vlm:granite_docling | B | 1 | 0.570 | 0.570 | both | 0.640 | 1/0 (0) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | vlm:granite_docling | B | 1 | 0.009 | 0.009 | both | 0.025 | 1/0 (0) | 0.00 | 1.03 | 2 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | vlm:granite_docling | B | 1 | 0.071 | 0.078 | both | 0.103 | 1/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | vlm:granite_docling | B | 2 | 0.038 | 0.038 | both | 0.098 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | vlm:lightonocr | A | 2 | 0.051 | 0.060 | both | 0.073 | 5/5 (4) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | vlm:lightonocr | A | 2 | 0.044 | 0.044 | both | 0.062 | 1/1 (1) | 0.00 | 1.00 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | vlm:lightonocr | A | 2 | 0.048 | 0.048 | both | 0.070 | 1/1 (1) | 0.00 | 1.00 | 1 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | vlm:lightonocr | B | 2 | 0.051 | 0.060 | both | 0.073 | 5/5 (4) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | vlm:lightonocr | B | 2 | 0.044 | 0.044 | both | 0.062 | 1/1 (1) | 0.00 | 1.00 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | vlm:lightonocr | B | 2 | 0.048 | 0.048 | both | 0.070 | 1/1 (1) | 0.00 | 1.00 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | vlm:lightonocr | B | 3 | 0.020 | 0.020 | both | 0.030 | 11/10 (10) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | vlm:lightonocr | B | 1 | 0.010 | 0.010 | both | 0.018 | 2/1 (1) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | vlm:lightonocr | B | 2 | 0.154 | 0.154 | both | 0.223 | 2/1 (1) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | vlm:lightonocr | B | 1 | 0.061 | 0.061 | both | 0.099 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | vlm:lightonocr | B | 1 | 0.022 | 0.035 | both | 0.041 | 2/1 (1) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | vlm:lightonocr | B | 1 | 0.068 | 0.198 | both | 0.117 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | vlm:lightonocr | B | 1 | 0.002 | 0.002 | both | 0.012 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | vlm:lightonocr | B | 1 | 0.001 | 0.001 | both | 0.006 | 1/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | vlm:lightonocr | B | 1 | 0.002 | 0.002 | both | 0.008 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | vlm:lightonocr | B | 2 | 0.002 | 0.002 | both | 0.012 | 1/0 (0) | 0.00 | 1.00 | 2 | yes | - |

## Skipped

- STATUTE-132-Pg5595 [vlm:glm_ocr/A]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [vlm:glm_ocr/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [vlm:granite_docling/A]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [vlm:granite_docling/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [vlm:lightonocr/A]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [vlm:lightonocr/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
