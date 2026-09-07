# Statutes at Large API design (statutes.linkedlegislation.org)

Date: 2026-09-07. Status: proposed.

An API that serves individual public laws from the Statutes at Large in USLM at the section
level, addressed by the same identifiers the US Code uses in its source credits, so that
uscode.linkedlegislation.org can link from a source credit or a version transition to the cited
section of the law. It also serves the Statute Compilations that the House Office of the
Legislative Counsel maintains, and every answer says which of the two it is and how current it
is.

## 1. What the US Code site does today

Facts from `../uscode-redesign` (FastAPI, Postgres, Astro; ADRs in `docs/adr/`):

- A citation is a URL: `GET /us/usc/t16/s45f/c/5?release=119-102not101` answers 307 to `/app/…`
  for a browser and `/api/v1/…` for everything else (ADR-0010). JSON by default; `?format=xml`
  returns the verbatim USLM element (ADR-0009).
- Every section response carries `note`, a sentence stating when the answer came from a
  different release point than the one asked for (`params.served_note`). 404 bodies say which
  release point was searched.
- `Cache-Control: public, max-age=31536000, immutable` when the release point was pinned and
  served exactly, `max-age=300` otherwise; `ETag` with `If-None-Match` (ADR-0018).
- Cross references in the rendered text (`frontend/src/lib/refs.ts`): `/us/usc/…` links
  internally with a label from the batched `/api/v1/labels` call; `/us/stat/{vol}/{page}` links
  to `https://www.govinfo.gov/link/statute/{vol}/{page}`; `/us/pl/{c}/{n}…` links to
  `https://www.govinfo.gov/link/plaw/{c}/public/{n}` for the 104th Congress onward and is plain
  text before that; `/us/act/…` is always plain text.
- Reference forms counted in `samples/uslm1/usc16.xml` (Title 16, one release point): 23,000
  `/us/pl/` refs, 18,571 `/us/stat/`, 4,026 `/us/act/`. Public-law refs run from 5 to 15 path
  segments (`/us/pl/104/333/dI/tVIII/s814/e/1`).
- The version timeline attributes text transitions to Public Laws (ADR-0074): `VersionOut.laws[]`
  carries `pl_congress`, `pl_num`, and the classification actions. The classification tables
  (ADR-0067) store `pl_section_raw` (`'101(3)'`, `''` for the whole law), so a transition can
  name the amending section.
- A citation index (refs extracted from every section, keyed by `@href`) is designed in
  `docs/citation-index-plan.md` and not built.

The statutes site fills the gap in the third bullet: every `/us/pl/`, `/us/pvtl/`, `/us/act/`,
and `/us/stat/` reference gets a target that serves the cited section, for every Congress.

## 2. Sources

| Shelf | Collection | Coverage | Format | Identifiers |
|---|---|---|---|---|
| As enacted | GovInfo `PLAW` | 104th Congress (1995) onward; USLM from the 113th (2013) | PDF, HTML, USLM (113+) | GPO's, `/us/pl/118/5/dA/tI/s101/a` |
| As enacted | GovInfo `STATUTE` volumes 1 to 137 (on the Hub) | 1789 to 2023 | PDF, volume USLM | none on sections; added by the pipeline (OCR plan, section 7) |
| Compiled | GovInfo `COMPS` | 2,685 packages on 2026-09-07 | PDF, USLM (`statuteCompilation` root, schema 2.0.13) | `/us/sComp/{congress}/{law}/tI/ch1./s1/a` |
| Codified | uscode.linkedlegislation.org | 382 release points | its own API | `/us/usc/…` |

COMPS facts (`COMPS-1630`, Atomic Energy Act of 1954): the package summary carries
`law.congress`, `law.number`, `amendedThrough[]` (`publicLaw`, `congress`, `enacted`),
`shortTitle[]`, `lastModified`, `pages`. The USLM `meta` carries `currentThroughPublicLaw`,
`property[@role='fileId']`, `congress`, `approvedDate`; the `preface` carries an
`editionNote` ("As Amended Through P.L. 118–67, Enacted July 9, 2024") and two
`explanationNote`s (currency; not an official version). GovInfo keeps only the current text of
each compilation; a superseded version is not retrievable. Compilations before the 112th Congress
can be partial; the Public Health Service Act and the Social Security Act are split into one file
per title.

PLAW packages before the 113th Congress have PDF and text but no USLM; their PDFs are typeset
files, so they run through the `digital` profile of the pipeline.

## 3. Identifiers served

| Pattern | Resolves to |
|---|---|
| `/us/pl/{congress}/{num}` | the public law |
| `/us/pl/{congress}/{num}/{path}` | a section or lower level; `{path}` in GPO's PLAW form |
| `/us/pvtl/{congress}/{num}[/{path}]` | a private law |
| `/us/act/{YYYY-MM-DD}/ch{n}[/{path}]` | a chapter-numbered act (1789 to 1957) |
| `/us/stat/{volume}/{page}` | the page: every document that starts on or spans it, with the position of the page marker |
| `/us/sComp/{congress}/{num}[/{path}]` | the compilation section, in GPO's identifier form |

Resolution rules:

1. Exact identifier match on the stored unit.
2. If no unit has the identifier, the longest stored prefix wins (`…/s814/e/1` served as
   `…/s814` when only the section is stored), and `note` says so.
3. If the path names a section number that exists under a different hierarchy (the source
   credit writes `/us/pl/104/333/s814`, the stored unit is `/us/pl/104/333/dI/tVIII/s814`), the
   section-number index resolves it and `served_identifier` reports the stored form.
4. A law from 1901 to 1957 answers to both its public-law and its chapter identifier.

## 4. Views and currency

Every response has a `view`, a `currency` block, an `alternatives` list, and a `note`. A caller
asks for a view with `?view=enacted` (default) or `?view=compiled`; a section that has no
compilation answers 404 for `view=compiled` with the alternatives it does have.

```json
{
  "identifier": "/us/pl/83/703/s1",
  "served_identifier": "/us/pl/83/703/tI/ch1/s1",
  "view": "enacted",
  "law": {
    "kind": "pl", "congress": 83, "number": 703, "chapter": 1073,
    "short_titles": ["Atomic Energy Act of 1954"],
    "enacted": "1954-08-30", "citation": "68 Stat. 919",
    "source": {"collection": "STATUTE", "package": "STATUTE-68", "granule": "STATUTE-68-Pg919"}
  },
  "currency": {
    "kind": "as_enacted",
    "date": "1954-08-30",
    "amended": {"status": "known_amended", "latest": {"pl": "118-67", "enacted": "2024-07-09"}, "evidence": ["compilation", "source_credit"]}
  },
  "alternatives": [
    {"view": "compiled", "identifier": "/us/sComp/83/703/tI/ch1./s1", "current_through": {"pl": "118-67", "enacted": "2024-07-09"}, "url": "https://statutes.linkedlegislation.org/us/sComp/83/703/tI/ch1./s1"},
    {"view": "codified", "identifiers": ["/us/usc/t42/s2011"], "url": "https://uscode.linkedlegislation.org/us/usc/t42/s2011"}
  ],
  "note": "This is section 1 of Public Law 83-703 as enacted on August 30, 1954 (68 Stat. 919). It is not updated. This section has been amended since; the most recent law recorded is Public Law 118-67 (July 9, 2024). The compiled text is at /us/sComp/83/703/tI/ch1./s1, and the codified text at 42 U.S.C. 2011.",
  "provenance": {"text": "gpo-uslm" , "identifiers": "pipeline-1.0", "sha256": "…"},
  "pages": [{"page": "/us/stat/68/921", "pdf": "https://www.govinfo.gov/link/statute/68/921"}],
  "text": "…",
  "xml_url": "…?format=xml"
}
```

`currency.amended.status` takes one of:

| Status | Meaning | Evidence used |
|---|---|---|
| `known_amended` | at least one later law amended this section | a US Code source credit that cites this section and lists a later law; a classification row naming this law's section as amended; a compilation whose `currentThroughPublicLaw` is later than enactment and whose section text differs from the enacted text |
| `no_record` | the indexes hold no amendment of this section | none of the above matched; the note says amendment may still have occurred |
| `unknown` | the section is not in any index (private laws, most pre-1901 acts) | |

The note text for each view:

- **As enacted**: "This is {section} of {law} as enacted on {date} ({Stat. citation}). It is not
  updated. {amended sentence} To check for later amendments: the compiled text {link, if any};
  the US Code section(s) classified from it {links}; the classification tables at
  uscode.house.gov for laws after {date}."
- **Compiled**: "This is {section} of {short title} as compiled by the House Office of the
  Legislative Counsel, incorporating amendments through Public Law {n} ({date}). Compilations
  are not an official version; the official text is in the Statutes at Large and the United
  States Code (1 U.S.C. 112, 204). Laws enacted after {date} are not reflected; check the
  classification tables for {short title} and the US Code section(s) {links}. The enacted text
  is at {link}."

The compiled view's `currency` is `{"kind": "compiled", "current_through": {"pl": "118-67",
"enacted": "2024-07-09"}, "fetched": "2026-09-07", "govinfo_last_modified": "2026-09-04T12:08:06Z"}`.

Compilation history: each fetch that changes a package's `currentThroughPublicLaw` or content
hash is stored as a new `comp_versions` row. `?through=118-67` selects a stored version; the
history starts at the first ingest, because GovInfo does not keep superseded versions.

## 5. Routes

Same shape as the US Code site: a bare identifier URL redirects by `Accept`, `/api/v1` is
machine-only.

| Route | Answer |
|---|---|
| `GET /us/pl/{c}/{n}[/{path}]`, `/us/pvtl/…`, `/us/act/…`, `/us/stat/…`, `/us/sComp/…` | 307 to `/app/…` or `/api/v1/…` |
| `GET /api/v1/us/pl/{c}/{n}[/{path}]?view=enacted\|compiled&format=json\|xml&through=` | the unit (section 4) |
| `GET /api/v1/us/act/{date}/ch{n}[/{path}]` | same |
| `GET /api/v1/us/stat/{vol}/{page}` | `{page, documents: [{identifier, kind, title, starts_here, unit_on_page}], pdf}` |
| `GET /api/v1/us/sComp/{c}/{n}[/{path}]?through=` | the compilation unit; `alternatives` points at the enacted section and the US Code |
| `GET /api/v1/laws/{c}/{n}` | law summary: titles, dates, citation, TOC of units with identifiers, compilations, US Code classification |
| `GET /api/v1/laws/{c}/{n}/sections/{num}` | section-number lookup ignoring hierarchy (rule 3) |
| `GET /api/v1/comps?law=/us/pl/83/703&q=` | compilations for a law, or by title search |
| `GET /api/v1/comps/{fileId}` | compilation summary and version list |
| `GET /api/v1/cite?q=110 Stat. 4196` | citation parser: `Pub. L. 104-333, § 814`, `110 Stat. 4196`, `Act of Aug. 25, 1916, ch. 408`, `43 U.S.C. 1701` (returns the US Code URL) |
| `POST /api/v1/labels` `{identifiers: […]}` | `{identifier: {exists, served_identifier, num, heading, kind, currency}}` for up to 100 identifiers; what the US Code site's `resolveRef` calls |
| `GET /api/v1/cited-by?identifier=/us/pl/104/333/s814` | US Code sections whose source credits or notes cite this unit, with the release point checked |
| `GET /api/v1/status` | latest STATUTE, PLAW, COMPS package seen; last poll time; `stale` after a week |

Caching: `immutable` for enacted units and for a compilation pinned with `through=`; `max-age=300`
for unpinned compiled views, `labels`, `cited-by`, and `status`. `ETag` on everything.

Rate limits follow ADR-0029's shape: `labels` sized for a server (the US Code site calls it once
per rendered page), `cite` and `cited-by` for a person.

## 6. Storage

Postgres, one `Repository` protocol, no SQL outside `storage/` (the US Code site's rule 1).

| Table | Row |
|---|---|
| `laws` | one per law: kind (`pl`, `pvtl`, `act`, `res`), congress, number, chapter, enacted date, Stat. volume and page range, short titles, source package and granule, provenance (`gpo-uslm` or pipeline version) |
| `units` | one per section and lower level: `law_id`, `identifier`, `section_num`, `level`, `num`, `heading`, verbatim XML fragment, plain text, `content_hash`, order, ancestor headings |
| `stat_pages` | volume, page label, `law_id`, first `unit_id` on the page |
| `comps` | `file_id`, package id, `law_id`, title, short titles |
| `comp_versions` | `comp_id`, `current_through_pl`, `current_through_date`, GovInfo `lastModified`, fetched at, content hash |
| `comp_units` | `comp_version_id`, `/us/sComp/…` identifier, `section_num`, XML, text |
| `citations` | `from_identifier` (`/us/usc/…`), `to_identifier` (`/us/pl/…`, `/us/act/…`, `/us/stat/…`), `context` (`sourceCredit`, `note`, `text`), release label; built from the `dreamproit/uscode` dataset's verbatim XML |
| `classifications` | mirror of the US Code site's classification rows, keyed by `(pl_congress, pl_num, pl_section)` |
| `source_checks` | collection, checked at, newest `lastModified` seen |

Ingest:

- `STATUTE` volumes: from the Hub (`xmls/STATUTE-{n}.xml` for structure, `uslm/STATUTE-{n}/…`
  from the reprocessing run for identifiers and corrected text). Until the reprocessing run
  lands, the volume USLM is loaded as is, with identifiers assigned by the rules in the OCR plan
  section 7 from `docNumber`, `citableAs`, and section `num`.
- `PLAW` 113th onward: GovInfo bulk data USLM; 104th to 112th: PDF through the pipeline's
  `digital` profile.
- `COMPS`: `collections/COMPS/{since}` polled daily; USLM per package.
- `citations`: from `dreamproit/uscode` (`versions` config) on each new release point.

## 7. Integration with uscode.linkedlegislation.org (later task)

- `refs.ts`: `/us/pl/…`, `/us/pvtl/…`, `/us/act/…`, `/us/stat/…` link to
  `https://statutes.linkedlegislation.org{href}` when `POST /api/v1/labels` reports `exists`;
  the hover label comes from the same call; govinfo remains the fallback for a `false`.
- Version timeline: each `laws[]` entry links to `/us/pl/{c}/{n}` and, when `pl_section_raw`
  parses, to the section; the link carries `?view=enacted`.
- A "cited by" panel on a statutes page lists the US Code sections from `cited-by`.

## 8. Repository and deployment

A new repository, `statutes-linkedlegislation`, started from the US Code site's skeleton:
FastAPI, Postgres, the `Repository` protocol, `params.py` conventions (`served_note`,
`cache_control`, `not_found`), Caddy in front of the API and an Astro reader, one EC2 box or the
same box as the US Code site with a second Caddy site block. The pipeline repository
(`us-statute-pdf-to-xml`) stays the producer of the Hub dataset and does not serve HTTP.

## 9. Order of work

1. Schema and ingest for `STATUTE` volume USLM with rule-based identifiers; `laws`, `units`,
   `stat_pages`; `/api/v1/us/pl`, `/us/act`, `/us/stat`, `labels`, `status`. Enacted view with
   `amended.status = unknown`.
2. `COMPS` ingest and the compiled view; `alternatives` between the two.
3. `citations` from the uscode dataset; `cited-by`; `amended.status` from evidence.
4. `PLAW` 113th onward from bulk data, replacing the volume-derived units for those laws.
5. Reader at `/app`, citation parser, and the US Code site integration.
6. Swap in the reprocessed USLM from the OCR plan as it lands on the Hub, volume by volume.
