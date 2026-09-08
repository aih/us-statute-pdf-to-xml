# Benchmark wp9-comparison

Date: 2026-09-08T17:04:03. Spec: `benchmark/sample.yaml`. Rows: 397 (38 granules, profiles digital, easyocr, hybrid:digital, hybrid:rapidocr, hybrid:scanned, hybrid:textlayer, hybrid:vlm:glm_ocr, rapidocr, scanned, tesseract:psm4, tesseract:psm6, textlayer, vlm:glm_ocr, vlm:granite_docling, vlm:lightonocr). Judged: 0 ($0.00).

CER and WER are scored on the generated text clipped to the reference span (F3); `CER unclipped` is the score over the whole generated body. `Kept` is characters kept in the generated document over characters Docling produced (F2). Section recall matches sections by number and the first 40 characters.

## Profile by era

| Profile | Tier | Era | Granules | Mean CER | Median CER | Mean WER | Section recall | Id F1 | Clipped both | Min kept | XSD valid | s/page | Judge (n) | Judge mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| digital | B | digital-2003+ | 5 | 0.048 | 0.055 | 0.073 | 1.00 | 0.00 | 5/5 | 0.92 | 5/5 | 0.4 | 0 | - |
| easyocr | B | scanned-1951-2002 | 6 | 0.762 | 0.770 | 0.846 | 0.18 | 0.17 | 0/6 | 1.01 | 6/6 | 0.0 | 0 | - |
| easyocr | B | scanned-pre-1951 | 6 | 0.799 | 0.781 | 0.895 | 0.17 | 0.17 | 0/6 | 1.00 | 6/6 | 0.9 | 0 | - |
| hybrid:digital | B | digital-2003+ | 5 | 0.052 | 0.063 | 0.075 | 1.00 | 0.00 | 5/5 | 1.03 | 5/5 | 0.3 | 0 | - |
| hybrid:rapidocr | B | digital-2003+ | 5 | 0.084 | 0.088 | 0.100 | 0.96 | 0.00 | 5/5 | 1.03 | 5/5 | 0.0 | 0 | - |
| hybrid:rapidocr | B | scanned-1951-2002 | 15 | 0.091 | 0.080 | 0.137 | 0.99 | 0.60 | 14/15 | 1.04 | 15/15 | 0.0 | 0 | - |
| hybrid:rapidocr | B | scanned-pre-1951 | 18 | 0.183 | 0.090 | 0.235 | 0.94 | 0.67 | 14/18 | 1.01 | 18/18 | 0.1 | 0 | - |
| hybrid:scanned | B | scanned-1951-2002 | 15 | 0.238 | 0.160 | 0.354 | 0.75 | 0.60 | 14/15 | 1.04 | 15/15 | 0.0 | 0 | - |
| hybrid:scanned | B | scanned-pre-1951 | 18 | 0.111 | 0.050 | 0.169 | 0.94 | 0.67 | 16/18 | 1.07 | 18/18 | 0.1 | 0 | - |
| hybrid:textlayer | B | digital-2003+ | 5 | 0.052 | 0.063 | 0.075 | 1.00 | 0.00 | 5/5 | 1.03 | 5/5 | 0.0 | 0 | - |
| hybrid:textlayer | B | scanned-1951-2002 | 15 | 0.054 | 0.043 | 0.107 | 0.98 | 0.60 | 14/15 | 1.04 | 15/15 | 0.0 | 0 | - |
| hybrid:textlayer | B | scanned-pre-1951 | 18 | 0.140 | 0.033 | 0.182 | 0.94 | 0.67 | 14/18 | 1.07 | 18/18 | 0.1 | 0 | - |
| hybrid:vlm:glm_ocr | B | digital-2003+ | 3 | 0.034 | 0.042 | 0.040 | 1.00 | 0.00 | 3/3 | 1.03 | 3/3 | 0.0 | 0 | - |
| hybrid:vlm:glm_ocr | B | scanned-1951-2002 | 5 | 0.003 | 0.002 | 0.014 | 1.00 | 0.00 | 5/5 | 1.04 | 5/5 | 0.0 | 0 | - |
| hybrid:vlm:glm_ocr | B | scanned-pre-1951 | 5 | 0.002 | 0.002 | 0.005 | 1.00 | 0.00 | 5/5 | 1.98 | 5/5 | 0.9 | 0 | - |
| rapidocr | A | digital-2003+ | 5 | 0.076 | 0.077 | 0.092 | 0.86 | 0.00 | 5/5 | 1.01 | 5/5 | 0.3 | 0 | - |
| rapidocr | B | digital-2003+ | 5 | 0.079 | 0.084 | 0.099 | 0.96 | 0.00 | 5/5 | 1.01 | 5/5 | 0.0 | 0 | - |
| rapidocr | B | scanned-1951-2002 | 15 | 0.097 | 0.083 | 0.140 | 0.40 | 0.60 | 12/15 | 1.01 | 15/15 | 0.0 | 0 | - |
| rapidocr | B | scanned-pre-1951 | 18 | 0.245 | 0.134 | 0.305 | 0.31 | 0.67 | 13/18 | 1.01 | 18/18 | 0.1 | 0 | - |
| scanned | B | scanned-1951-2002 | 15 | 0.252 | 0.157 | 0.374 | 0.25 | 0.60 | 12/15 | 1.01 | 15/15 | 0.0 | 0 | - |
| scanned | B | scanned-pre-1951 | 18 | 0.181 | 0.078 | 0.248 | 0.29 | 0.67 | 15/18 | 1.01 | 18/18 | 0.1 | 0 | - |
| tesseract:psm4 | A | digital-2003+ | 5 | 0.046 | 0.053 | 0.062 | 1.00 | 0.00 | 5/5 | 1.01 | 5/5 | 0.4 | 0 | - |
| tesseract:psm4 | B | digital-2003+ | 5 | 0.046 | 0.053 | 0.060 | 1.00 | 0.00 | 5/5 | 1.01 | 5/5 | 0.0 | 0 | - |
| tesseract:psm4 | B | scanned-1951-2002 | 15 | 0.376 | 0.185 | 0.514 | 0.25 | 0.60 | 11/15 | 1.00 | 15/15 | 0.0 | 0 | - |
| tesseract:psm4 | B | scanned-pre-1951 | 18 | 0.189 | 0.089 | 0.255 | 0.30 | 0.67 | 14/18 | 1.01 | 18/18 | 0.1 | 0 | - |
| tesseract:psm6 | A | digital-2003+ | 5 | 0.046 | 0.053 | 0.063 | 1.00 | 0.00 | 5/5 | 1.01 | 5/5 | 0.3 | 0 | - |
| tesseract:psm6 | B | digital-2003+ | 5 | 0.046 | 0.053 | 0.061 | 1.00 | 0.00 | 5/5 | 1.01 | 5/5 | 0.0 | 0 | - |
| tesseract:psm6 | B | scanned-1951-2002 | 15 | 0.240 | 0.134 | 0.366 | 0.30 | 0.60 | 13/15 | 1.00 | 15/15 | 0.0 | 0 | - |
| tesseract:psm6 | B | scanned-pre-1951 | 18 | 0.263 | 0.122 | 0.342 | 0.29 | 0.67 | 14/18 | 1.01 | 18/18 | 0.1 | 0 | - |
| textlayer | A | digital-2003+ | 5 | 1.000 | 1.000 | 1.000 | 0.00 | 0.00 | 0/5 | 1.00 | 5/5 | 0.4 | 0 | - |
| textlayer | B | digital-2003+ | 5 | 0.048 | 0.055 | 0.073 | 1.00 | 0.00 | 5/5 | 0.92 | 5/5 | 0.0 | 0 | - |
| textlayer | B | scanned-1951-2002 | 15 | 0.060 | 0.055 | 0.112 | 0.44 | 0.60 | 13/15 | 1.00 | 15/15 | 0.0 | 0 | - |
| textlayer | B | scanned-pre-1951 | 18 | 0.201 | 0.039 | 0.250 | 0.32 | 0.67 | 13/18 | 1.01 | 18/18 | 0.1 | 0 | - |
| vlm:glm_ocr | A | digital-2003+ | 3 | 0.029 | 0.034 | 0.036 | 1.00 | 0.00 | 3/3 | 1.02 | 3/3 | 0.9 | 0 | - |
| vlm:glm_ocr | B | digital-2003+ | 3 | 0.029 | 0.034 | 0.037 | 1.00 | 0.00 | 3/3 | 1.02 | 3/3 | 0.0 | 0 | - |
| vlm:glm_ocr | B | scanned-1951-2002 | 5 | 0.006 | 0.005 | 0.010 | 0.48 | 0.00 | 5/5 | 1.01 | 5/5 | 0.0 | 0 | - |
| vlm:glm_ocr | B | scanned-pre-1951 | 5 | 0.002 | 0.002 | 0.008 | 0.00 | 0.00 | 5/5 | 1.01 | 5/5 | 0.9 | 0 | - |
| vlm:granite_docling | A | digital-2003+ | 3 | 0.060 | 0.081 | 0.064 | 1.00 | 0.00 | 1/3 | 1.02 | 3/3 | 0.9 | 0 | - |
| vlm:granite_docling | B | digital-2003+ | 3 | 0.057 | 0.081 | 0.060 | 1.00 | 0.00 | 1/3 | 1.02 | 3/3 | 0.0 | 0 | - |
| vlm:granite_docling | B | scanned-1951-2002 | 5 | 0.257 | 0.133 | 0.294 | 0.28 | 0.00 | 4/5 | 0.09 | 5/5 | 0.0 | 0 | - |
| vlm:granite_docling | B | scanned-pre-1951 | 5 | 0.787 | 0.071 | 0.835 | 0.00 | 0.00 | 4/5 | 1.01 | 5/5 | 0.9 | 0 | - |
| vlm:lightonocr | A | digital-2003+ | 3 | 0.100 | 0.068 | 0.123 | 0.93 | 0.00 | 2/3 | 1.00 | 3/3 | 0.9 | 0 | - |
| vlm:lightonocr | B | digital-2003+ | 3 | 0.100 | 0.068 | 0.123 | 0.93 | 0.00 | 2/3 | 1.00 | 3/3 | 0.0 | 0 | - |
| vlm:lightonocr | B | scanned-1951-2002 | 5 | 0.242 | 0.061 | 0.258 | 0.20 | 0.00 | 3/5 | 1.01 | 5/5 | 0.0 | 0 | - |
| vlm:lightonocr | B | scanned-pre-1951 | 5 | 0.022 | 0.002 | 0.043 | 0.00 | 0.00 | 5/5 | 1.01 | 5/5 | 0.9 | 0 | - |

## By granule

| Granule | Class | Profile | Tier | Pages | CER | CER unclipped | Clip | WER | Sections ref/gen (matched) | Id F1 | Kept | Warn | XSD | Judge |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| STATUTE-124-Pg2256 | PUBLICLAW | digital | B | 2 | 0.022 | 0.022 | both | 0.058 | 5/5 (5) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | digital | B | 2 | 0.055 | 0.055 | both | 0.078 | 1/1 (1) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | digital | B | 2 | 0.060 | 0.060 | both | 0.090 | 1/1 (1) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | digital | B | 4 | 0.059 | 0.059 | both | 0.083 | 2/2 (2) | 0.00 | 0.94 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | digital | B | 6 | 0.042 | 0.042 | both | 0.054 | 11/22 (11) | 0.00 | 0.96 | 2 | yes | - |
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
| STATUTE-124-Pg2256 | PUBLICLAW | hybrid:digital | B | 2 | 0.026 | 0.026 | both | 0.058 | 5/5 (5) | 0.00 | 1.16 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | hybrid:digital | B | 2 | 0.063 | 0.063 | both | 0.080 | 1/1 (1) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | hybrid:digital | B | 2 | 0.064 | 0.064 | both | 0.093 | 1/1 (1) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | hybrid:digital | B | 4 | 0.065 | 0.065 | both | 0.090 | 2/2 (2) | 0.00 | 1.07 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | hybrid:digital | B | 6 | 0.043 | 0.043 | both | 0.053 | 11/11 (11) | 0.00 | 1.07 | 1 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | hybrid:rapidocr | B | 2 | 0.042 | 0.042 | both | 0.055 | 5/5 (5) | 0.00 | 1.17 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | hybrid:rapidocr | B | 2 | 0.104 | 0.104 | both | 0.120 | 1/1 (1) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | hybrid:rapidocr | B | 2 | 0.088 | 0.088 | both | 0.117 | 1/1 (1) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | hybrid:rapidocr | B | 4 | 0.081 | 0.081 | both | 0.094 | 2/2 (2) | 0.00 | 1.07 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | hybrid:rapidocr | B | 6 | 0.102 | 0.102 | both | 0.117 | 11/11 (9) | 0.00 | 1.11 | 2 | yes | - |
| STATUTE-72-Pg1572 | PUBLICLAW | hybrid:rapidocr | B | 8 | 0.075 | 0.075 | both | 0.086 | 6/6 (5) | 0.00 | 1.04 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | hybrid:rapidocr | B | 3 | 0.082 | 0.082 | both | 0.118 | 11/11 (11) | 0.00 | 1.04 | 2 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | hybrid:rapidocr | B | 1 | 0.002 | 0.002 | both | 0.018 | 2/2 (2) | 0.00 | 4.52 | 0 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | hybrid:rapidocr | B | 2 | 0.187 | 0.187 | head | 0.271 | 2/2 (2) | 0.00 | 4.24 | 1 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | hybrid:rapidocr | B | 1 | 0.009 | 0.009 | both | 0.066 | 1/1 (1) | 0.00 | 6.77 | 0 | yes | - |
| STATUTE-72-PgB14 | HCONRES | hybrid:rapidocr | B | 1 | 0.107 | 0.107 | both | 0.146 | 1/1 (1) | 1.00 | 3.06 | 1 | yes | - |
| STATUTE-72-PgB21 | SCONRES | hybrid:rapidocr | B | 1 | 0.002 | 0.002 | both | 0.018 | 1/1 (1) | 1.00 | 3.59 | 1 | yes | - |
| STATUTE-72-PgB23-3 | SCONRES | hybrid:rapidocr | B | 1 | 0.004 | 0.004 | both | 0.035 | 1/1 (1) | 1.00 | 5.64 | 1 | yes | - |
| STATUTE-72-PgB5 | HCONRES | hybrid:rapidocr | B | 1 | 0.159 | 0.159 | both | 0.200 | 1/1 (1) | 1.00 | 7.12 | 1 | yes | - |
| STATUTE-72-PgC40 | PROCLAMATION | hybrid:rapidocr | B | 1 | 0.082 | 0.083 | both | 0.098 | 0/0 (0) | 1.00 | 1.51 | 3 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | hybrid:rapidocr | B | 1 | 0.205 | 0.205 | both | 0.268 | 2/2 (2) | 0.00 | 1.88 | 1 | yes | - |
| STATUTE-85-Pg864 | HCONRES | hybrid:rapidocr | B | 1 | 0.322 | 0.322 | both | 0.500 | 1/1 (1) | 1.00 | 7.03 | 2 | yes | - |
| STATUTE-85-Pg868-5 | SCONRES | hybrid:rapidocr | B | 2 | 0.039 | 0.039 | both | 0.072 | 2/2 (2) | 1.00 | 1.92 | 1 | yes | - |
| STATUTE-85-Pg906 | PROCLAMATION | hybrid:rapidocr | B | 2 | 0.009 | 0.015 | both | 0.073 | 0/0 (0) | 1.00 | 1.69 | 1 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | hybrid:rapidocr | B | 1 | 0.080 | 0.092 | both | 0.089 | 0/0 (0) | 1.00 | 1.06 | 2 | yes | - |
| STATUTE-10-Pg1177-2 | PROCLAMATION | hybrid:rapidocr | B | 2 | 0.683 | 0.683 | none | 0.837 | 0/0 (0) | 1.00 | 2.80 | 4 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | hybrid:rapidocr | B | 1 | 0.202 | 0.200 | both | 0.282 | 1/1 (1) | 0.00 | 5.96 | 1 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | hybrid:rapidocr | B | 1 | 0.007 | 0.007 | both | 0.035 | 1/1 (1) | 0.00 | 7.98 | 0 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | hybrid:rapidocr | B | 1 | 0.130 | 0.130 | both | 0.160 | 1/1 (1) | 0.00 | 4.25 | 0 | yes | - |
| STATUTE-10-Pg954 | TREATY | hybrid:rapidocr | B | 6 | 0.168 | 0.168 | tail | 0.226 | 1/1 (1) | 1.00 | 1.11 | 3 | yes | - |
| STATUTE-10-Pg972 | TREATY | hybrid:rapidocr | B | 1 | 0.030 | 0.030 | both | 0.062 | 0/0 (0) | 1.00 | 1.01 | 1 | yes | - |
| STATUTE-39-Pg1058 | PUBLICLAW | hybrid:rapidocr | B | 12 | 0.050 | 0.050 | both | 0.065 | 5/5 (5) | 0.00 | 1.17 | 2 | yes | - |
| STATUTE-39-Pg1599-4 | HCONRES | hybrid:rapidocr | B | 1 | 0.193 | 0.193 | both | 0.267 | 1/1 (1) | 1.00 | 4.80 | 1 | yes | - |
| STATUTE-39-Pg1600-3 | SCONRES | hybrid:rapidocr | B | 1 | 0.601 | 0.601 | none | 0.752 | 1/1 (1) | 1.00 | 3.99 | 3 | yes | - |
| STATUTE-39-Pg1603-4 | SCONRES | hybrid:rapidocr | B | 1 | 0.570 | 0.570 | none | 0.705 | 1/1 (0) | 1.00 | 4.81 | 3 | yes | - |
| STATUTE-39-Pg1604-3 | HCONRES | hybrid:rapidocr | B | 1 | 0.032 | 0.032 | both | 0.057 | 1/1 (1) | 1.00 | 5.98 | 2 | yes | - |
| STATUTE-39-Pg1606 | SCONRES | hybrid:rapidocr | B | 1 | 0.015 | 0.015 | both | 0.017 | 1/1 (1) | 1.00 | 1.97 | 1 | yes | - |
| STATUTE-39-Pg1606-4 | HCONRES | hybrid:rapidocr | B | 2 | 0.037 | 0.037 | both | 0.044 | 1/1 (1) | 1.00 | 9.46 | 1 | yes | - |
| STATUTE-39-Pg1645 | TREATY | hybrid:rapidocr | B | 5 | 0.351 | 0.351 | both | 0.357 | 0/0 (0) | 1.00 | 1.42 | 2 | yes | - |
| STATUTE-39-Pg1738 | PROCLAMATION | hybrid:rapidocr | B | 3 | 0.042 | 0.040 | both | 0.058 | 0/0 (0) | 1.00 | 6.63 | 3 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | hybrid:rapidocr | B | 1 | 0.047 | 0.047 | both | 0.051 | 0/0 (0) | 1.00 | 1.28 | 1 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | hybrid:rapidocr | B | 1 | 0.006 | 0.006 | both | 0.047 | 1/1 (1) | 0.00 | 2.02 | 0 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | hybrid:rapidocr | B | 2 | 0.138 | 0.137 | both | 0.209 | 1/1 (1) | 0.00 | 3.84 | 1 | yes | - |
| STATUTE-72-Pg1572 | PUBLICLAW | hybrid:scanned | B | 8 | 0.318 | 0.314 | both | 0.417 | 6/6 (3) | 0.00 | 1.06 | 2 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | hybrid:scanned | B | 3 | 0.170 | 0.170 | both | 0.252 | 11/11 (9) | 0.00 | 1.04 | 2 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | hybrid:scanned | B | 1 | 0.139 | 0.139 | both | 0.188 | 2/2 (2) | 0.00 | 4.50 | 2 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | hybrid:scanned | B | 2 | 0.252 | 0.252 | both | 0.308 | 2/2 (2) | 0.00 | 4.40 | 1 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | hybrid:scanned | B | 1 | 0.207 | 0.207 | both | 0.319 | 1/1 (1) | 0.00 | 7.52 | 1 | yes | - |
| STATUTE-72-PgB14 | HCONRES | hybrid:scanned | B | 1 | 1.154 | 1.154 | none | 1.942 | 1/1 (0) | 1.00 | 1.62 | 4 | yes | - |
| STATUTE-72-PgB21 | SCONRES | hybrid:scanned | B | 1 | 0.117 | 0.117 | both | 0.136 | 1/1 (0) | 1.00 | 3.07 | 1 | yes | - |
| STATUTE-72-PgB23-3 | SCONRES | hybrid:scanned | B | 1 | 0.386 | 0.386 | both | 0.523 | 1/1 (1) | 1.00 | 6.58 | 1 | yes | - |
| STATUTE-72-PgB5 | HCONRES | hybrid:scanned | B | 1 | 0.075 | 0.075 | both | 0.100 | 1/1 (1) | 1.00 | 3.22 | 1 | yes | - |
| STATUTE-72-PgC40 | PROCLAMATION | hybrid:scanned | B | 1 | 0.125 | 0.127 | both | 0.136 | 0/0 (0) | 1.00 | 1.51 | 3 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | hybrid:scanned | B | 1 | 0.156 | 0.156 | both | 0.258 | 2/2 (2) | 0.00 | 1.89 | 1 | yes | - |
| STATUTE-85-Pg864 | HCONRES | hybrid:scanned | B | 1 | 0.160 | 0.160 | both | 0.291 | 1/1 (0) | 1.00 | 5.22 | 1 | yes | - |
| STATUTE-85-Pg868-5 | SCONRES | hybrid:scanned | B | 2 | 0.311 | 0.311 | both | 0.429 | 2/2 (2) | 1.00 | 2.24 | 4 | yes | - |
| STATUTE-85-Pg906 | PROCLAMATION | hybrid:scanned | B | 2 | 0.005 | 0.012 | both | 0.013 | 0/0 (0) | 1.00 | 1.57 | 2 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | hybrid:scanned | B | 1 | 0.001 | 0.013 | both | 0.004 | 0/0 (0) | 1.00 | 1.06 | 2 | yes | - |
| STATUTE-10-Pg1177-2 | PROCLAMATION | hybrid:scanned | B | 2 | 0.180 | 0.180 | both | 0.306 | 0/0 (0) | 1.00 | 3.38 | 1 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | hybrid:scanned | B | 1 | 0.090 | 0.090 | both | 0.184 | 1/1 (1) | 0.00 | 3.12 | 0 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | hybrid:scanned | B | 1 | 0.034 | 0.048 | both | 0.105 | 1/1 (1) | 0.00 | 6.73 | 0 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | hybrid:scanned | B | 1 | 0.028 | 0.028 | both | 0.062 | 1/1 (1) | 0.00 | 2.28 | 0 | yes | - |
| STATUTE-10-Pg954 | TREATY | hybrid:scanned | B | 6 | 0.130 | 0.131 | tail | 0.218 | 1/1 (1) | 1.00 | 1.13 | 3 | yes | - |
| STATUTE-10-Pg972 | TREATY | hybrid:scanned | B | 1 | 0.050 | 0.050 | both | 0.128 | 0/0 (0) | 1.00 | 1.97 | 2 | yes | - |
| STATUTE-39-Pg1058 | PUBLICLAW | hybrid:scanned | B | 12 | 0.104 | 0.104 | both | 0.151 | 5/5 (5) | 0.00 | 1.23 | 2 | yes | - |
| STATUTE-39-Pg1599-4 | HCONRES | hybrid:scanned | B | 1 | 0.047 | 0.047 | both | 0.081 | 1/1 (1) | 1.00 | 5.28 | 1 | yes | - |
| STATUTE-39-Pg1600-3 | SCONRES | hybrid:scanned | B | 1 | 0.070 | 0.070 | both | 0.124 | 1/1 (1) | 1.00 | 1.92 | 1 | yes | - |
| STATUTE-39-Pg1603-4 | SCONRES | hybrid:scanned | B | 1 | 0.040 | 0.040 | both | 0.079 | 1/1 (1) | 1.00 | 4.25 | 1 | yes | - |
| STATUTE-39-Pg1604-3 | HCONRES | hybrid:scanned | B | 1 | 0.522 | 0.522 | head | 0.632 | 1/1 (0) | 1.00 | 6.53 | 3 | yes | - |
| STATUTE-39-Pg1606 | SCONRES | hybrid:scanned | B | 1 | 0.032 | 0.032 | both | 0.043 | 1/1 (1) | 1.00 | 1.57 | 1 | yes | - |
| STATUTE-39-Pg1606-4 | HCONRES | hybrid:scanned | B | 2 | 0.042 | 0.042 | both | 0.062 | 1/1 (1) | 1.00 | 2.55 | 1 | yes | - |
| STATUTE-39-Pg1645 | TREATY | hybrid:scanned | B | 5 | 0.390 | 0.391 | both | 0.431 | 0/0 (0) | 1.00 | 1.48 | 2 | yes | - |
| STATUTE-39-Pg1738 | PROCLAMATION | hybrid:scanned | B | 3 | 0.010 | 0.010 | both | 0.019 | 0/0 (0) | 1.00 | 7.03 | 3 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | hybrid:scanned | B | 1 | 0.049 | 0.049 | both | 0.090 | 0/0 (0) | 1.00 | 1.07 | 1 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | hybrid:scanned | B | 1 | 0.134 | 0.135 | both | 0.233 | 1/1 (1) | 0.00 | 1.60 | 0 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | hybrid:scanned | B | 2 | 0.051 | 0.050 | both | 0.095 | 1/1 (1) | 0.00 | 4.12 | 1 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | hybrid:textlayer | B | 2 | 0.026 | 0.026 | both | 0.058 | 5/5 (5) | 0.00 | 1.16 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | hybrid:textlayer | B | 2 | 0.063 | 0.063 | both | 0.080 | 1/1 (1) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | hybrid:textlayer | B | 2 | 0.064 | 0.064 | both | 0.093 | 1/1 (1) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | hybrid:textlayer | B | 4 | 0.065 | 0.065 | both | 0.090 | 2/2 (2) | 0.00 | 1.07 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | hybrid:textlayer | B | 6 | 0.043 | 0.043 | both | 0.053 | 11/11 (11) | 0.00 | 1.07 | 1 | yes | - |
| STATUTE-72-Pg1572 | PUBLICLAW | hybrid:textlayer | B | 8 | 0.065 | 0.065 | both | 0.117 | 6/6 (5) | 0.00 | 1.04 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | hybrid:textlayer | B | 3 | 0.072 | 0.072 | both | 0.121 | 11/11 (10) | 0.00 | 1.04 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | hybrid:textlayer | B | 1 | 0.007 | 0.007 | both | 0.054 | 2/2 (2) | 0.00 | 4.54 | 0 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | hybrid:textlayer | B | 2 | 0.207 | 0.207 | head | 0.260 | 2/2 (2) | 0.00 | 4.25 | 1 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | hybrid:textlayer | B | 1 | 0.016 | 0.016 | both | 0.121 | 1/1 (1) | 0.00 | 2.09 | 0 | yes | - |
| STATUTE-72-PgB14 | HCONRES | hybrid:textlayer | B | 1 | 0.043 | 0.043 | both | 0.102 | 1/1 (1) | 1.00 | 3.21 | 1 | yes | - |
| STATUTE-72-PgB21 | SCONRES | hybrid:textlayer | B | 1 | 0.011 | 0.011 | both | 0.045 | 1/1 (1) | 1.00 | 3.60 | 1 | yes | - |
| STATUTE-72-PgB23-3 | SCONRES | hybrid:textlayer | B | 1 | 0.008 | 0.008 | both | 0.058 | 1/1 (1) | 1.00 | 5.51 | 1 | yes | - |
| STATUTE-72-PgB5 | HCONRES | hybrid:textlayer | B | 1 | 0.139 | 0.137 | both | 0.222 | 1/1 (1) | 1.00 | 3.19 | 1 | yes | - |
| STATUTE-72-PgC40 | PROCLAMATION | hybrid:textlayer | B | 1 | 0.108 | 0.108 | both | 0.129 | 0/0 (0) | 1.00 | 1.47 | 3 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | hybrid:textlayer | B | 1 | 0.004 | 0.004 | both | 0.025 | 2/2 (2) | 0.00 | 1.87 | 0 | yes | - |
| STATUTE-85-Pg864 | HCONRES | hybrid:textlayer | B | 1 | 0.072 | 0.072 | both | 0.233 | 1/1 (1) | 1.00 | 2.44 | 1 | yes | - |
| STATUTE-85-Pg868-5 | SCONRES | hybrid:textlayer | B | 2 | 0.009 | 0.009 | both | 0.035 | 2/2 (2) | 1.00 | 1.94 | 1 | yes | - |
| STATUTE-85-Pg906 | PROCLAMATION | hybrid:textlayer | B | 2 | 0.003 | 0.011 | both | 0.023 | 0/0 (0) | 1.00 | 1.72 | 2 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | hybrid:textlayer | B | 1 | 0.044 | 0.044 | both | 0.066 | 0/0 (0) | 1.00 | 1.11 | 2 | yes | - |
| STATUTE-10-Pg1177-2 | PROCLAMATION | hybrid:textlayer | B | 2 | 0.622 | 0.622 | tail | 0.823 | 0/0 (0) | 1.00 | 3.27 | 3 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | hybrid:textlayer | B | 1 | 0.004 | 0.004 | both | 0.010 | 1/1 (1) | 0.00 | 1.14 | 0 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | hybrid:textlayer | B | 1 | 0.000 | 0.000 | both | 0.000 | 1/1 (1) | 0.00 | 7.95 | 0 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | hybrid:textlayer | B | 1 | 0.000 | 0.000 | both | 0.000 | 1/1 (1) | 0.00 | 2.26 | 0 | yes | - |
| STATUTE-10-Pg954 | TREATY | hybrid:textlayer | B | 6 | 0.113 | 0.113 | tail | 0.172 | 1/1 (1) | 1.00 | 1.12 | 3 | yes | - |
| STATUTE-10-Pg972 | TREATY | hybrid:textlayer | B | 1 | 0.006 | 0.005 | both | 0.037 | 0/0 (0) | 1.00 | 1.97 | 2 | yes | - |
| STATUTE-39-Pg1058 | PUBLICLAW | hybrid:textlayer | B | 12 | 0.035 | 0.035 | both | 0.043 | 5/5 (5) | 0.00 | 1.18 | 1 | yes | - |
| STATUTE-39-Pg1599-4 | HCONRES | hybrid:textlayer | B | 1 | 0.042 | 0.042 | both | 0.070 | 1/1 (1) | 1.00 | 5.27 | 1 | yes | - |
| STATUTE-39-Pg1600-3 | SCONRES | hybrid:textlayer | B | 1 | 0.577 | 0.577 | none | 0.723 | 1/1 (1) | 1.00 | 4.17 | 3 | yes | - |
| STATUTE-39-Pg1603-4 | SCONRES | hybrid:textlayer | B | 1 | 0.570 | 0.570 | none | 0.705 | 1/1 (0) | 1.00 | 4.80 | 3 | yes | - |
| STATUTE-39-Pg1604-3 | HCONRES | hybrid:textlayer | B | 1 | 0.030 | 0.030 | both | 0.046 | 1/1 (1) | 1.00 | 5.67 | 1 | yes | - |
| STATUTE-39-Pg1606 | SCONRES | hybrid:textlayer | B | 1 | 0.015 | 0.015 | both | 0.017 | 1/1 (1) | 1.00 | 1.97 | 1 | yes | - |
| STATUTE-39-Pg1606-4 | HCONRES | hybrid:textlayer | B | 2 | 0.039 | 0.038 | both | 0.053 | 1/1 (1) | 1.00 | 9.42 | 1 | yes | - |
| STATUTE-39-Pg1645 | TREATY | hybrid:textlayer | B | 5 | 0.408 | 0.408 | both | 0.416 | 0/0 (0) | 1.00 | 1.47 | 2 | yes | - |
| STATUTE-39-Pg1738 | PROCLAMATION | hybrid:textlayer | B | 3 | 0.001 | 0.004 | both | 0.003 | 0/0 (0) | 1.00 | 6.61 | 3 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | hybrid:textlayer | B | 1 | 0.007 | 0.011 | both | 0.025 | 0/0 (0) | 1.00 | 1.07 | 1 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | hybrid:textlayer | B | 1 | 0.009 | 0.009 | both | 0.059 | 1/1 (1) | 0.00 | 1.98 | 0 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | hybrid:textlayer | B | 2 | 0.040 | 0.040 | both | 0.071 | 1/1 (1) | 0.00 | 4.18 | 0 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | hybrid:vlm:glm_ocr | B | 2 | 0.019 | 0.019 | both | 0.023 | 5/5 (5) | 0.00 | 1.25 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | hybrid:vlm:glm_ocr | B | 2 | 0.042 | 0.042 | both | 0.044 | 1/1 (1) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | hybrid:vlm:glm_ocr | B | 2 | 0.042 | 0.042 | both | 0.053 | 1/1 (1) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | hybrid:vlm:glm_ocr | B | 3 | 0.010 | 0.010 | both | 0.012 | 11/11 (11) | 0.00 | 1.04 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | hybrid:vlm:glm_ocr | B | 1 | 0.002 | 0.002 | both | 0.018 | 2/2 (2) | 0.00 | 4.53 | 0 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | hybrid:vlm:glm_ocr | B | 2 | 0.001 | 0.001 | both | 0.010 | 2/2 (2) | 0.00 | 4.28 | 0 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | hybrid:vlm:glm_ocr | B | 1 | 0.002 | 0.002 | both | 0.022 | 1/1 (1) | 0.00 | 6.90 | 0 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | hybrid:vlm:glm_ocr | B | 1 | 0.001 | 0.001 | both | 0.010 | 2/2 (2) | 0.00 | 1.86 | 0 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | hybrid:vlm:glm_ocr | B | 1 | 0.004 | 0.004 | both | 0.010 | 1/1 (1) | 0.00 | 6.61 | 0 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | hybrid:vlm:glm_ocr | B | 1 | 0.000 | 0.000 | both | 0.000 | 1/1 (1) | 0.00 | 9.10 | 0 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | hybrid:vlm:glm_ocr | B | 1 | 0.000 | 0.000 | both | 0.000 | 1/1 (1) | 0.00 | 4.11 | 0 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | hybrid:vlm:glm_ocr | B | 1 | 0.002 | 0.002 | both | 0.003 | 1/1 (1) | 0.00 | 1.98 | 0 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | hybrid:vlm:glm_ocr | B | 2 | 0.002 | 0.002 | both | 0.012 | 1/1 (1) | 0.00 | 4.01 | 1 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | rapidocr | A | 2 | 0.038 | 0.038 | both | 0.043 | 5/5 (5) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | rapidocr | A | 2 | 0.077 | 0.077 | both | 0.100 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | rapidocr | A | 2 | 0.104 | 0.104 | both | 0.137 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | rapidocr | A | 4 | 0.097 | 0.097 | both | 0.108 | 2/2 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | rapidocr | A | 6 | 0.061 | 0.061 | both | 0.073 | 11/20 (9) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | rapidocr | B | 2 | 0.038 | 0.038 | both | 0.045 | 5/5 (5) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | rapidocr | B | 2 | 0.096 | 0.096 | both | 0.118 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | rapidocr | B | 2 | 0.084 | 0.084 | both | 0.115 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | rapidocr | B | 4 | 0.104 | 0.104 | both | 0.127 | 2/2 (2) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | rapidocr | B | 6 | 0.074 | 0.074 | both | 0.090 | 11/20 (9) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-Pg1572 | PUBLICLAW | rapidocr | B | 8 | 0.071 | 0.071 | both | 0.077 | 6/5 (4) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | rapidocr | B | 3 | 0.083 | 0.083 | both | 0.120 | 11/9 (9) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | rapidocr | B | 1 | 0.010 | 0.010 | both | 0.018 | 2/1 (1) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | rapidocr | B | 2 | 0.191 | 0.191 | head | 0.277 | 2/1 (1) | 0.00 | 1.01 | 3 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | rapidocr | B | 1 | 0.019 | 0.056 | both | 0.088 | 1/0 (0) | 0.00 | 1.02 | 3 | yes | - |
| STATUTE-72-PgB14 | HCONRES | rapidocr | B | 1 | 0.109 | 0.109 | both | 0.153 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-72-PgB21 | SCONRES | rapidocr | B | 1 | 0.000 | 0.000 | both | 0.000 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-72-PgB23-3 | SCONRES | rapidocr | B | 1 | 0.002 | 0.002 | both | 0.012 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgB5 | HCONRES | rapidocr | B | 1 | 0.161 | 0.161 | both | 0.189 | 1/0 (0) | 1.00 | 1.02 | 3 | yes | - |
| STATUTE-72-PgC40 | PROCLAMATION | rapidocr | B | 1 | 0.084 | 0.122 | tail | 0.105 | 0/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | rapidocr | B | 1 | 0.205 | 0.205 | both | 0.271 | 2/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-85-Pg864 | HCONRES | rapidocr | B | 1 | 0.361 | 0.361 | head | 0.547 | 1/0 (0) | 1.00 | 1.02 | 0 | yes | - |
| STATUTE-85-Pg868-5 | SCONRES | rapidocr | B | 2 | 0.045 | 0.045 | both | 0.079 | 2/1 (1) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg906 | PROCLAMATION | rapidocr | B | 2 | 0.008 | 0.030 | both | 0.067 | 0/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | rapidocr | B | 1 | 0.100 | 0.114 | both | 0.105 | 0/0 (0) | 1.00 | 1.04 | 0 | yes | - |
| STATUTE-10-Pg1177-2 | PROCLAMATION | rapidocr | B | 2 | 0.687 | 0.687 | none | 0.854 | 0/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | rapidocr | B | 1 | 0.222 | 0.228 | both | 0.320 | 1/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | rapidocr | B | 1 | 0.010 | 0.010 | both | 0.047 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | rapidocr | B | 1 | 0.131 | 0.131 | both | 0.167 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-10-Pg954 | TREATY | rapidocr | B | 6 | 0.218 | 0.218 | tail | 0.299 | 1/0 (0) | 1.00 | 1.01 | 1 | yes | - |
| STATUTE-10-Pg972 | TREATY | rapidocr | B | 1 | 0.030 | 0.863 | both | 0.062 | 0/0 (0) | 1.00 | 1.03 | 1 | yes | - |
| STATUTE-39-Pg1058 | PUBLICLAW | rapidocr | B | 12 | 0.050 | 0.051 | both | 0.065 | 5/3 (3) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-39-Pg1599-4 | HCONRES | rapidocr | B | 1 | 0.191 | 0.191 | both | 0.244 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-39-Pg1600-3 | SCONRES | rapidocr | B | 1 | 0.608 | 0.608 | none | 0.752 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1603-4 | SCONRES | rapidocr | B | 1 | 0.569 | 0.569 | none | 0.691 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1604-3 | HCONRES | rapidocr | B | 1 | 0.030 | 0.030 | both | 0.046 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1606 | SCONRES | rapidocr | B | 1 | 0.015 | 0.015 | both | 0.013 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1606-4 | HCONRES | rapidocr | B | 2 | 0.035 | 0.035 | both | 0.027 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1645 | TREATY | rapidocr | B | 5 | 0.644 | 0.663 | both | 0.789 | 0/0 (0) | 1.00 | 1.01 | 0 | yes | - |
| STATUTE-39-Pg1738 | PROCLAMATION | rapidocr | B | 3 | 0.784 | 0.784 | head | 0.813 | 0/0 (0) | 1.00 | 1.03 | 0 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | rapidocr | B | 1 | 0.046 | 0.064 | both | 0.051 | 0/0 (0) | 1.00 | 1.02 | 0 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | rapidocr | B | 1 | 0.007 | 0.007 | both | 0.047 | 1/0 (0) | 0.00 | 1.01 | 3 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | rapidocr | B | 2 | 0.137 | 0.137 | both | 0.199 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
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
| STATUTE-124-Pg2256 | PUBLICLAW | tesseract:psm4 | A | 2 | 0.020 | 0.020 | both | 0.043 | 5/5 (5) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | tesseract:psm4 | A | 2 | 0.053 | 0.053 | both | 0.070 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | tesseract:psm4 | A | 2 | 0.058 | 0.058 | both | 0.081 | 1/1 (1) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | tesseract:psm4 | A | 4 | 0.058 | 0.058 | both | 0.068 | 2/2 (2) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | tesseract:psm4 | A | 6 | 0.041 | 0.041 | both | 0.046 | 11/22 (11) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | tesseract:psm4 | B | 2 | 0.019 | 0.019 | both | 0.035 | 5/5 (5) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | tesseract:psm4 | B | 2 | 0.053 | 0.053 | both | 0.070 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | tesseract:psm4 | B | 2 | 0.058 | 0.058 | both | 0.081 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | tesseract:psm4 | B | 4 | 0.058 | 0.058 | both | 0.070 | 2/2 (2) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | tesseract:psm4 | B | 6 | 0.041 | 0.041 | both | 0.044 | 11/22 (11) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-Pg1572 | PUBLICLAW | tesseract:psm4 | B | 8 | 0.317 | 0.317 | both | 0.416 | 6/4 (3) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | tesseract:psm4 | B | 3 | 0.185 | 0.185 | both | 0.271 | 11/3 (3) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | tesseract:psm4 | B | 1 | 0.116 | 0.116 | both | 0.170 | 2/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | tesseract:psm4 | B | 2 | 0.643 | 0.895 | head | 0.801 | 2/0 (0) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | tesseract:psm4 | B | 1 | 1.566 | 1.566 | head | 1.824 | 1/0 (0) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-PgB14 | HCONRES | tesseract:psm4 | B | 1 | 1.231 | 1.231 | none | 2.095 | 1/0 (0) | 1.00 | 1.03 | 1 | yes | - |
| STATUTE-72-PgB21 | SCONRES | tesseract:psm4 | B | 1 | 0.140 | 0.140 | both | 0.173 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-72-PgB23-3 | SCONRES | tesseract:psm4 | B | 1 | 0.390 | 0.390 | both | 0.512 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgB5 | HCONRES | tesseract:psm4 | B | 1 | 0.079 | 1.052 | both | 0.122 | 1/0 (0) | 1.00 | 1.01 | 3 | yes | - |
| STATUTE-72-PgC40 | PROCLAMATION | tesseract:psm4 | B | 1 | 0.123 | 0.139 | tail | 0.142 | 0/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | tesseract:psm4 | B | 1 | 0.155 | 0.155 | both | 0.248 | 2/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-85-Pg864 | HCONRES | tesseract:psm4 | B | 1 | 0.309 | 0.309 | both | 0.430 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg868-5 | SCONRES | tesseract:psm4 | B | 2 | 0.355 | 0.355 | both | 0.464 | 2/1 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg906 | PROCLAMATION | tesseract:psm4 | B | 2 | 0.015 | 0.022 | both | 0.017 | 0/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | tesseract:psm4 | B | 1 | 0.021 | 0.034 | both | 0.019 | 0/0 (0) | 1.00 | 1.04 | 0 | yes | - |
| STATUTE-10-Pg1177-2 | PROCLAMATION | tesseract:psm4 | B | 2 | 0.417 | 0.417 | head | 0.566 | 0/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | tesseract:psm4 | B | 1 | 0.092 | 1.216 | both | 0.175 | 1/0 (0) | 0.00 | 1.03 | 3 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | tesseract:psm4 | B | 1 | 0.026 | 0.055 | both | 0.105 | 1/0 (0) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | tesseract:psm4 | B | 1 | 0.041 | 0.790 | both | 0.080 | 1/0 (0) | 0.00 | 1.02 | 0 | yes | - |
| STATUTE-10-Pg954 | TREATY | tesseract:psm4 | B | 6 | 0.166 | 0.166 | tail | 0.278 | 1/0 (0) | 1.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg972 | TREATY | tesseract:psm4 | B | 1 | 0.088 | 0.088 | both | 0.165 | 0/0 (0) | 1.00 | 1.03 | 0 | yes | - |
| STATUTE-39-Pg1058 | PUBLICLAW | tesseract:psm4 | B | 12 | 0.095 | 0.095 | both | 0.131 | 5/2 (2) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-39-Pg1599-4 | HCONRES | tesseract:psm4 | B | 1 | 0.044 | 0.044 | both | 0.070 | 1/0 (0) | 1.00 | 1.03 | 3 | yes | - |
| STATUTE-39-Pg1600-3 | SCONRES | tesseract:psm4 | B | 1 | 0.063 | 0.888 | both | 0.131 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-39-Pg1603-4 | SCONRES | tesseract:psm4 | B | 1 | 0.038 | 0.669 | both | 0.058 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-39-Pg1604-3 | HCONRES | tesseract:psm4 | B | 1 | 0.558 | 0.558 | head | 0.690 | 1/0 (0) | 1.00 | 1.03 | 1 | yes | - |
| STATUTE-39-Pg1606 | SCONRES | tesseract:psm4 | B | 1 | 0.030 | 0.286 | both | 0.043 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-39-Pg1606-4 | HCONRES | tesseract:psm4 | B | 2 | 0.042 | 2.722 | both | 0.053 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1645 | TREATY | tesseract:psm4 | B | 5 | 0.665 | 0.690 | both | 0.830 | 0/0 (0) | 1.00 | 1.02 | 0 | yes | - |
| STATUTE-39-Pg1738 | PROCLAMATION | tesseract:psm4 | B | 3 | 0.789 | 0.789 | head | 0.798 | 0/0 (0) | 1.00 | 1.03 | 0 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | tesseract:psm4 | B | 1 | 0.090 | 0.300 | both | 0.121 | 0/0 (0) | 1.00 | 1.02 | 1 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | tesseract:psm4 | B | 1 | 0.106 | 0.288 | both | 0.209 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | tesseract:psm4 | B | 2 | 0.045 | 0.045 | both | 0.089 | 1/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | tesseract:psm6 | A | 2 | 0.020 | 0.020 | both | 0.043 | 5/5 (5) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | tesseract:psm6 | A | 2 | 0.053 | 0.053 | both | 0.070 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | tesseract:psm6 | A | 2 | 0.059 | 0.059 | both | 0.088 | 1/1 (1) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | tesseract:psm6 | A | 4 | 0.058 | 0.058 | both | 0.068 | 2/2 (2) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | tesseract:psm6 | A | 6 | 0.041 | 0.041 | both | 0.045 | 11/22 (11) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | tesseract:psm6 | B | 2 | 0.019 | 0.019 | both | 0.035 | 5/5 (5) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | tesseract:psm6 | B | 2 | 0.053 | 0.053 | both | 0.070 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | tesseract:psm6 | B | 2 | 0.058 | 0.059 | both | 0.084 | 1/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | tesseract:psm6 | B | 4 | 0.058 | 0.058 | both | 0.070 | 2/2 (2) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | tesseract:psm6 | B | 6 | 0.041 | 0.041 | both | 0.044 | 11/22 (11) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-Pg1572 | PUBLICLAW | tesseract:psm6 | B | 8 | 0.222 | 0.222 | both | 0.303 | 6/5 (3) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | tesseract:psm6 | B | 3 | 0.134 | 0.134 | both | 0.203 | 11/5 (5) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | tesseract:psm6 | B | 1 | 0.319 | 1.700 | both | 0.482 | 2/0 (0) | 0.00 | 1.00 | 0 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | tesseract:psm6 | B | 2 | 0.313 | 0.313 | both | 0.349 | 2/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | tesseract:psm6 | B | 1 | 0.065 | 0.065 | both | 0.088 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-72-PgB14 | HCONRES | tesseract:psm6 | B | 1 | 1.498 | 1.498 | none | 2.569 | 1/0 (0) | 1.00 | 1.03 | 1 | yes | - |
| STATUTE-72-PgB21 | SCONRES | tesseract:psm6 | B | 1 | 0.071 | 0.071 | both | 0.082 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-72-PgB23-3 | SCONRES | tesseract:psm6 | B | 1 | 0.239 | 0.239 | both | 0.349 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgB5 | HCONRES | tesseract:psm6 | B | 1 | 0.075 | 4.599 | both | 0.122 | 1/0 (0) | 1.00 | 1.02 | 1 | yes | - |
| STATUTE-72-PgC40 | PROCLAMATION | tesseract:psm6 | B | 1 | 0.156 | 0.172 | tail | 0.186 | 0/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | tesseract:psm6 | B | 1 | 0.107 | 0.107 | both | 0.169 | 2/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-85-Pg864 | HCONRES | tesseract:psm6 | B | 1 | 0.026 | 0.026 | both | 0.058 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg868-5 | SCONRES | tesseract:psm6 | B | 2 | 0.342 | 0.342 | both | 0.475 | 2/1 (1) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg906 | PROCLAMATION | tesseract:psm6 | B | 2 | 0.017 | 0.025 | both | 0.019 | 0/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | tesseract:psm6 | B | 1 | 0.015 | 0.038 | both | 0.031 | 0/0 (0) | 1.00 | 1.03 | 0 | yes | - |
| STATUTE-10-Pg1177-2 | PROCLAMATION | tesseract:psm6 | B | 2 | 0.202 | 0.246 | both | 0.346 | 0/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | tesseract:psm6 | B | 1 | 0.140 | 1.164 | both | 0.262 | 1/0 (0) | 0.00 | 1.03 | 2 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | tesseract:psm6 | B | 1 | 0.029 | 0.058 | both | 0.105 | 1/0 (0) | 0.00 | 1.03 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | tesseract:psm6 | B | 1 | 0.085 | 0.768 | both | 0.148 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg954 | TREATY | tesseract:psm6 | B | 6 | 0.170 | 0.170 | tail | 0.290 | 1/0 (0) | 1.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg972 | TREATY | tesseract:psm6 | B | 1 | 0.081 | 0.081 | both | 0.165 | 0/0 (0) | 1.00 | 1.03 | 0 | yes | - |
| STATUTE-39-Pg1058 | PUBLICLAW | tesseract:psm6 | B | 12 | 0.104 | 0.104 | both | 0.142 | 5/1 (1) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-39-Pg1599-4 | HCONRES | tesseract:psm6 | B | 1 | 0.051 | 0.818 | both | 0.093 | 1/0 (0) | 1.00 | 1.03 | 1 | yes | - |
| STATUTE-39-Pg1600-3 | SCONRES | tesseract:psm6 | B | 1 | 0.902 | 1.435 | tail | 1.051 | 1/0 (0) | 1.00 | 1.03 | 1 | yes | - |
| STATUTE-39-Pg1603-4 | SCONRES | tesseract:psm6 | B | 1 | 0.566 | 0.566 | none | 0.698 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-39-Pg1604-3 | HCONRES | tesseract:psm6 | B | 1 | 0.078 | 1.032 | both | 0.126 | 1/0 (0) | 1.00 | 1.04 | 4 | yes | - |
| STATUTE-39-Pg1606 | SCONRES | tesseract:psm6 | B | 1 | 0.042 | 0.042 | both | 0.063 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-39-Pg1606-4 | HCONRES | tesseract:psm6 | B | 2 | 0.048 | 0.048 | both | 0.062 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-39-Pg1645 | TREATY | tesseract:psm6 | B | 5 | 0.655 | 0.679 | both | 0.807 | 0/0 (0) | 1.00 | 1.02 | 0 | yes | - |
| STATUTE-39-Pg1738 | PROCLAMATION | tesseract:psm6 | B | 3 | 0.792 | 0.792 | head | 0.800 | 0/0 (0) | 1.00 | 1.04 | 0 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | tesseract:psm6 | B | 1 | 0.558 | 0.672 | both | 0.582 | 0/0 (0) | 1.00 | 1.02 | 1 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | tesseract:psm6 | B | 1 | 0.160 | 0.371 | both | 0.276 | 1/0 (0) | 0.00 | 1.02 | 0 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | tesseract:psm6 | B | 2 | 0.077 | 0.077 | both | 0.132 | 1/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | textlayer | A | 2 | 1.000 | 1.000 | none | 1.000 | 5/0 (0) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | textlayer | A | 2 | 1.000 | 1.000 | none | 1.000 | 1/0 (0) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | textlayer | A | 2 | 1.000 | 1.000 | none | 1.000 | 1/0 (0) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | textlayer | A | 4 | 1.000 | 1.000 | none | 1.000 | 2/0 (0) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | textlayer | A | 6 | 1.000 | 1.000 | none | 1.000 | 11/0 (0) | 0.00 | 1.00 | 2 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | textlayer | B | 2 | 0.022 | 0.022 | both | 0.058 | 5/5 (5) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | textlayer | B | 2 | 0.055 | 0.055 | both | 0.078 | 1/1 (1) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | textlayer | B | 2 | 0.060 | 0.060 | both | 0.090 | 1/1 (1) | 0.00 | 0.92 | 1 | yes | - |
| STATUTE-132-Pg2888 | PUBLICLAW | textlayer | B | 4 | 0.059 | 0.059 | both | 0.083 | 2/2 (2) | 0.00 | 0.94 | 1 | yes | - |
| STATUTE-132-Pg5019 | PUBLICLAW | textlayer | B | 6 | 0.042 | 0.042 | both | 0.054 | 11/22 (11) | 0.00 | 0.96 | 2 | yes | - |
| STATUTE-72-Pg1572 | PUBLICLAW | textlayer | B | 8 | 0.061 | 0.061 | both | 0.112 | 6/5 (4) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | textlayer | B | 3 | 0.076 | 0.076 | both | 0.127 | 11/10 (10) | 0.00 | 1.00 | 1 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | textlayer | B | 1 | 0.016 | 0.016 | both | 0.054 | 2/1 (1) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | textlayer | B | 2 | 0.211 | 0.211 | head | 0.264 | 2/1 (1) | 0.00 | 1.01 | 3 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | textlayer | B | 1 | 0.063 | 2.315 | both | 0.165 | 1/0 (0) | 0.00 | 1.00 | 0 | yes | - |
| STATUTE-72-PgB14 | HCONRES | textlayer | B | 1 | 0.044 | 0.044 | both | 0.102 | 1/0 (0) | 1.00 | 1.03 | 3 | yes | - |
| STATUTE-72-PgB21 | SCONRES | textlayer | B | 1 | 0.010 | 0.010 | both | 0.036 | 1/0 (0) | 1.00 | 1.03 | 3 | yes | - |
| STATUTE-72-PgB23-3 | SCONRES | textlayer | B | 1 | 0.006 | 0.006 | both | 0.035 | 1/0 (0) | 1.00 | 1.01 | 3 | yes | - |
| STATUTE-72-PgB5 | HCONRES | textlayer | B | 1 | 0.144 | 1.129 | both | 0.244 | 1/0 (0) | 1.00 | 1.01 | 4 | yes | - |
| STATUTE-72-PgC40 | PROCLAMATION | textlayer | B | 1 | 0.112 | 0.186 | tail | 0.132 | 0/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | textlayer | B | 1 | 0.007 | 0.007 | both | 0.025 | 2/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-85-Pg864 | HCONRES | textlayer | B | 1 | 0.070 | 1.333 | both | 0.221 | 1/0 (0) | 1.00 | 1.02 | 3 | yes | - |
| STATUTE-85-Pg868-5 | SCONRES | textlayer | B | 2 | 0.015 | 0.015 | both | 0.050 | 2/1 (1) | 1.00 | 1.02 | 3 | yes | - |
| STATUTE-85-Pg906 | PROCLAMATION | textlayer | B | 2 | 0.016 | 0.023 | both | 0.031 | 0/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-85-Pg943 | PROCLAMATION | textlayer | B | 1 | 0.055 | 0.055 | both | 0.074 | 0/0 (0) | 1.00 | 1.04 | 0 | yes | - |
| STATUTE-10-Pg1177-2 | PROCLAMATION | textlayer | B | 2 | 0.626 | 0.653 | tail | 0.840 | 0/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | textlayer | B | 1 | 0.008 | 4.842 | both | 0.039 | 1/1 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | textlayer | B | 1 | 0.002 | 0.002 | both | 0.023 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | textlayer | B | 1 | 0.003 | 0.807 | both | 0.019 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg954 | TREATY | textlayer | B | 6 | 0.157 | 0.157 | tail | 0.226 | 1/0 (0) | 1.00 | 1.01 | 1 | yes | - |
| STATUTE-10-Pg972 | TREATY | textlayer | B | 1 | 0.054 | 0.054 | both | 0.073 | 0/0 (0) | 1.00 | 1.02 | 0 | yes | - |
| STATUTE-39-Pg1058 | PUBLICLAW | textlayer | B | 12 | 0.038 | 0.038 | both | 0.046 | 5/4 (4) | 0.00 | 1.01 | 1 | yes | - |
| STATUTE-39-Pg1599-4 | HCONRES | textlayer | B | 1 | 0.040 | 0.040 | both | 0.047 | 1/0 (0) | 1.00 | 1.03 | 2 | yes | - |
| STATUTE-39-Pg1600-3 | SCONRES | textlayer | B | 1 | 0.584 | 0.584 | none | 0.723 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1603-4 | SCONRES | textlayer | B | 1 | 0.569 | 0.569 | none | 0.691 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1604-3 | HCONRES | textlayer | B | 1 | 0.027 | 0.028 | both | 0.023 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1606 | SCONRES | textlayer | B | 1 | 0.014 | 0.014 | both | 0.010 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1606-4 | HCONRES | textlayer | B | 2 | 0.037 | 0.037 | both | 0.035 | 1/0 (0) | 1.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg1645 | TREATY | textlayer | B | 5 | 0.627 | 0.652 | both | 0.784 | 0/0 (0) | 1.00 | 1.02 | 0 | yes | - |
| STATUTE-39-Pg1738 | PROCLAMATION | textlayer | B | 3 | 0.776 | 0.776 | head | 0.778 | 0/0 (0) | 1.00 | 1.03 | 0 | yes | - |
| STATUTE-39-Pg1782 | PROCLAMATION | textlayer | B | 1 | 0.010 | 0.231 | both | 0.025 | 0/0 (0) | 1.00 | 1.02 | 1 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | textlayer | B | 1 | 0.009 | 0.009 | both | 0.062 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | textlayer | B | 2 | 0.040 | 0.040 | both | 0.067 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
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
| STATUTE-124-Pg4523 | PRIVATELAW | vlm:granite_docling | A | 2 | 0.081 | 0.081 | head | 0.084 | 1/1 (1) | 0.00 | 1.02 | 3 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | vlm:granite_docling | A | 2 | 0.084 | 0.084 | head | 0.090 | 1/1 (1) | 0.00 | 1.02 | 3 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | vlm:granite_docling | B | 2 | 0.003 | 0.003 | both | 0.000 | 5/5 (5) | 0.00 | 1.03 | 2 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | vlm:granite_docling | B | 2 | 0.081 | 0.081 | head | 0.084 | 1/1 (1) | 0.00 | 1.02 | 3 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | vlm:granite_docling | B | 2 | 0.087 | 0.087 | head | 0.097 | 1/1 (1) | 0.00 | 1.02 | 3 | yes | - |
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
| STATUTE-124-Pg2256 | PUBLICLAW | vlm:lightonocr | A | 2 | 0.169 | 0.179 | head | 0.176 | 5/4 (4) | 0.00 | 1.02 | 3 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | vlm:lightonocr | A | 2 | 0.063 | 0.064 | both | 0.090 | 1/1 (1) | 0.00 | 1.00 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | vlm:lightonocr | A | 2 | 0.068 | 0.068 | both | 0.104 | 1/1 (1) | 0.00 | 1.00 | 1 | yes | - |
| STATUTE-124-Pg2256 | PUBLICLAW | vlm:lightonocr | B | 2 | 0.169 | 0.179 | head | 0.176 | 5/4 (4) | 0.00 | 1.02 | 3 | yes | - |
| STATUTE-124-Pg4523 | PRIVATELAW | vlm:lightonocr | B | 2 | 0.063 | 0.064 | both | 0.090 | 1/1 (1) | 0.00 | 1.00 | 1 | yes | - |
| STATUTE-124-Pg4525 | PRIVATELAW | vlm:lightonocr | B | 2 | 0.068 | 0.068 | both | 0.104 | 1/1 (1) | 0.00 | 1.00 | 1 | yes | - |
| STATUTE-72-Pg1751 | PUBLICLAW | vlm:lightonocr | B | 3 | 0.720 | 0.720 | head | 0.709 | 11/0 (0) | 0.00 | 1.01 | 3 | yes | - |
| STATUTE-72-Pg983-2 | PUBLICLAW | vlm:lightonocr | B | 1 | 0.010 | 0.010 | both | 0.018 | 2/1 (1) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-72-PgA13 | PRIVATELAW | vlm:lightonocr | B | 2 | 0.397 | 0.397 | head | 0.425 | 2/0 (0) | 0.00 | 1.01 | 3 | yes | - |
| STATUTE-72-PgA144-2 | PRIVATELAW | vlm:lightonocr | B | 1 | 0.061 | 0.061 | both | 0.099 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-85-Pg844-2 | PRIVATELAW | vlm:lightonocr | B | 1 | 0.022 | 0.035 | both | 0.041 | 2/1 (1) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg764 | PRIVATELAW | vlm:lightonocr | B | 1 | 0.068 | 0.198 | both | 0.117 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-10-Pg826-5 | PRIVATELAW | vlm:lightonocr | B | 1 | 0.002 | 0.002 | both | 0.012 | 1/0 (0) | 0.00 | 1.02 | 1 | yes | - |
| STATUTE-10-Pg840-3 | PRIVATELAW | vlm:lightonocr | B | 1 | 0.001 | 0.001 | both | 0.006 | 1/0 (0) | 0.00 | 1.02 | 2 | yes | - |
| STATUTE-39-Pg342-2 | PUBLICLAW | vlm:lightonocr | B | 1 | 0.002 | 0.002 | both | 0.008 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |
| STATUTE-39-Pg354-4 | PUBLICLAW | vlm:lightonocr | B | 2 | 0.039 | 0.039 | both | 0.074 | 1/0 (0) | 0.00 | 1.01 | 2 | yes | - |

## Skipped

- STATUTE-10-Pg1177-2 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg1177-2 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg1177-2 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-10-Pg1177-2 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-10-Pg1177-2 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg1177-2 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg1177-2 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg764 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg764 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-10-Pg826-5 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg826-5 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-10-Pg840-3 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg840-3 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-10-Pg954 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg954 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg954 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-10-Pg954 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-10-Pg954 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg954 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg954 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg972 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg972 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg972 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-10-Pg972 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-10-Pg972 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg972 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-10-Pg972 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg2256 [digital/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg2256 [easyocr/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg2256 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg2256 [hybrid:scanned/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-124-Pg2256 [scanned/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg2256 [scanned/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg4523 [digital/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg4523 [easyocr/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg4523 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg4523 [hybrid:scanned/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-124-Pg4523 [scanned/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg4523 [scanned/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg4525 [digital/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg4525 [easyocr/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg4525 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg4525 [hybrid:scanned/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-124-Pg4525 [scanned/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-124-Pg4525 [scanned/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg2888 [digital/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg2888 [easyocr/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg2888 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg2888 [hybrid:scanned/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-132-Pg2888 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-132-Pg2888 [scanned/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg2888 [scanned/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg2888 [vlm:glm_ocr/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg2888 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg2888 [vlm:granite_docling/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg2888 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg2888 [vlm:lightonocr/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg2888 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5019 [digital/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5019 [easyocr/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5019 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5019 [hybrid:scanned/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-132-Pg5019 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-132-Pg5019 [scanned/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5019 [scanned/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5019 [vlm:glm_ocr/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5019 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5019 [vlm:granite_docling/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5019 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5019 [vlm:lightonocr/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5019 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5595 [digital/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5595 [digital/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [easyocr/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5595 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5595 [hybrid:digital/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [hybrid:rapidocr/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [hybrid:scanned/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-132-Pg5595 [hybrid:textlayer/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [hybrid:vlm:glm_ocr/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [rapidocr/A]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [rapidocr/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [scanned/A]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5595 [scanned/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-132-Pg5595 [tesseract:psm4/A]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [tesseract:psm4/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [tesseract:psm6/A]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [tesseract:psm6/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [textlayer/A]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [textlayer/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [vlm:glm_ocr/A]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [vlm:glm_ocr/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [vlm:granite_docling/A]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [vlm:granite_docling/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [vlm:lightonocr/A]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-132-Pg5595 [vlm:lightonocr/B]: no one-to-one reference (PRIVATELAW: no slice; F4)
- STATUTE-39-Pg1058 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1058 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1058 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1058 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1058 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1058 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1058 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1599-4 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1599-4 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1599-4 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1599-4 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1599-4 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1599-4 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1599-4 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1600-3 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1600-3 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1600-3 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1600-3 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1600-3 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1600-3 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1600-3 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1603-4 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1603-4 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1603-4 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1603-4 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1603-4 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1603-4 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1603-4 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1604-3 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1604-3 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1604-3 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1604-3 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1604-3 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1604-3 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1604-3 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1606 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1606 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1606 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1606 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1606 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1606 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1606 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1606-4 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1606-4 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1606-4 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1606-4 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1606-4 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1606-4 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1606-4 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1645 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1645 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1645 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1645 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1645 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1645 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1645 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1738 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1738 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1738 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1738 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1738 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1738 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1738 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1782 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1782 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1782 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg1782 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1782 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg1782 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg342-2 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg342-2 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-39-Pg354-4 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-39-Pg354-4 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-Pg1572 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-Pg1572 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-Pg1572 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-Pg1572 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-Pg1572 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-Pg1572 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-Pg1572 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-Pg1751 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-Pg1751 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-Pg983-2 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-Pg983-2 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgA13 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgA13 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgA144-2 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgA144-2 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgB14 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB14 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB14 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgB14 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgB14 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB14 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB14 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB21 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB21 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB21 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgB21 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgB21 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB21 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB21 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB23-3 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB23-3 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB23-3 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgB23-3 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgB23-3 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB23-3 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB23-3 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB5 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB5 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB5 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgB5 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgB5 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB5 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgB5 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgC40 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgC40 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgC40 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgC40 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-72-PgC40 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgC40 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-72-PgC40 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg844-2 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg844-2 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-85-Pg864 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg864 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg864 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-85-Pg864 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-85-Pg864 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg864 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg864 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg868-5 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg868-5 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg868-5 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-85-Pg868-5 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-85-Pg868-5 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg868-5 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg868-5 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg906 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg906 [easyocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg906 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-85-Pg906 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-85-Pg906 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg906 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg906 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg943 [digital/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg943 [hybrid:digital/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-85-Pg943 [hybrid:vlm:glm_ocr/B]: no candidate output for the hybrid's text profile on this granule
- STATUTE-85-Pg943 [vlm:glm_ocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg943 [vlm:granite_docling/B]: no DoclingDocument JSON for this profile (not converted by its runner)
- STATUTE-85-Pg943 [vlm:lightonocr/B]: no DoclingDocument JSON for this profile (not converted by its runner)

## Notes

- One `--rebuild` pass over every profile's stored DoclingDocument JSON (`data/doclang/<profile>/`), so the s/page column
  is the rebuild time. Measured conversion times per page: `scanned` 4.4 s per worker, `tesseract:psm4` 3.9, `tesseract:psm6`
  4.2, `textlayer` 1.5, `rapidocr` 5.7, `easyocr` 60.9 (container, 2 workers unless noted in 2026-09-08-wp9a-cpu.md);
  `vlm:glm_ocr` 9.6 to 13.4 s, `vlm:lightonocr` 11.3 to 18.0 s, `vlm:granite_docling` 4.3 to 23.2 s (Mac, MLX,
  2026-09-08-wp9b-vlm.md); hybrid assembly 0.0 to 0.3 s (2026-09-08-wp9c-claude-hybrid.md).
- Coverage differs by profile: the VLM profiles ran on `benchmark/sample_vlm.yaml` (14 laws with at most three pages);
  `easyocr` on 12 granules (`benchmark/sample-easyocr.yaml`); the CPU profiles and the hybrids on the full sample. Skipped
  rows are profile and granule combinations without stored output. docs/plans/2026-09-08-ocr-decision.md compares every
  profile on the 14 common laws.
- `claude:<model>` profiles have no rows: the Anthropic credit balance was too low for every request on 2026-09-08.
- The `Kept` value 1.98 for `hybrid:vlm:glm_ocr` pre-1951 is the hybrid's kept characters over the candidate's
  characters on a granule whose GPO text is longer than the candidate's; it is not a builder measurement.
- Tier A rows for the VLM profiles were produced on wrapper PDFs with 1912 x 2476 pt pages (fixed in benchmark/rasterize.py
  afterwards); text unaffected.
