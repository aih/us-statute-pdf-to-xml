from collections import Counter
from pathlib import Path

import pytest
from lxml import etree

from benchmark import metrics
from pipeline import hybrid, profiles, uslm
from pipeline.uslm import DocIdentity

FIXTURES = Path(__file__).parent / "fixtures"
NS = "{http://schemas.gpo.gov/xml/uslm}"
HEAD = ('<pLaw xmlns="http://schemas.gpo.gov/xml/uslm" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://schemas.gpo.gov/xml/uslm https://www.govinfo.gov/schemas/xml/uslm/uslm-2.0.17.xsd">')


def _gpo(meta_extra="", body=""):
    return etree.fromstring((HEAD + f"""
<meta><dc:title>Chap. 162: Making appropriations.</dc:title><dc:type>Chapter</dc:type><docNumber>162</docNumber>
<citableAs>39 Stat. 1058</citableAs><dc:date>1917-03-03</dc:date>{meta_extra}</meta>
<preface><dc:type>Public Law</dc:type> <docNumber>64-380</docNumber></preface>
<main>
<longTitle><docTitle>AN ACT</docTitle><officialTitle>Making appropriations for the Post Office.</officialTitle>
<sidenote><p class="centered">March 3, 1917.</p></sidenote></longTitle>
<enactingFormula><i>Be it enacted by the Senate and Howe of Representatives,</i></enactingFormula>
<section class="inline"><content class="inline">That the following sums be, <sidenote><p>Postal Service.</p></sidenote>and they are hereby appropriated <page identifier="/us/stat/39/1059">1059</page>for the service of the Post Office Department.</content></section>
<section><num value="2"><inline class="smallCaps">Sec.</inline> 2. </num><heading>contracts.</heading><content>Contracts made in the Department shall be <proviso><i>Provided,</i> That no contract exceeds one year</proviso>.</content>
<subsection><num value="a">(a) </num><content>The first subsection.</content></subsection></section>
<section><num value="3"><inline class="smallCaps">Sec.</inline> 3. </num><content>The third section is short.</content></section>
{body}
<action><actionDescription>Approved, </actionDescription><date date="1917-03-03">March 3, 1917</date>.</action>
</main>
</pLaw>""").encode())


def _cand(main_text_blocks, preface=(), trailing=()):
    pre = "".join(f"<p>{t}</p>" for t in preface)
    app = f'<appendix role="trailingMatter"><content>{"".join(f"<p>{t}</p>" for t in trailing)}</content></appendix>' if trailing else ""
    return etree.fromstring((HEAD + f"""<meta><dc:title>x</dc:title></meta><preface>{pre}</preface><main>{"".join(main_text_blocks)}</main>{app}</pLaw>""").encode())


CAND_BLOCKS = [
    "<longTitle><docTitle>AN ACT</docTitle><officialTitle>Making appropriations for the Post 0ffice.</officialTitle></longTitle>",
    "<enactingFormula>Be it enacted by the Senate and House of Representatives,</enactingFormula>",
    "<p>That the following sums be, and they are hereby appropriated for the service of the Post Office Department.</p>",
    '<section><num value="2">SEC. 2. </num><heading>CONTRACTS.</heading><content><p>Contracts made in the Department shall be Provided, That no contract exceeds one year.</p></content>'
    '<subsection><num value="a">(a) </num><content>The first subsection.</content></subsection></section>',
    '<section><num value="3">SEC. 3. </num><content>The third section is short.</content></section>',
    "<p>Approved, March 3, 1917.</p>",
]
IDENTITY = DocIdentity(granule_id="STATUTE-39-Pg1058", package_id="STATUTE-39", volume=39, start_page=1058, congress=64, law_number=380,
                       date_issued="1917-03-03")


def _text(el):
    return metrics.body_text(el)


def test_runs_and_anchors_skip_kept_elements():
    root = _gpo()
    runs, linears = hybrid.collect_runs(root.find(NS + "main"))
    texts = [" ".join(r.tokens) for r in runs]
    assert texts[0] == "AN ACT" and "Postal Service." not in " ".join(texts) and "1059" not in texts
    assert [r.replaceable for r in runs][:3] == [True, True, True]
    num_runs = [r for r in runs if r.element.tag == NS + "num"]
    assert num_runs and not any(r.replaceable for r in num_runs)
    action = [r for r in runs if r.element.tag == NS + "action"]
    assert len(action) == 1 and action[0].opaque and " ".join(action[0].tokens).startswith("Approved,")
    offsets, total = [], 0
    for r in runs:
        offsets.append(total)
        total += len(r.tokens)
    anchors = hybrid.section_anchors(root.find(NS + "main"), runs, offsets)
    assert [a[0] for a in anchors] == ["2", "3"] and anchors[0][1] < anchors[1][1]


def test_hybrid_replaces_text_keeps_structure_and_validates():
    gpo, cand = _gpo(), _cand(CAND_BLOCKS)
    tree, stats = hybrid.build_hybrid(gpo, cand, IDENTITY, pages=1)
    root = tree.getroot()
    ok, errors = uslm.validate(tree)
    assert ok, errors[:3]
    assert stats["sections_matched"] == 2 and stats["sections_total"] == 3 and stats["pages"] == 1
    # candidate words replaced the GPO words; num, action, sidenotes, and page markers are the GPO's
    assert root.findtext(f"{NS}main/{NS}longTitle/{NS}officialTitle") == "Making appropriations for the Post 0ffice."
    assert root.findtext(f"{NS}main/{NS}enactingFormula").startswith("Be it enacted by the Senate and House")
    first = root.find(f"{NS}main/{NS}section/{NS}content")
    assert first.text.startswith("That the following sums be,") and first.find(NS + "sidenote") is not None
    page = first.find(NS + "page")
    assert page is not None and page.get("identifier") == "/us/stat/39/1059" and page.tail.strip().startswith("for the service")
    assert "Post Office Department." in _text(root) and "Howe" not in _text(root)
    nums = ["".join(n.itertext()).strip() for n in root.iter(NS + "num")]
    assert nums == ["Sec. 2.", "(a)", "Sec. 3."]  # GPO num text kept
    assert root.find(f"{NS}main/{NS}action/{NS}date").get("date") == "1917-03-03"
    assert [p.text for p in root.iterfind(f".//{NS}sidenote/{NS}p")] == ["March 3, 1917.", "Postal Service."]
    # a proviso is a run of its own and keeps its element; the inline <i> inside it is flattened
    sec2 = root.findall(f"{NS}main/{NS}section")[1]
    proviso = sec2.find(f"{NS}content/{NS}proviso")
    assert proviso is not None and proviso.find(NS + "i") is None and proviso.text.startswith("Provided,")
    assert "no contract exceeds one year" in " ".join(sec2.itertext())
    assert sec2.find(f"{NS}content").text.startswith("Contracts made in the Department shall be")
    assert sec2.findtext(f"{NS}heading") == "CONTRACTS."
    # every candidate token is in the output except those aligned to num/action (substituted)
    missing = Counter(_text(cand).split()) - Counter(_text(root).split())
    assert sum(missing.values()) <= stats["substituted_tokens"] + 2
    assert stats["kept_chars"] > 0 and stats["body_chars"] > 0 and stats["docling_chars"] == len(" ".join(_text(cand).split()))


def test_identifiers_1917_both_forms():
    tree, stats = hybrid.build_hybrid(_gpo(), _cand(CAND_BLOCKS), IDENTITY)
    root = tree.getroot()
    assert root.get("identifier") == "/us/pl/64/380" and stats["identifier"] == "/us/pl/64/380"
    props = [p for p in root.find(NS + "meta").findall(NS + "property") if p.get("role") == "alternateIdentifier"]
    assert [p.text for p in props] == ["/us/act/1917-03-03/ch162"]
    secs = root.findall(f"{NS}main/{NS}section")
    assert [s.get("identifier") for s in secs] == [None, "/us/pl/64/380/s2", "/us/pl/64/380/s3"]
    assert secs[1].find(NS + "subsection").get("identifier") == "/us/pl/64/380/s2/a"
    assert secs[1].get("id") == "id_us_pl_64_380_s2" and secs[1].find(NS + "subsection").get("id") == "id_us_pl_64_380_s2_a"
    assert uslm.validate(tree)[0]


def test_identifiers_chapter_era_and_public_law_era():
    early = DocIdentity(granule_id="STATUTE-10-Pg764", package_id="STATUTE-10", volume=10, congress=32, law_number=139, is_private=True,
                        date_issued="1853-03-03")
    gpo = _gpo()
    gpo.find(f"{NS}meta/{NS}docNumber").text = "CXXI"
    gpo.find(f"{NS}meta/{DC_DATE}").text = "1853-03-03"
    tree, stats = hybrid.build_hybrid(gpo, _cand(CAND_BLOCKS), early)
    assert tree.getroot().get("identifier") == "/us/act/1853-03-03/ch121" and stats["alternate_identifier"] is None
    assert tree.getroot().findall(f"{NS}main/{NS}section")[1].get("identifier") == "/us/act/1853-03-03/ch121/s2"
    late = DocIdentity(granule_id="STATUTE-72-Pg1751", package_id="STATUTE-72", volume=72, congress=85, law_number=910, date_issued="1958-09-02")
    gpo = _gpo()
    gpo.find(f"{NS}meta/{DC_DATE}").text = "1958-09-02"
    tree, stats = hybrid.build_hybrid(gpo, _cand(CAND_BLOCKS), late, chapter="5")
    assert tree.getroot().get("identifier") == "/us/pl/85/910" and stats["alternate_identifier"] is None
    private = DocIdentity(granule_id="x", package_id="STATUTE-72", volume=72, congress=85, law_number=12, is_private=True, date_issued="1958-09-02")
    assert hybrid.law_identifiers(private, gpo)[0] == "/us/pvtl/85/12"
    assert hybrid.chapter_number("CXXI") == "121" and hybrid.chapter_number("162.") == "162" and hybrid.chapter_number("abc") is None


DC_DATE = "{http://purl.org/dc/elements/1.1/}date"


def test_page_identifiers_lower_case():
    gpo = _gpo()
    gpo.find(f".//{NS}page").set("identifier", "/us/stat/39/B3")
    tree, _ = hybrid.build_hybrid(gpo, _cand(CAND_BLOCKS), IDENTITY)
    assert [p.get("identifier") for p in tree.getroot().iter(NS + "page")] == ["/us/stat/39/b3"]


def test_duplicate_section_numbers_prefer_similar_text():
    """A table of contents read as sections carries the same numbers as the real sections."""
    toc = ['<section><num value="2">SEC. 2. </num><content>Contracts.</content></section>',
           '<section><num value="3">SEC. 3. </num><content>Third.</content></section>']
    cand = _cand(CAND_BLOCKS[:3] + toc + CAND_BLOCKS[3:])
    tree, stats = hybrid.build_hybrid(_gpo(), cand, IDENTITY)
    root = tree.getroot()
    secs = root.findall(f"{NS}main/{NS}section")
    assert stats["sections_matched"] == 2
    assert "Contracts made in the Department" in " ".join(secs[1].itertext())
    assert "The third section is short." in " ".join(secs[2].itertext())


def test_unmatched_sections_align_by_text():
    cand = _cand([b.replace('value="2"', 'value="7"') for b in CAND_BLOCKS])
    tree, stats = hybrid.build_hybrid(_gpo(), cand, IDENTITY)
    assert stats["sections_matched"] == 1 and any("not matched" in w for w in stats["warning_log"])
    secs = tree.getroot().findall(f"{NS}main/{NS}section")
    assert "Contracts made in the Department" in " ".join(secs[1].itertext())


def test_clipped_neighbours_go_to_preface_and_appendix():
    lead = ["tail of the previous law, five hundred dollars.", "Approved, March 2, 1917."]
    trail = ["CHAP. 163.-An Act for other things.", "Be it enacted, That nothing happens."]
    cand = _cand([f"<p>{lead[0]}</p>", f"<p>{lead[1]}</p>"] + CAND_BLOCKS + [f"<p>{t}</p>" for t in trail],
                 preface=["Earlier preface text."], trailing=["Later trailing text."])
    tree, stats = hybrid.build_hybrid(_gpo(), cand, IDENTITY)
    root = tree.getroot()
    assert uslm.validate(tree)[0]
    preface = " ".join(root.find(NS + "preface").itertext())
    assert "Earlier preface text." in preface and "five hundred dollars" in preface
    appendix = root.find(NS + "appendix")
    assert appendix.get("role") == "trailingMatter" and "CHAP. 163" in " ".join(appendix.itertext()) and "Later trailing text." in " ".join(appendix.itertext())
    body = _text(root)
    assert "five hundred dollars" not in body and "CHAP. 163" not in body and "Post Office Department" in body


def test_no_gpo_slice_returns_candidate_with_warning():
    cand = _cand(CAND_BLOCKS)
    tree, stats = hybrid.build_hybrid(None, cand, IDENTITY, pages=2)
    assert stats["warnings"] == 1 and "no GPO slice" in stats["warning_log"][0] and stats["pages"] == 2
    assert _text(tree.getroot()) == _text(cand) and stats["sections_matched"] == 0


def test_empty_candidate_keeps_gpo_text():
    tree, stats = hybrid.build_hybrid(_gpo(), _cand(["<p></p>"]), IDENTITY)
    assert "Howe of Representatives" in _text(tree.getroot()) and any("no body text" in w for w in stats["warning_log"])


def test_map_index_and_align_segment():
    a = "the quick brown fox jumps over the lazy dog".split()
    b = "the quick brown cat jumps over a very lazy dog".split()
    cuts = hybrid.align_segment(a, b, [0, 3, 4, 7])
    assert cuts == [0, 3, 4, 8]
    assert hybrid.align_segment(a, [], [0, 3]) == [0, 0] and hybrid.align_segment([], b, [0]) == [0]


@pytest.mark.parametrize("name,identity", [
    ("STATUTE-72-Pg1751", DocIdentity(granule_id="STATUTE-72-Pg1751", package_id="STATUTE-72", volume=72, start_page=1751, congress=85,
                                      law_number=910, date_issued="1958-09-02")),
    ("STATUTE-10-Pg764", DocIdentity(granule_id="STATUTE-10-Pg764", package_id="STATUTE-10", volume=10, start_page=764, congress=32,
                                     law_number=139, is_private=True, date_issued="1853-03-03")),
])
def test_fixture_granules(name, identity):
    gpo = etree.parse(str(FIXTURES / f"{name}.gpo.xml"))
    cand = etree.parse(str(FIXTURES / f"{name}.scanned.xml"))
    tree, stats = hybrid.build_hybrid(gpo, cand, identity, pages=3, chapter="121" if name.startswith("STATUTE-10") else None)
    ok, errors = uslm.validate(tree)
    assert ok, errors[:3]
    ref = _text(gpo.getroot())
    cand_text = _text(cand.getroot())
    out = _text(tree.getroot())
    clipped = metrics.clip_to_reference(ref, cand_text).text
    # the hybrid body is the candidate's words (within the reference span), not the GPO's
    assert metrics.cer(clipped, out) < 0.08, metrics.cer(clipped, out)
    assert metrics.cer(ref, out) <= metrics.cer(ref, cand_text) + 0.01
    missing = Counter(clipped.split()) - Counter(out.split())
    assert sum(missing.values()) <= stats["substituted_tokens"] + 5
    assert [p.get("identifier") for p in tree.getroot().iter(NS + "page")] == [p.get("identifier") for p in gpo.getroot().iter(NS + "page")]
    assert len(list(tree.getroot().iter(NS + "sidenote"))) == len(list(gpo.getroot().iter(NS + "sidenote")))
    if name == "STATUTE-72-Pg1751":
        assert tree.getroot().get("identifier") == "/us/pl/85/910" and stats["sections_matched"] >= 3
        assert "/us/pl/85/910/s2" in {s.get("identifier") for s in tree.getroot().iter(NS + "section")}
    else:
        assert tree.getroot().get("identifier") == "/us/act/1853-03-03/ch121"


def test_uslm_builder_paths_and_registry(tmp_path, monkeypatch):
    from pipeline import convert

    monkeypatch.setattr(hybrid, "DATA_DIR", tmp_path)
    monkeypatch.setattr(convert, "XML_DIR", tmp_path / "generated_xmls")
    gpo_dir = tmp_path / "granules" / "STATUTE-72" / "uslm"
    gpo_dir.mkdir(parents=True)
    (gpo_dir / "STATUTE-72-Pg1751.xml").write_bytes((FIXTURES / "STATUTE-72-Pg1751.gpo.xml").read_bytes())
    cand_dir = tmp_path / "generated_xmls" / "scanned"
    cand_dir.mkdir(parents=True)
    (cand_dir / "STATUTE-72-Pg1751.xml").write_bytes((FIXTURES / "STATUTE-72-Pg1751.scanned.xml").read_bytes())
    identity = {"doc_type": "pLaw", "granule_id": "STATUTE-72-Pg1751", "package_id": "STATUTE-72", "volume": 72, "start_page": 1751,
                "congress": 85, "law_number": 910, "is_private": False, "date_issued": "1958-09-02"}
    xml_path = tmp_path / "generated_xmls" / "hybrid-scanned" / "STATUTE-72-Pg1751.xml"
    tree, stats = hybrid.uslm_builder(tmp_path / "granules" / "STATUTE-72" / "STATUTE-72-Pg1751.pdf", "scanned", None, identity=identity,
                                      doclang_path=None, xml_path=xml_path)
    assert tree.getroot().get("identifier") == "/us/pl/85/910" and stats["gpo"].endswith("STATUTE-72-Pg1751.xml")
    assert stats["pages"] == len(list(tree.getroot().iter(NS + "page")))
    with pytest.raises(FileNotFoundError):
        hybrid.uslm_builder("x.pdf", "digital", None, identity=identity, xml_path=xml_path)
    with pytest.raises(ValueError):
        hybrid.uslm_builder("x.pdf", None, None, identity=identity, xml_path=xml_path)
    fam = profiles.families()["hybrid"]
    assert fam.builds_uslm and fam.uslm_builder is hybrid.uslm_builder and not fam.is_docling
    assert profiles.parse_profile("hybrid:claude:claude-opus-5") == ("hybrid", "claude:claude-opus-5")
    assert convert.profile_dirname("hybrid:claude:claude-opus-5") == "hybrid-claude-claude-opus-5"
