import json
from pathlib import Path
from types import SimpleNamespace

from benchmark import judge

FIXTURES = Path(__file__).parent / "fixtures"


def test_schema_and_cost():
    assert judge.JUDGE_SCHEMA["required"] == ["text_score", "structure_score", "tagging_score", "issues", "summary"]
    assert judge.JUDGE_SCHEMA["additionalProperties"] is False
    # 1M input at $5 + 100k output at $25
    assert round(judge.cost_for("claude-opus-5", 1_000_000, 100_000), 2) == 7.5
    assert judge.cost_for("claude-opus-5", 1_000_000, 0, cache_read=1_000_000) == 0.5


def test_trim_xml_drops_meta_and_cuts_at_tag():
    xml = "<pLaw><meta><a>x</a></meta><main>" + "<p>t</p>" * 100 + "</main></pLaw>"
    out = judge.trim_xml(xml, limit=120)
    assert "<meta><!-- omitted --></meta>" in out and out.endswith("<!-- truncated for the judge -->")
    assert judge.trim_xml("<pLaw><main/></pLaw>") == "<pLaw><main/></pLaw>"


def test_build_messages_has_pdf_document_block(tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    msgs = judge.build_messages(pdf, "<pLaw/>", [{"op": "replace", "reference": "a", "generated": "b"}], {"granule_id": "G", "none": None})
    content = msgs[0]["content"]
    assert content[0]["type"] == "document" and content[0]["source"]["media_type"] == "application/pdf"
    assert "\n" not in content[0]["source"]["data"]
    assert "Generated USLM XML" in content[1]["text"] and "[replace]" in content[1]["text"] and '"none"' not in content[1]["text"]


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.message


class FakeBetaMessages:
    def __init__(self, message):
        self.message = message
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return FakeStream(self.message)


def test_judge_parses_structured_output_and_records_usage(tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    payload = {"text_score": 90, "structure_score": 80, "tagging_score": 70, "issues": [
        {"type": "ocr", "severity": "low", "location": "page 1", "description": "Spe. 2 for SEC. 2"}], "summary": "ok"}
    message = SimpleNamespace(
        stop_reason="end_turn", model="claude-opus-5",
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps(payload))],
        usage=SimpleNamespace(input_tokens=12000, output_tokens=400, cache_read_input_tokens=1000), _request_id="req_1",
    )
    fake = FakeBetaMessages(message)
    client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    j = judge.Judge(model="claude-opus-5", client=client)
    result = j.judge(pdf, "<pLaw/>", [], {"granule_id": "G"})
    assert result.scores == {"text_score": 90, "structure_score": 80, "tagging_score": 70}
    assert result.overall == 80.0 and result.issues[0]["type"] == "ocr"
    assert result.request_id == "req_1" and result.cost_usd > 0
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5" and call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["effort"] == "high"
    assert call["messages"][0]["content"][0]["type"] == "document"
    assert result.as_dict()["usage"]["input_tokens"] == 12000
