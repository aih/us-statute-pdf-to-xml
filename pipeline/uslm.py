"""Build GovInfo-namespace USLM from a DoclingDocument, with identifiers, and validate it against the XSD.

Output shape follows the GPO files (see docs/architecture.md):

    <pLaw xmlns="http://schemas.gpo.gov/xml/uslm" identifier="/us/pl/118/5">
      <meta>dc:title, dc:type, docNumber, citableAs, approvedDate, congress, publicPrivate ...</meta>
      <preface>centerRunningHead, page, dc:type, docNumber, congress</preface>
      <main>
        <longTitle><docTitle>An Act</docTitle><officialTitle>To ...</officialTitle></longTitle>
        <enactingFormula>Be it enacted ...</enactingFormula>
        <section identifier="/us/pl/118/5/s1" id="s1"><num value="1">SECTION 1. </num><heading>...</heading>
          <subsection identifier="/us/pl/118/5/s1/a" id="s1_a"><num value="a">(a) </num><heading>..</heading><content>..</content>
        <page identifier="/us/stat/137/11"/>    page markers at each PDF page boundary
        <sidenote><p>..</p></sidenote>          marginal notes, by geometry
        <action><actionDescription>Approved</actionDescription> <date date="2023-06-03">June 3, 2023</date>.</action>
      </main>
      <legislativeHistory>...</legislativeHistory>
    </pLaw>

Docling labels seen on statute pages: text, section_header, footnote, picture, table. Running heads,
typesetting footers (VerDate lines), and marginal sidenotes are separated by position on the page.

A STATUTE granule PDF holds whole pages, so page 1 starts with the tail of the previous law and the
last page ends with the head of the next one. The builder keeps every body item (defect F2 of the
2026-09-07 plan): items before the recognized document start go into `preface` as `p` elements, items
after the law's own "Approved" line go into an `appendix` with role `trailingMatter`, and items that
match no rule go into the current level as `content`/`p`. `UslmBuilder.stats` reports the character
counts and the warnings raised on the way; nothing Docling produced is discarded except page
furniture (running heads after the first, typesetting footers).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

from lxml import etree
from lxml.builder import ElementMaker

logger = logging.getLogger(__name__)

USLM_NS = "http://schemas.gpo.gov/xml/uslm"
DC_NS = "http://purl.org/dc/elements/1.1/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
XHTML_NS = "http://www.w3.org/1999/xhtml"
NSMAP = {None: USLM_NS, "dc": DC_NS, "xsi": XSI_NS}
SCHEMA_LOCATION = f"{USLM_NS} https://www.govinfo.gov/schemas/xml/uslm/uslm-2.0.17.xsd"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "uslm-2.0.17.xsd"

E = ElementMaker(namespace=USLM_NS, nsmap=NSMAP)
DCE = ElementMaker(namespace=DC_NS, nsmap=NSMAP)
H = ElementMaker(namespace=XHTML_NS, nsmap={None: XHTML_NS})

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
MONTH_RE = re.compile(rf"^(?:{MONTHS}|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?$", re.I)

RE_CHAPTER = re.compile(r"^[\[\(\{]?\s*CHAP(?:TER)?\s*[.,]?\s+(\d+|[IVXLCDM]+)\s*[.,]?\s*[\]\)\}]?\s*(?:[-–—]+\s*(.*))?$", re.I | re.S)
RE_CHAPTER_TITLE = re.compile(r"^(An\s+Act|A\s+Joint\s+Resolution|Joint\s+Resolution|A\s+Resolution)\b[.,]?\s*(.*)$", re.I | re.S)
RE_PROCLAMATION_HEAD = re.compile(r"^(BY\s+THE\s+PRESIDENT\s+OF\s+THE\s+UNITED\s+STATES|PROCLAMATION\s+\d{3,5}\s*$)", re.I)
RE_PUBLIC_LAW = re.compile(r"^Public\s+Law\s+(\d+)\s*[-–—]\s*(\d+)", re.I)
RE_PRIVATE_LAW = re.compile(r"^Private\s+Law\s+(\d+)\s*[-–—]\s*(\d+)", re.I)
RE_CONGRESS = re.compile(r"(\d+)(?:st|nd|rd|th)\s+Congress", re.I)
RE_DOC_TITLE = re.compile(r"^(AN\s+ACT|An\s+Act|JOINT\s+RESOLUTION|Joint\s+Resolution|CONCURRENT\s+RESOLUTION|A\s+PROCLAMATION)\b\.?$", re.I)
RE_ENACTING = re.compile(r"^(Be\s+it\s+enacted|Resolved\s+by|Resolved,)", re.I)
RE_SECTION = re.compile(r"^(SECTION|SEC|Sec|Spe|Sro)\s*[.,]?\s*(\d+[A-Za-z]?)\s*[.,:]\s*(.*)$", re.S)
RE_LEVEL = re.compile(r"^[\"“‘']?\(\s*([A-Za-z]{1,4}|\d{1,3})\s*\)\s*(.*)$", re.S)
RE_HEADING_DASH = re.compile(r"^([A-Z][A-Z0-9 ,;'’\-]{2,}?)\.\s*[-—–]+\s*(.*)$", re.S)
RE_APPROVED = re.compile(rf"^Approved,?\s+((?:{MONTHS})\s+\d{{1,2}},\s+\d{{4}})\.?", re.I)
# End of a document: "Approved, March 3, 1853." / "Agreed to August 16, 1958." / "Passed December 9, 1971.", also at
# the end of a longer item when OCR merged lines; the month may be garbled, the verb is matched fuzzily below.
RE_END = re.compile(r"(?:^|\s)([A-Za-z]{4,12}(?:\s+to)?),?\s+([A-Za-z]{2,10}\.?\s+\d{1,2},\s+\d{4})\.?\s*$", re.I)
END_VERBS = ("approved", "agreed to", "passed")
# Old chapter line with OCR damage: "Cuar. CXXII.- An Act for the Relief of ..." or "CXXL- An Act ..." (chapter word lost)
RE_CHAPTER_FUZZY = re.compile(r"^(?:([A-Za-z]{3,7})[.,]?\s+)?([IVXLCDM]{2,}[A-Z]?|\d{1,4})[.,]?\s*[-–—]+\s*(A[nx]\s+Act|A\s+Joint\s+Resolution|Joint\s+Resolution)\b", re.I)
RE_WHEREAS = re.compile(r"^Whereas\b", re.I)
# Lines found in the body of a document, after its heading and marker lines.
RE_BODY_SIGNAL = re.compile(r"^(Whereas\b|NOW,?\s+THEREFORE\b|IN\s+WITNESS\s+WHEREOF\b|Resolved\b|Be\s+it\s+(enacted|resolved)\b|SEC(TION)?[.,]?\s*\d)", re.I)
RE_DATE_LINE = re.compile(rf"^(?:{MONTHS})\.?\s+\d{{1,2}},\s+\d{{4}}$")
RE_SHORT_MONTH_DATE = re.compile(r"^[A-Z][a-z]{2,8}\.?\s+\d{1,2},\s+\d{4}$")
RE_BILL_REF = re.compile(r"^\[?(H\.\s?R\.|S\.|H\.\s?J\.\s?Res\.|S\.\s?J\.\s?Res\.|H\.\s?Con\.\s?Res\.|S\.\s?Con\.\s?Res\.)\s*\d+\]?$")
RE_LEG_HISTORY = re.compile(r"^LEGISLATIVE\s+HISTORY", re.I)
RE_STAT_HEAD = re.compile(r"^\d+\s+STAT\.\s*\d*", re.I)
RE_VERDATE = re.compile(r"^(VerDate|Jkt\s|PO\s0|Frm\s0|Fmt\s\d|Sfmt\s\d|E:\\|PsN:|APPS\d|\d{2}:\d{2}\s\w{3}\s\d{2},\s\d{4}$)")
RE_PAGE_NUM = re.compile(r"^[\[\(]?\s*\d{1,4}\s*[\]\)]?$")

LEVEL_ORDER = ["section", "subsection", "paragraph", "subparagraph", "clause", "subclause", "item", "subitem"]
ROMAN = re.compile(r"^(i{1,3}|iv|v|vi{0,3}|ix|x{1,3}|xi{1,3}|xiv|xv)$")


# ---------------------------------------------------------------------------- inputs


@dataclass
class DocIdentity:
    """What the builder needs to know about the document beyond its pages."""

    doc_type: str = "pLaw"  # pLaw | presidentialDoc | resolution
    congress: Optional[int] = None
    law_number: Optional[int] = None
    is_private: bool = False
    volume: Optional[int] = None
    start_page: Optional[int] = None  # Statutes at Large page of PDF page 1
    granule_id: Optional[str] = None
    package_id: Optional[str] = None
    date_issued: Optional[str] = None
    title: Optional[str] = None
    session: Optional[int] = None

    @property
    def law_identifier(self) -> Optional[str]:
        if self.congress and self.law_number:
            kind = "pvtl" if self.is_private else "pl"
            return f"/us/{kind}/{self.congress}/{self.law_number}"
        return None


@dataclass
class Item:
    page: int
    label: str
    text: str
    l: float
    t: float
    r: float
    b: float
    kind: str = "body"  # body | sidenote | header | footer
    table: Optional[list[list[str]]] = None


@dataclass
class Page:
    no: int
    width: float
    height: float
    items: list[Item] = field(default_factory=list)


# ---------------------------------------------------------------------------- Docling -> items


def _clean(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    return text.strip()


def load_pages(doc) -> list[Page]:
    """Flatten a DoclingDocument into pages of positioned items (body/sidenote/header/footer)."""
    pages: dict[int, Page] = {}
    for no, p in doc.pages.items():
        pages[int(no)] = Page(no=int(no), width=float(p.size.width), height=float(p.size.height))
    for item, _level in doc.iterate_items():
        label = str(getattr(item, "label", "")).split(".")[-1].lower()
        prov = getattr(item, "prov", None)
        if not prov:
            continue
        pr = prov[0]
        bbox = pr.bbox
        page = pages.get(pr.page_no)
        if page is None:
            page = pages[pr.page_no] = Page(no=pr.page_no, width=612.0, height=792.0)
        table = None
        text = getattr(item, "text", "") or ""
        if label == "table":
            table = table_grid(item)
            text = " ".join(" | ".join(row) for row in table) if table else ""
        elif label == "picture":
            continue
        text = _clean(text)
        if not text:
            continue
        t, b = (bbox.t, bbox.b) if bbox.t >= bbox.b else (bbox.b, bbox.t)
        page.items.append(Item(page=page.no, label=label, text=text, l=float(bbox.l), t=float(t), r=float(bbox.r), b=float(b), table=table))
    result = [pages[k] for k in sorted(pages)]
    for page in result:
        classify_items(page)
    return result


def table_grid(item) -> Optional[list[list[str]]]:
    data = getattr(item, "data", None)
    grid = getattr(data, "grid", None)
    if not grid:
        return None
    rows = []
    for row in grid:
        rows.append([_clean(getattr(cell, "text", "") or "") for cell in row])
    return rows


def classify_items(page: Page) -> None:
    """Mark header, footer, and sidenote items by position relative to the main text column."""
    if not page.items:
        return
    W, Hh = page.width, page.height
    wide = [it for it in page.items if (it.r - it.l) > 0.4 * W]
    if wide:
        main_l = sorted(it.l for it in wide)[len(wide) // 2]
        main_r = sorted(it.r for it in wide)[len(wide) // 2]
    else:
        main_l, main_r = 0.15 * W, 0.85 * W
    for it in page.items:
        centre_y = (it.t + it.b) / 2
        if it.t < 0.06 * Hh or RE_VERDATE.match(it.text):
            it.kind = "footer"
        elif it.b > 0.93 * Hh and (RE_STAT_HEAD.match(it.text) or RE_PUBLIC_LAW.match(it.text) or RE_PRIVATE_LAW.match(it.text)
                                   or RE_PAGE_NUM.match(it.text) or len(it.text) < 60):
            it.kind = "header"
        elif it.r <= main_l + 0.02 * W or it.l >= main_r - 0.02 * W:
            it.kind = "sidenote"
        elif (it.r - it.l) < 0.25 * W and (it.l > main_r - 0.3 * W and it.l > 0.6 * W):
            it.kind = "sidenote"
        else:
            it.kind = "body"
    page.items.sort(key=lambda it: (-round(it.t / 4), it.l))


# ---------------------------------------------------------------------------- text helpers


def level_for(designator: str, current: Optional[str]) -> str:
    """Pick the USLM level for a parenthesized designator, using the current nesting for ambiguous cases."""
    d = designator
    if d.isdigit():
        return "paragraph" if current in (None, "section", "subsection", "paragraph") else "subclause" if current in ("clause", "subclause") else "paragraph"
    if ROMAN.match(d) and current in ("subparagraph", "clause"):
        return "clause"
    if d.islower():
        return "subsection" if current in (None, "section", "subsection") else "clause" if current in ("subparagraph", "clause") else "subsection"
    if d.isupper():
        return "subparagraph" if current in ("paragraph", "subparagraph", "clause", "subclause") else "subparagraph"
    return "subsection"


def parse_us_date(text: str) -> Optional[str]:
    text = text.replace(".", "").strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def slug_id(identifier: str) -> str:
    return "id" + re.sub(r"[^A-Za-z0-9]+", "_", identifier)


def split_heading(text: str) -> tuple[Optional[str], str]:
    """'IN GENERAL.-For purposes ...' -> ('IN GENERAL.', 'For purposes ...')."""
    m = RE_HEADING_DASH.match(text)
    if m:
        return m.group(1).strip() + ".", m.group(2).strip()
    return None, text


def split_section_heading(rest: str) -> tuple[Optional[str], str]:
    """Leading capitalized run ending in a period is the heading; the remainder is content."""
    m = re.match(r"^([A-Z0-9][A-Z0-9 ,;:'’\-\(\)]{3,}?\.)(\s+(.*))?$", rest, re.S)
    if m:
        return m.group(1).strip(), (m.group(3) or "").strip()
    return None, rest


# ---------------------------------------------------------------------------- builder


class UslmBuilder:
    def __init__(self, identity: DocIdentity):
        self.identity = identity
        self.pages: list[Page] = []
        self.running_head: Optional[str] = None
        self.doc_number: Optional[str] = None
        self.chapter: Optional[str] = None
        self.approved: Optional[str] = None
        self.approved_text: Optional[str] = None
        self.official_title: list[str] = []
        self.doc_title: Optional[str] = None
        self.enacting: Optional[str] = None
        self.sidenotes: list[tuple[int, float, str]] = []
        self.leg_history: list[str] = []
        self.body: list[etree._Element] = []  # main children in order
        self.stack: list[tuple[str, etree._Element, str]] = []  # (level, element, identifier)
        self.section_count = 0
        self.seen_body_start = False
        self.page_markers: list[etree._Element] = []
        self.warnings: list[str] = []
        self.used_ids: set[str] = set()
        self.body_signal_seen = False  # an enacting formula, section, or preamble line since the document start
        self.title_open = False  # collecting officialTitle lines right after the docTitle line
        self.preface_items: list[str] = []  # text before the document start (previous law's tail)
        self.trailing_items: list[str] = []  # text after the document's "Approved" line (next law's head)
        self.start_rule: Optional[str] = None
        self.stats: dict = {}

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        logger.debug("%s: %s", self.identity.granule_id or self.identity.package_id, message)

    def _unique_id(self, base: str) -> str:
        """xsd:ID values must be unique; quoted or repeated section numbers get a numeric suffix."""
        candidate = base
        n = 2
        while candidate in self.used_ids:
            candidate = f"{base}_{n}"
            n += 1
        self.used_ids.add(candidate)
        return candidate

    # ------------------------------------------------------------------ public

    def build(self, doc) -> etree._ElementTree:
        self.pages = load_pages(doc)
        self._ingest()
        tree = etree.ElementTree(self._assemble())
        self.stats = self._stats(doc, tree)
        return tree

    def _stats(self, doc, tree: etree._ElementTree) -> dict:
        docling_chars = docling_text_chars(doc)
        kept = kept_text_chars(tree)
        body = len(_squash(" ".join(tree.getroot().find(f"{{{USLM_NS}}}main").itertext())))
        return {
            "docling_chars": docling_chars, "kept_chars": kept, "body_chars": body,
            "kept_ratio": round(kept / docling_chars, 4) if docling_chars else 1.0,
            "preface_items": len(self.preface_items), "trailing_items": len(self.trailing_items),
            "start_rule": self.start_rule, "warnings": len(self.warnings), "warning_log": self.warnings,
        }

    # ------------------------------------------------------------------ ingest

    def _statute_page(self, page_no: int) -> Optional[int]:
        if self.identity.start_page is None:
            return None
        return self.identity.start_page + page_no - 1

    def _page_marker(self, page_no: int) -> etree._Element:
        stat_page = self._statute_page(page_no)
        marker = E.page()
        if self.identity.volume and stat_page is not None:
            marker.set("identifier", f"/us/stat/{self.identity.volume}/{stat_page}")
            marker.text = f"{self.identity.volume} STAT. {stat_page}"
        return marker

    @property
    def _shares_pages(self) -> bool:
        """STATUTE granules are cut from volume pages shared with the neighbouring laws."""
        return bool(self.identity.package_id and self.identity.package_id.startswith("STATUTE") and self.identity.granule_id)

    @staticmethod
    def is_start_marker(text: str) -> bool:
        """A line that begins a document: a law number, a bracketed chapter ("[CHAPTER 486]"), a chapter line
        with the title ("CHAP. 162.-An Act ..."), a bare "AN ACT"/"JOINT RESOLUTION", or a proclamation head.
        A chapter heading inside a law ("CHAPTER 1-GENERAL PROVISIONS") is not one."""
        if RE_PUBLIC_LAW.match(text) or RE_PRIVATE_LAW.match(text) or RE_DOC_TITLE.match(text) or RE_PROCLAMATION_HEAD.match(text):
            return True
        m = RE_CHAPTER.match(text)
        if not m:
            return UslmBuilder.is_fuzzy_chapter_start(text)
        rest = (m.group(2) or "").strip()
        bracketed = text.lstrip()[:1] in "[({"
        return bracketed or not rest or bool(RE_CHAPTER_TITLE.match(rest))

    @staticmethod
    def is_end_marker(text: str) -> bool:
        m = RE_END.search(text)
        if not m:
            return False
        verb = re.sub(r"\s+", " ", m.group(1)).lower()
        if verb in END_VERBS:
            return True
        # OCR of small capitals: "Arprrovep", "Appnoven"
        from rapidfuzz import fuzz

        return fuzz.ratio(verb, "approved") >= 60 and MONTH_RE.match(m.group(2).split()[0]) is not None

    @staticmethod
    def is_fuzzy_chapter_start(text: str) -> bool:
        m = RE_CHAPTER_FUZZY.match(text)
        if not m:
            return False
        word = (m.group(1) or "").lower()
        if not word:
            return True
        from rapidfuzz import fuzz

        return fuzz.ratio(word, "chap") >= 50 or fuzz.ratio(word, "chapter") >= 60

    @staticmethod
    def is_start_signal(text: str) -> bool:
        """Something a document has near its start: a start marker, a preamble, an enacting formula, a section."""
        return bool(UslmBuilder.is_start_marker(text) or RE_WHEREAS.match(text) or RE_ENACTING.match(text) or RE_SECTION.match(text))

    def _law_number_line(self, text: str) -> bool:
        """A Public/Private Law line carrying this document's own law number."""
        if not self.identity.law_number:
            return False
        m = RE_PRIVATE_LAW.match(text) if self.identity.is_private else RE_PUBLIC_LAW.match(text)
        return bool(m and int(m.group(2)) == self.identity.law_number)

    @property
    def _ordinal(self) -> int:
        """Position of the granule on its first page: STATUTE-72-Pg983-2 is the second document starting there."""
        m = re.search(r"-Pg[A-Za-z]*\d+-(\d+)$", self.identity.granule_id or "")
        return int(m.group(1)) if m else 1

    def _title_match(self, items: list[Item]) -> Optional[int]:
        """Index of the start-marker or heading line most similar to the GovInfo title, if any is close."""
        title = _squash(self.identity.title or "")
        if len(title) < 12:
            return None
        from rapidfuzz import fuzz

        best, best_score = None, 0.0
        for i, it in enumerate(items):
            text = it.text
            if len(text) < 0.5 * len(title) or not (self.is_start_marker(text) or it.label == "section_header" or len(text) <= 1.5 * len(title) + 20):
                continue
            # partial_ratio would score a short fragment inside the title at 100; compare whole strings when the
            # line is shorter than the title
            score = fuzz.ratio(title.lower(), text.lower()) if len(text) < len(title) else fuzz.partial_ratio(title.lower(), text.lower())
            if score > best_score:
                best, best_score = i, score
        if best is None or best_score < 80:
            return None
        # the marker run the title belongs to starts at the previous consecutive marker lines
        while best > 0 and self.is_start_marker(items[best - 1].text):
            best -= 1
        return best

    def _find_start(self, items: list[Item]) -> tuple[int, str]:
        """Index of the first item of this document among the body items of its first page.

        Rules, in order: the line carrying this document's own law number; the line closest to the GovInfo
        title; the n-th run of start-marker lines (chapter, law number, "AN ACT", proclamation head) where n
        is the granule's position on the page; the item after the k-th end marker ("Approved", "Agreed to",
        "Passed" plus a date), where k is n - 1 plus one when the page opens with the tail of an earlier
        document; else the first item.
        """
        for i, it in enumerate(items):
            if self._law_number_line(it.text):
                return i, "law-number"
        by_title = self._title_match(items)
        if by_title is not None:
            return by_title, "title"
        groups: list[int] = []  # index of the first marker line of each run of marker lines
        previous_marker = False
        for i, it in enumerate(items):
            marker = self.is_start_marker(it.text)
            if marker and not previous_marker:
                groups.append(i)
            previous_marker = marker
        if groups:
            n = self._ordinal
            if n <= len(groups):
                return groups[n - 1], "marker"
            self.warn(f"granule is document {n} on its first page but only {len(groups)} start marker run(s) found")
            return groups[-1], "marker"
        ends = [i for i, it in enumerate(items) if self.is_end_marker(it.text)]
        if ends:
            first_signal = next((i for i, it in enumerate(items) if self.is_start_signal(it.text)), len(items))
            tail_present = ends[0] < first_signal
            k = self._ordinal - 1 + (1 if tail_present else 0)
            if 0 < k <= len(ends) and ends[k - 1] + 1 < len(items):
                return ends[k - 1] + 1, "end-marker"
        return 0, "none"

    @property
    def _started(self) -> bool:
        """The document's own text has begun: an enacting or resolving clause, a section, or a preamble line
        has been seen since the start. A heading before the document's own marker run does not count, so a
        proclamation's title line followed by "BY THE PRESIDENT ..." does not end the document."""
        return self.body_signal_seen or self.enacting is not None or self.section_count > 0

    def _ingest(self) -> None:
        phase = "leading" if self._shares_pages else "body"
        in_leg_history = False
        for page in self.pages:
            heads = [it.text for it in page.items if it.kind == "header"]
            if heads and self.running_head is None:
                self.running_head = max(heads, key=len)
            marker = self._page_marker(page.no)
            self.body.append(marker)
            self.page_markers.append(marker)
            for it in page.items:
                if it.kind == "sidenote":
                    self.sidenotes.append((page.no, it.t, it.text))
            body_items: list[Item] = []
            for it in (it for it in page.items if it.kind == "body"):
                text = it.text
                if in_leg_history or it.label == "footnote" and RE_LEG_HISTORY.match(text):
                    if RE_LEG_HISTORY.match(text):
                        in_leg_history = True
                    self.leg_history.append(text)
                    continue
                if it.label == "footnote":
                    self.sidenotes.append((page.no, it.t, text))
                    continue
                body_items.append(it)
            if phase == "leading" and body_items:
                start, self.start_rule = self._find_start(body_items)
                if self.start_rule not in ("marker", "law-number", "title"):
                    self.warn(f"document start not recognized on page {page.no} (rule {self.start_rule}); nothing dropped")
                self.preface_items.extend(it.text for it in body_items[:start])
                body_items = body_items[start:]
                phase = "body"
            for it in body_items:
                if phase == "trailing":
                    self.trailing_items.append(it.text)
                    continue
                if self._shares_pages and self._started and self.is_start_marker(it.text):
                    # the next document begins on this page; everything from here on is trailing matter
                    phase = "trailing"
                    self.warn(f"next document starts on page {page.no} at {it.text[:40]!r}; kept as trailing matter")
                    self.trailing_items.append(it.text)
                    continue
                self._handle(it)
                if RE_BODY_SIGNAL.match(it.text):
                    self.body_signal_seen = True
                if self._shares_pages and self._started and self.is_end_marker(it.text):
                    self.warn(f"document ends on page {page.no} at {it.text[-40:]!r}")
                    phase = "trailing"
        if self.trailing_items:
            self.warn(f"{len(self.trailing_items)} item(s) after the approval line kept as trailing matter")
        if self.identity.doc_type == "pLaw":
            if not self.enacting:
                self.warn("no enacting formula recognized")
            if not self.approved_text:
                self.warn("no approval line recognized")
        if self.identity.doc_type == "resolution" and not self.enacting:
            self.warn("no resolving clause recognized")

    def _handle(self, it: Item) -> None:
        text = it.text
        m = RE_CHAPTER.match(text)
        if not m and not self.stack and self.is_fuzzy_chapter_start(text):
            fm = RE_CHAPTER_FUZZY.match(text)
            self.chapter = self.chapter or fm.group(2)
            self.doc_number = self.doc_number or fm.group(2)
            rest = text[fm.start(3):].strip()
            t = RE_CHAPTER_TITLE.match(rest) or re.match(r"^(A[nx]\s+Act)\b[.,]?\s*(.*)$", rest, re.I | re.S)
            if t:
                self.doc_title = self.doc_title or re.sub(r"^Ax", "An", t.group(1))
                rest = t.group(2).strip()
            if rest:
                self.official_title.append(rest)
            return
        if m and not self.stack:
            self.chapter = m.group(1)
            self.doc_number = self.doc_number or m.group(1)
            rest = (m.group(2) or "").strip()
            if rest:
                t = RE_CHAPTER_TITLE.match(rest)
                if t:
                    self.doc_title = self.doc_title or t.group(1)
                    rest = t.group(2).strip()
                if rest:
                    self.official_title.append(rest)
            return
        m = RE_PUBLIC_LAW.match(text) or RE_PRIVATE_LAW.match(text)
        if m and not self.stack:
            self.identity.congress = self.identity.congress or int(m.group(1))
            self.identity.law_number = self.identity.law_number or int(m.group(2))
            self.doc_number = f"{m.group(1)}–{m.group(2)}"
            c = RE_CONGRESS.search(text)
            if c and not self.identity.congress:
                self.identity.congress = int(c.group(1))
            return
        if RE_DOC_TITLE.match(text) and not self.stack:
            self.doc_title = text.rstrip(".")
            # a law's official title follows on the next line(s); a proclamation's heading precedes this line
            self.title_open = self.identity.doc_type != "presidentialDoc" and not self.official_title
            return
        if self.title_open and not self.stack and not self.enacting and len(self.official_title) < 3:
            self.official_title.append(text)
            if text.rstrip().endswith((".", "purposes", ")")) or len(self.official_title) >= 3:
                self.title_open = False
            return
        self.title_open = False
        if RE_ENACTING.match(text) and not self.stack and not self.enacting:
            self.enacting = text
            self.body.append(E.enactingFormula(text))
            return
        m = RE_APPROVED.match(text)
        if m:
            self.approved_text = m.group(1)
            self.approved = parse_us_date(m.group(1))
            return
        if not self.approved_text and self.is_end_marker(text) and self.identity.doc_type == "pLaw":
            e = RE_END.search(text)
            if e and e.start() == 0:
                self.approved_text = e.group(2)
                self.approved = parse_us_date(e.group(2))
                return
        if it.table:
            self._append_content(self._table_element(it.table))
            return
        m = RE_SECTION.match(text)
        if m and (it.label == "section_header" or m.group(1).upper() in ("SECTION", "SEC", "SEC.", "SPE", "SRO") and len(m.group(2)) <= 4):
            self._start_section(m.group(2), m.group(3))
            return
        m = RE_LEVEL.match(text)
        if m and len(m.group(1)) <= 4:
            if self.stack:
                self._start_level(m.group(1), m.group(2))
                return
            self.warn(f"designator ({m.group(1)}) before any section; kept as a paragraph")
        self._append_text(text)

    # ------------------------------------------------------------------ structure

    def _law_id(self) -> Optional[str]:
        return self.identity.law_identifier

    def _start_section(self, num: str, rest: str) -> None:
        self.section_count += 1
        num = num.strip()
        heading, content = split_section_heading(rest.strip())
        law_id = self._law_id()
        identifier = f"{law_id}/s{num}" if law_id else None
        sec = E.section()
        if identifier:
            sec.set("identifier", identifier)
            sec.set("id", self._unique_id(slug_id(identifier)))
        else:
            sec.set("id", self._unique_id(f"s{num}"))
        label = "SECTION" if self.section_count == 1 else "SEC."
        sec.append(E.num(f"{label} {num}. ", value=num))
        if heading:
            sec.append(E.heading(heading))
        self.body.append(sec)
        self.stack = [("section", sec, identifier or f"s{num}")]
        if content:
            self._append_text(content)

    def _start_level(self, designator: str, rest: str) -> None:
        current = self.stack[-1][0] if self.stack else None
        level = level_for(designator, current)
        # pop to the parent level of the new element
        while self.stack and LEVEL_ORDER.index(self.stack[-1][0]) >= LEVEL_ORDER.index(level):
            self.stack.pop()
        if not self.stack:
            self._append_text(f"({designator}) {rest}")
            return
        parent_level, parent, parent_ident = self.stack[-1]
        identifier = f"{parent_ident}/{designator}"
        el = etree.SubElement(parent, f"{{{USLM_NS}}}{level}")
        if parent_ident.startswith("/us/"):
            el.set("identifier", identifier)
        el.set("id", self._unique_id(slug_id(identifier)))
        el.append(E.num(f"({designator}) ", value=designator))
        heading, content = split_heading(rest.strip())
        if heading:
            el.append(E.heading(heading))
        self.stack.append((level, el, identifier))
        if content:
            self._append_text(content)

    def _current_container(self) -> etree._Element:
        if self.stack:
            return self.stack[-1][1]
        holder = E.p()
        self.body.append(holder)
        return holder

    def _append_text(self, text: str) -> None:
        if not self.stack:
            # text before any section: a paragraph in main (preamble, whereas clauses, recitals)
            p = E.p(text)
            self.body.append(p)
            return
        el = self.stack[-1][1]
        content = el.find(f"{{{USLM_NS}}}content")
        if content is None:
            # a level that already has children levels must not get trailing content in a new <content>;
            # append a continuation paragraph instead
            if any(child.tag == f"{{{USLM_NS}}}{lvl}" for child in el for lvl in LEVEL_ORDER):
                etree.SubElement(el, f"{{{USLM_NS}}}continuation").text = text
                return
            content = etree.SubElement(el, f"{{{USLM_NS}}}content")
            content.text = text
            return
        if any(child.tag == f"{{{USLM_NS}}}{lvl}" for child in el for lvl in LEVEL_ORDER):
            etree.SubElement(el, f"{{{USLM_NS}}}continuation").text = text
            return
        p = etree.SubElement(content, f"{{{USLM_NS}}}p")
        p.text = text

    def _append_content(self, element: etree._Element) -> None:
        if not self.stack:
            self.body.append(element)
            return
        el = self.stack[-1][1]
        content = el.find(f"{{{USLM_NS}}}content")
        if content is None:
            content = etree.SubElement(el, f"{{{USLM_NS}}}content")
        content.append(element)

    def _table_element(self, grid: list[list[str]]) -> etree._Element:
        table = H.table()
        for row in grid:
            tr = etree.SubElement(table, f"{{{XHTML_NS}}}tr")
            for cell in row:
                etree.SubElement(tr, f"{{{XHTML_NS}}}td").text = cell
        return table

    # ------------------------------------------------------------------ assemble

    def _assemble(self) -> etree._Element:
        ident = self.identity
        root_tag = ident.doc_type if ident.doc_type in ("pLaw", "presidentialDoc", "resolution") else "pLaw"
        root = etree.Element(f"{{{USLM_NS}}}{root_tag}", nsmap=NSMAP)
        root.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        root.set(f"{{{XSI_NS}}}schemaLocation", SCHEMA_LOCATION)
        if ident.law_identifier:
            root.set("identifier", ident.law_identifier)

        # The GovInfo title feeds dc:title only; main/longTitle holds text read from the page, so that the
        # generated body never carries text the pipeline did not produce.
        parsed_title = " ".join(self.official_title).strip()
        title_text = parsed_title or ident.title or ""
        law_label = None
        if ident.congress and ident.law_number:
            law_label = f"{'Private' if ident.is_private else 'Public'} Law {ident.congress}–{ident.law_number}"

        meta = etree.SubElement(root, f"{{{USLM_NS}}}meta")
        meta.append(DCE.title(f"{law_label}: {title_text}" if law_label else title_text or (ident.granule_id or "")))
        meta.append(DCE.type("Private Law" if ident.is_private else "Public Law" if root_tag == "pLaw" else root_tag))
        if ident.law_number:
            meta.append(E.docNumber(str(ident.law_number)))
        elif self.chapter:
            meta.append(E.docNumber(self.chapter))
        if law_label:
            meta.append(E.citableAs(law_label))
        if ident.volume and ident.start_page:
            meta.append(E.citableAs(f"{ident.volume} Stat. {ident.start_page}"))
        approved = self.approved or ident.date_issued
        if approved:
            meta.append(E.approvedDate(approved))
            meta.append(DCE.date(approved))
        meta.append(DCE.publisher("statute-pdf-to-xml (Docling conversion of the GovInfo PDF)"))
        meta.append(DCE.format("text/xml"))
        meta.append(DCE.language("EN"))
        meta.append(E.processedBy("statute-pdf-to-xml pipeline.uslm"))
        meta.append(E.processedDate(date.today().isoformat()))
        if ident.congress:
            meta.append(E.congress(str(ident.congress)))
        if ident.session:
            meta.append(E.session(str(ident.session)))
        if root_tag == "pLaw":
            meta.append(E.publicPrivate("private" if ident.is_private else "public"))

        preface = etree.SubElement(root, f"{{{USLM_NS}}}preface")
        if self.running_head:
            preface.append(E.centerRunningHead(self.running_head))
        for text in self.preface_items:
            preface.append(E.p(text))
        if self.page_markers:
            first = self.page_markers[0]
            self.body.remove(first)
            preface.append(first)
        preface.append(DCE.type("Private Law" if ident.is_private else "Public Law" if root_tag == "pLaw" else root_tag))
        if ident.congress and ident.law_number:
            preface.append(E.docNumber(f"{ident.congress}–{ident.law_number}"))
        elif self.doc_number:
            preface.append(E.docNumber(self.doc_number))
        if ident.congress:
            preface.append(E.congress(f"{ordinal(ident.congress)} Congress", value=str(ident.congress)))

        main = etree.SubElement(root, f"{{{USLM_NS}}}main")
        if self.doc_title or parsed_title:
            long_title = etree.SubElement(main, f"{{{USLM_NS}}}longTitle")
            if self.doc_title:
                long_title.append(E.docTitle(self.doc_title))
            if parsed_title:
                long_title.append(E.officialTitle(parsed_title))
        self._place_sidenotes()
        for el in self.body:
            main.append(el)
        if self.approved_text:
            action = etree.SubElement(main, f"{{{USLM_NS}}}action")
            desc = etree.SubElement(action, f"{{{USLM_NS}}}actionDescription")
            desc.text = "Approved"
            desc.tail = " "
            d = etree.SubElement(action, f"{{{USLM_NS}}}date")
            d.text = self.approved_text
            if self.approved:
                d.set("date", self.approved)
            d.tail = "."

        if self.leg_history:
            lh = etree.SubElement(root, f"{{{USLM_NS}}}legislativeHistory")
            lh.append(E.heading(self.leg_history[0]))
            note = etree.SubElement(lh, f"{{{USLM_NS}}}note")
            for line in self.leg_history[1:]:
                note.append(E.p(line))
            if len(lh) == 2 and len(note) == 0:
                note.append(E.p(""))
        if self.trailing_items:
            appendix = etree.SubElement(root, f"{{{USLM_NS}}}appendix")
            appendix.set("role", "trailingMatter")
            content = etree.SubElement(appendix, f"{{{USLM_NS}}}content")
            for text in self.trailing_items:
                content.append(E.p(text))
        return root

    def _place_sidenotes(self) -> None:
        """Insert <sidenote> elements into main before the body element nearest to each note."""
        if not self.sidenotes:
            return
        # positions of body elements: (page, top) recorded through the page markers order
        # Fallback: group notes by page and insert after the page marker of that page.
        by_page: dict[int, list[tuple[float, str]]] = {}
        for page_no, top, text in self.sidenotes:
            by_page.setdefault(page_no, []).append((top, text))
        for idx, marker in enumerate(self.page_markers):
            page_no = idx + 1
            notes = by_page.get(page_no)
            if not notes:
                continue
            notes.sort(key=lambda n: -n[0])
            sidenote = E.sidenote(*[E.p(text) for _, text in notes])
            if marker in self.body:
                pos = self.body.index(marker) + 1
                self.body.insert(pos, sidenote)
            else:
                self.body.insert(0, sidenote)


# ---------------------------------------------------------------------------- text accounting


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def docling_text_chars(doc) -> int:
    """Characters of text Docling produced (every item with text; table cells joined)."""
    total = 0
    for item, _level in doc.iterate_items():
        label = str(getattr(item, "label", "")).split(".")[-1].lower()
        if label == "table":
            grid = table_grid(item) or []
            total += len(_squash(" ".join(" ".join(row) for row in grid)))
        else:
            total += len(_squash(getattr(item, "text", "") or ""))
    return total


def kept_text_chars(tree: etree._ElementTree) -> int:
    """Characters of text anywhere in the generated document except `meta`."""
    root = tree.getroot()
    parts = []
    for child in root:
        if child.tag == f"{{{USLM_NS}}}meta":
            continue
        parts.append(" ".join(child.itertext()))
    return len(_squash(" ".join(parts)))


# ---------------------------------------------------------------------------- API


def build_uslm(doc, identity: DocIdentity) -> etree._ElementTree:
    return UslmBuilder(identity).build(doc)


def build_uslm_with_stats(doc, identity: DocIdentity) -> tuple[etree._ElementTree, dict]:
    builder = UslmBuilder(identity)
    tree = builder.build(doc)
    return tree, builder.stats


def write_uslm(tree: etree._ElementTree, path: Path | str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(path), xml_declaration=True, encoding="utf-8", pretty_print=True)


_SCHEMA: Optional[etree.XMLSchema] = None


def schema() -> etree.XMLSchema:
    global _SCHEMA
    if _SCHEMA is None:
        parser = etree.XMLParser(no_network=True)
        _SCHEMA = etree.XMLSchema(etree.parse(str(SCHEMA_PATH), parser))
    return _SCHEMA


def validate(tree_or_path) -> tuple[bool, list[str]]:
    """Validate against uslm-2.0.17.xsd. Returns (ok, error messages)."""
    tree = etree.parse(str(tree_or_path)) if isinstance(tree_or_path, (str, Path)) else tree_or_path
    ok = schema().validate(tree)
    errors = [f"line {e.line}: {e.message}" for e in schema().error_log]
    return ok, errors


def identity_from_granule(row: dict) -> DocIdentity:
    """DocIdentity from a granules row (fetch_granules) with MODS fields."""
    mods = row.get("mods") or {}
    cls = row.get("granule_class") or mods.get("granule_class") or "PUBLICLAW"
    doc_type = {"PROCLAMATION": "presidentialDoc", "TREATY": "presidentialDoc", "HCONRES": "resolution",
                "SCONRES": "resolution"}.get(cls, "pLaw")
    number = row.get("number") or mods.get("number")
    volume = mods.get("volume")
    if volume is None and row.get("package_id", "").startswith("STATUTE-"):
        volume = int(row["package_id"].split("-")[1])
    return DocIdentity(
        doc_type=doc_type,
        congress=row.get("congress") or mods.get("congress"),
        law_number=int(number) if number and str(number).isdigit() and doc_type == "pLaw" else None,
        is_private=cls == "PRIVATELAW",
        volume=volume,
        start_page=row.get("page_start") or mods.get("page_start"),
        granule_id=row.get("granule_id"),
        package_id=row.get("package_id"),
        date_issued=str(row.get("date_issued") or mods.get("granule_date") or "") or None,
        title=row.get("title") or mods.get("title"),
        session=mods.get("session"),
    )


def identity_from_plaw(package_id: str, statute: Optional[dict] = None, summary: Optional[dict] = None) -> DocIdentity:
    m = re.match(r"^PLAW-(\d+)(publ|pvtl)(\d+)$", package_id)
    congress = int(m.group(1)) if m else None
    number = int(m.group(3)) if m else None
    statute = statute or {}
    return DocIdentity(
        doc_type="pLaw",
        congress=congress,
        law_number=number,
        is_private=bool(m and m.group(2) == "pvtl"),
        volume=statute.get("volume"),
        start_page=statute.get("start_page"),
        package_id=package_id,
        date_issued=str(statute.get("date_enacted") or (summary or {}).get("dateIssued") or "") or None,
        title=statute.get("title") or (summary or {}).get("title"),
    )
