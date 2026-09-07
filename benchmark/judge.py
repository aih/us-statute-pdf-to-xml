"""Claude judge for one granule: PDF pages as a document block, the generated USLM, and the text diff
against the GovInfo USLM. Returns structured scores.

Model `claude-opus-5` (override with JUDGE_MODEL), adaptive thinking, streaming, structured output via
`output_config.format`, and server-side refusal fallbacks (`fallbacks="default"`, beta
`server-side-fallback-2026-07-01`). Cost is computed from `usage` at the Opus 5 list price.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
PRICE_PER_MTOK = {  # USD, first-party rates (skill table, cached 2026-06-24)
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
}
MAX_XML_CHARS = 120_000
MAX_PDF_BYTES = 30 * 1024 * 1024

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "text_score": {"type": "integer", "minimum": 0, "maximum": 100,
                       "description": "Fidelity of the body text to the PDF: 100 = no missing, added, or misread words."},
        "structure_score": {"type": "integer", "minimum": 0, "maximum": 100,
                            "description": "Sections, subsections, paragraphs, headings, and page breaks match the printed law."},
        "tagging_score": {"type": "integer", "minimum": 0, "maximum": 100,
                          "description": "USLM element choice and identifier scheme (/us/pl/{congress}/{law}/s{n}/...) are correct."},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["ocr", "missing_text", "extra_text", "structure", "tagging", "identifier", "sidenote", "page", "other"]},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "location": {"type": "string", "description": "Identifier, page, or quoted words that locate the issue."},
                    "description": {"type": "string"},
                },
                "required": ["type", "severity", "location", "description"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["text_score", "structure_score", "tagging_score", "issues", "summary"],
    "additionalProperties": False,
}

SYSTEM = """You evaluate a PDF-to-USLM conversion of a United States statute. You receive the scanned or
born-digital PDF of one law, the USLM XML our pipeline generated from it, and a list of the largest text
differences between our XML and the official GovInfo USLM for the same law (the reference).

Score three things from 0 to 100 and list concrete issues:
- text_score: does the body text in the generated XML match the words printed in the PDF? Penalize OCR
  errors, dropped or duplicated passages, and marginal notes merged into body text. The reference text
  can itself contain OCR errors; the PDF is the ground truth for words.
- structure_score: are sections, subsections, paragraphs, headings, the enacting formula, the approval
  line, and page breaks placed where the printed law has them?
- tagging_score: are USLM elements chosen correctly (section, subsection, paragraph, heading, content,
  sidenote, page, action) and do identifiers follow /us/pl/{congress}/{law}/s{n}/{a}/{1} and
  /us/stat/{volume}/{page}?

Be specific: each issue names where it is (an identifier, a page, or quoted words). Keep the summary to
three sentences."""


@dataclass
class JudgeResult:
    model: str
    scores: dict
    issues: list[dict]
    summary: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    seconds: float
    stop_reason: Optional[str]
    served_by: Optional[str] = None
    request_id: Optional[str] = None
    raw: dict = field(default_factory=dict)

    @property
    def overall(self) -> float:
        return round((self.scores["text_score"] + self.scores["structure_score"] + self.scores["tagging_score"]) / 3, 2)

    def as_dict(self) -> dict:
        return {
            "model": self.model, "served_by": self.served_by, "scores": self.scores, "overall": self.overall,
            "issues": self.issues, "summary": self.summary, "usage": {
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cache_read_input_tokens": self.cache_read_tokens,
            }, "cost_usd": round(self.cost_usd, 4), "seconds": round(self.seconds, 1),
            "stop_reason": self.stop_reason, "request_id": self.request_id,
        }


def cost_for(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0) -> float:
    price_in, price_out = PRICE_PER_MTOK.get(model, PRICE_PER_MTOK[DEFAULT_MODEL])
    return (max(0, input_tokens - cache_read) * price_in + cache_read * price_in * 0.1 + output_tokens * price_out) / 1_000_000


def trim_xml(xml_text: str, limit: int = MAX_XML_CHARS) -> str:
    """Drop the meta block and cut very long documents at a tag boundary so the request fits."""
    xml_text = re.sub(r"<meta>.*?</meta>", "<meta><!-- omitted --></meta>", xml_text, count=1, flags=re.S)
    if len(xml_text) <= limit:
        return xml_text
    cut = xml_text.rfind("</", 0, limit)
    return xml_text[: cut if cut > 0 else limit] + "\n<!-- truncated for the judge -->"


def build_messages(pdf_path: Path, generated_xml: str, diffs: list[dict], identity: dict) -> list[dict]:
    pdf_bytes = pdf_path.read_bytes()
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError(f"{pdf_path} is {len(pdf_bytes)} bytes; over the {MAX_PDF_BYTES} byte judge limit")
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    diff_lines = [f"- [{d['op']}] reference: {d['reference']!r}\n  generated: {d['generated']!r}" for d in diffs[:25]]
    context = json.dumps({k: v for k, v in identity.items() if v is not None}, indent=0)
    text = (
        f"Document identity (from GovInfo metadata):\n{context}\n\n"
        f"Generated USLM XML:\n```xml\n{trim_xml(generated_xml)}\n```\n\n"
        "Largest text differences against the GovInfo USLM (reference vs generated), token aligned:\n"
        + ("\n".join(diff_lines) if diff_lines else "(no differences)")
        + "\n\nCompare the generated XML with the PDF and return the scores and issues."
    )
    return [{
        "role": "user",
        "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
             "title": pdf_path.name},
            {"type": "text", "text": text},
        ],
    }]


class Judge:
    def __init__(self, model: Optional[str] = None, client: Optional[anthropic.Anthropic] = None,
                 effort: str = "high", max_tokens: int = 16000):
        self.model = model or os.getenv("JUDGE_MODEL", DEFAULT_MODEL)
        if client is None:
            # Keys that are not scoped to a workspace must name one per request.
            workspace = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
            headers = {"anthropic-workspace-id": workspace} if workspace else None
            client = anthropic.Anthropic(default_headers=headers)
        self.client = client
        self.effort = effort
        self.max_tokens = max_tokens

    def judge(self, pdf_path: Path | str, generated_xml: str, diffs: list[dict], identity: dict) -> JudgeResult:
        started = time.monotonic()
        messages = build_messages(Path(pdf_path), generated_xml, diffs, identity)
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()

        served_by = getattr(message, "model", None)
        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            raise RuntimeError(f"judge refused: {getattr(details, 'category', None)} {getattr(details, 'explanation', '')}")
        text = next((b.text for b in message.content if b.type == "text"), "")
        data = json.loads(text)
        usage = message.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        result = JudgeResult(
            model=self.model,
            served_by=served_by,
            scores={k: int(data[k]) for k in ("text_score", "structure_score", "tagging_score")},
            issues=list(data.get("issues", [])),
            summary=data.get("summary", ""),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=cache_read,
            cost_usd=cost_for(served_by or self.model, usage.input_tokens, usage.output_tokens, cache_read),
            seconds=time.monotonic() - started,
            stop_reason=message.stop_reason,
            request_id=getattr(message, "_request_id", None),
            raw=data,
        )
        logger.info(
            "judge %s: text %d structure %d tagging %d, %d in / %d out tokens, $%.4f, %.0fs%s",
            identity.get("granule_id") or identity.get("package_id"), *result.scores.values(),
            result.input_tokens, result.output_tokens, result.cost_usd, result.seconds,
            f" (served by {served_by})" if served_by and served_by != self.model else "",
        )
        return result
