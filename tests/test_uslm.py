from pathlib import Path

import pytest
from lxml import etree

from pipeline import uslm
from pipeline.uslm import DocIdentity, level_for, parse_us_date, split_heading, split_section_heading

FIXTURES = Path(__file__).parent / "fixtures"
NS = "{http://schemas.gpo.gov/xml/uslm}"


@pytest.fixture(scope="module")
def digital_tree():
    DoclingDocument = pytest.importorskip("docling_core.types.doc").DoclingDocument
    doc = DoclingDocument.load_from_json(FIXTURES / "STATUTE-119-Pg3.docling.json")
    identity = DocIdentity(doc_type="pLaw", congress=109, law_number=1, volume=119, start_page=3,
                           granule_id="STATUTE-119-Pg3", package_id="STATUTE-119", date_issued="2005-01-07")
    return uslm.build_uslm(doc, identity)


@pytest.fixture(scope="module")
def scanned_tree():
    DoclingDocument = pytest.importorskip("docling_core.types.doc").DoclingDocument
    doc = DoclingDocument.load_from_json(FIXTURES / "STATUTE-64-Pg371.docling.json")
    identity = DocIdentity(doc_type="pLaw", congress=81, law_number=619, volume=64, start_page=371,
                           granule_id="STATUTE-64-Pg371", package_id="STATUTE-64", date_issued="1950-07-22")
    return uslm.build_uslm(doc, identity)


def test_helpers():
    assert parse_us_date("January 7, 2005") == "2005-01-07"
    assert parse_us_date("Jan. 7, 2005") == "2005-01-07"
    assert parse_us_date("someday") is None
    assert split_heading("IN GENERAL.-For purposes of section 170") == ("IN GENERAL.", "For purposes of section 170")
    assert split_heading("plain text") == (None, "plain text")
    assert split_section_heading("SHORT TITLE. This Act may be cited") == ("SHORT TITLE.", "This Act may be cited")
    assert split_section_heading("This Act may be cited") == (None, "This Act may be cited")
    assert level_for("a", "section") == "subsection"
    assert level_for("1", "subsection") == "paragraph"
    assert level_for("A", "paragraph") == "subparagraph"
    assert level_for("i", "subparagraph") == "clause"
    assert level_for("I", "clause") == "subclause" or level_for("I", "clause") == "subparagraph"


def test_digital_structure_and_identifiers(digital_tree):
    root = digital_tree.getroot()
    assert root.tag == NS + "pLaw"
    assert root.get("identifier") == "/us/pl/109/1"
    sections = root.findall(f".//{NS}section")
    assert [s.get("identifier") for s in sections] == ["/us/pl/109/1/s1"]
    subs = root.findall(f".//{NS}subsection")
    assert [s.get("identifier") for s in subs] == ["/us/pl/109/1/s1/a", "/us/pl/109/1/s1/b"]
    assert [s.findtext(f"{NS}heading") for s in subs] == ["IN GENERAL.", "CONTRIBUTION DESCRIBED."]
    assert all(s.get("id") for s in sections + subs)
    assert root.findtext(f"{NS}main/{NS}longTitle/{NS}docTitle") == "An Act"
    assert root.findtext(f"{NS}main/{NS}longTitle/{NS}officialTitle").startswith("To accelerate")
    assert root.findtext(f"{NS}main/{NS}enactingFormula").startswith("Be it enacted")
    page = root.find(f"{NS}preface/{NS}page")
    assert page.get("identifier") == "/us/stat/119/3"
    action = root.find(f"{NS}main/{NS}action")
    assert action.find(f"{NS}date").get("date") == "2005-01-07"
    assert root.find(f"{NS}legislativeHistory") is not None
    sidenote_texts = [p.text for p in root.findall(f".//{NS}sidenote/{NS}p")]
    assert "[H.R. 241]" in sidenote_texts
    assert not any("VerDate" in (el.text or "") for el in root.iter())  # typesetting footer dropped
    assert root.findtext(f"{NS}meta/{NS}citableAs") == "Public Law 109–1"


def test_scanned_structure(scanned_tree):
    root = scanned_tree.getroot()
    assert root.get("identifier") == "/us/pl/81/619"
    pages = [p.get("identifier") for p in root.iter(NS + "page")]
    assert pages == ["/us/stat/64/371", "/us/stat/64/372", "/us/stat/64/373"]
    assert root.findtext(f"{NS}preface/{NS}docNumber") == "81–619"
    assert root.findtext(f"{NS}main/{NS}longTitle/{NS}docTitle") == "AN ACT"
    # the page starts with the tail of the previous law: kept in the preface, not in main (F2)
    main_text = " ".join(t for t in root.find(f"{NS}main").itertext())
    preface_text = " ".join(t for t in root.find(f"{NS}preface").itertext())
    assert "Approved July 21, 1950" not in main_text and "Approved July 21, 1950" in preface_text
    # the last page ends with the heads of the next two laws: kept as trailing matter, not as sections
    appendix = root.find(f"{NS}appendix")
    assert appendix is not None and appendix.get("role") == "trailingMatter"
    trailing = [p.text for p in appendix.iter(NS + "p")]
    assert "[CHAPTER 491]" in trailing and "Approved July 22, 1950." in trailing
    assert "Approved July 22, 1950" not in main_text
    assert root.find(f"{NS}main/{NS}action/{NS}date").get("date") == "1950-07-22"


def _identity_for(name: str) -> DocIdentity:
    volume = int(name.split("-")[1])
    return DocIdentity(granule_id=name, package_id=f"STATUTE-{volume}", volume=volume)


def _load(name: str):
    DoclingDocument = pytest.importorskip("docling_core.types.doc").DoclingDocument
    return DoclingDocument.load_from_json(FIXTURES / f"{name}.docling.json")


def test_f2_reproduction_mangled_start_keeps_body():
    """Reproduction of F2 on STATUTE-72-Pg1751: page 1 came out of OCR mirrored, so no start line
    matches. The WP6 builder dropped every body item (9,085 characters in, 124 out)."""
    doc = _load("STATUTE-72-Pg1751")
    identity = DocIdentity(granule_id="STATUTE-72-Pg1751", package_id="STATUTE-72", congress=85, law_number=910,
                           volume=72, start_page=1751)
    tree, stats = uslm.build_uslm_with_stats(doc, identity)
    assert stats["docling_chars"] > 8000
    assert stats["body_chars"] >= 0.8 * stats["docling_chars"]
    assert stats["start_rule"] == "none" and stats["warnings"] >= 1
    assert any("start not recognized" in w for w in stats["warning_log"])
    main_text = " ".join(tree.getroot().find(f"{NS}main").itertext())
    assert "Grand Portage" in main_text  # page 2 text reached the body
    ok, errors = uslm.validate(tree)
    assert ok, errors[:3]


def test_f2_start_after_previous_approved_line():
    """Page 1 of a granule whose chapter line is not recognized: the document starts after the previous
    law's "Approved" line, and the previous law's tail goes into the preface."""
    Doc = pytest.importorskip("docling_core.types.doc")
    doc = Doc.DoclingDocument(name="synthetic")
    doc.add_page(page_no=1, size=Doc.Size(width=612, height=792))
    lines = ["and for other purposes, $5,000.", "Approved, March 3, 1917.", "CHAP 163 An Act Making appropriations",
             "Be it enacted by the Senate and House of Representatives,", "SEC. 2. That the sum of $10 is appropriated.",
             "(a) for salaries;", "Approved, March 3, 1917."]
    for i, text in enumerate(lines):
        top = 700 - i * 40
        doc.add_text(label=Doc.DocItemLabel.TEXT, text=text,
                     prov=Doc.ProvenanceItem(page_no=1, bbox=Doc.BoundingBox(l=100, t=top, r=500, b=top - 20), charspan=(0, len(text))))
    tree, stats = uslm.build_uslm_with_stats(doc, DocIdentity(granule_id="STATUTE-39-Pg1058", package_id="STATUTE-39", volume=39, start_page=1058))
    assert stats["start_rule"] == "end-marker"
    root = tree.getroot()
    assert [p.text for p in root.find(f"{NS}preface").iter(NS + "p")] == lines[:2]
    main_text = " ".join(root.find(f"{NS}main").itertext())
    assert "CHAP 163" in main_text and "salaries" in main_text and stats["kept_ratio"] >= 0.8
    assert root.find(f"{NS}main/{NS}section") is not None
    assert uslm.validate(tree)[0]


def test_nothing_recognized_at_all_keeps_everything():
    """STATUTE-10-Pg764: the whole page is mirrored OCR; the builder still keeps every character."""
    doc = _load("STATUTE-10-Pg764")
    tree, stats = uslm.build_uslm_with_stats(doc, _identity_for("STATUTE-10-Pg764"))
    assert stats["start_rule"] == "none" and stats["kept_ratio"] >= 0.8
    assert uslm.validate(tree)[0]


@pytest.mark.parametrize("name", sorted(p.name[: -len(".docling.json")] for p in FIXTURES.glob("*.docling.json")))
def test_builder_keeps_at_least_80_percent_of_docling_text(name):
    doc = _load(name)
    tree, stats = uslm.build_uslm_with_stats(doc, _identity_for(name))
    assert stats["docling_chars"] > 0
    assert stats["kept_chars"] >= 0.8 * stats["docling_chars"], stats
    assert stats["body_chars"] >= 0.8 * stats["docling_chars"] - (stats["kept_chars"] - stats["body_chars"]), stats
    assert uslm.docling_text_chars(doc) == stats["docling_chars"] and uslm.kept_text_chars(tree) == stats["kept_chars"]


def test_chapter_forms():
    assert uslm.RE_CHAPTER.match("[CHAPTER 486]").group(1) == "486"
    assert uslm.RE_CHAPTER.match("(CHAPTER 456}").group(1) == "456"
    m = uslm.RE_CHAPTER.match("CHAP. 162.—An Act Making appropriations for the Post Office.")
    assert m.group(1) == "162" and m.group(2).startswith("An Act Making")
    assert uslm.RE_CHAPTER.match("CHAP. CXXI.—An Act for the Relief of Robert Gibson.").group(1) == "CXXI"
    assert uslm.RE_CHAPTER.match("Chapter 3 of title 5") is None
    assert uslm.UslmBuilder.is_start_marker("Public Law 85-910") and uslm.UslmBuilder.is_start_marker("AN ACT")
    assert not uslm.UslmBuilder.is_start_marker("Approved September 2, 1958.")


@pytest.mark.parametrize("fixture", ["digital_tree", "scanned_tree"])
def test_output_validates_against_xsd(fixture, request):
    tree = request.getfixturevalue(fixture)
    ok, errors = uslm.validate(tree)
    assert ok, errors[:5]


def test_identity_from_granule_row():
    row = {"granule_id": "STATUTE-64-Pg371", "package_id": "STATUTE-64", "granule_class": "PUBLICLAW", "number": "619",
           "page_start": 371, "congress": 81, "date_issued": "1950-07-22", "title": "AN ACT",
           "mods": {"volume": 64, "session": 2}}
    ident = uslm.identity_from_granule(row)
    assert (ident.congress, ident.law_number, ident.volume, ident.start_page, ident.session) == (81, 619, 64, 371, 2)
    assert ident.law_identifier == "/us/pl/81/619"
    treaty = uslm.identity_from_granule({"granule_id": "STATUTE-64-PgB3", "package_id": "STATUTE-64", "granule_class": "TREATY", "number": "1982"})
    assert treaty.doc_type == "presidentialDoc" and treaty.law_number is None and treaty.volume == 64


def test_identity_from_plaw():
    ident = uslm.identity_from_plaw("PLAW-118publ5", {"volume": 137, "start_page": 10, "date_enacted": "2023-06-03", "title": "An act"})
    assert ident.law_identifier == "/us/pl/118/5" and ident.volume == 137 and ident.start_page == 10
    assert uslm.identity_from_plaw("PLAW-117pvtl3").is_private


def test_second_enacting_formula_is_kept_as_text():
    """A page with several resolutions: every "Resolved" line after the first stays in the body."""
    Doc = pytest.importorskip("docling_core.types.doc")
    doc = Doc.DoclingDocument(name="synthetic")
    doc.add_page(page_no=1, size=Doc.Size(width=612, height=792))
    lines = ["CONCURRENT RESOLUTION", "Resolved by the House of Representatives (the Senate concurring), That A.",
             "Resolved by the Senate (the House of Representatives concurring), That B."]
    for i, text in enumerate(lines):
        top = 700 - i * 40
        doc.add_text(label=Doc.DocItemLabel.TEXT, text=text,
                     prov=Doc.ProvenanceItem(page_no=1, bbox=Doc.BoundingBox(l=100, t=top, r=500, b=top - 20), charspan=(0, len(text))))
    tree, stats = uslm.build_uslm_with_stats(doc, DocIdentity(doc_type="resolution", granule_id="STATUTE-39-Pg1606-4", package_id="STATUTE-39", volume=39))
    main_text = " ".join(tree.getroot().find(f"{NS}main").itertext())
    assert "That A." in main_text and "That B." in main_text and stats["kept_ratio"] >= 0.95


def _synthetic(lines, **identity):
    Doc = pytest.importorskip("docling_core.types.doc")
    doc = Doc.DoclingDocument(name="synthetic")
    doc.add_page(page_no=1, size=Doc.Size(width=612, height=792))
    for i, text in enumerate(lines):
        top = 700 - i * 30
        doc.add_text(label=Doc.DocItemLabel.TEXT, text=text,
                     prov=Doc.ProvenanceItem(page_no=1, bbox=Doc.BoundingBox(l=100, t=top, r=500, b=top - 20), charspan=(0, len(text))))
    return uslm.build_uslm_with_stats(doc, DocIdentity(**identity))


PAGE_983 = ["of this Act.", "Approved August 28, 1958.", "Public Law 85-821", "JOINT RESOLUTION",
            "To authorize the Commissioners of the District of Columbia to use certain funds.",
            "Resolved by the Senate and House of Representatives, That the Commissioners may.",
            "Approved August 28, 1958.", "Public Law 85-822", "AN ACT",
            "Authorizing a survey of the Tensaw River, Alabama.",
            "Be it enacted by the Senate and House of Representatives, That the Secretary of the Army is authorized.",
            "Approved August 28, 1958.", "Public Law 85-823", "AN ACT", "To do something else."]


def test_second_document_on_a_page_starts_at_its_own_law_number():
    """STATUTE-72-Pg983-2 is the second law starting on page 983; the builder must not start at PL 85-821."""
    tree, stats = _synthetic(PAGE_983, granule_id="STATUTE-72-Pg983-2", package_id="STATUTE-72", congress=85, law_number=822, volume=72, start_page=983)
    assert stats["start_rule"] == "law-number"
    root = tree.getroot()
    main_text = " ".join(root.find(f"{NS}main").itertext())
    assert "Tensaw River" in main_text and "Commissioners" not in main_text
    assert root.findtext(f"{NS}main/{NS}longTitle/{NS}officialTitle").startswith("Authorizing a survey")
    assert "Public Law 85-823" in [p.text for p in root.find(f"{NS}appendix").iter(NS + "p")]
    assert stats["kept_ratio"] >= 0.9 and uslm.validate(tree)[0]


def test_second_document_on_a_page_by_ordinal_without_law_number():
    tree, stats = _synthetic(PAGE_983, granule_id="STATUTE-72-Pg983-2", package_id="STATUTE-72", volume=72, start_page=983)
    assert stats["start_rule"] == "marker"
    main_text = " ".join(tree.getroot().find(f"{NS}main").itertext())
    assert "Tensaw River" in main_text and "Commissioners" not in main_text
    first, _ = _synthetic(PAGE_983, granule_id="STATUTE-72-Pg983", package_id="STATUTE-72", volume=72, start_page=983)
    assert "Commissioners" in " ".join(first.getroot().find(f"{NS}main").itertext())


PAGE_764 = ["ation of the mails, the sum of three thousand dollars.", "Approved, March 3, 1853.",
            "CHAP. CXXI.-An Act for the Relief of Robert Gibson.",
            "Be it enacted by the Senate and House of Representatives, That the Secretary pay Robert Gibson.",
            "Approved, Marck 3, 1853.",  # OCR error: not an end marker
            "CHAP. CXXII.-An Act for the Relief of Ursula E. Cobb.",
            "Be it enacted by the Senate and House of Representatives, That the Secretary pay Ursula E. Cobb.",
            "Approved, March 3, 1853."]


def test_next_chapter_line_ends_the_document_even_without_an_approval_line():
    tree, stats = _synthetic(PAGE_764, granule_id="STATUTE-10-Pg764", package_id="STATUTE-10", volume=10, start_page=764, is_private=True)
    root = tree.getroot()
    assert stats["start_rule"] == "marker"
    main_text = " ".join(root.find(f"{NS}main").itertext())
    assert "Robert Gibson" in main_text and "Ursula" not in main_text
    assert root.findtext(f"{NS}main/{NS}longTitle/{NS}officialTitle") == "for the Relief of Robert Gibson."
    assert "CHAP. CXXII.-An Act for the Relief of Ursula E. Cobb." in [p.text for p in root.find(f"{NS}appendix").iter(NS + "p")]
    assert stats["kept_ratio"] >= 0.9 and uslm.validate(tree)[0]


def test_chapter_heading_inside_a_law_is_not_a_document_start():
    assert not uslm.UslmBuilder.is_start_marker("CHAPTER 1-GENERAL PROVISIONS")
    assert uslm.UslmBuilder.is_start_marker("[CHAPTER 486]") and uslm.UslmBuilder.is_start_marker("CHAP. 162.-An Act Making appropriations")
    assert uslm.UslmBuilder.is_end_marker("Agreed to August 16, 1958.") and uslm.UslmBuilder.is_end_marker("Passed December 9, 1971.")
    assert not uslm.UslmBuilder.is_end_marker("Approved by the Secretary on March 3, 1853 as follows")


PAGE_B21 = ["A-6083416, Yen Tien Shan,", "Passed August 13, 1958.", "NEVADA CENTENNIAL CELEBRATION",
            "Whereas June 8, 1959, marks the one hundredth anniversary of the discovery of silver.",
            "Resolved by the Senate (the House of Representatives concurring), That the Congress extends felicitations.",
            "Agreed to August 16, 1958.", "CORRECTION OF H. R. 18132",
            "Resolved by the House of Representatives (the Senate concurring), That the Clerk correct the enrollment.",
            "Agreed to August 20, 1958."]


def test_resolution_starts_after_previous_end_marker_and_keeps_preamble_order():
    tree, stats = _synthetic(PAGE_B21, doc_type="resolution", granule_id="STATUTE-72-PgB21", package_id="STATUTE-72", volume=72)
    root = tree.getroot()
    assert stats["start_rule"] == "end-marker"
    main = root.find(f"{NS}main")
    texts = [t.strip() for t in main.itertext() if t.strip()]
    assert texts.index("NEVADA CENTENNIAL CELEBRATION") < texts.index(PAGE_B21[3]) < texts.index(PAGE_B21[4])
    assert "Clerk" not in " ".join(texts) and "Yen Tien Shan" not in " ".join(texts)
    assert [p.text for p in root.find(f"{NS}preface").iter(NS + "p")] == PAGE_B21[:2]
    assert root.find(f"{NS}appendix") is not None and stats["kept_ratio"] >= 0.9
    assert uslm.validate(tree)[0]
    second, st2 = _synthetic(PAGE_B21, doc_type="resolution", granule_id="STATUTE-72-PgB21-2", package_id="STATUTE-72", volume=72)
    assert "Clerk" in " ".join(second.getroot().find(f"{NS}main").itertext()) and "felicitations" not in " ".join(second.getroot().find(f"{NS}main").itertext())


def test_markers_tolerate_ocr_forms():
    B = uslm.UslmBuilder
    assert B.is_end_marker("Arprrovep, March 3, 1853.") and B.is_end_marker("Appnoven, January 12, 1855.")
    assert B.is_end_marker("Agreed to ta 22, 1958.")  # month garbled
    assert B.is_end_marker("That when the House adjourns it stands adjourned. Passed October 7, 1971.")  # merged lines
    assert not B.is_end_marker("Reported, March 3, 1853.") and not B.is_end_marker("Approved by the board on March 3, 1853 and later")
    assert B.is_start_marker("Cuar. CXXII.- An Act for the Relief of Ursula E. Cobb.")
    assert B.is_start_marker("CXXL- An Act far the Relief of Rebert")
    assert B.is_start_marker("Cuav, XXXIL- Ax Act for the Relief of Mrs, Ann W. Angus.")
    assert not B.is_start_marker("XII. An Act is not a chapter line") and not B.is_start_marker("Section 12 - An Act")
    tree, stats = _synthetic(["Arprrovep, March 3, 1853.", "Cuar. CXXI.- An Act for the Relief of Robert Gibson.",
                              "Be it enacted by the Senate, That the Secretary pay Robert Gibson.", "Arrroven, March 3, 1853.",
                              "Caar, CXXII.- An Act for the Relief of Ursula E. Cobb.", "Be it enacted, That the Secretary pay Ursula E. Cobb."],
                             granule_id="STATUTE-10-Pg764", package_id="STATUTE-10", volume=10, start_page=764, is_private=True)
    root = tree.getroot()
    main_text = " ".join(root.find(f"{NS}main").itertext())
    assert "Robert Gibson" in main_text and "Ursula" not in main_text
    assert root.find(f"{NS}main/{NS}action/{NS}date").get("date") == "1853-03-03"
    assert root.findtext(f"{NS}main/{NS}longTitle/{NS}docTitle") == "An Act"
    assert stats["kept_ratio"] >= 0.9 and uslm.validate(tree)[0]


def test_proclamation_keeps_body_order_and_title_is_bounded():
    lines = ["IN WITNESS WHEREOF, I have set my hand this nineteenth day of May.", "PROCLAMATION 4055",
             "Flag Day and National Flag Week, 1971", "By the President of the United States of America", "A Proclamation",
             "On June 14, 1777, the Continental Congress adopted the flag.", "With the passing decades the proof has come.",
             "NOW, THEREFORE, I, RICHARD NIXON, President, do hereby designate June 14 as Flag Day.",
             "PROCLAMATION 4056", "Prayer for Peace, Memorial Day, 1971", "By the President of the United States of America",
             "A Proclamation", "It is a tradition of our Nation to honor the dead."]
    tree, stats = _synthetic(lines, doc_type="presidentialDoc", granule_id="STATUTE-85-Pg906", package_id="STATUTE-85",
                             volume=85, start_page=906, title="Flag Day and National Flag Week, 1971")
    root = tree.getroot()
    main = root.find(f"{NS}main")
    texts = [t.strip() for t in main.itertext() if t.strip()]
    assert stats["start_rule"] == "title"
    assert texts.index("Flag Day and National Flag Week, 1971") < texts.index("By the President of the United States of America") < texts.index(lines[5]) < texts.index(lines[6])
    assert root.findtext(f"{NS}main/{NS}longTitle/{NS}docTitle") == "A Proclamation"
    assert root.find(f"{NS}main/{NS}longTitle/{NS}officialTitle") is None
    assert "Prayer for Peace" not in " ".join(texts) and "tradition" not in " ".join(texts)
    assert uslm.validate(tree)[0] and stats["kept_ratio"] >= 0.9


def test_official_title_stops_at_the_enacting_formula_and_is_bounded():
    lines = ["Public Law 85-910", "AN ACT", "To provide for the establishment of Grand Portage National Monument,",
             "and for other purposes.", "Be it enacted by the Senate, That the Secretary may.", "SEC. 2. Funds are authorized."]
    tree, _ = _synthetic(lines, granule_id="STATUTE-72-Pg1751", package_id="STATUTE-72", congress=85, law_number=910, volume=72, start_page=1751)
    root = tree.getroot()
    assert root.findtext(f"{NS}main/{NS}longTitle/{NS}officialTitle") == lines[2] + " " + lines[3]
    assert root.findtext(f"{NS}main/{NS}enactingFormula") == lines[4]
    assert root.find(f"{NS}main/{NS}section") is not None


def test_running_heads_in_vlm_markdown_do_not_end_the_document():
    """LightOnOCR output has synthesized boxes, so the page-2 running head "PUBLIC LAW 85-910—SEPT. 2, 1958"
    reached the body and the next-document rule moved pages 2 and 3 into trailing matter."""
    DoclingDocument = pytest.importorskip("docling_core.types.doc").DoclingDocument
    doc = DoclingDocument.load_from_json(FIXTURES / "STATUTE-72-Pg1751.lightonocr.docling.json")
    identity = DocIdentity(granule_id="STATUTE-72-Pg1751", package_id="STATUTE-72", volume=72, start_page=1751,
                           congress=85, law_number=910)
    pages = uslm.load_pages(doc)
    assert [it.text for it in pages[1].items if it.kind == "header"] == ["1752", "PUBLIC LAW 85-910—SEPT. 2, 1958", "[72 STAT."]
    assert [it.text for it in pages[2].items if it.kind == "header"] == ["72 STAT.] PUBLIC LAW 85-910—SEPT. 2, 1958 1753"]
    tree, stats = uslm.build_uslm_with_stats(doc, identity)
    assert not any("next document starts" in w for w in stats["warning_log"])
    assert stats["trailing_items"] == 1 and stats["body_chars"] > 10000  # "16 USC 1." after the approval line
    ns = {"u": uslm.USLM_NS}
    assert len(tree.findall(".//u:section", ns)) == 10
    body_text = " ".join(tree.getroot().find(".//u:main", ns).itertext())
    assert "Grand Portage National Monument is abandoned" in body_text
    assert uslm.is_running_head("448 FOURTH CONGRESS. SESS. I. CH. 2, 4. 1796.")
    assert uslm.is_running_head("SIXTY-SECOND CONGRESS. SESS. II. CHS. 32, 33. 1912.")
    assert not uslm.is_running_head("Public Law 85-910") and not uslm.is_running_head("AN ACT")
    assert not uslm.is_running_head("Be it enacted by the Senate and House of Representatives of the United")
