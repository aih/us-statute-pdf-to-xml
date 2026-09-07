from pathlib import Path

from downloader.mods import page_label_to_int, parse_mods

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_public_law_mods():
    m = parse_mods((FIXTURES / "STATUTE-64-Pg371.mods.xml").read_bytes())
    assert m["granule_id"] == "STATUTE-64-Pg371"
    assert m["granule_class"] == "PUBLICLAW"
    assert m["number"] == "619" and m["congress"] == 81 and m["session"] == 2 and m["volume"] == 64
    assert (m["page_start"], m["page_end"]) == (371, 373)
    assert m["page_range"] == "371-373" and m["total_pages"] == 3
    assert m["citation"] == "64 Stat. 371"
    assert m["granule_date"] == "1950-07-22"
    assert m["is_private"] is False
    assert m["bill"] == {"type": "S", "number": "2201", "congress": "81"}
    assert m["title"].startswith("AN ACT To amend section 2")
    assert m["pdf_url"].endswith("STATUTE-64-Pg371.pdf")


def test_parse_treaty_mods_with_lettered_pages():
    m = parse_mods((FIXTURES / "STATUTE-64-PgB3.mods.xml").read_bytes())
    assert m["granule_class"] == "TREATY"
    assert m["page_start_label"] == "B3" and m["page_end_label"] == "B32"
    assert m["page_start"] is None and m["page_end"] is None
    assert m["page_range"] == "B3-B32" and m["total_pages"] == 32


def test_page_label_to_int():
    assert page_label_to_int("371") == 371
    assert page_label_to_int("B3") is None
    assert page_label_to_int("") is None
