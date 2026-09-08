"""Hybrid USLM (candidate C6 of the 2026-09-07 plan): the GPO slice's structure with a text candidate's words.

Profile `hybrid:{candidate profile}`, for example `hybrid:scanned` or `hybrid:claude:claude-opus-5`
(`parse_profile` splits at the first colon, so the variant keeps its own colon). Inputs for a granule:

    data/granules/STATUTE-{v}/uslm/{granule_id}.xml            the GPO slice (pipeline.split_uslm)
    data/generated_xmls/{candidate dir}/{granule_id}.xml       the candidate's USLM (pipeline.convert)

The GPO document is copied and its text runs are replaced, in document order, by the candidate's body
text. Both documents are cut at the sections whose `num` values match (in order); inside each cut the
GPO runs are aligned to the candidate tokens with `difflib.SequenceMatcher` and every run boundary is
mapped to a candidate token index, so the candidate tokens are partitioned among the GPO runs and none
is lost. Every element with text takes the candidate text (`content`, `p`, `chapeau`, `heading`,
`enactingFormula`, `officialTitle`, `proviso`, layout columns, table cells, signatures, ...) except `num`,
`action`, and `toc`, which keep the GPO text; the candidate tokens aligned to those are dropped and
counted in `substituted_tokens`. `sidenote`, `note`, `page`, `meta`, and `legislativeHistory` are not
touched; a sidenote or page marker inside a run is put back at the corresponding position of the new
text. Inline markup inside a run (`i`, `inline`, `ref`, `term`, `date`, ...) is flattened. `stats`
reports `candidate_share`, the share of body tokens that come from the candidate rather than from GPO
text kept in `num`, `action`, `toc`, and runs whose candidate span was empty.

Candidate text before the first or after the last words of the GPO text (the neighbouring laws on shared
pages; `benchmark.metrics.clip_to_reference`) goes into the preface and into an `appendix` with role
`trailingMatter`, together with the candidate's own preface and trailing paragraphs. A run whose candidate
span is empty keeps the GPO text and counts a warning. Without a GPO slice the candidate document is
returned unchanged with a warning.

Identifiers follow section 7 of the plan: `/us/pl/{congress}/{number}` and `/us/pvtl/...` from 1901 on,
`/us/act/{YYYY-MM-DD}/ch{chapter}` before 1901, both from 1901 to 1957 with the chapter form on
`meta/property[@role='alternateIdentifier']`; `/s{n}`, `/s{n}/{a}`, ... below the law with division and
title segments; page identifiers `/us/stat/{volume}/{page}` in lower case. The output validates against
uslm-2.0.17.xsd (`pipeline.uslm.validate`).
"""

from __future__ import annotations

import copy
import difflib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lxml import etree

from downloader.config import DATA_DIR
from pipeline import uslm
from pipeline.profiles import ProfileFamily, register_family
from pipeline.uslm import DC_NS, USLM_NS, DocIdentity, slug_id

logger = logging.getLogger("hybrid")

FAMILY = "hybrid"
NS = f"{{{USLM_NS}}}"
DC = f"{{{DC_NS}}}"

KEEP_TAGS = {NS + t for t in ("sidenote", "note", "page", "meta", "legislativeHistory", "notes", "editorialContent")}
OPAQUE_TAGS = {NS + "action", NS + "toc"}  # GPO text kept as one run; candidate tokens aligned to it are dropped
NON_REPLACE_TAGS = OPAQUE_TAGS | {NS + "num"}
# Inline markup flattened into the text of the run around it. Every other element (any namespace) is
# structural: it is kept as an element and its own text forms runs.
INLINE_TAGS = {NS + t for t in ("i", "b", "u", "inline", "ref", "term", "span", "sub", "sup", "quotedText", "amendingAction",
                                "date", "br", "del", "ins", "fillIn", "marker", "shortTitle", "entity", "def")}
LEVEL_TAGS = {NS + t for t in uslm.LEVEL_ORDER}
BIG_LEVELS = {NS + "division": "d", NS + "title": "t", NS + "subtitle": "st", NS + "chapter": "ch", NS + "subchapter": "sch",
              NS + "part": "pt", NS + "subpart": "spt"}
KEEP_GPO_FOR_EMPTY_RUNS = True  # a replaceable run with no candidate tokens keeps the GPO text
FIRST_PUBLIC_LAW_YEAR = 1901
LAST_CHAPTER_YEAR = 1957


# ---------------------------------------------------------------------------- runs


@dataclass
class Run:
    """One text run of a structural element: `parts[index]` of `element`'s linearized content."""

    element: etree._Element
    index: int  # position in the element's parts list
    tokens: list[str]
    replaceable: bool
    opaque: bool = False


@dataclass
class Linear:
    """Own content of a structural element: strings and anchor elements in document order."""

    element: etree._Element
    parts: list = field(default_factory=list)  # str | etree._Element


def _tokens(text: Optional[str]) -> list[str]:
    return (text or "").split()


def is_anchor(el: etree._Element) -> bool:
    """An element kept whole while its parent's text is rewritten: everything structural, anything from
    another namespace, and any inline element that contains such a thing."""
    if not isinstance(el.tag, str):
        return True
    if el.tag not in INLINE_TAGS:
        return True
    return any(is_anchor(child) for child in el)


def linearize(el: etree._Element) -> Linear:
    lin = Linear(el)

    def walk(node: etree._Element) -> None:
        if node.text:
            lin.parts.append(node.text)
        for child in node:
            if is_anchor(child):
                lin.parts.append(child)
            else:
                walk(child)
            if child.tail:
                lin.parts.append(child.tail)

    walk(el)
    return lin


def _opaque_text(el: etree._Element) -> str:
    parts = []

    def walk(node):
        if not isinstance(node.tag, str) or node.tag in KEEP_TAGS:
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(el)
    return " ".join(parts)


def collect_runs(scope: etree._Element) -> tuple[list[Run], dict[int, Linear]]:
    """Text runs of `scope` in document order, skipping KEEP subtrees. Returns the runs and the
    linearized content per element id (for rewriting)."""
    runs: list[Run] = []
    linears: dict[int, Linear] = {}

    def visit(el: etree._Element) -> None:
        if not isinstance(el.tag, str) or el.tag in KEEP_TAGS:
            return
        if el.tag in OPAQUE_TAGS:
            toks = _tokens(_opaque_text(el))
            if toks:
                runs.append(Run(el, 0, toks, replaceable=False, opaque=True))
            return
        lin = linearize(el)
        linears[id(el)] = lin
        replaceable = el.tag not in NON_REPLACE_TAGS
        for i, part in enumerate(lin.parts):
            if isinstance(part, str):
                toks = _tokens(part)
                if toks:
                    runs.append(Run(el, i, toks, replaceable))
            elif isinstance(part.tag, str) and part.tag not in KEEP_TAGS:
                visit(part)

    visit(scope)
    return runs, linears


def section_anchors(scope: etree._Element, runs: list[Run], offsets: list[int]) -> list[tuple[str, int, etree._Element]]:
    """(num value, token index of the section's first run, section element) for sections with a num."""
    first_run: dict[int, int] = {}
    for i, run in enumerate(runs):
        node = run.element
        while node is not None:
            if node.tag == NS + "section" and id(node) not in first_run:
                first_run[id(node)] = i
            node = node.getparent()
    out = []
    for sec in scope.iter(NS + "section"):
        num = sec.find(NS + "num")
        value = (num.get("value") if num is not None else None) or ""
        value = re.sub(r"\s+", "", value).lower()
        if value and id(sec) in first_run:
            out.append((value, offsets[first_run[id(sec)]], sec))
    return out


# ---------------------------------------------------------------------------- alignment


def map_index(opcodes: list[tuple], i: int, a_len: int, b_len: int) -> int:
    """Map an index of sequence a to sequence b through SequenceMatcher opcodes: exact inside equal
    blocks, proportional inside replacements, the block start elsewhere."""
    if i >= a_len:
        return b_len
    for tag, i1, i2, j1, j2 in opcodes:
        if i1 <= i < i2 or (i1 == i2 == i):
            if tag == "equal":
                return j1 + (i - i1)
            if tag == "replace" and i2 > i1:
                return j1 + round((i - i1) / (i2 - i1) * (j2 - j1))
            return j1
    return b_len


def align_segment(a: list[str], b: list[str], cuts: list[int]) -> list[int]:
    """Map GPO token cut points (relative to `a`) to candidate token indexes (relative to `b`), monotone."""
    if not a or not b:
        return [0 if not b else (0 if c == 0 else len(b)) for c in cuts]
    opcodes = difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()
    out = []
    last = 0
    for c in cuts:
        j = max(last, min(len(b), map_index(opcodes, c, len(a), len(b))))
        out.append(j)
        last = j
    return out


SECTION_WINDOW = 60  # tokens compared when several candidate sections carry the same num


def match_sections(gpo: list[tuple[str, int, etree._Element]], cand: list[tuple[str, int, etree._Element]],
                   gpo_tokens: Optional[list[str]] = None, cand_tokens: Optional[list[str]] = None) -> list[tuple[int, int]]:
    """Monotone pairs (gpo token index, candidate token index) of sections with the same num value. When a
    num occurs more than once on either side (a table of contents read as sections, quoted sections), the
    chain with the largest total similarity of the sections' first `SECTION_WINDOW` tokens wins."""
    from rapidfuzz import fuzz

    def window(tokens: Optional[list[str]], idx: int) -> str:
        return " ".join(tokens[idx: idx + SECTION_WINDOW]).lower() if tokens else ""

    candidates: list[tuple[int, int, float]] = []
    for value, g_idx, _ in gpo:
        for c_value, c_idx, _ in cand:
            if c_value != value:
                continue
            score = fuzz.ratio(window(gpo_tokens, g_idx), window(cand_tokens, c_idx)) if gpo_tokens and cand_tokens else 100.0
            candidates.append((g_idx, c_idx, 1.0 + score))
    candidates.sort()
    best: list[tuple[float, int]] = []  # (total, previous index)
    for i, (g, c, s) in enumerate(candidates):
        total, prev = s, -1
        for j in range(i):
            gj, cj, _ = candidates[j]
            if gj < g and cj < c and best[j][0] + s > total:
                total, prev = best[j][0] + s, j
        best.append((total, prev))
    if not best:
        return []
    i = max(range(len(best)), key=lambda k: best[k][0])
    chain = []
    while i >= 0:
        chain.append((candidates[i][0], candidates[i][1]))
        i = best[i][1]
    return chain[::-1]


def align_runs(runs: list[Run], cand_tokens: list[str], pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Candidate token span per run. Anchored at the matched section pairs, aligned with difflib between them."""
    offsets = []
    total = 0
    for run in runs:
        offsets.append(total)
        total += len(run.tokens)
    gpo_tokens = [t for run in runs for t in run.tokens]
    anchors = [(0, 0)] + [p for p in pairs if 0 < p[0] < total and 0 < p[1] < len(cand_tokens)] + [(total, len(cand_tokens))]
    cut_map: dict[int, int] = {}
    for (g0, c0), (g1, c1) in zip(anchors, anchors[1:]):
        cuts = [o for o in offsets if g0 <= o < g1]
        rel = align_segment(gpo_tokens[g0:g1], cand_tokens[c0:c1], [c - g0 for c in cuts])
        for cut, j in zip(cuts, rel):
            cut_map[cut] = c0 + j
        cut_map.setdefault(g0, c0)
    cut_map[total] = len(cand_tokens)
    spans = []
    for i, start in enumerate(offsets):
        end = offsets[i + 1] if i + 1 < len(offsets) else total
        spans.append((cut_map.get(start, 0), cut_map.get(end, len(cand_tokens))))
    # the first run starts at 0 and consecutive spans share their boundary, so every candidate token lands in a run
    fixed = []
    prev_end = 0
    for s, e in spans:
        s = prev_end
        e = max(s, e)
        fixed.append((s, e))
        prev_end = e
    if fixed:
        fixed[-1] = (fixed[-1][0], len(cand_tokens))
    return fixed


# ---------------------------------------------------------------------------- rewriting


def rewrite_element(lin: Linear, new_parts: dict[int, str]) -> None:
    """Rebuild `lin.element` from its parts with the strings at `new_parts` indexes replaced. Anchor elements
    are re-attached at the same positions; flattened inline elements disappear."""
    el = lin.element
    parts = list(lin.parts)
    for i, text in new_parts.items():
        parts[i] = text
    for child in list(el):
        el.remove(child)
    el.text = None
    last: Optional[etree._Element] = None
    for part in parts:
        if isinstance(part, str):
            if not part:
                continue
            if last is None:
                el.text = (el.text or "") + part if el.text else part
            else:
                last.tail = (last.tail or "") + part if last.tail else part
        else:
            part.tail = None  # lxml keeps the tail on a removed element; the run text is re-added from `parts`
            el.append(part)
            last = part
    if el.text is not None:
        el.text = re.sub(r"[ \t]+", " ", el.text)
    for child in el:
        if child.tail:
            child.tail = re.sub(r"[ \t]+", " ", child.tail)


def replace_runs(runs: list[Run], linears: dict[int, Linear], cand_tokens: list[str], spans: list[tuple[int, int]],
                 warnings: list[str]) -> dict:
    """Apply the candidate spans to the replaceable runs; keep GPO text where the span is empty."""
    by_element: dict[int, dict[int, str]] = {}
    kept_empty = substituted = replaced = gpo_tokens = cand_used = 0
    for run, (s, e) in zip(runs, spans):
        toks = cand_tokens[s:e]
        if not run.replaceable:
            substituted += len(toks)
            gpo_tokens += len(run.tokens)
            continue
        if not toks:
            kept_empty += 1
            if KEEP_GPO_FOR_EMPTY_RUNS:
                gpo_tokens += len(run.tokens)
            else:
                by_element.setdefault(id(run.element), {})[run.index] = ""
            continue
        cand_used += len(toks)
        # keep the original leading and trailing space so that inline anchors stay separated from words
        part = linears[id(run.element)].parts[run.index]
        text = " ".join(toks)
        if _leading_space(part):
            text = " " + text
        if _trailing_space(part):
            text += " "
        by_element.setdefault(id(run.element), {})[run.index] = text
        replaced += 1
    for el_id, new_parts in by_element.items():
        rewrite_element(linears[el_id], new_parts)
    if kept_empty:
        warnings.append(f"{kept_empty} run(s) had no candidate text and keep the GPO text")
    return {"runs_replaced": replaced, "runs_kept": kept_empty, "substituted_tokens": substituted,
            "candidate_tokens": cand_used, "gpo_tokens": gpo_tokens,
            "candidate_share": round(cand_used / (cand_used + gpo_tokens), 4) if cand_used + gpo_tokens else 0.0}


def _leading_space(part: str) -> bool:
    return bool(part) and part[0].isspace()


def _trailing_space(part: str) -> bool:
    return bool(part) and part[-1].isspace()


# ---------------------------------------------------------------------------- identifiers


ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def roman_to_int(text: str) -> Optional[int]:
    s = text.strip().lower()
    if not s or any(ch not in ROMAN for ch in s):
        return None
    total = 0
    for i, ch in enumerate(s):
        v = ROMAN[ch]
        if i + 1 < len(s) and ROMAN[s[i + 1]] > v:
            total -= v
        else:
            total += v
    return total


def chapter_number(text: Optional[str]) -> Optional[str]:
    """'162' -> '162'; 'CXXI' -> '121'; None otherwise."""
    if not text:
        return None
    s = text.strip().rstrip(".")
    if s.isdigit():
        return s
    n = roman_to_int(s)
    return str(n) if n else None


def law_identifiers(identity: DocIdentity, root: etree._Element, chapter: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """(primary, alternate) document identifiers by the rules of plan section 7."""
    meta = root.find(NS + "meta")
    dc_type = (meta.findtext(DC + "type") if meta is not None else "") or ""
    doc_number = (meta.findtext(NS + "docNumber") if meta is not None else None) or None
    approved = (meta.findtext(NS + "approvedDate") or meta.findtext(DC + "date")) if meta is not None else None
    approved = approved or identity.date_issued
    congress = identity.congress or (int(meta.findtext(NS + "congress")) if meta is not None and (meta.findtext(NS + "congress") or "").isdigit() else None)
    private = identity.is_private or (meta is not None and (meta.findtext(NS + "publicPrivate") or "").strip() == "private")
    number = identity.law_number
    if number is None and doc_number and dc_type in ("Public Law", "Private Law") and doc_number.isdigit():
        number = int(doc_number)
    if chapter is None and dc_type == "Chapter":
        chapter = chapter_number(doc_number)
    year = int(approved[:4]) if approved and re.match(r"^\d{4}-\d{2}-\d{2}", approved) else None
    pl = f"/us/{'pvtl' if private else 'pl'}/{congress}/{number}" if congress and number and root.tag == NS + "pLaw" else None
    act = f"/us/act/{approved}/ch{chapter}" if approved and year and chapter and root.tag == NS + "pLaw" else None
    if year is not None and year < FIRST_PUBLIC_LAW_YEAR:
        return act, None
    if pl and act and year is not None and year <= LAST_CHAPTER_YEAR:
        return pl, act
    if pl:
        return pl, None
    return act, None


def add_identifiers(root: etree._Element, primary: Optional[str], alternate: Optional[str], volume: Optional[int]) -> dict:
    """Set the document identifier, section and level identifiers, the alternate identifier property, and
    lower-case page identifiers. Returns counts."""
    counts = {"levels": 0, "pages": 0}
    used_ids = {el.get("id") for el in root.iter() if isinstance(el.tag, str) and el.get("id")}

    def unique(base: str) -> str:
        candidate, n = base, 2
        while candidate in used_ids:
            candidate = f"{base}_{n}"
            n += 1
        used_ids.add(candidate)
        return candidate

    if primary:
        root.set("identifier", primary)
    if alternate:
        meta = root.find(NS + "meta")
        if meta is None:
            meta = etree.Element(NS + "meta")
            root.insert(0, meta)
        for prop in meta.findall(NS + "property"):
            if prop.get("role") == "alternateIdentifier":
                meta.remove(prop)
        prop = etree.SubElement(meta, NS + "property")
        prop.set("role", "alternateIdentifier")
        prop.text = alternate
    main = root.find(NS + "main")
    if main is not None and primary:
        def walk(el: etree._Element, path: str) -> None:
            for child in el:
                if not isinstance(child.tag, str) or child.tag in KEEP_TAGS:
                    continue
                if child.tag == NS + "section":
                    value = _num_value(child)
                    if value:
                        ident = f"{path}/s{value}"
                        child.set("identifier", ident)
                        if not child.get("id"):
                            child.set("id", unique(slug_id(ident)))
                        counts["levels"] += 1
                        walk(child, ident)
                        continue
                    walk(child, path)
                elif child.tag in LEVEL_TAGS and "/s" in path:
                    value = _num_value(child)
                    if value:
                        ident = f"{path}/{value}"
                        child.set("identifier", ident)
                        if not child.get("id"):
                            child.set("id", unique(slug_id(ident)))
                        counts["levels"] += 1
                        walk(child, ident)
                        continue
                    walk(child, path)
                elif child.tag in BIG_LEVELS:
                    value = _num_value(child)
                    walk(child, f"{path}/{BIG_LEVELS[child.tag]}{value}" if value else path)
                else:
                    walk(child, path)

        walk(main, primary)
    for page in root.iter(NS + "page"):
        ident = page.get("identifier")
        if ident:
            page.set("identifier", ident.lower())
            counts["pages"] += 1
        elif volume:
            m = re.search(r"(\d+)\s*Stat\.?\s*([A-Za-z]*\d+)", " ".join(page.itertext()), re.I)
            if m:
                page.set("identifier", f"/us/stat/{volume}/{m.group(2).lower()}")
                counts["pages"] += 1
    return counts


def _num_value(el: etree._Element) -> Optional[str]:
    num = el.find(NS + "num")
    if num is None:
        return None
    value = num.get("value")
    if value:
        return re.sub(r"[^A-Za-z0-9.\-]", "", value.strip())
    text = re.sub(r"\s+", " ", " ".join(num.itertext())).strip()
    m = re.match(r"^(?:SEC(?:TION)?\.?\s*)?(\d+[A-Za-z]?)\.?$", text, re.I) or re.match(r"^\(([A-Za-z0-9]{1,4})\)$", text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------- candidate text


def candidate_tokens(cand_root: etree._Element) -> tuple[list[str], list[tuple[str, int, etree._Element]], list[str], list[str]]:
    """(main tokens, section anchors, preface paragraphs, trailing paragraphs) of a candidate document."""
    main = cand_root.find(NS + "main")
    runs, _ = collect_runs(main) if main is not None else ([], {})
    offsets, total = [], 0
    for run in runs:
        offsets.append(total)
        total += len(run.tokens)
    tokens = [t for run in runs for t in run.tokens]
    anchors = section_anchors(main, runs, offsets) if main is not None else []
    preface = cand_root.find(NS + "preface")
    lead = [" ".join(p.itertext()).strip() for p in preface.findall(NS + "p")] if preface is not None else []
    trail = []
    for appendix in cand_root.findall(NS + "appendix"):
        if appendix.get("role") == "trailingMatter":
            trail += [" ".join(p.itertext()).strip() for p in appendix.iter(NS + "p")]
    return tokens, anchors, [t for t in lead if t], [t for t in trail if t]


def clip_tokens(gpo_tokens: list[str], cand: list[str], warnings: list[str]) -> tuple[int, int]:
    """Token span of the candidate that covers the GPO text (benchmark.metrics.clip_to_reference)."""
    from benchmark import metrics

    if not gpo_tokens or not cand:
        return 0, len(cand)
    text = " ".join(cand)
    clip = metrics.clip_to_reference(" ".join(gpo_tokens), text)
    starts = []
    pos = 0
    for t in cand:
        starts.append(pos)
        pos += len(t) + 1
    start_tok = next((i for i, s in enumerate(starts) if s + len(cand[i]) > clip.start), 0) if clip.head_found else 0
    end_tok = next((i for i, s in enumerate(starts) if s >= clip.end), len(cand)) if clip.tail_found else len(cand)
    if not clip.head_found:
        warnings.append("candidate text: the first words of the GPO text were not found; nothing clipped at the head")
    if not clip.tail_found:
        warnings.append("candidate text: the last words of the GPO text were not found; nothing clipped at the tail")
    return start_tok, max(start_tok, end_tok)


def _add_preface_paragraphs(root: etree._Element, texts: list[str]) -> None:
    if not texts:
        return
    preface = root.find(NS + "preface")
    if preface is None:
        preface = etree.Element(NS + "preface")
        meta = root.find(NS + "meta")
        root.insert(root.index(meta) + 1 if meta is not None else 0, preface)
    for i, text in enumerate(texts):
        p = etree.Element(NS + "p")
        p.text = text
        preface.insert(i, p)


def _add_trailing_paragraphs(root: etree._Element, texts: list[str]) -> None:
    if not texts:
        return
    appendix = etree.SubElement(root, NS + "appendix")
    appendix.set("role", "trailingMatter")
    content = etree.SubElement(appendix, NS + "content")
    for text in texts:
        p = etree.SubElement(content, NS + "p")
        p.text = text


# ---------------------------------------------------------------------------- build


def build_hybrid(gpo_tree, cand_tree, identity: DocIdentity, pages: Optional[int] = None,
                 chapter: Optional[str] = None) -> tuple[etree._ElementTree, dict]:
    """GPO structure with the candidate's text. `gpo_tree` may be None (the candidate is returned as is)."""
    warnings: list[str] = []
    cand_root = copy.deepcopy(uslm_root(cand_tree))
    cand_tokens_all, cand_anchors, cand_lead, cand_trail = candidate_tokens(cand_root)
    docling_chars = len(" ".join(cand_tokens_all))
    if gpo_tree is None:
        warnings.append("no GPO slice; candidate document returned unchanged")
        tree = etree.ElementTree(cand_root)
        return tree, _stats(tree, docling_chars, pages, warnings, 0, 0, {})

    root = copy.deepcopy(uslm_root(gpo_tree))
    etree.strip_elements(root, etree.Comment, etree.ProcessingInstruction, with_tail=False)
    main = root.find(NS + "main")
    if main is None:
        main = etree.SubElement(root, NS + "main")
    runs, linears = collect_runs(main)
    gpo_tokens = [t for run in runs for t in run.tokens]
    offsets, total = [], 0
    for run in runs:
        offsets.append(total)
        total += len(run.tokens)
    gpo_anchors = section_anchors(main, runs, offsets)

    start, end = clip_tokens(gpo_tokens, cand_tokens_all, warnings)
    cand_tokens = cand_tokens_all[start:end]
    lead = cand_lead + ([" ".join(cand_tokens_all[:start])] if start else [])
    trail = ([" ".join(cand_tokens_all[end:])] if end < len(cand_tokens_all) else []) + cand_trail
    shifted = [(v, i - start, el) for v, i, el in cand_anchors if start <= i < end]
    pairs = match_sections(gpo_anchors, shifted, gpo_tokens, cand_tokens)
    matched, total_sections = len(pairs), len(list(main.iter(NS + "section")))
    if total_sections and matched < len(gpo_anchors):
        warnings.append(f"{len(gpo_anchors) - matched} of {len(gpo_anchors)} numbered GPO section(s) not matched in the candidate; aligned by text")
    counts = {}
    if not cand_tokens:
        warnings.append("candidate has no body text; GPO text kept")
    elif not runs:
        warnings.append("GPO document has no text runs; candidate text appended to main")
        p = etree.SubElement(main, NS + "p")
        p.text = " ".join(cand_tokens)
    else:
        spans = align_runs(runs, cand_tokens, pairs)
        counts = replace_runs(runs, linears, cand_tokens, spans, warnings)
    _add_preface_paragraphs(root, lead)
    _add_trailing_paragraphs(root, trail)
    primary, alternate = law_identifiers(identity, root, chapter)
    if primary is None:
        warnings.append("no document identifier (no congress and law number, and no date and chapter)")
    ids = add_identifiers(root, primary, alternate, identity.volume)
    counts.update({"identifiers": ids["levels"], "page_identifiers": ids["pages"], "identifier": primary, "alternate_identifier": alternate})
    etree.cleanup_namespaces(root)
    tree = etree.ElementTree(root)
    return tree, _stats(tree, docling_chars, pages, warnings, matched, total_sections, counts)


def uslm_root(tree_or_root) -> etree._Element:
    if isinstance(tree_or_root, etree._ElementTree):
        return tree_or_root.getroot()
    return tree_or_root


def _stats(tree: etree._ElementTree, docling_chars: int, pages: Optional[int], warnings: list[str], matched: int, total: int,
           counts: dict) -> dict:
    root = tree.getroot()
    main = root.find(NS + "main")
    body = len(uslm._squash(" ".join(main.itertext()))) if main is not None else 0
    kept = uslm.kept_text_chars(tree)
    if pages is None:
        pages = len(list(root.iter(NS + "page")))
    return {
        "pages": pages, "kept_chars": kept, "body_chars": body, "docling_chars": docling_chars,
        "kept_ratio": round(kept / docling_chars, 4) if docling_chars else 1.0,
        "warnings": len(warnings), "warning_log": warnings, "sections_matched": matched, "sections_total": total, **counts,
    }


# ---------------------------------------------------------------------------- paths and profile family


def gpo_slice_path(identity: DocIdentity) -> Optional[Path]:
    volume = identity.volume
    if volume is None and identity.package_id and identity.package_id.startswith("STATUTE-"):
        volume = int(identity.package_id.split("-")[1])
    if volume is None or not identity.granule_id:
        return None
    return DATA_DIR / "granules" / f"STATUTE-{volume}" / "uslm" / f"{identity.granule_id}.xml"


def candidate_xml_path(variant: str, xml_path: Path | str) -> Path:
    from pipeline.convert import XML_DIR, profile_dirname

    return XML_DIR / profile_dirname(variant) / Path(xml_path).name


def chapter_from_mods(pdf_path: Path | str) -> Optional[str]:
    mods = Path(pdf_path).with_suffix(".mods.xml")
    if not mods.exists():
        return None
    try:
        from downloader.mods import parse_mods

        return chapter_number(parse_mods(mods.read_bytes()).get("chapter"))
    except Exception as exc:  # a MODS file that does not parse only loses the chapter identifier
        logger.warning("%s: MODS not parsed (%s)", mods, exc)
        return None


def pdf_page_count(pdf_path: Path | str, page_range) -> Optional[int]:
    if page_range:
        return page_range[1] - page_range[0] + 1
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(pdf_path))
        try:
            return len(pdf)
        finally:
            pdf.close()
    except Exception:
        return None


def uslm_builder(pdf_path, variant: Optional[str], page_range, identity=None, doclang_path=None, xml_path=None, **kwargs):
    """pipeline.convert entry point for `hybrid:{candidate profile}`: returns (lxml tree, stats)."""
    if not variant:
        raise ValueError("the hybrid profile needs the text candidate's profile as its variant, e.g. hybrid:scanned")
    if isinstance(identity, dict):
        identity = DocIdentity(**identity)
    identity = identity or DocIdentity()
    cand_path = candidate_xml_path(variant, xml_path or f"{identity.granule_id or Path(pdf_path).stem}.xml")
    if not cand_path.exists():
        raise FileNotFoundError(f"candidate USLM {cand_path} missing; run the {variant!r} profile first")
    cand_tree = etree.parse(str(cand_path))
    gpo_path = gpo_slice_path(identity)
    gpo_tree = etree.parse(str(gpo_path)) if gpo_path and gpo_path.exists() else None
    if gpo_tree is None:
        logger.warning("%s: no GPO slice at %s; returning the %s output unchanged", identity.granule_id, gpo_path, variant)
    tree, stats = build_hybrid(gpo_tree, cand_tree, identity, pages=pdf_page_count(pdf_path, page_range),
                               chapter=chapter_from_mods(pdf_path))
    stats["candidate"] = str(cand_path)
    stats["gpo"] = str(gpo_path) if gpo_tree is not None else None
    logger.info("%s [hybrid:%s]: sections %d/%d matched, %d run(s) replaced, %d kept, body %d chars (candidate %d), %d warning(s)",
                identity.granule_id, variant, stats["sections_matched"], stats["sections_total"], stats.get("runs_replaced", 0),
                stats.get("runs_kept", 0), stats["body_chars"], stats["docling_chars"], stats["warnings"])
    return tree, stats


register_family(ProfileFamily(FAMILY, "GPO slice structure with a text candidate's body text; variant = the candidate's profile",
                              uslm_builder=uslm_builder, runs_in_container=True))
