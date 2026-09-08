"""Claude page transcription (candidate C5 of the 2026-09-07 plan).

    python -m pipeline.claude_ocr --spec benchmark/sample.yaml [--model claude-sonnet-5] [--batch] [--limit N] [--granule ID ...]
    python -m pipeline.claude_ocr --pdf path.pdf --id NAME [--pages 1-3] [--dry-run]

Family `claude`; the variant is the model id (`claude:claude-sonnet-5`; default `claude-opus-5`). One request
per page image: the page is rendered with pypdfium2 as a JPEG whose longest side is `TARGET_LONG_SIDE`
pixels (about 2,000 image tokens for a letter page), sent with a cached system prompt, adaptive thinking
(none on Haiku 4.5), and a JSON schema of lines in reading order, each with a role: `running-head`,
`sidenote`, `body`, `footnote`, or `page-number`. Sidenote lines follow the body line they sit beside; body
lines of a two-column page come column by column. `--batch` sends the same requests through the Message
Batches API at half price and polls until they finish.

The adapter (`to_docling`) builds a DoclingDocument with one page per PDF page (size from the PDF) and text
items with synthetic geometry from the line order: body lines fill the main column top to bottom, sidenotes
sit in the right margin at the height of the body line before them, running heads and page numbers in the
top 5 percent of the page, footnotes just above the foot. `pipeline.uslm.classify_items` then sorts them as
it sorts Docling output. Every returned line is kept. By default consecutive lines of one paragraph
(`starts_paragraph` false) are joined with newlines into one item, which is the shape Docling produces;
`merge_paragraphs=False` (`--line-items`) keeps one item per line.

Outputs per granule under data/doclang/claude-{model}/: `{id}.json` (DoclingDocument), `{id}.lines.json`
(the transcription as returned, per page), and `{id}.usage.json` (tokens, cost, seconds per page). The CLI
reads granule PDFs from data/granules/ and needs no database. In the container `benchmark.evaluate
--profiles claude:{model}` runs the same converter through pipeline.convert; `--rebuild` scores the JSON
already on disk.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import math
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

import anthropic

from downloader.config import DATA_DIR, LOG_DIR, setup_logging
from pipeline.profiles import ProfileFamily, register_family

logger = logging.getLogger("claude_ocr")

FAMILY = "claude"
DEFAULT_MODEL = "claude-opus-5"
MODELS = ("claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"
PRICE_PER_MTOK = {  # USD per million tokens (input, output); first-party rates, skill table cached 2026-06-24
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.1
BATCH_MULTIPLIER = 0.5
NO_THINKING_MODELS = ("claude-haiku-4-5",)  # takes budget_tokens only; transcription runs without thinking
NO_EFFORT_MODELS = ("claude-haiku-4-5",)
DEFAULT_EFFORT = "medium"
DEFAULT_MAX_TOKENS = 32000
TARGET_LONG_SIDE = 1500  # pixels; a letter page is then 1159 x 1500 px, about 2,300 image tokens
JPEG_QUALITY = 85
PIXELS_PER_TOKEN = 750
DEFAULT_WORKERS = 4  # requests in flight
MAX_ATTEMPTS = 6
BATCH_POLL_SECONDS = 30
ROLES = ("running-head", "sidenote", "body", "footnote", "page-number")

LINE_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "enum": list(ROLES)},
                    "text": {"type": "string"},
                    "starts_paragraph": {"type": "boolean"},
                },
                "required": ["role", "text", "starts_paragraph"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["lines"],
    "additionalProperties": False,
}

SYSTEM = """You transcribe one page of the United States Statutes at Large from its image. Return every printed line of the page as one object of the JSON schema you are given, in reading order, and nothing else.

Roles:
- running-head: the header line or lines at the top of the page. In the early volumes it reads like "SIXTY-FOURTH CONGRESS. Sess. II. Ch. 162. 1917." or "64 Stat.] 81st Cong., 2d Sess.-Chs. 485, 486-July 21, 22, 1950"; in later volumes it is a law number and date or a "72 STAT." line.
- page-number: the printed page number when it stands apart from the running head.
- body: every line of the law text: chapter and law-number lines ("[CHAPTER 486]", "Public Law 85-910"), "AN ACT" and title lines, the enacting clause, section lines ("SEC. 2. That ..."), headings, provisos, appropriation items, tables, signature lines, and the approval line ("Approved, September 2, 1958."). Text of the neighbouring laws that shares the page is body text too. On a two-column page (treaties, bilingual text) give all lines of the left column first, then all lines of the right column.
- sidenote: a marginal note in the outer margin: a subject cue ("Post Office Department."), a citation ("Vol. 39, p. 412.", "42 U.S.C. 1857."), a date, a bill number ("[H. R. 11009]"), "Proviso.", "Post, p. 123.". Place each sidenote line immediately after the body line it sits beside. Each sidenote line is its own object; do not merge sidenote lines into body lines.
- footnote: lines at the foot of the page below the body text: footnotes and, in later volumes, the legislative history block.

Rules:
- One object per printed line, in the order the page is read. Keep the line breaks of the page: do not merge lines, do not reflow text, and do not omit a line however damaged or faint it is. A blank line is not an object.
- Transcribe the characters as printed: original spelling, capitalization, punctuation, numbers, and end-of-line hyphens. Words set in small capitals are transcribed in capitals as they appear ("SEC.", "Provided"). Do not correct, modernize, expand, or complete anything.
- starts_paragraph is true on the first line of a paragraph: an indented first line, a heading, a chapter or law-number line, a section line, a line that begins a new paragraph with a designator such as "(a)" or "(1)", the enacting clause, the approval line. It is false on a line that continues the paragraph of the line before it. For sidenote, running-head, page-number, and footnote lines it is true on the first line of each note and false on its continuation lines.
- Characters you cannot read: give the legible characters and write [illegible] for the rest. Never invent text.
- A page with no text returns an empty lines array.

Example for a page beginning with a running head, a chapter line, a title, a sidenote beside the first body line, and a page number:
{"lines": [
 {"role": "running-head", "text": "SIXTY-FOURTH CONGRESS. Sess. II. Ch. 162. 1917.", "starts_paragraph": true},
 {"role": "page-number", "text": "1058", "starts_paragraph": true},
 {"role": "body", "text": "CHAP. 162.-An Act Making appropriations for the service of the Post Office", "starts_paragraph": true},
 {"role": "sidenote", "text": "March 3, 1917.", "starts_paragraph": true},
 {"role": "sidenote", "text": "[H. R. 19410.]", "starts_paragraph": true},
 {"role": "body", "text": "Department for the fiscal year ending June thirtieth, nineteen hundred and eighteen,", "starts_paragraph": false},
 {"role": "body", "text": "and for other purposes.", "starts_paragraph": false},
 {"role": "body", "text": "Be it enacted by the Senate and House of Representatives of the United States of", "starts_paragraph": true},
 {"role": "body", "text": "America in Congress assembled, That the following sums be, and they are hereby,", "starts_paragraph": false},
 {"role": "sidenote", "text": "Postal Service", "starts_paragraph": true},
 {"role": "sidenote", "text": "appropriations.", "starts_paragraph": false}
]}"""


class CreditError(RuntimeError):
    """The organization's credit balance is too low (HTTP 400). Not retried."""


# ---------------------------------------------------------------------------- cost


def cost_for(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0,
             batch: bool = False) -> float:
    """USD for one response. `input_tokens` is the uncached input as the API reports it (cache reads and
    writes are separate counters); batch requests are billed at half price."""
    price_in, price_out = PRICE_PER_MTOK.get(model, PRICE_PER_MTOK[DEFAULT_MODEL])
    usd = (input_tokens * price_in + cache_read * price_in * CACHE_READ_MULTIPLIER
           + cache_write * price_in * CACHE_WRITE_MULTIPLIER + output_tokens * price_out) / 1_000_000
    return usd * BATCH_MULTIPLIER if batch else usd


def estimate_image_tokens(width_px: int, height_px: int) -> int:
    return math.ceil(width_px * height_px / PIXELS_PER_TOKEN)


# ---------------------------------------------------------------------------- pages and images


@dataclass
class PageImage:
    page_no: int
    width_pt: float
    height_pt: float
    width_px: int
    height_px: int
    jpeg: bytes

    @property
    def image_tokens(self) -> int:
        return estimate_image_tokens(self.width_px, self.height_px)

    @property
    def b64(self) -> str:
        return base64.standard_b64encode(self.jpeg).decode("ascii")


def page_sizes(pdf_path: Path | str) -> list[tuple[float, float]]:
    """(width, height) in points for every page."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        return [tuple(float(v) for v in pdf[i].get_size()) for i in range(len(pdf))]
    finally:
        pdf.close()


def render_page(pdf_path: Path | str, page_no: int, long_side: int = TARGET_LONG_SIDE, quality: int = JPEG_QUALITY) -> PageImage:
    """Render one 1-based page so that its longest side is `long_side` pixels; JPEG bytes."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page = pdf[page_no - 1]
        width_pt, height_pt = (float(v) for v in page.get_size())
        scale = long_side / max(width_pt, height_pt)
        image = page.render(scale=scale).to_pil().convert("RGB")
    finally:
        pdf.close()
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    return PageImage(page_no, width_pt, height_pt, image.width, image.height, buf.getvalue())


def parse_pages(spec: Optional[str]) -> Optional[list[int]]:
    if not spec:
        return None
    a, _, b = spec.partition("-")
    return list(range(int(a), int(b or a) + 1))


# ---------------------------------------------------------------------------- requests


def build_params(model: str, image: PageImage, label: str, page_index: int, page_count: int,
                 effort: str = DEFAULT_EFFORT, max_tokens: int = DEFAULT_MAX_TOKENS) -> dict:
    """Messages API parameters for one page (without the fallback beta, which the Batches API rejects)."""
    text = (f"{label}: page {page_index} of {page_count} ({image.width_px} x {image.height_px} px). "
            "Transcribe every line of this page.")
    params = {
        "model": model,
        "max_tokens": max_tokens,
        "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image.b64}},
                {"type": "text", "text": text},
            ],
        }],
        "output_config": {"format": {"type": "json_schema", "schema": LINE_SCHEMA}},
    }
    if model not in NO_THINKING_MODELS:
        params["thinking"] = {"type": "adaptive"}
    if model not in NO_EFFORT_MODELS:
        params["output_config"]["effort"] = effort
    return params


def parse_lines(text: str) -> list[dict]:
    """The `lines` list of a response, each with role, text, starts_paragraph; unknown roles become body."""
    data = json.loads(text)
    lines = []
    for raw in data.get("lines", []):
        role = raw.get("role", "body")
        if role not in ROLES:
            role = "body"
        lines.append({"role": role, "text": str(raw.get("text", "")), "starts_paragraph": bool(raw.get("starts_paragraph", True))})
    return lines


@dataclass
class PageUsage:
    page: int
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    image_tokens_est: int = 0
    image_px: Optional[list[int]] = None
    cost_usd: float = 0.0
    seconds: float = 0.0
    attempts: int = 1
    stop_reason: Optional[str] = None
    served_by: Optional[str] = None
    request_id: Optional[str] = None
    lines: int = 0


@dataclass
class PageResult:
    page_no: int
    width_pt: float
    height_pt: float
    lines: list[dict]
    usage: PageUsage


@dataclass
class Transcription:
    name: str
    model: str
    pages: list[PageResult]
    effort: str = DEFAULT_EFFORT
    batch: bool = False
    batch_id: Optional[str] = None
    seconds: float = 0.0

    def totals(self) -> dict:
        us = [p.usage for p in self.pages]
        n = len(us) or 1
        cost = sum(u.cost_usd for u in us)
        return {
            "pages": len(us),
            "input_tokens": sum(u.input_tokens for u in us),
            "output_tokens": sum(u.output_tokens for u in us),
            "cache_read_tokens": sum(u.cache_read_tokens for u in us),
            "cache_write_tokens": sum(u.cache_write_tokens for u in us),
            "image_tokens_est": sum(u.image_tokens_est for u in us),
            "cost_usd": round(cost, 6),
            "cost_per_page_usd": round(cost / n, 6),
            "request_seconds": round(sum(u.seconds for u in us), 1),
            "seconds_per_page": round(sum(u.seconds for u in us) / n, 2),
            "wall_seconds": round(self.seconds, 1),
            "lines": sum(u.lines for u in us),
        }

    def usage_dict(self) -> dict:
        return {"name": self.name, "model": self.model, "effort": self.effort, "batch": self.batch, "batch_id": self.batch_id,
                "totals": self.totals(), "pages": [asdict(p.usage) for p in self.pages]}

    def lines_dict(self) -> dict:
        return {"name": self.name, "model": self.model, "pages": [
            {"page": p.page_no, "width_pt": p.width_pt, "height_pt": p.height_pt, "lines": p.lines} for p in self.pages]}


def make_client() -> anthropic.Anthropic:
    """Keys that are not scoped to a workspace must name one per request (as benchmark.judge does)."""
    workspace = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
    headers = {"anthropic-workspace-id": workspace} if workspace else None
    return anthropic.Anthropic(default_headers=headers)


def is_credit_error(exc: Exception) -> bool:
    return isinstance(exc, anthropic.BadRequestError) and "credit balance" in str(exc).lower()


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code == 529 or exc.status_code >= 500 or "overloaded" in str(exc).lower()
    return False


class Transcriber:
    def __init__(self, model: str = DEFAULT_MODEL, client: Optional[anthropic.Anthropic] = None, effort: str = DEFAULT_EFFORT,
                 workers: int = DEFAULT_WORKERS, max_tokens: int = DEFAULT_MAX_TOKENS, long_side: int = TARGET_LONG_SIDE,
                 use_fallbacks: bool = True, poll_seconds: float = BATCH_POLL_SECONDS, sleep=time.sleep):
        if model not in PRICE_PER_MTOK:
            raise ValueError(f"unknown model {model!r}; known: {', '.join(MODELS)}")
        self.model = model
        self.client = client or make_client()
        self.effort = effort
        self.workers = max(1, workers)
        self.max_tokens = max_tokens
        self.long_side = long_side
        self.use_fallbacks = use_fallbacks
        self.poll_seconds = poll_seconds
        self.sleep = sleep
        self._stop = threading.Event()

    # ------------------------------------------------------------------ one page, streaming

    def _stream_once(self, params: dict):
        kwargs = dict(params)
        if self.use_fallbacks:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        with self.client.beta.messages.stream(**kwargs) as stream:
            return stream.get_final_message()

    def call(self, params: dict, label: str = "") -> tuple[list[dict], PageUsage]:
        """One request with retries on 429, 529, 5xx, and connection errors; no retry on credit errors."""
        usage = PageUsage(page=0)
        started = time.monotonic()
        last: Optional[Exception] = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if self._stop.is_set():
                raise CreditError("stopped after a credit error")
            usage.attempts = attempt
            try:
                message = self._stream_once(params)
                break
            except anthropic.BadRequestError as exc:
                if is_credit_error(exc):
                    self._stop.set()
                    raise CreditError(str(exc)) from exc
                if self.use_fallbacks and "fallback" in str(exc).lower():
                    logger.warning("%s: the API rejected `fallbacks` for %s; retrying without it", label, self.model)
                    self.use_fallbacks = False
                    continue
                raise
            except Exception as exc:
                if not is_retryable(exc) or attempt == MAX_ATTEMPTS:
                    raise
                last = exc
                delay = min(60.0, 2.0 ** attempt + random.uniform(0, 1))
                headers = getattr(getattr(exc, "response", None), "headers", None)
                retry_after = headers.get("retry-after") if headers is not None else None
                if retry_after and str(retry_after).isdigit():
                    delay = max(delay, float(retry_after))
                logger.warning("%s: %s (attempt %d/%d); retrying in %.0fs", label, type(exc).__name__, attempt, MAX_ATTEMPTS, delay)
                self.sleep(delay)
        else:  # pragma: no cover - the loop raises before exhausting
            raise last or RuntimeError("no attempts")
        usage.seconds = time.monotonic() - started
        lines = self._read_message(message, usage, label)
        return lines, usage

    def _read_message(self, message, usage: PageUsage, label: str, batch: bool = False) -> list[dict]:
        served_by = getattr(message, "model", None)
        usage.served_by = served_by
        usage.stop_reason = getattr(message, "stop_reason", None)
        usage.request_id = getattr(message, "_request_id", None)
        u = message.usage
        usage.input_tokens = int(getattr(u, "input_tokens", 0) or 0)
        usage.output_tokens = int(getattr(u, "output_tokens", 0) or 0)
        usage.cache_read_tokens = int(getattr(u, "cache_read_input_tokens", 0) or 0)
        usage.cache_write_tokens = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
        usage.cost_usd = cost_for(served_by if served_by in PRICE_PER_MTOK else self.model, usage.input_tokens, usage.output_tokens,
                                  usage.cache_read_tokens, usage.cache_write_tokens, batch=batch)
        if usage.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            raise RuntimeError(f"{label}: refused ({getattr(details, 'category', None)}: {getattr(details, 'explanation', '')})")
        text = next((b.text for b in message.content if getattr(b, "type", None) == "text"), "")
        if usage.stop_reason == "max_tokens":
            raise RuntimeError(f"{label}: output cut at max_tokens ({usage.output_tokens} tokens)")
        try:
            lines = parse_lines(text)
        except (ValueError, AttributeError) as exc:
            raise RuntimeError(f"{label}: response is not the line schema: {exc}") from exc
        usage.lines = len(lines)
        logger.info("%s: %d lines, %d in (%d cached, %d written) / %d out tokens, $%.4f, %.1fs%s%s", label, len(lines),
                    usage.input_tokens, usage.cache_read_tokens, usage.cache_write_tokens, usage.output_tokens, usage.cost_usd,
                    usage.seconds, " (batch)" if batch else "",
                    f" (served by {served_by})" if served_by and served_by != self.model else "")
        return lines

    # ------------------------------------------------------------------ a document

    def transcribe(self, pdf_path: Path | str, name: Optional[str] = None, pages: Optional[Iterable[int]] = None,
                   batch: bool = False) -> Transcription:
        pdf_path = Path(pdf_path)
        name = name or pdf_path.stem
        sizes = page_sizes(pdf_path)
        wanted = list(pages) if pages else list(range(1, len(sizes) + 1))
        for no in wanted:
            if no < 1 or no > len(sizes):
                raise ValueError(f"page {no} outside 1-{len(sizes)} of {pdf_path}")
        started = time.monotonic()
        images = {no: render_page(pdf_path, no, self.long_side) for no in wanted}
        requests = {no: build_params(self.model, images[no], name, i + 1, len(wanted), self.effort, self.max_tokens)
                    for i, no in enumerate(wanted)}
        result = Transcription(name=name, model=self.model, pages=[], effort=self.effort, batch=batch)
        if batch:
            outcomes, result.batch_id = self._run_batch(name, requests)
        else:
            outcomes = self._run_streaming(name, requests)
        for no in wanted:
            lines, usage = outcomes[no]
            usage.page = no
            usage.image_tokens_est = images[no].image_tokens
            usage.image_px = [images[no].width_px, images[no].height_px]
            result.pages.append(PageResult(no, images[no].width_pt, images[no].height_pt, lines, usage))
        result.seconds = time.monotonic() - started
        t = result.totals()
        logger.info("%s [%s]: %d page(s), %d in / %d out tokens, $%.4f ($%.4f/page), %.1fs/page, %.0fs wall", name, self.model,
                    t["pages"], t["input_tokens"] + t["cache_read_tokens"] + t["cache_write_tokens"], t["output_tokens"],
                    t["cost_usd"], t["cost_per_page_usd"], t["seconds_per_page"], t["wall_seconds"])
        return result

    def _run_streaming(self, name: str, requests: dict[int, dict]) -> dict[int, tuple[list[dict], PageUsage]]:
        outcomes: dict[int, tuple[list[dict], PageUsage]] = {}
        errors: dict[int, Exception] = {}
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self.call, params, f"{name} p{no}"): no for no, params in requests.items()}
            for fut in as_completed(futures):
                no = futures[fut]
                try:
                    outcomes[no] = fut.result()
                except CreditError:
                    for f in futures:
                        f.cancel()
                    raise
                except Exception as exc:
                    errors[no] = exc
        if errors:
            first = min(errors)
            raise RuntimeError(f"{name}: {len(errors)} page(s) failed; p{first}: {errors[first]}") from errors[first]
        return outcomes

    def _run_batch(self, name: str, requests: dict[int, dict]) -> tuple[dict[int, tuple[list[dict], PageUsage]], str]:
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request

        safe = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:40]
        custom_ids = {f"{safe}_p{no}": no for no in requests}
        batch_requests = [Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**requests[no])) for cid, no in custom_ids.items()]
        started = time.monotonic()
        try:
            created = self.client.messages.batches.create(requests=batch_requests)
        except anthropic.BadRequestError as exc:
            if is_credit_error(exc):
                raise CreditError(str(exc)) from exc
            raise
        logger.info("%s: batch %s with %d request(s) submitted", name, created.id, len(batch_requests))
        while True:
            status = self.client.messages.batches.retrieve(created.id)
            if status.processing_status == "ended":
                break
            counts = getattr(status, "request_counts", None)
            logger.info("%s: batch %s %s (%s processing) after %.0fs", name, created.id, status.processing_status,
                        getattr(counts, "processing", "?"), time.monotonic() - started)
            self.sleep(self.poll_seconds)
        elapsed = time.monotonic() - started
        outcomes: dict[int, tuple[list[dict], PageUsage]] = {}
        errors: dict[int, str] = {}
        for item in self.client.messages.batches.results(created.id):
            no = custom_ids.get(item.custom_id)
            if no is None:
                continue
            kind = item.result.type
            if kind != "succeeded":
                err = getattr(item.result, "error", None)
                errors[no] = f"{kind}: {getattr(err, 'message', None) or getattr(err, 'type', None) or ''}"
                continue
            usage = PageUsage(page=no, seconds=elapsed / max(1, len(requests)))
            try:
                lines = self._read_message(item.result.message, usage, f"{name} p{no}", batch=True)
            except RuntimeError as exc:
                errors[no] = str(exc)
                continue
            outcomes[no] = (lines, usage)
        missing = set(requests) - set(outcomes) - set(errors)
        for no in missing:
            errors[no] = "no result in the batch output"
        if errors:
            first = min(errors)
            raise RuntimeError(f"{name}: batch {created.id}: {len(errors)} page(s) failed; p{first}: {errors[first]}")
        return outcomes, created.id


# ---------------------------------------------------------------------------- adapter


BODY_L, BODY_R = 0.12, 0.72  # main column, fractions of the page width
NOTE_L, NOTE_R = 0.75, 0.97  # right margin
BODY_TOP, BODY_BOTTOM = 0.92, 0.14  # fractions of the page height, measured from the bottom
HEAD_TOP, HEAD_BOTTOM = 0.985, 0.945  # running heads and page numbers (classify_items: b > 0.93 H)
FOOT_TOP, FOOT_BOTTOM = 0.125, 0.065  # footnotes (classify_items: t >= 0.06 H so they are not furniture)


def merge_lines(lines: list[dict], merge_paragraphs: bool = True) -> list[dict]:
    """Group consecutive lines of one role into items. With `merge_paragraphs`, lines whose
    `starts_paragraph` is false join the item before them (same role) with a newline. Every line's text
    ends up in exactly one item."""
    items: list[dict] = []
    for line in lines:
        text = line.get("text") or ""
        if not text.strip():
            continue  # a line without characters has nothing to keep
        role = line.get("role", "body")
        if merge_paragraphs and not line.get("starts_paragraph", True):
            # continue the most recent item of the same role: a sidenote between two body lines does not
            # break the body paragraph
            previous = next((it for it in reversed(items) if it["role"] == role), None)
            if previous is not None:
                previous["text"] = previous["text"] + "\n" + text
                previous["lines"] += 1
                continue
        items.append({"role": role, "text": text, "lines": 1})
    return items


def to_docling(name: str, pages: list[PageResult], merge_paragraphs: bool = True):
    """DoclingDocument with one page per PageResult and one text item per line group, positioned by role
    and order so that pipeline.uslm.classify_items separates body, sidenote, header, and footnote."""
    from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem, Size

    doc = DoclingDocument(name=name)
    labels = {"running-head": DocItemLabel.PAGE_HEADER, "page-number": DocItemLabel.PAGE_HEADER,
              "footnote": DocItemLabel.FOOTNOTE, "sidenote": DocItemLabel.TEXT, "body": DocItemLabel.TEXT}
    for page in pages:
        W, H = page.width_pt, page.height_pt
        doc.add_page(page_no=page.page_no, size=Size(width=W, height=H))
        items = merge_lines(page.lines, merge_paragraphs)
        rows = sum(1 for it in items if it["role"] == "body") or 1
        step = (BODY_TOP - BODY_BOTTOM) * H / rows
        line_h = min(step * 0.8, 12.0)
        row = -1
        heads = feet = 0
        for it in items:
            role = it["role"]
            if role == "body":
                row += 1
                t = BODY_TOP * H - row * step
                l, r = BODY_L * W, BODY_R * W
            elif role == "sidenote":
                t = BODY_TOP * H - max(row, 0) * step
                l, r = NOTE_L * W, NOTE_R * W
            elif role in ("running-head", "page-number"):
                t = max(HEAD_BOTTOM * H + 0.01 * H, HEAD_TOP * H - heads * 0.01 * H)
                heads += 1
                l, r = (BODY_L * W, BODY_R * W) if role == "running-head" else (0.80 * W, 0.95 * W)
            else:  # footnote
                t = max(FOOT_BOTTOM * H + 0.01 * H, FOOT_TOP * H - feet * 0.01 * H)
                feet += 1
                l, r = BODY_L * W, BODY_R * W
            b = t - min(line_h, 0.009 * H) if role != "body" else t - line_h
            b = max(b, 0.0)
            text = it["text"]
            doc.add_text(label=labels.get(role, DocItemLabel.TEXT), text=text,
                         prov=ProvenanceItem(page_no=page.page_no, bbox=BoundingBox(l=l, t=t, r=r, b=b, coord_origin=CoordOrigin.BOTTOMLEFT),
                                             charspan=(0, len(text))))
    return doc


def line_chars(pages: list[PageResult]) -> int:
    return sum(len(re.sub(r"\s+", " ", ln.get("text", "") or "").strip()) for p in pages for ln in p.lines)


# ---------------------------------------------------------------------------- outputs


def profile_dir(model: str) -> Path:
    return DATA_DIR / "doclang" / f"{FAMILY}-{model}"


def output_stem(name: str, pages: Optional[Iterable[int]] = None) -> str:
    pages = list(pages) if pages else None
    return f"{name}_p{pages[0]}-{pages[-1]}" if pages else name


def write_outputs(result: Transcription, doc, out_dir: Path, stem: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stem}.json"
    path.write_text(json.dumps(doc.export_to_dict(), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (out_dir / f"{stem}.lines.json").write_text(json.dumps(result.lines_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
    (out_dir / f"{stem}.usage.json").write_text(json.dumps(result.usage_dict(), indent=1), encoding="utf-8")
    return path


def transcribe_to_docling(pdf_path: Path | str, model: str = DEFAULT_MODEL, name: Optional[str] = None,
                          pages: Optional[Iterable[int]] = None, batch: bool = False, effort: str = DEFAULT_EFFORT,
                          workers: int = DEFAULT_WORKERS, merge_paragraphs: bool = True, out_dir: Optional[Path] = None,
                          transcriber: Optional[Transcriber] = None):
    """Transcribe a PDF and write the three outputs; returns (DoclingDocument, Transcription)."""
    pages = list(pages) if pages else None
    name = name or Path(pdf_path).stem
    tr = transcriber or Transcriber(model, effort=effort, workers=workers)
    result = tr.transcribe(pdf_path, name, pages, batch=batch)
    doc = to_docling(name, result.pages, merge_paragraphs)
    write_outputs(result, doc, out_dir or profile_dir(tr.model), output_stem(name, pages))
    return doc, result


# ---------------------------------------------------------------------------- profile family


def converter(pdf_path, variant: Optional[str], page_range, identity=None, dpi=None, **kwargs):
    """pipeline.convert entry point: `claude:{model}` -> DoclingDocument. `dpi` is ignored (the page is
    rendered to `TARGET_LONG_SIDE` pixels); page numbers are relative to `page_range` as in Docling."""
    model = variant or DEFAULT_MODEL
    identity = identity or {}
    name = identity.get("granule_id") or identity.get("package_id") or Path(pdf_path).stem
    pages = list(range(page_range[0], page_range[1] + 1)) if page_range else None
    batch = os.getenv("CLAUDE_OCR_BATCH", "").strip().lower() in ("1", "true", "yes")
    effort = os.getenv("CLAUDE_OCR_EFFORT", DEFAULT_EFFORT)
    doc, _ = transcribe_to_docling(pdf_path, model, name, pages, batch=batch, effort=effort)
    if pages:  # convert.py shifts start_page by the range offset; number pages from 1 to match
        from docling_core.types.doc import DoclingDocument

        data = doc.export_to_dict()
        renumber = {no: i + 1 for i, no in enumerate(pages)}
        data["pages"] = {str(renumber[int(k)]): {**v, "page_no": renumber[int(k)]} for k, v in data["pages"].items()}
        for item in data.get("texts", []):
            for prov in item.get("prov", []):
                prov["page_no"] = renumber[prov["page_no"]]
        doc = DoclingDocument.model_validate(data)
    return doc


register_family(ProfileFamily(FAMILY, "Claude page transcription to structured lines (one request per page image)",
                              converter=converter, variants=MODELS, runs_in_container=True))


# ---------------------------------------------------------------------------- CLI


def granule_jobs(spec_path: str, only: list[str], limit: Optional[int]) -> list[tuple[str, Path]]:
    from downloader.fetch_granules import granule_paths, load_spec

    jobs = []
    for entry in load_spec(spec_path):
        gid = entry["granule_id"]
        if only and gid not in only:
            continue
        pdf, _ = granule_paths(gid, DATA_DIR / "granules")
        if not pdf.exists():
            logger.warning("%s: %s missing (run downloader.fetch_granules or benchmark.evaluate first)", gid, pdf)
            continue
        jobs.append((gid, pdf))
    return jobs[:limit] if limit else jobs


def dry_run(jobs: list[tuple[str, Path]], model: str, long_side: int) -> None:
    """Render the pages, report image sizes and the projected cost without calling the API."""
    price_in, price_out = PRICE_PER_MTOK[model]
    pages = tokens = 0
    for name, pdf in jobs:
        for no in range(1, len(page_sizes(pdf)) + 1):
            img = render_page(pdf, no, long_side)
            pages += 1
            tokens += img.image_tokens
            logger.info("%s p%d: %d x %d px, %d KB, about %d image tokens", name, no, img.width_px, img.height_px, len(img.jpeg) // 1024, img.image_tokens)
    est = ((tokens + 400 * pages) * price_in + 1500 * pages * price_out) / 1_000_000
    logger.info("%d page(s), %d image tokens; projected $%.2f with %s (%d image + 400 prompt tokens in, 1,500 out per page); half with --batch",
                pages, tokens, est, model, tokens // max(pages, 1))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m pipeline.claude_ocr", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", help="YAML sample spec with granule ids (PDFs under data/granules/)")
    p.add_argument("--granule", action="append", default=[], help="only these granule ids of the spec (repeatable)")
    p.add_argument("--pdf", help="a single PDF path")
    p.add_argument("--id", help="output id for --pdf (default: file stem)")
    p.add_argument("--pages", default=None, help="1-based page range, e.g. 1-3")
    p.add_argument("--model", default=DEFAULT_MODEL, choices=MODELS)
    p.add_argument("--effort", default=DEFAULT_EFFORT, choices=["low", "medium", "high"], help="thinking effort (default medium; ignored on Haiku 4.5)")
    p.add_argument("--batch", action="store_true", help="send the requests through the Message Batches API (half price)")
    p.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="requests in flight (default 4)")
    p.add_argument("--limit", type=int, default=None, help="only the first N granules of the spec")
    p.add_argument("--long-side", type=int, default=TARGET_LONG_SIDE, help="pixels on the longest side of the page image")
    p.add_argument("--line-items", action="store_true", help="one DoclingDocument item per line instead of per paragraph")
    p.add_argument("--force", action="store_true", help="transcribe again when the output JSON exists")
    p.add_argument("--dry-run", action="store_true", help="render the pages and project the cost; no API calls")
    p.add_argument("--log-dir", default=str(LOG_DIR))
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging("claude_ocr", args.log_dir)
    jobs: list[tuple[str, Path]] = []
    if args.spec:
        jobs += granule_jobs(args.spec, args.granule, args.limit)
    if args.pdf:
        jobs.append((args.id or Path(args.pdf).stem, Path(args.pdf)))
    if not jobs:
        logger.error("nothing to transcribe (use --spec or --pdf)")
        return 2
    pages = parse_pages(args.pages)
    if args.dry_run:
        dry_run(jobs, args.model, args.long_side)
        return 0
    out_dir = profile_dir(args.model)
    transcriber = Transcriber(args.model, effort=args.effort, workers=args.workers, long_side=args.long_side)
    done = failed = skipped = 0
    total_cost = total_pages = 0.0
    for name, pdf in jobs:
        stem = output_stem(name, pages)
        if (out_dir / f"{stem}.json").exists() and not args.force:
            logger.info("%s: exists, skipped (use --force)", stem)
            skipped += 1
            continue
        try:
            _, result = transcribe_to_docling(pdf, args.model, name, pages, batch=args.batch, merge_paragraphs=not args.line_items,
                                              out_dir=out_dir, transcriber=transcriber)
        except CreditError as exc:
            logger.error("%s: %s; stopping", name, exc)
            failed += 1
            break
        except Exception as exc:
            logger.error("%s: %s", name, exc)
            failed += 1
            continue
        t = result.totals()
        total_cost += t["cost_usd"]
        total_pages += t["pages"]
        done += 1
    logger.info("done: %d transcribed, %d skipped, %d failed; %d page(s), $%.4f ($%.4f/page) with %s", done, skipped, failed,
                int(total_pages), total_cost, total_cost / total_pages if total_pages else 0.0, args.model)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
