import json
from datetime import date
from pathlib import Path

import pytest

from downloader import fetch_plaw

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_plaw_id_and_pl_number():
    assert fetch_plaw.parse_plaw_id("PLAW-118publ5") == (118, "publ", 5)
    assert fetch_plaw.pl_number("PLAW-118publ5") == "118-5"
    assert fetch_plaw.pl_number("PLAW-117pvtl3") == "117-pvt3"
    with pytest.raises(ValueError):
        fetch_plaw.parse_plaw_id("STATUTE-64")


def test_congress_gov_url():
    assert fetch_plaw.congress_gov_url("PLAW-114publ176") == (
        "https://www.congress.gov/114/plaws/publ176/PLAW-114publ176_uslm.xml"
    )


def test_issued_floor():
    assert fetch_plaw.issued_on_or_after({"dateIssued": "2023-06-03"}, date(2023, 1, 1))
    assert not fetch_plaw.issued_on_or_after({"dateIssued": "2011-01-04"}, date(2023, 1, 1))
    assert fetch_plaw.issued_on_or_after({"dateIssued": "2011-01-04"}, None)
    assert fetch_plaw.issued_on_or_after({}, date(2023, 1, 1))


def test_statute_row_from_summary(tmp_path):
    summary = json.loads((FIXTURES / "PLAW-118publ5.summary.json").read_text())
    row = fetch_plaw.statute_row(summary, tmp_path / "PLAW-118publ5.pdf")
    assert row["pl_number"] == "118-5" and row["congress"] == 118 and row["law_number"] == 5
    assert row["volume"] == 137 and (row["start_page"], row["end_page"]) == (10, 49)
    assert row["date_enacted"] == "2023-06-03"
    assert row["title"].startswith("An act to provide for a responsible increase")
