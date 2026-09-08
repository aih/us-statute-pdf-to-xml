import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from lxml import etree

from benchmark import gold

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------- sampling


def fake_listing(volume: int, laws: int, private: int = 3) -> list[dict]:
    out = []
    page = 1
    for i in range(laws):
        out.append({"granuleId": f"STATUTE-{volume}-Pg{page}", "granuleClass": "PUBLICLAW", "title": f"law {i}", "dateIssued": f"1{volume:03d}-01-01"})
        page += 1 + (i % 4)  # 1 to 4 pages each
    for i in range(private):
        out.append({"granuleId": f"STATUTE-{volume}-Pg{page}", "granuleClass": "PRIVATELAW", "title": f"private {i}"})
        page += 2
    out.append({"granuleId": f"STATUTE-{volume}-FrontMatter-1-Pgiii", "granuleClass": "FRONTMATTER", "title": "front"})
    return out


@pytest.fixture
def listings():
    out = {v: fake_listing(v, laws=12) for v in range(1, 117)}
    out[7] = fake_listing(7, laws=0)  # treaties only
    out[8] = fake_listing(8, laws=0)
    return out


def test_periods_cover_the_scanned_volumes():
    assert [gold.period_for_volume(v) for v in (1, 9, 10, 31, 32, 64, 65, 89, 90, 116)] == [
        "1789-1850", "1789-1850", "1851-1900", "1851-1900", "1901-1950", "1901-1950", "1951-1975", "1951-1975", "1976-2002", "1976-2002"]
    assert gold.period_for_volume(117) is None
    assert gold.boundary_volumes() == [1, 9, 10, 31, 32, 64, 65, 89, 90, 116]


def test_plan_sample_is_seeded_and_stratified(listings):
    rows = gold.plan_sample(listings, seed=7, pages_per_period=30)
    assert rows == gold.plan_sample(listings, seed=7, pages_per_period=30)
    assert rows != gold.plan_sample(listings, seed=8, pages_per_period=30)
    per_period = {}
    per_granule = {}
    volumes = {}
    for r in rows:
        per_period[r["period"]] = per_period.get(r["period"], 0) + 1
        per_granule[r["granule_id"]] = per_granule.get(r["granule_id"], 0) + 1
        volumes.setdefault(r["period"], set()).add(r["volume"])
        assert r["granule_class"] == "PUBLICLAW"
        assert 1 <= r["pdf_page"] <= r["pdf_pages"]
        assert gold.period_for_volume(r["volume"]) == r["period"]
    assert per_period == {p["name"]: 30 for p in gold.PERIODS}
    assert max(per_granule.values()) <= gold.PAGES_PER_GRANULE
    assert all(len(vs) == gold.VOLUMES_PER_PERIOD for vs in volumes.values())
    assert not volumes["1789-1850"] & {7, 8}  # volumes without public laws are replaced
    assert len(rows) == 150
    assert len({(r["granule_id"], r["pdf_page"]) for r in rows}) == 150


def test_plan_sample_uses_real_page_counts_and_skips_failures(listings):
    def page_count(g):
        if g["granule_id"].endswith("Pg1"):
            raise RuntimeError("download failed")
        return 5

    rows = gold.plan_sample(listings, seed=7, pages_per_period=4, page_count=page_count, periods=["1901-1950"])
    assert {r["period"] for r in rows} == {"1901-1950"} and len(rows) == 4
    assert all(r["pdf_pages"] == 5 and not r["granule_id"].endswith("Pg1") for r in rows)
    # the pages of a granule depend on the seed and the id only
    for r in rows:
        assert r["pdf_page"] in gold.select_pages(r["granule_id"], 5, 7)


def test_select_pages_and_stat_page_label():
    assert gold.select_pages("STATUTE-1-Pg3", 1, 1) == [1]
    assert gold.select_pages("STATUTE-1-Pg3", 0, 1) == []
    pages = gold.select_pages("STATUTE-1-Pg3", 9, 1)
    assert len(pages) == 2 and pages == sorted(pages) and pages == gold.select_pages("STATUTE-1-Pg3", 9, 1)
    assert gold.stat_page_label("1751", 3) == "1753"
    assert gold.stat_page_label("A13", 2) == "A14"
    assert gold.stat_page_label(None, 2) is None


def test_granule_pool_filters_class_and_length():
    listing = fake_listing(64, laws=3) + [{"granuleId": "STATUTE-64-Pg500", "granuleClass": "PUBLICLAW", "title": "long"},
                                          {"granuleId": "STATUTE-64-Pg900", "granuleClass": "PUBLICLAW", "title": "last"}]
    pool = gold.granule_pool(64, listing)
    ids = [g["granule_id"] for g in pool]
    assert "STATUTE-64-Pg500" not in ids  # 400 pages estimated
    assert "STATUTE-64-Pg900" in ids  # last granule: 1 page
    assert all(g["granule_class"] == "PUBLICLAW" and g["period"] == "1901-1950" and g["era"] == "scanned-pre-1951" for g in pool)


# ---------------------------------------------------------------------------- adjudication


A = [{"role": "running-head", "text": "72 STAT.] PUBLIC LAW 85-910-SEPT. 2, 1958"},
     {"role": "body", "text": "Be it enacted by the Senate and House of Representatives"},
     {"role": "sidenote", "text": "Grand Portage National Monument, Minn."},
     {"role": "body", "text": "That, for the purpose of preserving an area con-"},
     {"role": "body", "text": "taining unique historical values, there is hereby"}]
B = [{"role": "running-head", "text": "72 STAT.] PUBLIC LAW 85-910-SEPT. 2, 1958"},
     {"role": "body", "text": "Be it enacted by the Senate and House of Representatives"},
     {"role": "sidenote", "text": "Grant Portage National Monument, Minn."},
     {"role": "body", "text": "That, for the purpose of preserving an area con-"},
     {"role": "body", "text": "taining unique historical values, there is hereby"}]


def test_count_disagreements_and_agreed_lines():
    assert gold.count_disagreements(A, A) == 0
    assert gold.count_disagreements(A, B) == 1
    assert [l["text"] for l in gold.agreed_lines(A, B)] == [A[0]["text"], A[1]["text"], A[3]["text"], A[4]["text"]]
    assert gold.count_disagreements(A, A[:-1] + [{"role": "footnote", "text": A[-1]["text"]}]) == 1  # role counts


def test_differing_runs_and_apply_resolutions():
    runs = gold.differing_runs(A, B)
    assert len(runs) == 1 and runs[0]["run"] == 1 and runs[0]["a"] == [A[2]] and runs[0]["b"] == [B[2]]
    assert "A3 [sidenote] Grand Portage" in gold.runs_text(runs) and "B3 [sidenote] Grant Portage" in gold.runs_text(runs)
    fixed = {"role": "sidenote", "text": "Grand Portage National Monument, Minnesota."}
    lines, dis, unresolved = gold.apply_resolutions(A, runs, [{"run": 1, "lines": [fixed], "reason": "image"}])
    assert lines == A[:2] + [fixed] + A[3:] and unresolved == 0
    assert dis == [{"run": 1, "a": A[2]["text"], "b": B[2]["text"], "kept": fixed["text"], "reason": "image"}]
    # an unanswered run keeps A; an empty resolution drops the line; an extra B line is an insert run
    lines, dis, unresolved = gold.apply_resolutions(A, runs, [])
    assert lines == A and unresolved == 1 and dis[0]["reason"].startswith("unresolved")
    lines, _, _ = gold.apply_resolutions(A, runs, [{"run": 1, "lines": [], "reason": "not printed"}])
    assert lines == A[:2] + A[3:]
    extra = {"role": "footnote", "text": "1 Repealed."}
    runs2 = gold.differing_runs(A, A + [extra])
    assert runs2[0]["op"] == "insert" and runs2[0]["a"] == [] and runs2[0]["b"] == [extra]
    lines, _, _ = gold.apply_resolutions(A, runs2, [{"run": 1, "lines": [extra], "reason": "printed"}])
    assert lines == A + [extra]


# ---------------------------------------------------------------------------- Claude calls with a fake client


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
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads.pop(0)
        message = SimpleNamespace(
            stop_reason="end_turn", model="claude-opus-5",
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps(payload))],
            usage=SimpleNamespace(input_tokens=5000, output_tokens=800, cache_read_input_tokens=400, cache_creation_input_tokens=0),
            _request_id=f"req_{len(self.calls)}",
        )
        return FakeStream(message)


def fake_client(payloads):
    fake = FakeBetaMessages(payloads)
    return SimpleNamespace(beta=SimpleNamespace(messages=fake)), fake


@pytest.fixture
def page_png(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    png = tmp_path / "p1.png"
    Image.new("RGB", (200, 300), "white").save(png)
    return png


PAGE = {"granule_id": "STATUTE-72-Pg1751", "package_id": "STATUTE-72", "volume": 72, "period": "1951-1975", "pdf_page": 1,
        "pdf_pages": 3, "stat_page": "1751", "title": "An Act", "granule_class": "PUBLICLAW"}


def test_build_record_adjudicates_when_transcriptions_differ(page_png):
    fixed = {"role": "sidenote", "text": "Grand Portage National Monument, Minn."}
    client, fake = fake_client([{"lines": A}, {"lines": B},
                                {"resolutions": [{"run": 1, "lines": [fixed], "reason": "image reads Grand"}]}])
    t = gold.Transcriber(client=client, model="claude-opus-5")
    rec = gold.build_record(PAGE, page_png, t)
    assert len(fake.calls) == 3
    assert rec["disagreement_count"] == 1 and rec["adjudication"]["unresolved"] == 0
    assert rec["lines"] == A[:2] + [fixed] + A[3:]
    assert rec["transcriptions"]["A"]["lines"] == A and rec["transcriptions"]["B"]["lines"] == B
    assert rec["adjudication"]["disagreements"][0]["kept"] == fixed["text"] and rec["adjudication"]["disagreements"][0]["b"] == B[2]["text"]
    assert rec["tokens"] == {"input_tokens": 15000, "output_tokens": 2400, "cache_read_input_tokens": 1200, "cache_creation_input_tokens": 0}
    assert rec["cost_usd"] == pytest.approx(3 * (5000 * 5 + 400 * 0.5 + 800 * 25) / 1e6, rel=1e-3)
    assert rec["image_sha256"] == gold.sha256_file(page_png) and rec["dpi"] == 300 and rec["api_images"] == 3
    assert rec["models"] == ["claude-opus-5"] and rec["stat_page"] == "1751"
    # the two transcriptions use different prompts; every call carries the image, adaptive thinking, and the schema
    systems = [c["system"][0]["text"] for c in fake.calls]
    assert systems[0] != systems[1] and systems[2] == gold.SYSTEM_ADJ
    for c in fake.calls:
        assert c["thinking"] == {"type": "adaptive"} and c["fallbacks"] == "default" and c["betas"] == [gold.FALLBACK_BETA]
        assert c["output_config"]["format"]["type"] == "json_schema"
    assert [sum(1 for b in c["messages"][0]["content"] if b["type"] == "image") for c in fake.calls] == [2, 2, 3]
    assert fake.calls[0]["output_config"]["effort"] == "medium" and fake.calls[2]["output_config"]["effort"] == "high"
    adj_text = fake.calls[2]["messages"][0]["content"][-1]["text"]
    assert "Transcription A:" in adj_text and "Run 1 (after A line 2, B line 2):" in adj_text


def test_build_record_skips_adjudication_when_transcriptions_agree(page_png):
    client, fake = fake_client([{"lines": A}, {"lines": A}])
    rec = gold.build_record(PAGE, page_png, gold.Transcriber(client=client))
    assert len(fake.calls) == 2 and rec["disagreement_count"] == 0
    assert rec["lines"] == A and rec["adjudication"]["skipped"]


def test_record_roundtrip_and_review(tmp_path, page_png):
    client, _ = fake_client([{"lines": A}, {"lines": A}])
    rec = gold.build_record(PAGE, page_png, gold.Transcriber(client=client))
    out = gold.gold_path("STATUTE-72-Pg1751", 1, tmp_path)
    gold.write_record(rec, out)
    records = gold.load_gold(tmp_path)
    assert len(records) == 1 and records[0]["lines"] == A and gold.load_gold(tmp_path, period="1789-1850") == []
    assert gold.gold_text(records[0]) == gold.metrics.normalize("\n".join(l["text"] for l in A if l["role"] == "body"))
    assert gold.gold_text(records[0], ("sidenote",)) == "Grand Portage National Monument, Minn."
    review = gold.choose_review(records, seed=1, n=20)
    assert review == records
    md = gold.review_markdown(review)
    assert "STATUTE-72-Pg1751 page 1" in md and "[sidenote] Grand Portage" in md


def test_budget_projects_after_min_pages_and_counts_existing():
    b = gold.Budget(10.0, 10, spent=2.0, done=4, min_pages=2)
    b.add(0.5)
    assert not b.stopped and b.projected() == pytest.approx(2.5 + 5 * 0.5)
    b.add(4.0)  # this run's mean 2.25 on 4 remaining pages projects to 15.5
    assert b.stopped and b.run_pages == 2 and b.run_spent == 4.5
    c = gold.Budget(1.0, 100)
    c.add(0.9)  # projection not trusted yet
    assert not c.stopped
    c.add(0.2)  # spent itself passes the limit
    assert c.stopped


def test_choose_review_is_seeded_and_spread_over_periods():
    records = [{"granule_id": f"STATUTE-{v}-Pg{i}", "pdf_page": 1, "period": gold.period_for_volume(v), "volume": v}
               for v in (5, 20, 40, 70, 100) for i in range(10)]
    review = gold.choose_review(records, seed=3)
    assert len(review) == 20 and review == gold.choose_review(records, seed=3)
    counts = {}
    for r in review:
        counts[r["period"]] = counts.get(r["period"], 0) + 1
    assert counts == {p["name"]: 4 for p in gold.PERIODS}


# ---------------------------------------------------------------------------- page texts


def docling_json(tmp_path) -> Path:
    """A two-page DoclingDocument: body lines, a sidenote in the right margin, a running head, a footnote."""
    def text(i, page, l, t, r, b, label="text", txt="x"):
        return {"self_ref": f"#/texts/{i}", "parent": {"$ref": "#/body"}, "children": [], "content_layer": "body", "label": label,
                "prov": [{"page_no": page, "bbox": {"l": l, "t": t, "r": r, "b": b, "coord_origin": "BOTTOMLEFT"}, "charspan": [0, len(txt)]}],
                "orig": txt, "text": txt}
    texts = [
        text(0, 1, 60, 770, 400, 760, label="page_header", txt="72 STAT.] PUBLIC LAW 85-910"),
        text(1, 1, 60, 700, 400, 690, txt="Be it enacted by the Senate and House"),
        text(2, 1, 60, 680, 400, 670, txt="of Representatives of the United States"),
        text(3, 1, 430, 700, 500, 690, txt="Grand Portage National Monument."),
        text(4, 1, 60, 60, 400, 50, label="footnote", txt="1 See 16 U.S.C. 431."),
        text(5, 2, 60, 700, 400, 690, txt="SEC. 2. The Secretary of the Interior"),
    ]
    doc = {"schema_name": "DoclingDocument", "version": "1.7.0", "name": "t", "furniture": {"self_ref": "#/furniture", "children": [], "name": "_root_", "label": "unspecified"},
           "body": {"self_ref": "#/body", "children": [{"$ref": t["self_ref"]} for t in texts], "name": "_root_", "label": "unspecified"},
           "groups": [], "texts": texts, "pictures": [], "tables": [], "key_value_items": [], "form_items": [],
           "pages": {"1": {"size": {"width": 612, "height": 792}, "page_no": 1}, "2": {"size": {"width": 612, "height": 792}, "page_no": 2}}}
    path = tmp_path / "STATUTE-72-Pg1751.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_docling_page_texts_separates_body_sidenote_and_furniture(tmp_path):
    pytest.importorskip("docling_core")
    pages = gold.docling_page_texts(docling_json(tmp_path))
    assert set(pages) == {1, 2}
    # footnote items count as text-column text (no candidate separates footnotes reliably)
    assert pages[1]["body"] == "Be it enacted by the Senate and House of Representatives of the United States 1 See 16 U.S.C. 431."
    assert pages[1]["sidenote"] == "Grand Portage National Monument."
    assert pages[2]["body"] == "SEC. 2. The Secretary of the Interior" and pages[2]["sidenote"] == ""


VOLUME_XML = """<statutesAtLarge xmlns="http://schemas.gpo.gov/xml/uslm" xmlns:dc="http://purl.org/dc/elements/1.1/"><main>
<pLaw><meta><dc:title>Public Law 85-909: earlier</dc:title></meta><main>
<section><content>tail of the earlier law<page identifier="/us/stat/72/1751">72 Stat. 1751</page> continues on the new page.</content></section>
<action>Approved September 2, 1958.</action></main></pLaw>
<pLaw><meta><dc:title>Public Law 85-910: Grand Portage</dc:title></meta><main>
<longTitle><docTitle>AN ACT</docTitle><officialTitle>To provide for Grand Portage.</officialTitle><sidenote><p>September 2, 1958</p></sidenote></longTitle>
<enactingFormula>Be it enacted</enactingFormula><sidenote><p>Grand Portage National Monument.</p></sidenote>
<section><content>That the monument<page identifier="/us/stat/72/1752"/> is established.</content><note>a note</note></section>
</main></pLaw></main></statutesAtLarge>"""

SLICE_XML = """<pLaw xmlns="http://schemas.gpo.gov/xml/uslm" xmlns:dc="http://purl.org/dc/elements/1.1/"><meta><dc:title>Public Law 85-910</dc:title></meta><main>
<longTitle><docTitle>AN ACT</docTitle><officialTitle>To provide for Grand Portage.</officialTitle><sidenote><p>September 2, 1958</p></sidenote></longTitle>
<enactingFormula>Be it enacted</enactingFormula><sidenote><p>Grand Portage National Monument.</p></sidenote>
<section><content>That the monument<page identifier="/us/stat/72/1752"/> is established.</content><note>a note</note></section>
</main></pLaw>"""


def test_uslm_page_texts_from_volume_and_slice():
    pages = gold.uslm_page_texts(etree.fromstring(VOLUME_XML.encode()))
    assert set(pages) == {"1751", "1752"}
    assert pages["1751"]["body"] == "continues on the new page. Approved September 2, 1958. AN ACT To provide for Grand Portage. Be it enacted That the monument"
    assert pages["1751"]["sidenote"] == "September 2, 1958 Grand Portage National Monument."
    assert pages["1752"]["body"] == "is established." and pages["1752"]["sidenote"] == ""
    sliced = gold.uslm_page_texts(etree.fromstring(SLICE_XML.encode()), start_page="1751")
    assert sliced["1751"]["body"] == "AN ACT To provide for Grand Portage. Be it enacted That the monument"
    assert sliced["1752"]["body"] == "is established."
    assert "a note" not in sliced["1752"]["body"] and "Public Law" not in sliced["1751"]["body"]
    assert "1751" not in gold.uslm_page_texts(etree.fromstring(SLICE_XML.encode()))  # dropped without a start page


def test_c0_texts_prefers_volume_then_slice(tmp_path, monkeypatch):
    monkeypatch.setattr(gold, "DATA_DIR", tmp_path)
    monkeypatch.setattr(gold, "VOLUME_XML_DIR", tmp_path / "volumes" / "xmls")
    monkeypatch.delenv("HF_REPO_ID", raising=False)
    slice_dir = tmp_path / "granules" / "STATUTE-72" / "uslm"
    slice_dir.mkdir(parents=True)
    (slice_dir / "STATUTE-72-Pg1751.xml").write_text(SLICE_XML, encoding="utf-8")
    c0 = gold.C0Texts()
    texts, source = c0.for_page(72, "STATUTE-72-Pg1751", "1752")
    assert source == "slice" and texts["body"] == "is established."
    assert c0.for_page(72, "STATUTE-72-Pg1751", "1799") == (None, "no text for the page")
    (tmp_path / "volumes" / "xmls").mkdir(parents=True)
    (tmp_path / "volumes" / "xmls" / "STATUTE-72.xml").write_text(VOLUME_XML, encoding="utf-8")
    c0 = gold.C0Texts()
    texts, source = c0.for_page(72, "STATUTE-72-Pg1751", "1751")
    assert source == "volume" and texts["body"].startswith("continues on the new page.")


# ---------------------------------------------------------------------------- scoring


def make_record(gid, page, period, volume, body_lines, side_lines=()):
    lines = [{"role": "body", "text": t} for t in body_lines] + [{"role": "sidenote", "text": t} for t in side_lines]
    return {"granule_id": gid, "pdf_page": page, "period": period, "volume": volume, "stat_page": str(page), "lines": lines,
            "disagreement_count": 0, "tokens": {"input_tokens": 1, "output_tokens": 1}, "cost_usd": 0.0, "models": ["m"]}


def test_score_candidate_and_summary_per_period(tmp_path):
    records = [
        make_record("STATUTE-5-Pg1", 1, "1789-1850", 5, ["abcd efgh"], ["note"]),
        make_record("STATUTE-5-Pg1", 2, "1789-1850", 5, ["abcd efgh"]),
        make_record("STATUTE-70-Pg1", 1, "1951-1975", 70, ["abcdefghij"]),
    ]
    hyp = {("STATUTE-5-Pg1", 1): {"body": "abcd efgh", "sidenote": "nose"}, ("STATUTE-5-Pg1", 2): {"body": "abcd efgX", "sidenote": ""}}
    scores = gold.score_candidate(records, "X", lambda r: (hyp.get((r["granule_id"], r["pdf_page"])), "doclang" if (r["granule_id"], r["pdf_page"]) in hyp else "no output"))
    assert [s.cer for s in scores[:2]] == [0.0, pytest.approx(1 / 9)] and scores[2].cer is None and scores[2].source == "no output"
    assert scores[0].sidenote_cer == pytest.approx(0.25) and scores[1].sidenote_cer is None
    summ = gold.summarize(scores)
    assert summ["1789-1850"]["scored"] == 2 and summ["1789-1850"]["mean_cer"] == pytest.approx(1 / 18)
    assert summ["1951-1975"] == {"pages": 1, "scored": 0, "mean_cer": None, "median_cer": None, "sidenote_pages": 0, "sidenote_cer": None, "missing": 1}
    assert summ["all"]["pages"] == 3 and summ["all"]["missing"] == 1 and summ["all"]["sidenote_pages"] == 1
    table = gold.summary_table({"X": scores})
    assert "| X | 1789-1850 | 2 | 2 | 0.056 |" in table and "| X | all | 3 | 2 |" in table
    report = gold.write_score_report(records, {"X": scores}, tmp_path / "r.md")
    text = report.read_text(encoding="utf-8")
    assert "## Per period" in text and "STATUTE-70-Pg1 p1 | 1951-1975 | 70 Stat. 1 | 10 | 0 | no output |" in text


# ---------------------------------------------------------------------------- integration


@pytest.mark.integration
def test_transcribe_fixture_page_top():
    """One transcription of the fixture crop with the real API (skipped without a key)."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    png = FIXTURES / "STATUTE-72-Pg1751-p1-top.png"
    t = gold.Transcriber()
    try:
        result = t.transcribe(gold.api_images(png), "A")
    except Exception as exc:  # billing or permission errors are not test failures
        if "credit balance" in str(exc) or "permission" in str(exc).lower():
            pytest.skip(f"API not usable: {str(exc)[:120]}")
        raise
    assert result["lines"] and any("Grand Portage" in l["text"] for l in result["lines"])
    assert result["usage"]["input_tokens"] > 0 and result["cost_usd"] > 0
