"""Deterministic comparison of generated USLM against GovInfo USLM: CER, WER, structure counts, identifiers.

Text is taken from the document body (main), excluding meta, sidenotes, notes, and page markers, then
normalized: NFKC, curly quotes and dashes unified, soft hyphens removed, hyphenation at line ends
joined, whitespace collapsed. CER and WER are Levenshtein distances over characters and tokens divided
by the reference length (rapidfuzz).
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from lxml import etree
from rapidfuzz.distance import Levenshtein

USLM_NS = "http://schemas.gpo.gov/xml/uslm"
NS = f"{{{USLM_NS}}}"

STRUCTURE_TAGS = (
    "section", "subsection", "paragraph", "subparagraph", "clause", "subclause", "heading", "content",
    "note", "sidenote", "table", "page", "quotedContent", "longTitle", "enactingFormula", "action", "p",
)
EXCLUDED_FROM_TEXT = {NS + "meta", NS + "sidenote", NS + "note", NS + "page", NS + "legislativeHistory",
                      NS + "centerRunningHead"}

QUOTES = {"‘": "'", "’": "'", "‚": "'", "‛": "'", "“": '"', "”": '"', "„": '"',
          "′": "'", "″": '"', "´": "'", "`": "'"}
DASHES = {"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-"}


# ---------------------------------------------------------------------------- text


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "")
    for k, v in QUOTES.items():
        text = text.replace(k, v)
    for k, v in DASHES.items():
        text = text.replace(k, v)
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)  # hyphenation at line end
    text = re.sub(r"[ \t\r\f\v ]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s+([,.;:)\]])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    return text.strip()


def tokens(text: str) -> list[str]:
    return re.findall(r"\w+|[^\w\s]", text)


def body_text(root: etree._Element) -> str:
    """Text of the document body, in document order, without the excluded elements."""
    main = root.find(NS + "main")
    scope = main if main is not None else root
    parts: list[str] = []

    def walk(el: etree._Element) -> None:
        if not isinstance(el.tag, str):
            return
        if el.tag in EXCLUDED_FROM_TEXT:
            if el.tail:
                parts.append(el.tail)
            return
        if el.text:
            parts.append(el.text)
        for child in el:
            walk(child)
            if child.tail and child.tag not in EXCLUDED_FROM_TEXT:
                parts.append(child.tail)

    walk(scope)
    return normalize(" ".join(parts))


def load(path_or_tree) -> etree._Element:
    if isinstance(path_or_tree, (str, Path)):
        return etree.parse(str(path_or_tree)).getroot()
    if isinstance(path_or_tree, etree._ElementTree):
        return path_or_tree.getroot()
    return path_or_tree


# ---------------------------------------------------------------------------- metrics


def cer(reference: str, hypothesis: str) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return Levenshtein.distance(reference, hypothesis) / len(reference)


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = tokens(reference), tokens(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return Levenshtein.distance(ref, hyp) / len(ref)


def structure_counts(root: etree._Element) -> dict[str, int]:
    counter = Counter(el.tag.replace(NS, "") for el in root.iter() if isinstance(el.tag, str))
    return {tag: counter.get(tag, 0) for tag in STRUCTURE_TAGS}


def identifiers(root: etree._Element) -> tuple[set[str], set[str]]:
    """(structural identifiers such as /us/pl/118/5/s1/a, page identifiers such as /us/stat/137/10)."""
    structural, pages = set(), set()
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        ident = el.get("identifier")
        if not ident:
            continue
        if el.tag == NS + "page" or ident.startswith("/us/stat/"):
            pages.add(ident)
        else:
            structural.add(ident)
    return structural, pages


def overlap(reference: set[str], hypothesis: set[str]) -> dict[str, float]:
    tp = len(reference & hypothesis)
    precision = tp / len(hypothesis) if hypothesis else (1.0 if not reference else 0.0)
    recall = tp / len(reference) if reference else (1.0 if not hypothesis else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "reference": len(reference), "hypothesis": len(hypothesis), "matched": tp}


@dataclass
class Segment:
    op: str  # equal | replace | delete | insert
    ref: str
    hyp: str


def align(reference: str, hypothesis: str, max_segments: int = 400) -> list[Segment]:
    """Token-level alignment via difflib opcodes; each segment carries the reference and hypothesis text."""
    ref, hyp = tokens(reference), tokens(hypothesis)
    matcher = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    segments = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        segments.append(Segment(op=op, ref=" ".join(ref[i1:i2]), hyp=" ".join(hyp[j1:j2])))
        if len(segments) >= max_segments:
            break
    return segments


def alignment_report(segments: Iterable[Segment], limit: int = 25) -> list[dict]:
    """The largest non-equal segments, for the judge and the report."""
    diffs = [s for s in segments if s.op != "equal"]
    diffs.sort(key=lambda s: -(len(s.ref) + len(s.hyp)))
    return [{"op": s.op, "reference": s.ref[:400], "generated": s.hyp[:400]} for s in diffs[:limit]]


@dataclass
class Comparison:
    cer: float
    wer: float
    ref_chars: int
    hyp_chars: int
    ref_tokens: int
    hyp_tokens: int
    structure_reference: dict[str, int]
    structure_generated: dict[str, int]
    identifier_overlap: dict[str, float]
    page_overlap: dict[str, float]
    diffs: list[dict] = field(default_factory=list)
    equal_ratio: float = 0.0

    def as_dict(self) -> dict:
        return {
            "cer": round(self.cer, 4), "wer": round(self.wer, 4),
            "ref_chars": self.ref_chars, "hyp_chars": self.hyp_chars,
            "ref_tokens": self.ref_tokens, "hyp_tokens": self.hyp_tokens,
            "equal_ratio": round(self.equal_ratio, 4),
            "structure_reference": self.structure_reference, "structure_generated": self.structure_generated,
            "identifier_overlap": self.identifier_overlap, "page_overlap": self.page_overlap,
            "diffs": self.diffs,
        }


def compare(reference_xml, generated_xml, diff_limit: int = 25) -> Comparison:
    ref_root, hyp_root = load(reference_xml), load(generated_xml)
    ref_text, hyp_text = body_text(ref_root), body_text(hyp_root)
    segments = align(ref_text, hyp_text)
    equal = sum(len(s.ref) for s in segments if s.op == "equal")
    ref_ids, ref_pages = identifiers(ref_root)
    hyp_ids, hyp_pages = identifiers(hyp_root)
    return Comparison(
        cer=cer(ref_text, hyp_text),
        wer=wer(ref_text, hyp_text),
        ref_chars=len(ref_text), hyp_chars=len(hyp_text),
        ref_tokens=len(tokens(ref_text)), hyp_tokens=len(tokens(hyp_text)),
        structure_reference=structure_counts(ref_root),
        structure_generated=structure_counts(hyp_root),
        identifier_overlap=overlap(ref_ids, hyp_ids),
        page_overlap=overlap(ref_pages, hyp_pages),
        diffs=alignment_report(segments, diff_limit),
        equal_ratio=(equal / len(ref_text)) if ref_text else 0.0,
    )
