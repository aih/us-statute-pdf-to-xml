import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import claude_ocr, profiles
from pipeline.claude_ocr import PageImage, PageResult, PageUsage, Transcriber

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------- schema, cost, params


def test_schema_and_models():
    item = claude_ocr.LINE_SCHEMA["properties"]["lines"]["items"]
    assert item["required"] == ["role", "text", "starts_paragraph"] and item["additionalProperties"] is False
    assert set(item["properties"]["role"]["enum"]) == {"running-head", "sidenote", "body", "footnote", "page-number"}
    assert claude_ocr.DEFAULT_MODEL == "claude-opus-5" and set(claude_ocr.MODELS) <= set(claude_ocr.PRICE_PER_MTOK)


def test_cost_accounting():
    # 1M uncached input at $5 + 100k output at $25
    assert round(claude_ocr.cost_for("claude-opus-5", 1_000_000, 100_000), 2) == 7.5
    # cache reads at 0.1x, writes at 1.25x, batch at half price
    assert claude_ocr.cost_for("claude-opus-5", 0, 0, cache_read=1_000_000) == pytest.approx(0.5)
    assert claude_ocr.cost_for("claude-opus-5", 0, 0, cache_write=1_000_000) == pytest.approx(6.25)
    assert claude_ocr.cost_for("claude-haiku-4-5", 1_000_000, 1_000_000, batch=True) == pytest.approx(3.0)
    assert claude_ocr.cost_for("claude-sonnet-5", 2000, 1200) == pytest.approx(0.016)
    assert claude_ocr.estimate_image_tokens(1160, 1500) == 2320


def _image(page_no=1):
    return PageImage(page_no, 612.0, 792.0, 1159, 1500, b"\xff\xd8fake")


def test_build_params_per_model():
    p = claude_ocr.build_params("claude-opus-5", _image(), "G", 1, 3, effort="medium")
    assert p["model"] == "claude-opus-5" and p["thinking"] == {"type": "adaptive"}
    assert p["output_config"]["effort"] == "medium" and p["output_config"]["format"]["type"] == "json_schema"
    assert p["system"][0]["cache_control"] == {"type": "ephemeral"} and "Roles" in p["system"][0]["text"]
    content = p["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[0]["source"]["media_type"] == "image/jpeg"
    assert "\n" not in content[0]["source"]["data"] and "page 1 of 3" in content[1]["text"]
    assert "fallbacks" not in p and "betas" not in p  # added at call time; the Batches API rejects them
    h = claude_ocr.build_params("claude-haiku-4-5", _image(), "G", 1, 1)
    assert "thinking" not in h and "effort" not in h["output_config"]


def test_parse_lines_normalizes_roles():
    text = json.dumps({"lines": [{"role": "body", "text": "a", "starts_paragraph": True}, {"role": "weird", "text": "b"}]})
    lines = claude_ocr.parse_lines(text)
    assert lines[1]["role"] == "body" and lines[1]["starts_paragraph"] is True and lines[0]["text"] == "a"
    with pytest.raises(ValueError):
        claude_ocr.parse_lines("not json")


# ---------------------------------------------------------------------------- rendering


def _blank_pdf(path: Path, pages=((612, 792), (538.4, 826.75))) -> Path:
    pdfium = pytest.importorskip("pypdfium2")
    doc = pdfium.PdfDocument.new()
    for w, h in pages:
        doc.new_page(w, h)
    doc.save(str(path))
    return path


def test_render_page_targets_long_side(tmp_path):
    pdf = _blank_pdf(tmp_path / "blank.pdf")
    sizes = claude_ocr.page_sizes(pdf)
    assert sizes[0] == (612.0, 792.0) and sizes[1] == pytest.approx((538.4, 826.75), abs=0.01)
    img = claude_ocr.render_page(pdf, 1, long_side=1500)
    assert img.height_px == 1500 and 1150 <= img.width_px <= 1160 and img.jpeg[:2] == b"\xff\xd8"
    assert 2200 <= img.image_tokens <= 2400 and (img.width_pt, img.height_pt) == (612.0, 792.0)
    small = claude_ocr.render_page(pdf, 2, long_side=600)
    assert max(small.width_px, small.height_px) == 600
    assert claude_ocr.parse_pages("2-3") == [2, 3] and claude_ocr.parse_pages(None) is None


# ---------------------------------------------------------------------------- adapter


LINES = [
    {"role": "running-head", "text": "SIXTY-FOURTH CONGRESS. Sess. II. Ch. 162. 1917.", "starts_paragraph": True},
    {"role": "page-number", "text": "1058", "starts_paragraph": True},
    {"role": "body", "text": "CHAP. 162.-An Act Making appropriations for the service of the Post Office", "starts_paragraph": True},
    {"role": "sidenote", "text": "March 3, 1917.", "starts_paragraph": True},
    {"role": "sidenote", "text": "[H. R. 19410.]", "starts_paragraph": True},
    {"role": "body", "text": "Department for the fiscal year ending June thirtieth, nineteen hundred and eighteen,", "starts_paragraph": False},
    {"role": "body", "text": "and for other purposes.", "starts_paragraph": False},
    {"role": "body", "text": "Be it enacted by the Senate and House of Representatives of the United States of", "starts_paragraph": True},
    {"role": "body", "text": "America in Congress assembled, That the following sums be, and they are hereby,", "starts_paragraph": False},
    {"role": "sidenote", "text": "Postal Service", "starts_paragraph": True},
    {"role": "sidenote", "text": "appropriations.", "starts_paragraph": False},
    {"role": "body", "text": "SEC. 2. That the sum of ten dollars is appropriated.", "starts_paragraph": True},
    {"role": "body", "text": "", "starts_paragraph": False},
    {"role": "footnote", "text": "1 See 39 Stat. 412.", "starts_paragraph": True},
    {"role": "body", "text": "Approved, March 3, 1917.", "starts_paragraph": True},
]


def test_merge_lines_keeps_every_character():
    items = claude_ocr.merge_lines(LINES)
    assert [it["role"] for it in items] == ["running-head", "page-number", "body", "sidenote", "sidenote", "body", "sidenote", "body", "footnote", "body"]
    assert items[2]["text"].count("\n") == 2 and items[2]["lines"] == 3
    assert items[6]["text"] == "Postal Service\nappropriations."
    # every non-empty line is in exactly one item; continuation lines join the most recent item of their role
    assert items[2]["text"].endswith("and for other purposes.") and items[5]["text"].endswith("they are hereby,")
    assert sorted(t for it in items for t in it["text"].split("\n")) == sorted(ln["text"] for ln in LINES if ln["text"])
    per_line = claude_ocr.merge_lines(LINES, merge_paragraphs=False)
    assert len(per_line) == len([ln for ln in LINES if ln["text"].strip()])


def test_to_docling_geometry_sorts_like_docling():
    pytest.importorskip("docling_core")
    from pipeline import uslm

    page = PageResult(1, 538.4, 826.75, LINES, PageUsage(page=1))
    doc = claude_ocr.to_docling("STATUTE-39-Pg1058", [page])
    assert len(doc.pages) == 1 and doc.pages[1].size.width == 538.4
    pages = uslm.load_pages(doc)
    kinds = [(it.kind, it.label, it.text.split("\n")[0][:20]) for it in pages[0].items]
    assert ("header", "page_header", "SIXTY-FOURTH CONGRES") in kinds and ("header", "page_header", "1058") in kinds
    assert [k for k, _, t in kinds if t.startswith("March 3, 1917")] == ["sidenote"]
    assert [k for k, _, t in kinds if t.startswith("Postal Service")] == ["sidenote"]
    assert [lab for k, lab, t in kinds if t.startswith("1 See 39")] == ["footnote"]
    body = [t for k, lab, t in kinds if k == "body" and lab == "text"]
    assert body == ["CHAP. 162.-An Act Ma", "Be it enacted by the", "SEC. 2. That the sum", "Approved, March 3, 1"]
    # every character of every line is in the document (newlines join paragraph lines)
    total = sum(len(ln["text"]) for ln in LINES)
    assert uslm.docling_text_chars(doc) >= total - sum(ln["text"].count(" ") for ln in LINES)


def test_to_docling_feeds_the_uslm_builder():
    pytest.importorskip("docling_core")
    from pipeline import uslm

    page = PageResult(1, 538.4, 826.75, LINES, PageUsage(page=1))
    doc = claude_ocr.to_docling("STATUTE-39-Pg1058", [page])
    identity = uslm.DocIdentity(granule_id="STATUTE-39-Pg1058", package_id="STATUTE-39", volume=39, start_page=1058, congress=64, law_number=380)
    tree, stats = uslm.build_uslm_with_stats(doc, identity)
    assert stats["kept_chars"] >= 0.8 * stats["docling_chars"]
    root = tree.getroot()
    ns = "{http://schemas.gpo.gov/xml/uslm}"
    assert root.find(f"{ns}main/{ns}section").get("identifier") == "/us/pl/64/380/s2"
    assert root.findtext(f"{ns}main/{ns}enactingFormula").startswith("Be it enacted")
    assert root.find(f"{ns}main/{ns}action/{ns}date").get("date") == "1917-03-03"
    assert "[H. R. 19410.]" in [p.text for p in root.iter(f"{ns}p")]
    assert uslm.validate(tree)[0]


# ---------------------------------------------------------------------------- fake client


def _message(lines, input_tokens=2500, output_tokens=900, cache_read=0, cache_write=0, stop="end_turn", model="claude-opus-5"):
    return SimpleNamespace(
        stop_reason=stop, model=model, _request_id="req_x",
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps({"lines": lines}))],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens, cache_read_input_tokens=cache_read,
                              cache_creation_input_tokens=cache_write),
    )


class FakeStream:
    def __init__(self, outcome):
        self.outcome = outcome

    def __enter__(self):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.outcome


class FakeBeta:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return FakeStream(self.outcomes.pop(0))


def _client(outcomes, batches=None):
    return SimpleNamespace(beta=SimpleNamespace(messages=FakeBeta(outcomes)), messages=SimpleNamespace(batches=batches))


def _api_error(cls, status, message):
    import anthropic

    try:
        import httpx2 as httpx
    except ImportError:  # pragma: no cover
        import httpx
    response = httpx.Response(status, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    return cls(message, response=response, body={"error": {"message": message}})


def test_streaming_call_records_usage_and_fallbacks():
    client = _client([_message(LINES[:3], cache_read=800)])
    tr = Transcriber("claude-opus-5", client=client, workers=2)
    lines, usage = tr.call(claude_ocr.build_params("claude-opus-5", _image(), "G", 1, 1), "G p1")
    assert len(lines) == 3 and usage.input_tokens == 2500 and usage.cache_read_tokens == 800
    assert usage.cost_usd == pytest.approx((2500 * 5 + 800 * 0.5 + 900 * 25) / 1e6) and usage.request_id == "req_x"
    call = client.beta.messages.calls[0]
    assert call["fallbacks"] == "default" and call["betas"] == [claude_ocr.FALLBACK_BETA] and call["thinking"] == {"type": "adaptive"}


def test_retry_on_rate_limit_then_success():
    import anthropic

    client = _client([_api_error(anthropic.RateLimitError, 429, "rate limited"), _message(LINES[:1])])
    sleeps = []
    tr = Transcriber("claude-sonnet-5", client=client, sleep=sleeps.append)
    lines, usage = tr.call(claude_ocr.build_params("claude-sonnet-5", _image(), "G", 1, 1), "G p1")
    assert len(lines) == 1 and usage.attempts == 2 and len(sleeps) == 1 and sleeps[0] >= 2


def test_credit_error_is_not_retried():
    import anthropic

    client = _client([_api_error(anthropic.BadRequestError, 400, "Your credit balance is too low to access the Anthropic API."),
                      _message(LINES[:1])])
    tr = Transcriber("claude-opus-5", client=client, sleep=lambda s: None)
    with pytest.raises(claude_ocr.CreditError):
        tr.call(claude_ocr.build_params("claude-opus-5", _image(), "G", 1, 1), "G p1")
    assert len(client.beta.messages.calls) == 1


def test_fallbacks_rejected_then_retried_without():
    import anthropic

    client = _client([_api_error(anthropic.BadRequestError, 400, "fallbacks is not supported"), _message(LINES[:1])])
    tr = Transcriber("claude-sonnet-5", client=client, sleep=lambda s: None)
    tr.call(claude_ocr.build_params("claude-sonnet-5", _image(), "G", 1, 1), "G p1")
    assert "fallbacks" in client.beta.messages.calls[0] and "fallbacks" not in client.beta.messages.calls[1]
    # Haiku 4.5 rejects the parameter, so it is never sent
    client2 = _client([_message(LINES[:1])])
    Transcriber("claude-haiku-4-5", client=client2).call(claude_ocr.build_params("claude-haiku-4-5", _image(), "G", 1, 1), "G p1")
    assert "fallbacks" not in client2.beta.messages.calls[0]


def test_max_tokens_and_refusal_are_errors():
    tr = Transcriber("claude-opus-5", client=_client([_message(LINES[:1], stop="max_tokens")]))
    with pytest.raises(RuntimeError, match="max_tokens"):
        tr.call(claude_ocr.build_params("claude-opus-5", _image(), "G", 1, 1), "G p1")
    refused = _message([], stop="refusal")
    refused.stop_details = SimpleNamespace(category="other", explanation="no")
    tr = Transcriber("claude-opus-5", client=_client([refused]))
    with pytest.raises(RuntimeError, match="refused"):
        tr.call(claude_ocr.build_params("claude-opus-5", _image(), "G", 1, 1), "G p1")


def test_transcribe_pdf_with_fake_client(tmp_path):
    pdf = _blank_pdf(tmp_path / "doc.pdf")
    client = _client([_message(LINES[:2]), _message(LINES[2:5])])
    tr = Transcriber("claude-opus-5", client=client, workers=2)
    result = tr.transcribe(pdf, "DOC")
    assert [p.page_no for p in result.pages] == [1, 2] and result.pages[1].width_pt == pytest.approx(538.4, abs=0.01)
    totals = result.totals()
    assert totals["pages"] == 2 and totals["lines"] == 5 and totals["cost_usd"] > 0 and totals["seconds_per_page"] >= 0
    assert all(p.usage.image_tokens_est > 1900 for p in result.pages)
    doc, res = claude_ocr.transcribe_to_docling(pdf, "claude-opus-5", "DOC", out_dir=tmp_path / "out", transcriber=Transcriber("claude-opus-5", client=_client([_message(LINES[:2]), _message(LINES[2:5])])))
    assert (tmp_path / "out" / "DOC.json").exists() and (tmp_path / "out" / "DOC.usage.json").exists()
    usage = json.loads((tmp_path / "out" / "DOC.usage.json").read_text())
    assert usage["model"] == "claude-opus-5" and len(usage["pages"]) == 2 and usage["totals"]["input_tokens"] == 5000
    lines = json.loads((tmp_path / "out" / "DOC.lines.json").read_text())
    assert [len(p["lines"]) for p in lines["pages"]] == [2, 3]


class FakeBatches:
    def __init__(self, messages_by_page):
        self.messages = messages_by_page
        self.created = None
        self.polls = 0

    def create(self, requests):
        self.created = list(requests)
        return SimpleNamespace(id="msgbatch_1", processing_status="in_progress")

    def retrieve(self, batch_id):
        self.polls += 1
        status = "ended" if self.polls >= 2 else "in_progress"
        return SimpleNamespace(id=batch_id, processing_status=status, request_counts=SimpleNamespace(processing=1))

    def results(self, batch_id):
        for req in reversed(self.created):  # results arrive in any order
            no = int(req["custom_id"].rsplit("_p", 1)[1])
            yield SimpleNamespace(custom_id=req["custom_id"], result=SimpleNamespace(type="succeeded", message=self.messages[no]))


def test_batch_requests_and_half_price(tmp_path):
    pdf = _blank_pdf(tmp_path / "doc.pdf")
    batches = FakeBatches({1: _message(LINES[:2], model="claude-sonnet-5"), 2: _message(LINES[2:4], model="claude-sonnet-5")})
    client = _client([], batches=batches)
    sleeps = []
    tr = Transcriber("claude-sonnet-5", client=client, sleep=sleeps.append, poll_seconds=1)
    result = tr.transcribe(pdf, "STATUTE-10-Pg764", batch=True)
    assert result.batch and result.batch_id == "msgbatch_1" and len(sleeps) == 1
    ids = [r["custom_id"] for r in batches.created]
    assert ids == ["STATUTE-10-Pg764_p1", "STATUTE-10-Pg764_p2"]
    params = batches.created[0]["params"]
    assert "fallbacks" not in params and "betas" not in params and params["output_config"]["format"]["type"] == "json_schema"
    assert params["thinking"] == {"type": "adaptive"} and params["system"][0]["cache_control"]["type"] == "ephemeral"
    assert [p.page_no for p in result.pages] == [1, 2] and [len(p.lines) for p in result.pages] == [2, 2]
    full = claude_ocr.cost_for("claude-sonnet-5", 2500, 900)
    assert result.pages[0].usage.cost_usd == pytest.approx(full / 2)


def test_family_registered():
    fam = profiles.families()["claude"]
    assert fam.converter is claude_ocr.converter and not fam.is_docling and fam.variants == claude_ocr.MODELS
    assert "claude:claude-sonnet-5" in profiles.known_profiles()
    assert profiles.parse_profile("claude:claude-sonnet-5") == ("claude", "claude-sonnet-5")
    assert claude_ocr.output_stem("G", [2, 3]) == "G_p2-3" and claude_ocr.output_stem("G") == "G"


# ---------------------------------------------------------------------------- integration


@pytest.mark.integration
def test_live_one_page_transcription():
    """One Haiku request on the first page of a downloaded granule. Needs ANTHROPIC_API_KEY, the granule PDF,
    and credit on the account."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    pdf = claude_ocr.DATA_DIR / "granules" / "STATUTE-10" / "STATUTE-10-Pg764.pdf"
    if not pdf.exists():
        pytest.skip(f"{pdf} not downloaded")
    tr = Transcriber("claude-haiku-4-5", workers=1)
    try:
        result = tr.transcribe(pdf, "STATUTE-10-Pg764", pages=[1])
    except claude_ocr.CreditError as exc:
        pytest.skip(f"no API credit: {exc}")
    page = result.pages[0]
    assert page.usage.input_tokens > 1500 and page.lines and any(ln["role"] == "body" for ln in page.lines)
    assert any("Gibson" in ln["text"] for ln in page.lines)
