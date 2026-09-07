---
pretty_name: United States Statutes at Large
license: other
license_name: public-domain
license_link: https://www.law.cornell.edu/uscode/text/17/105
language:
  - en
tags:
  - legal
  - legislation
  - united-states
  - statutes
  - pdf
  - uslm
size_categories:
  - n<1K
---

# United States Statutes at Large

Bound volumes of the United States Statutes at Large as published by the U.S. Government Publishing
Office on [GovInfo](https://www.govinfo.gov/app/collection/statute), collection `STATUTE`. Each
volume is one PDF and one USLM XML file.

## Files

```
metadata.jsonl           one row per volume
pdfs/STATUTE-{n}.pdf     volume PDF as served by GovInfo
xmls/STATUTE-{n}.xml     volume USLM XML as served by GovInfo
granules/                per-law PDFs used by the conversion benchmark (a sample, not every law)
```

`metadata.jsonl` fields: `file_name` (PDF path), `package_id`, `volume`, `congress`, `session`,
`date_issued`, `pages`, `scanned`, `pdf_bytes`, `pdf_sha256`, `xml_file`, `xml_bytes`, `xml_sha256`,
`source_package_url`.

## Volumes and eras

| Volumes | Years | PDF | XML |
|---|---|---|---|
| 1 to 64 | 1789 to 1951 | scanned images, 45 MB to 1.1 GB | USLM produced by GPO from OCR and editorial markup |
| 65 to 116 | 1951 to 2002 | scanned images | USLM produced by GPO |
| 117 to 137 | 2003 to 2023 | born digital, 8 MB to 45 MB | USLM produced by GPO from the typesetting source |

`scanned` in `metadata.jsonl` is true for volumes 1 to 116.

## Source and license

Downloaded from `https://api.govinfo.gov/packages/STATUTE-{n}/pdf` and `/uslm`. Works of the
United States Government are not subject to copyright in the United States (17 U.S.C. 105).

Produced by the [statute-pdf-to-xml](https://github.com/aih/statute-pdf-to-xml) project, which
converts the PDFs to USLM with Docling and benchmarks the result against the GPO XML.
