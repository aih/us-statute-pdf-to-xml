"""Gold set for the scanned era: page images transcribed twice by Claude and adjudicated, then CER of a
profile's output and of the GPO USLM (C0) against those pages.

    python -m benchmark.gold build --pages 150 [--seed 20260908] [--model claude-opus-5] [--dry-run | --fetch-only] \
        [--period 1901-1950] [--limit N] [--budget 40]
    python -m benchmark.gold score [--profile scanned] [--period 1901-1950]

Sampling (`build`): 30 pages per period (PERIODS, volume ranges recorded in benchmark/gold_sample.yaml
with the dates GovInfo reports for the boundary volumes), PUBLICLAW granules only, at most three volumes
per period and two pages per granule. The volume choice and the granule order come from the seed; the
pages of a granule come from a generator seeded with the seed and the granule id, so a granule's pages
do not depend on which granules were downloaded before it. Granule listings are cached by
benchmark.sample.load_listing; PDFs and MODS go to data/granules/ (downloader.fetch_granules.process_granule
when POSTGRES_URL is set, a database-free download otherwise).

Each page is rendered at 300 dpi to data/gold/{granule}/p{n}.png; the two transcription calls see enlarged
crops of its top and bottom halves (overlapping) and the adjudication call sees the full page as well. Two
transcriptions come from two system prompts with
different wording (`SYSTEM_A`, `SYSTEM_B`). The two line lists are aligned (`differing_runs`, on role and
normalized text); when they differ, a third call sees both transcriptions, the numbered differing runs, and
the image, and returns the printed lines for each run. The page is A's lines where the two agree and the
adjudicator's lines in each differing run (`apply_resolutions`); a run the adjudicator did not answer keeps
A's lines and is counted in `adjudication.unresolved`. The record for each page is
benchmark/gold/{granule}/p{n}.json.

Scoring (`score`): the gold body text of a page is its `body` lines joined by newlines and normalized
with benchmark.metrics.normalize; sidenote lines are scored separately. A profile's page text comes
from data/doclang/<profile dir>/{granule}.json through pipeline.uslm.load_pages (items of kind `body`
that are not footnotes; kind `sidenote` for the sidenote score). C0's page text is the GPO USLM text
between the page markers of that Statutes at Large page, read from the volume USLM
(data/volumes/xmls/STATUTE-{v}.xml, downloaded from the Hub dataset when missing) or, failing that,
from the granule slice in data/granules/STATUTE-{v}/uslm/. The report goes to
data/reports/<date>-wp10-gold.md.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import io
import json
import logging
import os
import random
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median
from typing import Iterable, Optional

import yaml

from benchmark import metrics
from benchmark.judge import DEFAULT_MODEL, FALLBACK_BETA, PRICE_PER_MTOK
from benchmark.sample import estimate_pages, era_for_volume, listing_path, load_listing, page_key
from downloader.config import DATA_DIR, LOG_DIR, exit_on_missing_env, govinfo_api_key, setup_logging

logger = logging.getLogger("gold")

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLD_DIR = REPO_ROOT / "benchmark" / "gold"
SPEC_PATH = REPO_ROOT / "benchmark" / "gold_sample.yaml"
IMAGE_DIR = DATA_DIR / "gold"
REPORTS_DIR = DATA_DIR / "reports"
VOLUME_XML_DIR = DATA_DIR / "volumes" / "xmls"

PERIODS = [
    {"name": "1789-1850", "volumes": [1, 9]},
    {"name": "1851-1900", "volumes": [10, 31]},
    {"name": "1901-1950", "volumes": [32, 64]},
    {"name": "1951-1975", "volumes": [65, 89]},
    {"name": "1976-2002", "volumes": [90, 116]},
]
PAGES_PER_PERIOD = 30
VOLUMES_PER_PERIOD = 3
PAGES_PER_GRANULE = 2
MAX_GRANULE_PAGES = 30
GRANULE_CLASS = "PUBLICLAW"
DEFAULT_SEED = 20260908
DPI = 300
REVIEW_PAGES = 20
ROLES = ["running-head", "sidenote", "body", "footnote", "page-number"]
API_LONG_EDGE = 1568  # the API scales longer edges down to this
API_JPEG_QUALITY = 92
DEFAULT_BUDGET_USD = 40.0
IN_FLIGHT = 4


# ---------------------------------------------------------------------------- periods and sampling


def period_for_volume(volume: int) -> Optional[str]:
    for p in PERIODS:
        lo, hi = p["volumes"]
        if lo <= volume <= hi:
            return p["name"]
    return None


def boundary_volumes() -> list[int]:
    """Volumes whose GovInfo dates document the period boundaries: the last and first volume of each period."""
    out: set[int] = set()
    for p in PERIODS:
        out.update(p["volumes"])
    return sorted(out)


def choose_volumes(rng: random.Random, period: dict) -> list[int]:
    """The period's volumes in seeded order; the first VOLUMES_PER_PERIOD with public-law candidates are used
    (volumes 7 and 8 hold treaties only)."""
    lo, hi = period["volumes"]
    pool = list(range(lo, hi + 1))
    rng.shuffle(pool)
    return pool


def pick_volumes(order: list[int], listings: dict[int, list[dict]], n: int = VOLUMES_PER_PERIOD) -> list[int]:
    """The first `n` volumes of `order` whose listing has candidates; volumes without a listing are skipped."""
    out = []
    for v in order:
        if v in listings and granule_pool(v, listings[v]):
            out.append(v)
        if len(out) >= n:
            break
    return sorted(out)


def granule_pool(volume: int, listing: list[dict], max_pages: int = MAX_GRANULE_PAGES) -> list[dict]:
    """PUBLICLAW granules of a volume with an estimated length, sorted by page, at most `max_pages` long."""
    est = estimate_pages(listing)
    out = []
    for g in listing:
        if g.get("granuleClass") != GRANULE_CLASS or page_key(g["granuleId"]) is None:
            continue
        pages = est.get(g["granuleId"])
        if pages is None or pages > max_pages:
            continue
        out.append({"granule_id": g["granuleId"], "package_id": f"STATUTE-{volume}", "volume": volume,
                    "period": period_for_volume(volume), "era": era_for_volume(volume), "granule_class": GRANULE_CLASS,
                    "title": (g.get("title") or "")[:200], "est_pages": pages, "date_issued": g.get("dateIssued")})
    out.sort(key=lambda r: page_key(r["granule_id"]))
    return out


def order_granules(rng: random.Random, pools: dict[int, list[dict]]) -> list[dict]:
    """Shuffle each volume's pool and interleave the volumes, so the draw is balanced across volumes."""
    shuffled = []
    for volume in sorted(pools):
        pool = list(pools[volume])
        rng.shuffle(pool)
        shuffled.append(pool)
    out = []
    for i in range(max((len(p) for p in shuffled), default=0)):
        for pool in shuffled:
            if i < len(pool):
                out.append(pool[i])
    return out


def select_pages(granule_id: str, n_pages: int, seed: int, k: int = PAGES_PER_GRANULE) -> list[int]:
    """Up to `k` distinct 1-based pages of a granule, from a generator seeded with the seed and the id."""
    if n_pages <= 0:
        return []
    rng = random.Random(f"{seed}:{granule_id}")
    return sorted(rng.sample(range(1, n_pages + 1), min(k, n_pages)))


def chosen_volumes(seed: int) -> dict[str, list[int]]:
    rng = random.Random(seed)
    return {p["name"]: choose_volumes(rng, p) for p in PERIODS}


def plan_sample(listings: dict[int, list[dict]], seed: int, pages_per_period: int = PAGES_PER_PERIOD,
                page_count=None, periods: Optional[Iterable[str]] = None) -> list[dict]:
    """From {volume: listing} pick granules and pages per period; one row per page, with `pdf_pages`.
    `page_count(granule) -> int` gives the real page count of a granule (the estimate is used when it is
    None); a granule whose callback raises is skipped."""
    wanted = set(periods) if periods else None
    rows = []
    for period_name, volumes in chosen_volumes(seed).items():
        if wanted and period_name not in wanted:
            continue
        pools = {v: granule_pool(v, listings[v]) for v in pick_volumes(volumes, listings)}
        taken = 0
        for g in order_granules(random.Random(f"{seed}:{period_name}"), pools):
            if taken >= pages_per_period:
                break
            if page_count is None:
                n_pages = g["est_pages"]
            else:
                try:
                    n_pages = page_count(g)
                except Exception as exc:
                    logger.error("%s: skipped: %s", g["granule_id"], exc)
                    continue
            for n in select_pages(g["granule_id"], n_pages, seed):
                if taken >= pages_per_period:
                    break
                rows.append({**g, "pdf_page": n, "pdf_pages": n_pages})
                taken += 1
    return rows


# ---------------------------------------------------------------------------- inputs


def granule_paths(granule_id: str) -> tuple[Path, Path]:
    from downloader.fetch_granules import granule_paths as _paths

    return _paths(granule_id, DATA_DIR / "granules")


def fetch_granule(client, entry: dict) -> dict:
    """Download the granule PDF and MODS; return the parsed MODS. Uses process_granule (granules row) when a
    database is configured, else a database-free download to the same paths."""
    from downloader.mods import parse_mods

    pdf_path, mods_path = granule_paths(entry["granule_id"])
    if not (pdf_path.exists() and mods_path.exists()):
        if os.getenv("POSTGRES_URL"):
            from downloader.fetch_granules import process_granule

            process_granule(client, entry, DATA_DIR / "granules", 2)
        else:
            summary = client.granule_summary(entry["package_id"], entry["granule_id"])
            if summary is None:
                raise RuntimeError(f"{entry['granule_id']}: no granule summary")
            download = summary.get("download") or {}
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            if not mods_path.exists() and download.get("modsLink"):
                mods_path.write_bytes(client.fetch_bytes(download["modsLink"]))
            if not pdf_path.exists() and download.get("pdfLink"):
                client.download_ranged(download["pdfLink"], pdf_path, parts=2)
    if not pdf_path.exists():
        raise RuntimeError(f"{entry['granule_id']}: no PDF")
    return parse_mods(mods_path.read_bytes()) if mods_path.exists() else {}


def pdf_page_count(pdf_path: Path) -> int:
    import pypdfium2 as pdfium

    return len(pdfium.PdfDocument(str(pdf_path)))


STAT_PAGE = re.compile(r"^([A-Za-z]*)(\d+)$")


def stat_page_label(start_label: Optional[str], pdf_page: int) -> Optional[str]:
    """Statutes at Large page of a PDF page from the MODS start label: ('A13', 2) -> 'A14'."""
    m = STAT_PAGE.match((start_label or "").strip())
    if not m:
        return None
    return f"{m.group(1)}{int(m.group(2)) + pdf_page - 1}"


def render_page(pdf_path: Path, pdf_page: int, out_png: Path, dpi: int = DPI) -> Path:
    from benchmark.rasterize import render_pages

    if out_png.exists():
        return out_png
    out_png.parent.mkdir(parents=True, exist_ok=True)
    for _no, image in render_pages(pdf_path, dpi, [pdf_page]):
        image.save(out_png, format="PNG", optimize=False)
    return out_png


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def api_images(png_path: Path, long_edge: int = API_LONG_EDGE, overlap: float = 0.06) -> list[bytes]:
    """JPEG bytes for the model: the full page, then its top and bottom halves (overlapping), each scaled so
    the longer edge is at most `long_edge`."""
    from PIL import Image

    def encode(img) -> bytes:
        scale = long_edge / max(img.size)
        if scale < 1:
            img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=API_JPEG_QUALITY, optimize=True)
        return buf.getvalue()

    with Image.open(png_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        cut = int(h * overlap)
        top = im.crop((0, 0, w, h // 2 + cut))
        bottom = im.crop((0, h // 2 - cut, w, h))
        return [encode(im), encode(top), encode(bottom)]


def image_blocks(images: list[bytes]) -> list[dict]:
    labels = ["Full page.", "Upper half, enlarged.", "Lower half, enlarged."]
    blocks = []
    for label, data in zip(labels, images):
        blocks.append({"type": "text", "text": label})
        blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                   "data": base64.standard_b64encode(data).decode("ascii")}})
    return blocks


# ---------------------------------------------------------------------------- Claude


LINE_ITEM = {
    "type": "object",
    "properties": {
        "role": {"type": "string", "enum": ROLES},
        "text": {"type": "string", "description": "The printed line, character for character."},
    },
    "required": ["role", "text"],
    "additionalProperties": False,
}
LINES_SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": LINE_ITEM}},
    "required": ["lines"],
    "additionalProperties": False,
}
ADJUDICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "resolutions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "run": {"type": "integer", "description": "The run number from the list of differing runs."},
                    "lines": {"type": "array", "items": LINE_ITEM,
                              "description": "The lines printed at this point of the page, in order; empty when nothing is printed there."},
                    "reason": {"type": "string"},
                },
                "required": ["run", "lines", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["resolutions"],
    "additionalProperties": False,
}

SYSTEM_A = """You transcribe one printed page of the United States Statutes at Large from its image. You receive two
enlarged crops of the page, its upper half and its lower half; the crops overlap by a few lines.

Return every line of text on the page as one entry in `lines`, in reading order: the running head first,
then the main text column from top to bottom, with each marginal note placed immediately before the body
line it sits beside, then footnotes, then the page number when it is printed apart from the running head.

Roles:
- running-head: the header line at the top of the page (volume and page, "PUBLIC LAW ...", session, date).
- sidenote: a marginal note printed in small type beside the text column (citations, dates, short summaries).
- body: a line of the main text column, including headings, chapter and section lines, the enacting clause,
  and the approval line.
- footnote: a line printed below the main text and set apart from it.
- page-number: a bare page number.

Transcribe characters exactly as printed: keep spelling, capitalization, punctuation, ligatures written as
their letters, and the hyphen when a word is split at the line end. Small capitals are written as capitals.
Long s is written as s. Do not expand abbreviations, correct errors, or merge or split printed lines. Text
that cannot be read is written as [illegible]. Return only the transcription."""

SYSTEM_B = """You are producing a diplomatic transcription of a page from the United States Statutes at Large for an
OCR benchmark. The page is provided as two enlarged views, its top half and its bottom half, which overlap
by a few lines; a line shown in both views is transcribed once.

Output the text as a list of `lines`, one entry per typeset line, ordered as a reader proceeds: header
lines, then the text column top to bottom. Marginal notes are separate entries with role sidenote, inserted
at the point where they align with the text column. Notes below a rule at the foot of the page have role
footnote. A page number standing alone has role page-number; a header line carrying the volume, page, law
number, session, or date has role running-head. Everything else in the text column has role body.

Reproduce what is printed, character for character: archaic spellings, printing errors, italic and
small-capital words in their printed letters (small capitals as capitals), end-of-line hyphens, section
signs, and dashes. Never normalize, modernize, or complete anything. Keep each printed line as one entry;
do not join lines into paragraphs. Use [illegible] for characters that cannot be read. Return only the
transcription."""

SYSTEM_ADJ = """You reconcile two independent transcriptions of one page of the United States Statutes at Large against
the page image. You receive the page at full size, enlarged crops of its top and bottom halves, the two
transcriptions as numbered lines with roles (running-head, sidenote, body, footnote, page-number), and a
numbered list of the runs where the transcriptions differ in text, role, line breaks, or the presence of a
line. Lines outside those runs are agreed and are kept as they are.

For every run in the list, read the image and return in `resolutions` the lines actually printed at that
point of the page, in reading order, with the role of each line, and a short reason. Return an empty list
of lines for a run when nothing is printed there (a line one transcription invented). Keep printed
spelling, capitalization, end-of-line hyphens, and small capitals as capitals; use [illegible] only where
neither version can be confirmed from the image. Return one resolution per run and nothing else."""

PROMPTS = {"A": SYSTEM_A, "B": SYSTEM_B}
USER_TEXT = {"A": "Transcribe this page.", "B": "Produce the transcription of this page."}


def cost_for_usage(model: str, usage) -> float:
    price_in, price_out = PRICE_PER_MTOK.get(model, PRICE_PER_MTOK[DEFAULT_MODEL])
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return (usage.input_tokens * price_in + cache_read * price_in * 0.1 + cache_write * price_in * 1.25
            + usage.output_tokens * price_out) / 1_000_000


def usage_dict(usage) -> dict:
    return {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0}


def make_client(max_retries: int = 5):
    import anthropic

    workspace = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
    headers = {"anthropic-workspace-id": workspace} if workspace else None
    return anthropic.Anthropic(default_headers=headers, max_retries=max_retries)


def clean_lines(lines: Iterable[dict]) -> list[dict]:
    out = []
    for line in lines or []:
        text = str(line.get("text", "")).strip()
        role = line.get("role") if line.get("role") in ROLES else "body"
        if text:
            out.append({"role": role, "text": text})
    return out


def numbered(lines: list[dict]) -> str:
    return "\n".join(f"{i + 1:3d} [{l['role']}] {l['text']}" for i, l in enumerate(lines)) or "(no lines)"


class Transcriber:
    """Two transcriptions and an adjudication per page image through the Messages API."""

    def __init__(self, client=None, model: str = DEFAULT_MODEL, effort: str = "medium", adjudication_effort: str = "high",
                 max_tokens: int = 16000):
        self.client = client if client is not None else make_client()
        self.model = model
        self.effort = effort
        self.adjudication_effort = adjudication_effort
        self.max_tokens = max_tokens

    def _call(self, system: str, content: list[dict], schema: dict, effort: str) -> tuple[dict, dict]:
        started = time.monotonic()
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
            thinking={"type": "adaptive"},
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()
        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            raise RuntimeError(f"refused: {getattr(details, 'category', None)} {getattr(details, 'explanation', '')}")
        if message.stop_reason == "max_tokens":
            raise RuntimeError("output cut at max_tokens")
        text = next((b.text for b in message.content if b.type == "text"), "")
        data = json.loads(text)
        served_by = getattr(message, "model", None) or self.model
        meta = {"model": self.model, "served_by": served_by, "usage": usage_dict(message.usage),
                "cost_usd": round(cost_for_usage(served_by, message.usage), 5), "seconds": round(time.monotonic() - started, 1),
                "stop_reason": message.stop_reason, "request_id": getattr(message, "_request_id", None), "effort": effort}
        return data, meta

    def transcribe(self, images: list[bytes], variant: str) -> dict:
        """One transcription from the enlarged crops (`images[1:]` when the full page is `images[0]`)."""
        crops = images[1:] if len(images) == 3 else images
        content = image_blocks(crops) + [{"type": "text", "text": USER_TEXT[variant]}]
        data, meta = self._call(PROMPTS[variant], content, LINES_SCHEMA, self.effort)
        return {"variant": variant, "lines": clean_lines(data.get("lines")), **meta}

    def adjudicate(self, images: list[bytes], a: list[dict], b: list[dict], runs: list[dict]) -> dict:
        text = (f"Transcription A:\n{numbered(a)}\n\nTranscription B:\n{numbered(b)}\n\n"
                f"Differing runs:\n{runs_text(runs)}\n\nReturn one resolution per run.")
        content = image_blocks(images) + [{"type": "text", "text": text}]
        data, meta = self._call(SYSTEM_ADJ, content, ADJUDICATION_SCHEMA, self.adjudication_effort)
        resolutions = [{"run": int(r.get("run", -1)), "lines": clean_lines(r.get("lines")), "reason": str(r.get("reason", ""))}
                       for r in (data.get("resolutions") or [])]
        return {"resolutions": resolutions, **meta}


# ---------------------------------------------------------------------------- merging


def line_key(line: dict) -> tuple[str, str]:
    return line["role"], metrics.normalize(line["text"]).lower()


def count_disagreements(a: list[dict], b: list[dict]) -> int:
    """Number of differing runs between the two line lists (role and normalized text), by difflib opcodes."""
    ka, kb = [line_key(l) for l in a], [line_key(l) for l in b]
    matcher = difflib.SequenceMatcher(a=ka, b=kb, autojunk=False)
    return sum(1 for op, *_ in matcher.get_opcodes() if op != "equal")


def agreed_lines(a: list[dict], b: list[dict]) -> list[dict]:
    """Lines matched as equal by the alignment of A and B, in A's order."""
    ka, kb = [line_key(l) for l in a], [line_key(l) for l in b]
    matcher = difflib.SequenceMatcher(a=ka, b=kb, autojunk=False)
    out = []
    for op, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if op == "equal":
            out.extend(a[i1:i2])
    return out


def differing_runs(a: list[dict], b: list[dict]) -> list[dict]:
    """The runs where A and B differ (role or normalized text), numbered from 1, with each side's lines and
    the position in A and B."""
    ka, kb = [line_key(l) for l in a], [line_key(l) for l in b]
    runs = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ka, b=kb, autojunk=False).get_opcodes():
        if op != "equal":
            runs.append({"run": len(runs) + 1, "op": op, "a_range": (i1, i2), "b_range": (j1, j2), "a": a[i1:i2], "b": b[j1:j2]})
    return runs


def runs_text(runs: list[dict]) -> str:
    parts = []
    for r in runs:
        i1, i2 = r["a_range"]
        j1, j2 = r["b_range"]
        a_lines = "\n".join(f"    A{i + 1} [{l['role']}] {l['text']}" for i, l in zip(range(i1, i2), r["a"])) or "    (no line in A)"
        b_lines = "\n".join(f"    B{j + 1} [{l['role']}] {l['text']}" for j, l in zip(range(j1, j2), r["b"])) or "    (no line in B)"
        parts.append(f"Run {r['run']} (after A line {i1}, B line {j1}):\n{a_lines}\n{b_lines}")
    return "\n".join(parts) or "(none)"


def apply_resolutions(a: list[dict], runs: list[dict], resolutions: list[dict]) -> tuple[list[dict], list[dict], int]:
    """Assemble the page: A's lines where A and B agree, the adjudicator's lines for each differing run. A run
    without a resolution keeps A's lines and is counted as unresolved. Returns the lines, one disagreement
    record per run (both versions, the text kept, the reason), and the unresolved count."""
    by_run = {r["run"]: r for r in resolutions}
    lines: list[dict] = []
    disagreements: list[dict] = []
    unresolved = 0
    pos = 0
    for r in runs:
        i1, i2 = r["a_range"]
        lines.extend(a[pos:i1])
        res = by_run.get(r["run"])
        if res is None:
            unresolved += 1
            kept = list(r["a"])
            reason = "unresolved: no resolution returned; A kept"
        else:
            kept = [dict(l) for l in res["lines"]]
            reason = res["reason"]
        lines.extend(kept)
        disagreements.append({"run": r["run"], "a": "\n".join(l["text"] for l in r["a"]), "b": "\n".join(l["text"] for l in r["b"]),
                              "kept": "\n".join(l["text"] for l in kept), "reason": reason})
        pos = i2
    lines.extend(a[pos:])
    return lines, disagreements, unresolved


# ---------------------------------------------------------------------------- records


def gold_path(granule_id: str, pdf_page: int, root: Optional[Path] = None) -> Path:
    return Path(root or GOLD_DIR) / granule_id / f"p{pdf_page}.json"


def image_path(granule_id: str, pdf_page: int, root: Optional[Path] = None) -> Path:
    return Path(root or IMAGE_DIR) / granule_id / f"p{pdf_page}.png"


def build_record(page: dict, png: Path, transcriber: Transcriber, images: Optional[list[bytes]] = None) -> dict:
    """Transcribe twice, adjudicate when the transcriptions differ, and assemble the gold record."""
    images = images if images is not None else api_images(png)
    a = transcriber.transcribe(images, "A")
    b = transcriber.transcribe(images, "B")
    runs = differing_runs(a["lines"], b["lines"])
    disagreements = len(runs)
    calls = [a, b]
    if runs:
        adj = transcriber.adjudicate(images, a["lines"], b["lines"], runs)
        calls.append(adj)
        lines, resolved, unresolved = apply_resolutions(a["lines"], runs, adj["resolutions"])
        adjudication = {k: v for k, v in adj.items() if k != "resolutions"}
        adjudication.update({"disagreements": resolved, "unresolved": unresolved})
    else:
        lines, adjudication = list(a["lines"]), {"skipped": "transcriptions agree", "disagreements": [], "cost_usd": 0.0,
                                                  "usage": {"input_tokens": 0, "output_tokens": 0}}
    tokens = {"input_tokens": sum(c["usage"]["input_tokens"] for c in calls),
              "output_tokens": sum(c["usage"]["output_tokens"] for c in calls),
              "cache_read_input_tokens": sum(c["usage"].get("cache_read_input_tokens", 0) for c in calls),
              "cache_creation_input_tokens": sum(c["usage"].get("cache_creation_input_tokens", 0) for c in calls)}
    return {
        "granule_id": page["granule_id"], "package_id": page["package_id"], "volume": page["volume"], "period": page["period"],
        "granule_class": page.get("granule_class"), "title": page.get("title"), "date_issued": page.get("date_issued"),
        "pdf_page": page["pdf_page"], "pdf_pages": page.get("pdf_pages"), "stat_page": page.get("stat_page"),
        "image": str(png.relative_to(DATA_DIR.parent)) if png.is_relative_to(DATA_DIR.parent) else str(png),
        "image_sha256": sha256_file(png), "dpi": DPI, "api_images": len(images),
        "model": transcriber.model, "models": sorted({c.get("served_by") or transcriber.model for c in calls}),
        "effort": {"transcription": transcriber.effort, "adjudication": transcriber.adjudication_effort},
        "transcriptions": {"A": {k: v for k, v in a.items() if k != "variant"}, "B": {k: v for k, v in b.items() if k != "variant"}},
        "adjudication": adjudication, "lines": lines, "disagreement_count": disagreements,
        "tokens": tokens, "cost_usd": round(sum(c.get("cost_usd", 0.0) for c in calls), 5),
        "seconds": round(sum(c.get("seconds", 0.0) for c in calls), 1), "created": datetime.now().isoformat(timespec="seconds"),
    }


def write_record(record: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")


def load_gold(root: Optional[Path] = None, period: Optional[str] = None) -> list[dict]:
    records = []
    for path in sorted(Path(root or GOLD_DIR).glob("*/p*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if period and rec.get("period") != period:
            continue
        rec["_path"] = str(path)
        records.append(rec)
    records.sort(key=lambda r: (r["period"], r["volume"], page_key(r["granule_id"]) or (), r["pdf_page"]))
    return records


def gold_text(record: dict, roles: Iterable[str] = ("body",)) -> str:
    roles = set(roles)
    return metrics.normalize("\n".join(l["text"] for l in record["lines"] if l["role"] in roles))


def choose_review(records: list[dict], seed: int, n: int = REVIEW_PAGES) -> list[dict]:
    """`n` pages for human spot-check, the same number from each period, seeded."""
    rng = random.Random(f"{seed}:review")
    by_period: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_period[r["period"]].append(r)
    names = [p["name"] for p in PERIODS if p["name"] in by_period]
    if not names:
        return []
    per = max(1, n // len(names))
    out = []
    for name in names:
        pool = sorted(by_period[name], key=lambda r: (r["granule_id"], r["pdf_page"]))
        rng.shuffle(pool)
        out.extend(pool[:per])
    return out[:n]


def review_markdown(records: list[dict]) -> str:
    lines = ["# Gold set pages for human spot-check", "",
             f"{len(records)} pages. Open the image, compare it with the adjudicated lines, and note errors in the review.", ""]
    for r in records:
        lines += [f"## {r['granule_id']} page {r['pdf_page']} ({r['period']}, {r['volume']} Stat. {r.get('stat_page')})", "",
                  f"Image: `{r['image']}`  ", f"Record: `benchmark/gold/{r['granule_id']}/p{r['pdf_page']}.json`  ",
                  f"Disagreements between the two transcriptions: {r['disagreement_count']}", "", "```"]
        lines += [f"[{l['role']}] {l['text']}" for l in r["lines"]]
        lines += ["```", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------- build


def write_spec(path: Path, rows: list[dict], meta: dict) -> None:
    by_granule: dict[str, dict] = {}
    for r in rows:
        g = by_granule.setdefault(r["granule_id"], {k: v for k, v in r.items() if k not in ("pdf_page", "stat_page")})
        g.setdefault("pages", []).append(r["pdf_page"])
        g.setdefault("stat_pages", []).append(r.get("stat_page"))
    spec = {**meta, "periods": PERIODS, "granule_class": GRANULE_CLASS, "pages_per_period": PAGES_PER_PERIOD,
            "pages_per_granule": PAGES_PER_GRANULE, "granules": list(by_granule.values())}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")


def volume_dates(client, volumes: Iterable[int], listings: dict[int, list[dict]]) -> dict[int, dict]:
    """GovInfo's dateIssued for each volume and the first and last dateIssued of its public laws (from the
    cached listing when there is one)."""
    out = {}
    for v in sorted(set(volumes)):
        summary = client.package_summary(f"STATUTE-{v}") or {}
        row = {"date_issued": summary.get("dateIssued"), "congress": summary.get("congress"), "title": summary.get("title")}
        listing = listings.get(v)
        if listing:
            dates = sorted(g.get("dateIssued") for g in listing if g.get("granuleClass") == GRANULE_CLASS and g.get("dateIssued"))
            if dates:
                row["public_law_dates"] = [dates[0], dates[-1]]
        out[v] = row
    return out


class Budget:
    """Stops the run when the pages built so far project the whole set over the limit. Pages already on disk
    count in `spent` and `done`; the projection is trusted after `min_pages` pages of this run."""

    def __init__(self, limit_usd: float, total_pages: int, spent: float = 0.0, done: int = 0, min_pages: int = 5):
        self.limit = limit_usd
        self.total = total_pages
        self.spent = spent
        self.done = done
        self.min_pages = min_pages
        self.run_pages = 0
        self.run_spent = 0.0
        self.stopped = False
        self.lock = threading.Lock()

    def projected(self) -> float:
        return self.spent + (self.total - self.done) * (self.spent / self.done) if self.done else 0.0

    def add(self, cost: float) -> None:
        with self.lock:
            self.spent += cost
            self.done += 1
            self.run_pages += 1
            self.run_spent += cost
            projected = self.projected()
            if self.spent > self.limit or (self.run_pages >= self.min_pages and projected > self.limit):
                self.stopped = True
                logger.error("budget: $%.2f spent on %d/%d pages projects to $%.2f, over the $%.2f limit; stopping",
                             self.spent, self.done, self.total, projected, self.limit)


def build(args) -> int:
    setup_logging("gold", args.log_dir)
    from downloader.govinfo import GovInfoClient

    seed = args.seed
    periods = [args.period] if args.period else None
    chosen = chosen_volumes(seed)

    with GovInfoClient(govinfo_api_key()) as client:
        listings: dict[int, list[dict]] = {}
        used: dict[str, list[int]] = {}
        for name, order in chosen.items():
            if periods and name not in periods:
                continue
            for v in order:  # listings in seeded order until three volumes have candidates
                listings[v] = load_listing(v, client)
                pool = granule_pool(v, listings[v])
                logger.info("STATUTE-%d: %d granules, %d %s candidates up to %d pages", v, len(listings[v]), len(pool), GRANULE_CLASS, MAX_GRANULE_PAGES)
                used[name] = pick_volumes(order, listings)
                if len(used[name]) >= VOLUMES_PER_PERIOD:
                    break
        volumes = sorted(v for vs in used.values() for v in vs)
        logger.info("seed %d: volumes %s", seed, ", ".join(f"{name}: {vs}" for name, vs in used.items()))
        dates = volume_dates(client, list(volumes) + boundary_volumes(), listings) if not args.dry_run or args.dates else {}
        mods_by_granule: dict[str, dict] = {}

        def page_count(g: dict) -> int:
            mods_by_granule[g["granule_id"]] = fetch_granule(client, g)
            pdf_path, _ = granule_paths(g["granule_id"])
            return pdf_page_count(pdf_path)

        planned = plan_sample(listings, seed, args.pages_per_period, None if args.dry_run else page_count, periods)
    for p in planned:
        mods = mods_by_granule.get(p["granule_id"], {})
        p["stat_page"] = stat_page_label(mods.get("page_start_label"), p["pdf_page"])
    if args.limit:
        planned = planned[: args.limit]

    by_period = defaultdict(int)
    for p in planned:
        by_period[p["period"]] += 1
    for p in planned:
        print(f"{p['period']}  {p['granule_id']:24s} page {p['pdf_page']}/{p['pdf_pages']}"
              f"  {p['volume']} Stat. {p.get('stat_page') or '?'}  {p['title'][:60]}")
    print(", ".join(f"{k}: {v}" for k, v in sorted(by_period.items())) + f"; {len(planned)} pages")
    write_spec(SPEC_PATH, planned, {"seed": seed, "created": date.today().isoformat(), "dry_run": bool(args.dry_run),
                                    "volumes": used, "volume_dates": dates})
    logger.info("spec: %s", SPEC_PATH)
    if args.dry_run:
        return 0

    transcriber = Transcriber(model=args.model, effort=args.effort, adjudication_effort=args.adjudication_effort)
    todo = []
    existing = 0
    existing_cost = 0.0
    for p in planned:
        pdf_path, _ = granule_paths(p["granule_id"])
        png = render_page(pdf_path, p["pdf_page"], image_path(p["granule_id"], p["pdf_page"]))
        out = gold_path(p["granule_id"], p["pdf_page"])
        if out.exists():
            rec = json.loads(out.read_text(encoding="utf-8"))
            if rec.get("image_sha256") == sha256_file(png):
                existing += 1
                existing_cost += float(rec.get("cost_usd") or 0.0)
                continue
        todo.append((p, png, out))
    budget = Budget(args.budget, len(planned), spent=existing_cost, done=existing)
    logger.info("%d page(s) already built ($%.2f), %d to transcribe with %s (%d in flight, budget $%.0f)",
                existing, existing_cost, len(todo), args.model, IN_FLIGHT, args.budget)
    if args.fetch_only:
        logger.info("fetch only: %d page image(s) under %s; no API calls", len(planned), IMAGE_DIR)
        return 0

    failures: dict[str, str] = {}
    billing_error = None

    def work(item):
        p, png, out = item
        if budget.stopped or billing_error:
            return p, None, "skipped: stopped"
        try:
            rec = build_record(p, png, transcriber)
        except Exception as exc:
            return p, None, str(exc)
        write_record(rec, out)
        budget.add(rec["cost_usd"])
        return p, rec, None

    with ThreadPoolExecutor(max_workers=IN_FLIGHT) as pool:
        futures = [pool.submit(work, item) for item in todo]
        for fut in as_completed(futures):
            p, rec, err = fut.result()
            key = f"{p['granule_id']} p{p['pdf_page']}"
            if err:
                if "credit balance" in err.lower():
                    billing_error = err
                if not err.startswith("skipped"):
                    failures[key] = err
                    logger.error("%s: %s", key, err)
                continue
            t = rec["tokens"]
            logger.info("%s: %d lines, %d disagreement(s), %d in / %d out tokens, $%.3f (total $%.2f)",
                        key, len(rec["lines"]), rec["disagreement_count"], t["input_tokens"], t["output_tokens"],
                        rec["cost_usd"], budget.spent)

    records = load_gold(period=args.period)
    review = choose_review(records, seed)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    (IMAGE_DIR / "review.md").write_text(review_markdown(review), encoding="utf-8")
    print(f"\n{len(records)} gold page(s); ${budget.run_spent:.2f} spent this run, ${budget.spent:.2f} in all. "
          f"Pages for spot-check ({IMAGE_DIR / 'review.md'}):")
    for r in review:
        print(f"  {r['period']}  {r['granule_id']} p{r['pdf_page']}  {r['image']}")
    for key, err in sorted(failures.items()):
        logger.error("FAILED %s: %s", key, err)
    if billing_error:
        logger.error("billing: %s", billing_error)
        return 3
    return 1 if failures else 0


# ---------------------------------------------------------------------------- page texts for scoring


def docling_page_texts(doc_json: Path) -> dict[int, dict[str, str]]:
    """{pdf page: {'body': text, 'sidenote': text}} from a DoclingDocument JSON, classified by pipeline.uslm."""
    from docling_core.types.doc import DoclingDocument
    from pipeline.uslm import load_pages

    doc = DoclingDocument.load_from_json(doc_json)
    out = {}
    for page in load_pages(doc):
        body = [it.text for it in page.items if it.kind == "body" and it.label != "footnote"]
        side = [it.text for it in page.items if it.kind == "sidenote"]
        out[page.no] = {"body": metrics.normalize("\n".join(body)), "sidenote": metrics.normalize("\n".join(side))}
    return out


USLM_SKIP = {metrics.NS + "meta", metrics.NS + "note", metrics.NS + "legislativeHistory", metrics.NS + "centerRunningHead"}


def uslm_page_texts(root, start_page: Optional[str] = None) -> dict[str, dict[str, str]]:
    """{Statutes at Large page label (lower case): {'body', 'sidenote'}} from a USLM document, splitting the
    text at its `<page>` markers. Text before the first marker belongs to `start_page` (a granule slice
    starts on a page whose marker sits in the previous document); it is dropped when `start_page` is None."""
    from pipeline.split_uslm import normalize_page, page_from_identifier

    body: dict[str, list[str]] = defaultdict(list)
    side: dict[str, list[str]] = defaultdict(list)
    current = [normalize_page(start_page)]

    def add(bucket, text):
        if current[0] is not None and text:
            bucket[current[0]].append(text)

    def walk(el):
        if not isinstance(el.tag, str):
            return
        if el.tag == metrics.NS + "page":
            page = page_from_identifier(el.get("identifier"))
            if page:
                current[0] = page
            return
        if el.tag in USLM_SKIP:
            return
        if el.tag == metrics.NS + "sidenote":
            add(side, " ".join(el.itertext()))
            return
        add(body, el.text)
        for child in el:
            walk(child)
            add(body, child.tail)

    walk(root)
    pages = set(body) | set(side)
    return {p: {"body": metrics.normalize(" ".join(body.get(p, []))), "sidenote": metrics.normalize(" ".join(side.get(p, [])))}
            for p in pages}


def volume_xml(volume: int) -> Optional[Path]:
    """The volume USLM: data/volumes/xmls/, a copy under data/historical/xmls/ (read only), else the Hub dataset."""
    path = VOLUME_XML_DIR / f"STATUTE-{volume}.xml"
    if path.exists():
        return path
    historical = DATA_DIR / "historical" / "xmls" / f"STATUTE-{volume}.xml"
    if historical.exists():
        return historical
    repo_id = os.getenv("HF_REPO_ID", "").strip()
    if not repo_id:
        return None
    try:
        from huggingface_hub import hf_hub_download

        logger.info("STATUTE-%d: downloading the volume USLM from %s", volume, repo_id)
        got = Path(hf_hub_download(repo_id, f"xmls/STATUTE-{volume}.xml", repo_type="dataset",
                                   local_dir=str(VOLUME_XML_DIR.parent), token=os.getenv("HF_TOKEN") or None))
        if got != path:
            path.parent.mkdir(parents=True, exist_ok=True)
            got.replace(path)
        return path
    except Exception as exc:
        logger.warning("STATUTE-%d: Hub download failed: %s", volume, exc)
        return None


class C0Texts:
    """GPO USLM page texts per volume, from the volume USLM or the granule slices."""

    def __init__(self):
        self.volumes: dict[int, Optional[dict]] = {}
        self.slices: dict[str, Optional[dict]] = {}

    def for_page(self, volume: int, granule_id: str, stat_page: Optional[str]) -> tuple[Optional[dict[str, str]], str]:
        from lxml import etree

        if not stat_page:
            return None, "no page label"
        label = stat_page.lower()
        if volume not in self.volumes:
            path = volume_xml(volume)
            self.volumes[volume] = uslm_page_texts(etree.parse(str(path)).getroot()) if path else None
            logger.info("STATUTE-%d: %s", volume, f"{len(self.volumes[volume])} pages from the volume USLM" if path else "no volume USLM")
        texts = self.volumes[volume]
        if texts and label in texts:
            return texts[label], "volume"
        if granule_id not in self.slices:
            path = DATA_DIR / "granules" / f"STATUTE-{volume}" / "uslm" / f"{granule_id}.xml"
            if path.exists():
                m = re.match(r"^STATUTE-\d+-Pg([A-Za-z]*\d+)", granule_id)
                self.slices[granule_id] = uslm_page_texts(etree.parse(str(path)).getroot(), m.group(1) if m else None)
            else:
                self.slices[granule_id] = None
        texts = self.slices[granule_id]
        if texts and label in texts:
            return texts[label], "slice"
        return None, "no text for the page"


# ---------------------------------------------------------------------------- score


def profile_dir(profile: str) -> Path:
    return DATA_DIR / "doclang" / profile.replace(":", "-")


def profiles_with_output(records: list[dict]) -> list[str]:
    ids = {r["granule_id"] for r in records}
    out = []
    root = DATA_DIR / "doclang"
    if not root.exists():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if any((d / f"{gid}.json").exists() for gid in ids):
            out.append(d.name)
    return out


@dataclass
class PageScore:
    record: dict
    candidate: str
    cer: Optional[float]
    sidenote_cer: Optional[float]
    source: str
    hyp_chars: int = 0


def score_candidate(records: list[dict], candidate: str, page_texts) -> list[PageScore]:
    """`page_texts(record) -> (texts or None, source)` where texts has 'body' and 'sidenote'."""
    out = []
    for r in records:
        texts, source = page_texts(r)
        if texts is None:
            out.append(PageScore(r, candidate, None, None, source))
            continue
        ref = gold_text(r, ("body",))
        ref_side = gold_text(r, ("sidenote",))
        out.append(PageScore(r, candidate, metrics.cer(ref, texts["body"]) if ref else None,
                             metrics.cer(ref_side, texts["sidenote"]) if ref_side else None, source, len(texts["body"])))
    return out


def summarize(scores: list[PageScore]) -> dict[str, dict]:
    """{period or 'all': {pages, scored, mean_cer, median_cer, sidenote_pages, sidenote_cer, missing}}"""
    groups: dict[str, list[PageScore]] = defaultdict(list)
    for s in scores:
        groups[s.record["period"]].append(s)
        groups["all"].append(s)
    out = {}
    for name, ss in groups.items():
        cers = [s.cer for s in ss if s.cer is not None]
        sides = [s.sidenote_cer for s in ss if s.sidenote_cer is not None]
        out[name] = {"pages": len(ss), "scored": len(cers), "mean_cer": mean(cers) if cers else None,
                     "median_cer": median(cers) if cers else None, "sidenote_pages": len(sides),
                     "sidenote_cer": mean(sides) if sides else None, "missing": len(ss) - len(cers)}
    return out


def _fmt(v: Optional[float], digits: int = 3) -> str:
    return "-" if v is None else f"{v:.{digits}f}"


def summary_table(results: dict[str, list[PageScore]]) -> str:
    lines = ["| Candidate | Period | Pages | Scored | Mean CER | Median CER | Sidenote pages | Sidenote CER |",
             "|---|---|---|---|---|---|---|---|"]
    order = [p["name"] for p in PERIODS] + ["all"]
    for cand, scores in results.items():
        summ = summarize(scores)
        for name in order:
            if name not in summ:
                continue
            g = summ[name]
            lines.append(f"| {cand} | {name} | {g['pages']} | {g['scored']} | {_fmt(g['mean_cer'])} | {_fmt(g['median_cer'])} | "
                         f"{g['sidenote_pages']} | {_fmt(g['sidenote_cer'])} |")
    return "\n".join(lines)


def page_table(records: list[dict], results: dict[str, list[PageScore]]) -> str:
    cands = list(results)
    lines = ["| Page | Period | Stat. page | Gold chars | Disagreements | " + " | ".join(f"{c} CER" for c in cands) + " |",
             "|---|---|---|---|---|" + "---|" * len(cands)]
    by_key = {c: {(s.record["granule_id"], s.record["pdf_page"]): s for s in ss} for c, ss in results.items()}
    for r in records:
        key = (r["granule_id"], r["pdf_page"])
        cells = []
        for c in cands:
            s = by_key[c].get(key)
            cells.append(_fmt(s.cer) if s and s.cer is not None else (s.source if s else "-"))
        lines.append(f"| {r['granule_id']} p{r['pdf_page']} | {r['period']} | {r['volume']} Stat. {r.get('stat_page') or '?'} | "
                     f"{len(gold_text(r))} | {r['disagreement_count']} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_score_report(records: list[dict], results: dict[str, list[PageScore]], path: Path) -> Path:
    by_period = defaultdict(int)
    for r in records:
        by_period[r["period"]] += 1
    total_cost = sum(r.get("cost_usd", 0) for r in records)
    total_in = sum(r["tokens"]["input_tokens"] for r in records)
    total_out = sum(r["tokens"]["output_tokens"] for r in records)
    models = sorted({m for r in records for m in r.get("models", [r.get("model")])})
    disagree = [r["disagreement_count"] for r in records]
    body = [
        "# Gold set (WP10)", "",
        f"Date: {datetime.now().isoformat(timespec='seconds')}. Gold pages: {len(records)} ("
        + ", ".join(f"{k}: {v}" for k, v in sorted(by_period.items())) + f"). Models: {', '.join(models)}. "
        f"Transcription tokens: {total_in:,} in, {total_out:,} out, ${total_cost:.2f}. "
        f"Pages with disagreements between the two transcriptions: {sum(1 for d in disagree if d)}/{len(records)} "
        f"(mean {mean(disagree) if disagree else 0:.1f} differing runs per page).", "",
        "CER is the Levenshtein distance over normalized characters divided by the gold length, on the `body` lines of "
        "the page; `Sidenote CER` is the same over the `sidenote` lines, on pages that have any. C0 is the GPO USLM text "
        "between the page markers of the Statutes at Large page; a profile's text is the body items of the PDF page "
        "in its DoclingDocument, classified by pipeline.uslm.load_pages. Pages without candidate text are counted "
        "under `Pages` and not under `Scored`.", "",
        "## Per period", "", summary_table(results), "",
        "## Per page", "", page_table(records, results), "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def score(args) -> int:
    setup_logging("gold", args.log_dir)
    records = load_gold(period=args.period)
    if not records:
        logger.error("no gold records under %s", GOLD_DIR)
        return 2
    logger.info("%d gold page(s)", len(records))
    results: dict[str, list[PageScore]] = {}

    c0 = C0Texts()
    results["C0"] = score_candidate(records, "C0", lambda r: c0.for_page(r["volume"], r["granule_id"], r.get("stat_page")))

    profiles = [args.profile] if args.profile else profiles_with_output(records)
    for profile in profiles:
        cache: dict[str, Optional[dict]] = {}

        def texts_for(r, profile=profile):
            gid = r["granule_id"]
            if gid not in cache:
                path = profile_dir(profile) / f"{gid}.json"
                cache[gid] = docling_page_texts(path) if path.exists() else None
            pages = cache[gid]
            if pages is None:
                return None, "no output"
            if r["pdf_page"] not in pages:
                return None, "page missing"
            return pages[r["pdf_page"]], "doclang"

        results[profile] = score_candidate(records, profile, texts_for)

    table = summary_table(results)
    print(table)
    report = write_score_report(records, results, REPORTS_DIR / f"{date.today().isoformat()}-wp10-gold.md")
    logger.info("report: %s", report)
    return 0


# ---------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m benchmark.gold", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="sample pages, transcribe twice, adjudicate, write benchmark/gold/")
    b.add_argument("--pages", type=int, default=PAGES_PER_PERIOD * len(PERIODS), help="total pages (30 per period by default)")
    b.add_argument("--seed", type=int, default=DEFAULT_SEED)
    b.add_argument("--model", default=DEFAULT_MODEL)
    b.add_argument("--effort", default="medium", help="effort for the two transcriptions")
    b.add_argument("--adjudication-effort", default="high")
    b.add_argument("--budget", type=float, default=DEFAULT_BUDGET_USD, help="stop when the projected cost passes this (USD)")
    b.add_argument("--dry-run", action="store_true", help="print the sampled pages and write the spec; no download, no API calls")
    b.add_argument("--fetch-only", action="store_true", help="download the granules, render the page images, write the spec; no API calls")
    b.add_argument("--dates", action="store_true", help="fetch the volume dates in a dry run too")
    b.add_argument("--period", default=None, help="build one period only, e.g. 1901-1950")
    b.add_argument("--limit", type=int, default=None, help="build at most N pages")
    b.add_argument("--log-dir", default=str(LOG_DIR))
    s = sub.add_parser("score", help="CER per period for C0 and a profile's output")
    s.add_argument("--profile", default=None, help="profile name (family[:variant]); default every profile with output")
    s.add_argument("--period", default=None)
    s.add_argument("--log-dir", default=str(LOG_DIR))
    return p


@exit_on_missing_env
def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build":
        args.pages_per_period = max(1, args.pages // len(PERIODS))
        return build(args)
    return score(args)


if __name__ == "__main__":
    sys.exit(main())
