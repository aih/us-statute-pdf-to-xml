import json
from pathlib import Path

import pytest
from lxml import etree

from pipeline import split_uslm
from pipeline.split_uslm import (make_granule_id, normalize_page, page_from_citation, page_from_identifier,
                                 parse_granule_id, split_volume)

USLM = "http://schemas.gpo.gov/xml/uslm"

VOLUME_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<statutesAtLarge xmlns="{USLM}" xmlns:dc="http://purl.org/dc/elements/1.1/">
<meta><dc:title>Volume 64</dc:title></meta>
<main><collection role="statutesParts">
 <component role="statutesPart">
  <meta><dc:title>Part 1</dc:title></meta>
  <preface><page identifier="/us/stat/64/iii"/><p>CONTENTS</p></preface>
  <publicLaws>
   <component><pLaw><meta><dc:title>First</dc:title><citableAs>64 Stat. 3</citableAs></meta>
     <main><page identifier="/us/stat/64/3"/><section><content>Text one.</content></section></main></pLaw></component>
   <component><pLaw><meta><dc:title>Second</dc:title><citableAs>64 Stat. 3</citableAs></meta>
     <main><section><content>Text two.</content><page identifier="/us/stat/64/4"/></section></main></pLaw></component>
   <component><pLaw><meta><dc:title>Third</dc:title><citableAs>64 Stat. 4</citableAs></meta>
     <main><section><content>Text three.</content></section></main></pLaw></component>
  </publicLaws>
  <concurrentResolutions>
   <preface><page identifier="/us/stat/64/a279"/><p>RESOLUTIONS</p></preface>
   <component><resolution><meta><dc:type>House Concurrent Resolution</dc:type></meta>
     <preface><officialTitle>JOINT MEETING</officialTitle><approvedDate>January 4</approvedDate><page identifier="/us/stat/64/a283"/></preface>
     <main><content>Resolved.</content></main></resolution></component>
   <component><resolution><meta><dc:type>Senate Concurrent Resolution</dc:type></meta>
     <main><content>Resolved again on the same page.</content></main></resolution></component>
  </concurrentResolutions>
  <backMatter><page identifier="/us/stat/64/1283"/><p>INDEX</p></backMatter>
 </component>
 <component role="statutesPart">
  <meta><dc:title>Part 3</dc:title></meta>
  <preface><page identifier="/us/stat/64/biii"/><p>TREATIES</p></preface>
  <presidentialDocs role="treaties">
   <component><presidentialDoc><meta><dc:type>Treaty</dc:type><citableAs>64 Stat. B3</citableAs></meta>
     <main><page identifier="/us/stat/64/b3"/><content>Convention.</content><page identifier="/us/stat/64/b4@fre"/></main></presidentialDoc></component>
  </presidentialDocs>
  <backMatter><p>INDEX</p></backMatter>
 </component>
</collection></main>
</statutesAtLarge>
"""

GRANULES = [
    {"granuleId": "STATUTE-64-FrontMatter-1-PgIII", "granuleClass": "FRONTMATTER"},
    {"granuleId": "STATUTE-64-Pg3", "granuleClass": "PUBLICLAW"},
    {"granuleId": "STATUTE-64-Pg3-2", "granuleClass": "PUBLICLAW"},
    {"granuleId": "STATUTE-64-Pg4", "granuleClass": "PUBLICLAW"},
    {"granuleId": "STATUTE-64-PgA283", "granuleClass": "HCONRES"},
    {"granuleId": "STATUTE-64-PgA283-2", "granuleClass": "SCONRES"},
    {"granuleId": "STATUTE-64-BackMatter-1-Pg1283", "granuleClass": "BACKMATTER"},
    {"granuleId": "STATUTE-64-FrontMatter-2-Pgiii", "granuleClass": "FRONTMATTER"},
    {"granuleId": "STATUTE-64-PgB3", "granuleClass": "TREATY"},
    {"granuleId": "STATUTE-64-BackMatter-2-PgB1103", "granuleClass": "BACKMATTER"},
]


@pytest.fixture
def volume_file(tmp_path):
    path = tmp_path / "STATUTE-64.xml"
    path.write_text(VOLUME_XML, encoding="utf-8")
    return path


def test_page_helpers():
    assert normalize_page("B12@eng") == "b12"
    assert page_from_identifier("/us/stat/64/b3") == "b3"
    assert page_from_citation("64 Stat. B3") == "b3"
    assert page_from_citation("64 Stat. 371") == "371"
    assert parse_granule_id("STATUTE-64-PgA283-2") == ("a283", 2)
    assert parse_granule_id("STATUTE-64-Pg371") == ("371", 1)
    assert parse_granule_id("STATUTE-64-FrontMatter-1-PgIII") is None
    assert make_granule_id(64, "a283", 2) == "STATUTE-64-PgA283-2"
    assert make_granule_id(64, "371", 1) == "STATUTE-64-Pg371"


def test_split_assigns_ids_and_writes_files(volume_file, tmp_path):
    out = tmp_path / "out"
    report = split_volume(volume_file, out, GRANULES)
    ids = [s.granule_id for s in report.slices]
    assert ids == [
        "STATUTE-64-FrontMatter-1-PgIII",
        "STATUTE-64-Pg3",
        "STATUTE-64-Pg3-2",
        "STATUTE-64-Pg4",
        "STATUTE-64-PgA283",
        "STATUTE-64-PgA283-2",
        "STATUTE-64-BackMatter-1-Pg1283",
        "STATUTE-64-FrontMatter-2-Pgiii",
        "STATUTE-64-PgB3",
        "STATUTE-64-BackMatter-2-PgB1103",
    ]
    assert report.missing == [] and report.extra == []
    classes = {s.granule_id: s.granule_class for s in report.slices}
    assert classes["STATUTE-64-PgA283"] == "HCONRES" and classes["STATUTE-64-PgA283-2"] == "SCONRES"
    assert classes["STATUTE-64-PgB3"] == "TREATY" and classes["STATUTE-64-Pg3"] == "PUBLICLAW"
    files = sorted(p.name for p in out.glob("*.xml"))
    assert len(files) == 10 and "STATUTE-64-Pg3-2.xml" in files
    doc = etree.parse(str(out / "STATUTE-64-Pg3-2.xml"))
    root = doc.getroot()
    assert root.tag == f"{{{USLM}}}pLaw"
    assert root.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", "").startswith(USLM)
    assert root.findtext(f"{{{USLM}}}meta/{{{USLM}}}citableAs") == "64 Stat. 3"
    index = json.loads((out / "index.json").read_text())
    assert index[1]["granule_id"] == "STATUTE-64-Pg3" and index[1]["start_page"] == "3" and index[1]["matched"] is True


def test_split_without_listing_uses_synthetic_matter_ids(volume_file, tmp_path):
    report = split_volume(volume_file, tmp_path / "o", None, write=False)
    ids = [s.granule_id for s in report.slices]
    assert "STATUTE-64-FrontMatter-1-PgIII" in ids
    assert "STATUTE-64-BackMatter-1-Pg1283" in ids
    assert report.expected_ids == set() and report.extra == []


def test_dry_run_writes_nothing(volume_file, tmp_path):
    out = tmp_path / "o"
    split_volume(volume_file, out, GRANULES, write=False)
    assert not out.exists()


REAL_VOLUME = Path("data/historical/xmls/STATUTE-64.xml")
REAL_LISTING = Path("data/granules/STATUTE-64/granules.json")


@pytest.mark.integration
@pytest.mark.skipif(not (REAL_VOLUME.exists() and REAL_LISTING.exists()), reason="STATUTE-64 data not present")
def test_real_statute_64_yields_1393_documents(tmp_path):
    granules = json.loads(REAL_LISTING.read_text())
    report = split_volume(REAL_VOLUME, tmp_path / "o", granules, write=False)
    assert len(report.slices) == 1393 == len(granules)
    matched = len(report.produced_ids & report.expected_ids)
    assert matched >= 1385, (report.missing, report.extra)
