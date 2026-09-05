"""Split a Statutes at Large volume USLM into one USLM document per GovInfo granule.

    python -m pipeline.split_uslm data/historical/xmls/STATUTE-64.xml --out data/granules/STATUTE-64/uslm \
        [--granules data/granules/STATUTE-64/granules.json]

Volume structure (verified on STATUTE-64, see docs/architecture.md):

    statutesAtLarge/main/collection[@role=statutesParts]/component[@role=statutesPart]
        meta, preface                       -> FRONTMATTER granule
        publicLaws/component/pLaw           -> PUBLICLAW
        privateLaws/component/pLaw          -> PRIVATELAW
        concurrentResolutions/component/resolution  -> SCONRES / HCONRES
        presidentialDocs[@role=proclamations]/component/presidentialDoc -> PROCLAMATION
        presidentialDocs[@role=treaties]/component/presidentialDoc      -> TREATY
        component/reorganizationPlans/reorganizationPlan                -> REORGPLAN
        backMatter                          -> BACKMATTER

Each document carries `meta/citableAs` ("64 Stat. 371") giving its start page; documents without
it (proclamations, resolutions, reorganization plans) start on the page of the first `<page>`
marker inside them, or the last marker before them. Granule ids are `STATUTE-{v}-Pg{PAGE}` for
the first document starting on a page and `-Pg{PAGE}-{n}` for the n-th (GovInfo's `pagePosition`).
Page labels in `<page identifier="/us/stat/64/b3">` are lower case; granule ids use upper case.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from lxml import etree

logger = logging.getLogger(__name__)

USLM_NS = "http://schemas.gpo.gov/xml/uslm"
DC_NS = "http://purl.org/dc/elements/1.1/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
NS = f"{{{USLM_NS}}}"
DC = f"{{{DC_NS}}}"
NSMAP = {None: USLM_NS, "dc": DC_NS, "xsi": XSI_NS}
SCHEMA_LOCATION = f"{USLM_NS} https://www.govinfo.gov/schemas/xml/uslm/uslm-2.0.17.xsd"

DOC_TAGS = {NS + "pLaw", NS + "presidentialDoc", NS + "resolution", NS + "reorganizationPlan"}
GRANULE_ID = re.compile(r"^STATUTE-(\d+)-Pg([A-Za-z]*\d+)(?:-(\d+))?$")
MATTER_ID = re.compile(r"^STATUTE-(\d+)-(FrontMatter|BackMatter)-(\d+)-Pg(.+)$")


@dataclass
class Slice:
    element: etree._Element
    doc_type: str  # pLaw, presidentialDoc, resolution, reorganizationPlan, frontMatter, backMatter
    granule_class: Optional[str]
    start_page: Optional[str]  # normalized lower-case label: "371", "b3", "a283"
    ordinal: int = 1
    part: Optional[int] = None
    citable_as: Optional[str] = None
    title: Optional[str] = None
    granule_id: Optional[str] = None
    matched: bool = False
    path: Optional[str] = None


@dataclass
class SplitReport:
    volume: int
    slices: list[Slice]
    expected_ids: set[str] = field(default_factory=set)

    @property
    def produced_ids(self) -> set[str]:
        return {s.granule_id for s in self.slices if s.granule_id}

    @property
    def missing(self) -> list[str]:
        return sorted(self.expected_ids - self.produced_ids)

    @property
    def extra(self) -> list[str]:
        return sorted(self.produced_ids - self.expected_ids) if self.expected_ids else []


# ---------------------------------------------------------------------------- helpers


def normalize_page(label: Optional[str]) -> Optional[str]:
    if not label:
        return None
    label = label.strip().lower()
    label = re.sub(r"@.*$", "", label)  # b12@eng -> b12 (treaty language variants)
    return label or None


def page_from_identifier(identifier: Optional[str]) -> Optional[str]:
    if not identifier:
        return None
    return normalize_page(identifier.rsplit("/", 1)[-1])


def page_from_citation(citable_as: Optional[str]) -> Optional[str]:
    if not citable_as:
        return None
    m = re.search(r"Stat\.\s*([A-Za-z]*\d+)", citable_as)
    return normalize_page(m.group(1)) if m else None


def page_label_for_id(page: str) -> str:
    """'b3' -> 'B3', '371' -> '371'."""
    return page.upper()


def parse_granule_id(granule_id: str) -> Optional[tuple[str, int]]:
    """'STATUTE-64-PgA283-2' -> ('a283', 2). None for front/back matter ids."""
    m = GRANULE_ID.match(granule_id)
    if not m:
        return None
    return normalize_page(m.group(2)), int(m.group(3) or 1)


def make_granule_id(volume: int, page: str, ordinal: int) -> str:
    base = f"STATUTE-{volume}-Pg{page_label_for_id(page)}"
    return base if ordinal == 1 else f"{base}-{ordinal}"


def volume_from_root(root: etree._Element, fallback: Optional[int] = None) -> int:
    for page in root.iter(NS + "page"):
        m = re.match(r"/us/stat/(\d+)/", page.get("identifier") or "")
        if m:
            return int(m.group(1))
    if fallback is not None:
        return fallback
    raise ValueError("cannot determine the volume number from page identifiers")


HEADER_TEXT_NODES = 0


def first_marker_before_text(doc: etree._Element, max_text_nodes: int = HEADER_TEXT_NODES) -> Optional[str]:
    """Page label of the first <page> inside `doc` that appears within the document header.

    With the default of 0 text nodes, only a marker that precedes all text counts; a marker after
    body text belongs to a later page and the caller falls back to the last marker before the
    document. Documents without citableAs are then aligned to the GovInfo listing by position
    (see align_groups), which is exact when the class group counts agree.
    """
    seen_text = 0
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        if el.tag == NS + "page":
            page = page_from_identifier(el.get("identifier"))
            if page:
                return page
            continue
        if el.tag == NS + "meta" or any(a.tag == NS + "meta" for a in el.iterancestors()):
            continue
        if (el.text or "").strip():
            seen_text += 1
            if seen_text > max_text_nodes:
                return None
    return None


def granule_class_for(doc: etree._Element) -> Optional[str]:
    tag = doc.tag.replace(NS, "")
    if tag == "reorganizationPlan":
        return "REORGPLAN"
    container = doc.getparent()
    while container is not None and container.tag == NS + "component":
        container = container.getparent()
    ctag = container.tag.replace(NS, "") if container is not None else ""
    role = (container.get("role") or "") if container is not None else ""
    if tag == "pLaw":
        return {"publicLaws": "PUBLICLAW", "privateLaws": "PRIVATELAW"}.get(ctag)
    if tag == "presidentialDoc":
        return {"proclamations": "PROCLAMATION", "treaties": "TREATY"}.get(role)
    if tag == "resolution":
        dctype = (doc.findtext(f"{NS}meta/{DC}type") or "").lower()
        if "senate" in dctype:
            return "SCONRES"
        if "house" in dctype:
            return "HCONRES"
        return "CONRES"
    return None


def part_index(el: etree._Element) -> Optional[int]:
    """1-based index of the statutesPart component containing `el`."""
    for anc in el.iterancestors():
        if anc.tag == NS + "component" and anc.get("role") == "statutesPart":
            parent = anc.getparent()
            parts = [c for c in parent if c.tag == NS + "component" and c.get("role") == "statutesPart"]
            return parts.index(anc) + 1
    return None


# ---------------------------------------------------------------------------- splitting


def iter_slices(root: etree._Element) -> list[Slice]:
    """Documents in document order with their start pages, plus front and back matter per part."""
    slices: list[Slice] = []
    last_page: Optional[str] = None
    skip_until: Optional[etree._Element] = None

    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        if el.tag == NS + "page":
            page = page_from_identifier(el.get("identifier"))
            if page:
                last_page = page
            continue
        if el.tag in DOC_TAGS:
            if any(a.tag in DOC_TAGS for a in el.iterancestors()):
                continue  # nested document (e.g. quoted) stays inside its parent
            citable = el.findtext(f"{NS}meta/{NS}citableAs")
            start = page_from_citation(citable) or first_marker_before_text(el) or last_page
            title = el.findtext(f"{NS}meta/{DC}title")
            slices.append(
                Slice(element=el, doc_type=el.tag.replace(NS, ""), granule_class=granule_class_for(el),
                      start_page=start, part=part_index(el), citable_as=citable, title=(title or "").strip() or None)
            )
        elif el.tag == NS + "preface" and el.getparent() is not None and el.getparent().get("role") == "statutesPart":
            page = first_marker_before_text(el) or last_page
            slices.append(Slice(element=el, doc_type="frontMatter", granule_class="FRONTMATTER", start_page=page,
                                part=part_index(el)))
        elif el.tag == NS + "backMatter" and el.getparent() is not None and el.getparent().get("role") == "statutesPart":
            page = first_marker_before_text(el) or last_page
            slices.append(Slice(element=el, doc_type="backMatter", granule_class="BACKMATTER", start_page=page,
                                part=part_index(el)))
    return slices


def assign_ids(slices: Iterable[Slice], volume: int, granules: Optional[list[dict]] = None) -> None:
    """Assign granule ids by (start page, order); use the GovInfo listing for front/back matter when given."""
    per_page: dict[str, int] = {}
    for s in slices:
        if s.doc_type in ("frontMatter", "backMatter"):
            continue
        key = s.start_page or "unknown"
        per_page[key] = per_page.get(key, 0) + 1
        s.ordinal = per_page[key]
        s.granule_id = make_granule_id(volume, key, s.ordinal) if s.start_page else f"STATUTE-{volume}-unknown-{s.ordinal}"

    matter_ids: dict[tuple[str, int], list[str]] = {}
    for g in granules or []:
        m = MATTER_ID.match(g.get("granuleId", ""))
        if m:
            matter_ids.setdefault((m.group(2), int(m.group(3))), []).append(g["granuleId"])
    counters: dict[tuple[str, int], int] = {}
    for s in slices:
        if s.doc_type not in ("frontMatter", "backMatter"):
            continue
        kind = "FrontMatter" if s.doc_type == "frontMatter" else "BackMatter"
        key = (kind, s.part or 0)
        n = counters.get(key, 0)
        counters[key] = n + 1
        candidates = matter_ids.get(key, [])
        if n < len(candidates):
            s.granule_id = candidates[n]
        else:
            s.granule_id = f"STATUTE-{volume}-{kind}-{s.part or 0}-Pg{page_label_for_id(s.start_page or 'unknown')}"
            if n:
                s.granule_id += f"-{n + 1}"


GROUPS = {
    "PUBLICLAW": ("PUBLICLAW",),
    "PRIVATELAW": ("PRIVATELAW",),
    "PROCLAMATION": ("PROCLAMATION",),
    "TREATY": ("TREATY",),
    "REORGPLAN": ("REORGPLAN",),
    "RESOLUTION": ("HCONRES", "SCONRES", "CONRES"),
}


def page_sort_key(granule_id: str) -> tuple:
    parsed = parse_granule_id(granule_id)
    if parsed is None:
        return ("~", 0, 0)
    page, position = parsed
    m = re.match(r"([a-z]*)(\d+)$", page)
    return (m.group(1) if m else page, int(m.group(2)) if m else 0, position)


def align_groups(slices: list[Slice], granules: list[dict]) -> dict[str, str]:
    """For each class group whose XML document count equals GovInfo's granule count, assign ids by
    position (documents appear in page order in both). Documents with citableAs keep their ids.
    Returns {group: "aligned"|"count mismatch (xml n, govinfo m)"}."""
    outcome = {}
    for group, classes in GROUPS.items():
        docs = [s for s in slices if s.granule_class in classes]
        listed = sorted((g["granuleId"] for g in granules if g.get("granuleClass") in classes), key=page_sort_key)
        if not docs:
            continue
        if len(docs) != len(listed):
            outcome[group] = f"count mismatch (xml {len(docs)}, govinfo {len(listed)})"
            continue
        for s, gid in zip(docs, listed):
            if s.citable_as:
                continue
            s.granule_id = gid
            parsed = parse_granule_id(gid)
            if parsed:
                s.start_page, s.ordinal = parsed
        outcome[group] = "aligned"
    return outcome


def match_listing(report: SplitReport, granules: list[dict]) -> None:
    by_id = {g["granuleId"]: g for g in granules}
    report.expected_ids = set(by_id)
    for s in report.slices:
        g = by_id.get(s.granule_id or "")
        s.matched = g is not None
        if g is not None and s.granule_class and g.get("granuleClass") not in (s.granule_class, None):
            logger.warning("%s: class %s in XML, %s on GovInfo", s.granule_id, s.granule_class, g.get("granuleClass"))


def standalone_document(el: etree._Element) -> etree._ElementTree:
    """Deep-copy `el` into a standalone USLM document with namespace declarations and schemaLocation."""
    node = copy.deepcopy(el)
    root = etree.Element(node.tag, nsmap=NSMAP)
    for k, v in node.attrib.items():
        root.set(k, v)
    root.set(f"{{{XSI_NS}}}schemaLocation", SCHEMA_LOCATION)
    root.text = node.text
    for child in node:
        root.append(child)
    etree.cleanup_namespaces(root)
    return etree.ElementTree(root)


def split_volume(xml_path: Path | str, out_dir: Path | str, granules: Optional[list[dict]] = None,
                 volume: Optional[int] = None, write: bool = True) -> SplitReport:
    root = etree.parse(str(xml_path)).getroot()
    volume = volume_from_root(root, volume)
    slices = iter_slices(root)
    assign_ids(slices, volume, granules)
    report = SplitReport(volume=volume, slices=slices)
    if granules:
        for group, outcome in align_groups(slices, granules).items():
            logger.info("%s: %s", group, outcome)
        match_listing(report, granules)
    out_dir = Path(out_dir)
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        for s in slices:
            path = out_dir / f"{s.granule_id}.xml"
            standalone_document(s.element).write(str(path), xml_declaration=True, encoding="utf-8", pretty_print=False)
            s.path = str(path)
        index = [
            {
                "granule_id": s.granule_id, "doc_type": s.doc_type, "granule_class": s.granule_class,
                "start_page": s.start_page, "ordinal": s.ordinal, "part": s.part, "citable_as": s.citable_as,
                "title": s.title, "matched": s.matched, "file": Path(s.path).name if s.path else None,
            }
            for s in slices
        ]
        (out_dir / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return report


def summarize(report: SplitReport) -> str:
    from collections import Counter

    classes = Counter(s.granule_class or "?" for s in report.slices)
    lines = [f"volume {report.volume}: {len(report.slices)} documents", "  " + ", ".join(f"{k}={v}" for k, v in sorted(classes.items()))]
    if report.expected_ids:
        lines.append(f"  GovInfo lists {len(report.expected_ids)} granules; matched {len(report.produced_ids & report.expected_ids)}, "
                     f"missing {len(report.missing)}, extra {len(report.extra)}")
        if report.missing:
            lines.append("  missing: " + ", ".join(report.missing[:20]) + (" ..." if len(report.missing) > 20 else ""))
        if report.extra:
            lines.append("  extra: " + ", ".join(report.extra[:20]) + (" ..." if len(report.extra) > 20 else ""))
    return "\n".join(lines)


def load_granules(path: Optional[str], package_id: str, fetch: bool) -> Optional[list[dict]]:
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    if fetch:
        from downloader.config import govinfo_api_key
        from downloader.govinfo import GovInfoClient

        with GovInfoClient(govinfo_api_key()) as client:
            granules = list(client.iter_granules(package_id))
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(granules), encoding="utf-8")
        return granules
    return None


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m pipeline.split_uslm", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("xml", help="volume USLM, e.g. data/historical/xmls/STATUTE-64.xml")
    p.add_argument("--out", default=None, help="output directory (default data/granules/STATUTE-{v}/uslm)")
    p.add_argument("--granules", default=None, help="GovInfo granule listing JSON (default data/granules/STATUTE-{v}/granules.json)")
    p.add_argument("--fetch-granules", action="store_true", help="fetch the listing from GovInfo when the JSON is missing")
    p.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    m = re.search(r"STATUTE-(\d+)", Path(args.xml).name)
    volume = int(m.group(1)) if m else None
    package_id = f"STATUTE-{volume}" if volume else "STATUTE"
    out = args.out or f"data/granules/{package_id}/uslm"
    listing = args.granules or f"data/granules/{package_id}/granules.json"
    granules = load_granules(listing, package_id, args.fetch_granules)
    report = split_volume(args.xml, out, granules, volume, write=not args.dry_run)
    print(summarize(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
