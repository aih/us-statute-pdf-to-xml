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
    # the page starts with the tail of the previous law; content before "[CHAPTER 486]" is dropped
    first_main_text = " ".join(t for t in root.find(f"{NS}main").itertext())
    assert "Approved July 21, 1950" not in first_main_text


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
