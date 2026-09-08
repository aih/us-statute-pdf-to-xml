# Architecture

## Modules

```
downloader/
  config.py          env vars (no defaults for secrets), data paths, logging to data/logs/<script>-<date>.log
  govinfo.py         GovInfoClient: retries with backoff and Retry-After, rate-limit logging, collection and
                     granule iterators, download_ranged() (parallel Range requests, .part files, sha256,
                     Content-Length check, atomic rename)
  state.py           packages rows from summaries; decide() skip / upload-only / download; metadata.jsonl rows;
                     PLAW volume and pages from USLM citableAs and page markers
  hf_upload.py       HubUploader: one create_commit per volume (PDF + XML, dataset card on the first commit),
                     get_paths_info verification (size and LFS sha256), local delete, metadata.jsonl;
                     reconcile subcommand
  fetch_historical.py  CLI: fetch [--volumes --parts --files --queue-size --no-upload --keep-local], reconcile [--fix]
  fetch_plaw.py      CLI over collections/PLAW: per-law PDF + USLM, statutes and packages rows, congress.gov copy
  fetch_granules.py  CLI: granule PDFs and MODS for a YAML sample spec, granules rows
  mods.py            MODS parser (page range, total pages, law number, class, citation)
  dataset_card.md    README.md committed to the Hub dataset
  db.py              connection, migrations runner (db/migrations/NNN_*.sql, schema_migrations table)
pipeline/
  profiles.py        profile registry (`family[:variant]`): scanned (Tesseract CLI without orientation detection,
                     eng, full-page OCR, 300 dpi, psm4/psm6 variants) and digital (no OCR, backend text layer);
                     other modules register families through register_family(); profile chosen by volume (<= 116 scanned)
  tesseract.py       TesseractNoOsdModel: Docling's Tesseract CLI model with `_perform_osd` fixed at 0 degrees,
                     registered with Docling's OCR factory as kind `tesseract_noosd`
  convert.py         ProcessPoolExecutor (default 2 workers, memory-bound), one DocumentConverter per worker per profile, page_range,
                     outputs under data/{doclang,generated_xmls}/{profile}/, module_used = profile[@tag], builder stats
                     (docling_chars, kept_chars, body_chars, warnings) in conversions, skip when outputs exist and input
                     sha256 unchanged; non-Docling families run through their `converter` callable
  uslm.py            DoclingDocument -> USLM (lxml): meta, preface, longTitle, enactingFormula, section /
                     subsection / paragraph / subparagraph / clause with identifier and id, page markers,
                     sidenotes by geometry, action, legislativeHistory; XSD validation (pipeline/schemas/).
                     Keeps every body item: text before the document start -> preface/p, text after the
                     approval line -> appendix[@role=trailingMatter]; UslmBuilder.stats and warnings
  split_uslm.py      volume USLM -> one USLM document per granule; unpaired.json lists granules without a slice
  schemas/           uslm-2.0.17.xsd and its imports (xml.xsd, dc.xsd, xhtml-datatypes-1.xsd, mathml3*.xsd,
                     uslm-table-module-2.0.17.xsd) with schemaLocation rewritten to local files
benchmark/
  sample.py          stratified sample (era x granule class) -> benchmark/sample.yaml; digital era limited to
                     PUBLICLAW and PRIVATELAW (ERA_CLASSES)
  metrics.py         text normalization, clipping of the generated text to the reference span (rapidfuzz
                     partial_ratio_alignment on the first and last 30 tokens), CER, WER, structure counts,
                     section match (num + first 40 chars), sidenote recall, identifier overlap, alignment
  rasterize.py       tier A inputs: page images (clean PNG; degraded JPEG q60, 0.5 degree skew, noise) and
                     img2pdf wrappers under data/raster/{id}/
  judge.py           Claude judge: structured output, PDF pages as document blocks, aligned XML segments
  evaluate.py        convert -> metrics -> judge for --profiles and --tier A,B; benchmarks rows (profile, tier);
                     profile-by-era matrix report in data/reports/
db/migrations/       001_initial, 002_packages_granules, 003_title_text, 004_granule_pages,
                     005_conversion_benchmark_columns, 006_conversion_stats_profile
tests/               pytest; fixtures hold real GovInfo MODS, summaries, a PLAW USLM, four Docling outputs, and the
                     page image on which Tesseract's orientation detection fails
```

## Data flow

```
GovInfo API ──summary/HEAD──> state.decide ──download_ranged──> data/historical/{pdfs,xmls}/STATUTE-n.*
                                               │                       │
                                               │                  HubUploader.upload_volume (create_commit)
                                               │                       │ get_paths_info verify -> delete local
                                               └──────────────> packages table ──> metadata.jsonl on the Hub

collections/PLAW ──> fetch_plaw ──> data/pdfs/PLAW-*.pdf, data/xmls/PLAW-*.xml, statutes + packages rows
granules API ──────> fetch_granules ──> data/granules/STATUTE-n/{granuleId}.pdf + .mods.xml, granules rows
volume USLM ───────> split_uslm ──> data/granules/STATUTE-n/uslm/{granuleId}.xml   (ground truth per granule)

PDF ──Docling (profile)──> data/doclang/{profile}/{id}.json ──uslm.py──> data/generated_xmls/{profile}/{id}.xml ──XSD──> conversions row
born-digital granule PDF ──rasterize──> data/raster/{id}/p{n}.png + {id}.clean.pdf ──(tier A) same path as above
generated XML + ground truth XML ──metrics──> benchmarks row ──judge (sample)──> benchmarks.judge
```

Concurrency: threads for network I/O (`ThreadPoolExecutor` for range requests and for volumes, one uploader
thread behind a bounded queue), processes for Docling (`ProcessPoolExecutor`, `min(2, cpu_count // 2)`
workers by default, one converter per worker; four OCR workers peaked at 6 GB and were OOM-killed in the 8 GB container), threads for judge calls (4 in flight).

## Source facts verified on 2026-09-05

### GovInfo

- `STATUTE` volumes 1 to 137. Package summary fields: `volume`, `congress`, `session`, `dateIssued`,
  `pages` (absent on some volumes, e.g. 119), `download.pdfLink`, `download.uslmLink`.
- The download endpoints send `Content-Length` and `Accept-Ranges: bytes` only when the request carries
  `Accept-Encoding: identity`; with gzip accepted, XML responses are chunked and have no length.
- `X-Api-Key` header works in place of the `api_key` query parameter.
- Granule ids encode the start page: `STATUTE-64-Pg371`, `STATUTE-64-Pg373-2` (second granule starting on
  page 373), `STATUTE-64-PgB3` (part B, lettered pages), `STATUTE-64-FrontMatter-1-PgIII`,
  `STATUTE-64-BackMatter-3-PgB1107`. `pagePosition` in the granule summary is the granule's position on
  its first page, not a page number.
- Granule MODS carries the page range: `part[@type='article']/extent[@unit='pages']/start|end`,
  `extension/totalPages`, `extension/statuteAtLarge/pages/@pages` ("371-373", "B3-B32"),
  `extension/granuleClass`, `extension/number` (law number), `extension/law/@isPrivate`,
  `extension/congress`, `extension/session`, `identifier[@type='preferred citation']` ("64 Stat. 371").
- `collections/PLAW/{since}` filters on lastModified, paginates with `offsetMark`, and accepts
  `docClass` and `congress` query parameters. A PLAW summary's `references` list every Statutes at
  Large citation in the law, including earlier statutes it amends; the law's own entry is the one whose
  page count equals the summary's `pages`. The USLM is the reliable source: `<citableAs>140 Stat. 173</citableAs>`
  and `<page identifier="/us/stat/140/N">`.
- The congress.gov copy of a public law's USLM (`https://www.congress.gov/{c}/plaws/publ{n}/PLAW-{c}publ{n}_uslm.xml`)
  was byte-identical to the GovInfo copy for PL 114-176 and for the twenty 119th Congress laws checked.

### Volume USLM (STATUTE-64.xml, 29 MB)

```
statutesAtLarge xmlns="http://schemas.gpo.gov/xml/uslm"
  meta
  main/collection[@role=statutesParts]
    component[@role=statutesPart]            (3 parts in volume 64)
      meta, preface                          -> FRONTMATTER granule
      publicLaws/component/pLaw              -> PUBLICLAW (481)
      privateLaws/component/pLaw             -> PRIVATELAW (749 in XML, 750 granules)
      concurrentResolutions/component/resolution   -> SCONRES, HCONRES (60 in XML, 58 granules)
      presidentialDocs[@role=proclamations]/component/presidentialDoc -> PROCLAMATION (58)
      presidentialDocs[@role=treaties]/component/presidentialDoc      -> TREATY (19)
      component/reorganizationPlans/reorganizationPlan                -> REORGPLAN (20)
      backMatter                             -> BACKMATTER (3 in XML, 4 granules)
```

- Each pLaw has `meta` (dc:title, dc:type "Chapter" or "Public Law", docNumber, citableAs
  "64 Stat. 370", approvedDate, congress, session, publicPrivate), `preface`, `main` (longTitle,
  enactingFormula, sidenote, section, action).
- Page markers are `<page identifier="/us/stat/64/371">` (3,080 with identifiers; lettered pages are
  lower case: `/us/stat/64/b3`; treaty language variants: `/us/stat/64/b12@fre`). The marker for the
  page a document starts on is often inside the document, after its heading lines.
- In the volume XML only `page` elements carry `identifier`; sections have no `identifier` or `id`.
  The PLAW USLM has them: `section identifier="/us/pl/118/5/s1"`, `subsection identifier="/us/pl/118/5/s1/a"`,
  `paragraph .../s2/1`, `subparagraph .../s2/1/A`, `clause .../s2/1/E/i`, plus `id` attributes on every
  level and `<page identifier="/us/stat/137/10">`. The generated USLM follows the PLAW scheme.
- Splitting result for volume 64: 1,393 documents produced for 1,393 granules; 1,385 ids match GovInfo's.
  The eight differences come from the two class groups whose counts differ (resolutions, private laws)
  and the back matter GovInfo splits in two.

### Born-digital volumes (STATUTE-124.xml)

Each `component[@role=statutesPart]` holds `meta`, `preface`, `main`, `backMatter`, with the law
containers under `main`. GovInfo's granulation differs from the XML document boundaries in this era:
volume 124 has 172 `presidentialDoc` elements for 153 PROCLAMATION granules and 38 `resolution`
elements for 2 HCONRES granules (GovInfo groups all concurrent resolutions of a session into one or
two granules). Public and private laws align exactly. The splitter emits one file per XML document,
so proclamation and resolution granules from 2003 on have no one-to-one ground-truth slice.

### PLAW USLM (PLAW-119publ1.xml)

Root `pLaw`, children `meta`, `preface` (centerRunningHead, page, dc:type, docNumber, congress), `main`
(longTitle/docTitle "An Act", longTitle/officialTitle, enactingFormula, section..., action),
`legislativeHistory`. Elements used: num[@value], heading, content, chapeau, paragraph, subparagraph,
quotedContent, quotedText, amendingAction, sidenote, note, ref, inline, p. `xsi:schemaLocation` points
at `https://www.govinfo.gov/schemas/xml/uslm/uslm-2.0.17.xsd`. Both PLAW files and the whole
STATUTE-64 volume validate against that XSD with lxml (schema load 2.7 s, volume validation 0.7 s).

### Tesseract orientation detection (verified 2026-09-08)

Docling's `TesseractOcrCliModel` runs `tesseract --psm 0 -l osd` on the image it renders for OCR (216 dpi
by default) and rotates the image by the result. On page 1 of `STATUTE-72-Pg1751` and of `STATUTE-10-Pg764`
that call returns "Orientation in degrees: 180, confidence 0.07" (0.03 for volume 10) on upright pages, and
the OCR text comes out mirrored. The same pages rendered directly with pypdfium2 at 144, 216, or 300 dpi
are detected as upright; the difference is in Docling's render. `pipeline/tesseract.py` removes the
detection instead of thresholding it.

### Docling output on statute pages (docling 2.126.0)

Labels observed: `text` (most items), `section_header` ("SECTION 1. ..." headings, "An Act"), `footnote`
(legislative history at the page foot), `picture` (seal), `table`. Sidenotes come out as `text` items in
the margin (right margin x > 0.72 of the page width on the digital page; left or right on scanned
spreads); the typesetting footer ("VerDate ... PsN: PUBL001") is a row of `text` items at the page
foot. `uslm.py` separates them by position relative to the main text column, then parses section,
subsection, paragraph, and subparagraph designators from the text.

Timings in the 10-CPU container: digital PLAW-118publ5 (41 pages) 58 s; scanned STATUTE-64-Pg873 (22
pages, Tesseract) 105 s; STATUTE-64-Pg371 (3 pages) 13 s. The first conversion in a container without
the pre-fetched models also downloads them (about 3 minutes).

### HuggingFace Hub (huggingface_hub 1.30.0)

`HfApi.create_commit(repo_id, operations, commit_message=..., repo_type="dataset")` with
`CommitOperationAdd(path_in_repo, path_or_fileobj)`; `get_paths_info(repo_id, paths, repo_type=...)`
and `list_repo_tree(repo_id, recursive=True, repo_type=...)` return `RepoFile` objects with `path`,
`size`, and `lfs.sha256` for LFS files. The verification after each commit compares size and, for LFS
files, sha256, against the local file.
