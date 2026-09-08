"""Deterministic comparison of generated USLM against GovInfo USLM: CER, WER, structure counts, identifiers.

Text is taken from the document body (main), excluding meta, sidenotes, notes, and page markers, then
normalized: NFKC, curly quotes and dashes unified, soft hyphens removed, hyphenation at line ends
joined, whitespace collapsed. CER and WER are Levenshtein distances over characters and tokens divided
by the reference length (rapidfuzz).

A granule PDF holds whole pages, so the generated text starts with the tail of the previous law and
ends with the head of the next one, while the reference holds only the granule's own text (defect F3
of the 2026-09-07 plan). `clip_to_reference` anchors the first and last `CLIP_TOKENS` tokens of the
reference in the generated text (`rapidfuzz.fuzz.partial_ratio_alignment`, threshold `CLIP_THRESHOLD`)
and scores the span between them. `clip_found` records which anchors were found; when one is missing
the text is scored unclipped on that side.
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
from rapidfuzz import fuzz
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


# ---------------------------------------------------------------------------- clipping (F3)

CLIP_TOKENS = 30
CLIP_THRESHOLD = 70.0


@dataclass
class Clip:
    text: str
    start: int
    end: int
    head_found: bool
    tail_found: bool
    head_score: float = 0.0
    tail_score: float = 0.0

    @property
    def found(self) -> str:
        return {(True, True): "both", (True, False): "head", (False, True): "tail", (False, False): "none"}[(self.head_found, self.tail_found)]

    def as_dict(self) -> dict:
        return {"clip_found": self.found, "clip_start": self.start, "clip_end": self.end,
                "head_score": round(self.head_score, 1), "tail_score": round(self.tail_score, 1)}


def _anchor(text: str, n_tokens: int, tail: bool) -> str:
    toks = tokens(text)
    if not toks:
        return ""
    picked = toks[-n_tokens:] if tail else toks[:n_tokens]
    return normalize(" ".join(picked))


def clip_to_reference(reference: str, hypothesis: str, n_tokens: int = CLIP_TOKENS,
                      threshold: float = CLIP_THRESHOLD) -> Clip:
    """Clip `hypothesis` to the span between the reference's first and last `n_tokens` tokens."""
    if not reference or not hypothesis:
        return Clip(hypothesis, 0, len(hypothesis), False, False)
    ref_toks = tokens(reference)
    n = min(n_tokens, max(1, len(ref_toks) // 2))
    head, tail = _anchor(reference, n, tail=False), _anchor(reference, n, tail=True)
    start, end = 0, len(hypothesis)
    head_found = tail_found = False
    head_score = tail_score = 0.0
    if head:
        a = fuzz.partial_ratio_alignment(head, hypothesis)
        if a is not None and a.score >= threshold:
            head_found, head_score, start = True, a.score, a.dest_start
    if tail and len(ref_toks) > n:
        # Search after the head anchor, first within twice the reference length: the closing words of a law
        # ("... Approved, March 3, 1853.") recur for every law on a shared page, and the best match over the
        # whole remainder can belong to a later law.
        offset = start
        for window in (offset + 2 * len(reference) + len(tail), None):
            a = fuzz.partial_ratio_alignment(tail, hypothesis[offset:window])
            if a is not None and a.score >= threshold and offset + a.dest_end > start:
                tail_found, tail_score, end = True, a.score, offset + a.dest_end
                break
            if window is None or window >= len(hypothesis):
                break
    return Clip(hypothesis[start:end].strip(), start, end, head_found, tail_found, head_score, tail_score)


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


def sections(root: etree._Element) -> list[tuple[str, str]]:
    """(num value, first 40 normalized characters of the section text after the num) per section."""
    out = []
    for sec in root.iter(NS + "section"):
        num = sec.find(NS + "num")
        value = (num.get("value") if num is not None else None) or normalize(num.text or "") if num is not None else ""
        parts = []
        for child in sec:
            if child is num or child.tag in EXCLUDED_FROM_TEXT or not isinstance(child.tag, str):
                continue
            parts.append(" ".join(child.itertext()))
        out.append((str(value).strip(), normalize(" ".join(parts))[:40]))
    return out


def section_match(ref_root: etree._Element, hyp_root: etree._Element, threshold: float = 70.0) -> dict:
    """Precision and recall of generated sections: a match needs the same num value and a similar start
    (`fuzz.ratio` of the first 40 characters at or above `threshold`)."""
    ref, hyp = sections(ref_root), sections(hyp_root)
    used: set[int] = set()
    matched = 0
    for r_num, r_start in ref:
        for j, (h_num, h_start) in enumerate(hyp):
            if j in used or h_num != r_num:
                continue
            if not r_start or not h_start or fuzz.ratio(r_start, h_start) >= threshold:
                used.add(j)
                matched += 1
                break
    precision = matched / len(hyp) if hyp else (1.0 if not ref else 0.0)
    recall = matched / len(ref) if ref else (1.0 if not hyp else 0.0)
    return {"precision": round(precision, 4), "recall": round(recall, 4), "reference": len(ref), "hypothesis": len(hyp), "matched": matched}


def sidenote_texts(root: etree._Element) -> list[str]:
    return [normalize(" ".join(sn.itertext())) for sn in root.iter(NS + "sidenote")]


def sidenote_recall(ref_root: etree._Element, hyp_root: etree._Element, threshold: float = 70.0) -> dict:
    """Share of reference sidenotes found (partial ratio at or above `threshold`) among generated sidenotes."""
    ref, hyp = [t for t in sidenote_texts(ref_root) if t], [t for t in sidenote_texts(hyp_root) if t]
    joined = " | ".join(hyp)
    found = sum(1 for t in ref if joined and fuzz.partial_ratio(t, joined) >= threshold)
    return {"recall": round(found / len(ref), 4) if ref else 1.0, "reference": len(ref), "hypothesis": len(hyp), "matched": found}


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
    section_match: dict = field(default_factory=dict)
    sidenote_recall: dict = field(default_factory=dict)
    diffs: list[dict] = field(default_factory=list)
    equal_ratio: float = 0.0
    clip: Optional[Clip] = None
    hyp_chars_unclipped: int = 0
    cer_unclipped: float = 0.0

    def as_dict(self) -> dict:
        return {
            "cer": round(self.cer, 4), "wer": round(self.wer, 4),
            "cer_unclipped": round(self.cer_unclipped, 4),
            "ref_chars": self.ref_chars, "hyp_chars": self.hyp_chars, "hyp_chars_unclipped": self.hyp_chars_unclipped,
            "ref_tokens": self.ref_tokens, "hyp_tokens": self.hyp_tokens,
            "equal_ratio": round(self.equal_ratio, 4),
            **(self.clip.as_dict() if self.clip else {"clip_found": "off"}),
            "structure_reference": self.structure_reference, "structure_generated": self.structure_generated,
            "identifier_overlap": self.identifier_overlap, "page_overlap": self.page_overlap,
            "section_match": self.section_match, "sidenote_recall": self.sidenote_recall,
            "diffs": self.diffs,
        }


def compare(reference_xml, generated_xml, diff_limit: int = 25, clip: bool = True) -> Comparison:
    ref_root, hyp_root = load(reference_xml), load(generated_xml)
    ref_text, hyp_full = body_text(ref_root), body_text(hyp_root)
    clipped = clip_to_reference(ref_text, hyp_full) if clip else None
    hyp_text = clipped.text if clipped else hyp_full
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
        section_match=section_match(ref_root, hyp_root),
        sidenote_recall=sidenote_recall(ref_root, hyp_root),
        diffs=alignment_report(segments, diff_limit),
        equal_ratio=(equal / len(ref_text)) if ref_text else 0.0,
        clip=clipped,
        hyp_chars_unclipped=len(hyp_full),
        cer_unclipped=cer(ref_text, hyp_full),
    )
