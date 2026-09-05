import datetime as dt

from downloader import state
from downloader.state import HubEntry, decide

PDF = "pdfs/STATUTE-64.pdf"
XML = "xmls/STATUTE-64.xml"
EXPECTED = {PDF: 1000, XML: 200}


def test_skip_when_hub_has_both_with_matching_sizes():
    d = decide("STATUTE-64", EXPECTED, {PDF: HubEntry(1000), XML: HubEntry(200)}, {PDF: None, XML: None})
    assert d.action == "skip"


def test_upload_only_when_local_complete_and_hub_missing():
    d = decide("STATUTE-64", EXPECTED, {}, {PDF: 1000, XML: 200})
    assert d.action == "upload-only"


def test_upload_only_when_one_file_on_hub_and_other_complete_locally():
    d = decide("STATUTE-64", EXPECTED, {PDF: HubEntry(1000)}, {PDF: None, XML: 200})
    assert d.action == "upload-only"


def test_download_when_local_missing():
    d = decide("STATUTE-64", EXPECTED, {}, {PDF: None, XML: None})
    assert d.action == "download"
    assert PDF in d.reason and XML in d.reason


def test_download_when_local_truncated():
    d = decide("STATUTE-64", EXPECTED, {}, {PDF: 999, XML: 200})
    assert d.action == "download"
    assert PDF in d.reason and XML not in d.reason


def test_hub_size_mismatch_triggers_reupload_from_local():
    d = decide("STATUTE-64", EXPECTED, {PDF: HubEntry(5), XML: HubEntry(200)}, {PDF: 1000, XML: 200})
    assert d.action == "upload-only"
    assert "mismatch" in d.reason


def test_hub_size_mismatch_without_local_triggers_download():
    d = decide("STATUTE-64", EXPECTED, {PDF: HubEntry(5), XML: HubEntry(200)}, {PDF: None, XML: None})
    assert d.action == "download"


def test_no_upload_mode_skips_when_local_complete():
    d = decide("STATUTE-64", EXPECTED, {}, {PDF: 1000, XML: 200}, upload_enabled=False)
    assert d.action == "skip"


def test_no_upload_mode_ignores_hub():
    d = decide("STATUTE-64", EXPECTED, {PDF: HubEntry(1000), XML: HubEntry(200)}, {PDF: None, XML: None},
               upload_enabled=False)
    assert d.action == "download"


def test_missing_remote_file_is_ignored():
    d = decide("STATUTE-64", {PDF: 1000, XML: None}, {PDF: HubEntry(1000)}, {PDF: None, XML: None})
    assert d.action == "skip"
    assert len(d.files) == 1


def test_package_row_from_statute_summary():
    row = state.package_row_from_summary(
        {
            "packageId": "STATUTE-64", "collectionCode": "STATUTE", "volume": "64", "congress": "81",
            "session": "2", "dateIssued": "1951-01-02", "pages": "3266", "title": "Vol 64",
            "download": {"pdfLink": "https://x/pdf", "uslmLink": "https://x/uslm"},
        }
    )
    assert row["volume"] == 64 and row["congress"] == 81 and row["session"] == 2
    assert row["date_issued"] == dt.date(1951, 1, 2)
    assert row["pages"] == 3266 and row["scanned"] is True
    assert row["pdf_url"] == "https://x/pdf" and row["xml_url"] == "https://x/uslm"


def test_package_row_marks_digital_volumes():
    row = state.package_row_from_summary({"packageId": "STATUTE-119", "collectionCode": "STATUTE", "volume": "119"})
    assert row["scanned"] is False and row["pages"] is None


def test_plaw_pages_from_summary():
    summary = {
        "packageId": "PLAW-118publ5", "collectionCode": "PLAW", "congress": "118", "pages": "40",
        "references": [
            {"collectionCode": "USCODE", "contents": [{"title": "2", "sections": ["621"]}]},
            {"collectionCode": "STATUTE", "contents": [{"title": "137", "pages": [str(p) for p in range(10, 50)]}]},
        ],
    }
    assert state.plaw_pages_from_summary(summary) == (137, 10, 49)
    row = state.package_row_from_summary(summary)
    assert row["volume"] == 137 and row["scanned"] is None


def test_metadata_rows_only_uploaded_statute_volumes():
    rows = state.metadata_rows(
        [
            {"package_id": "STATUTE-2", "collection": "STATUTE", "volume": 2, "pdf_status": "verified",
             "xml_status": "verified", "date_issued": dt.date(1799, 1, 1), "pdf_bytes": 10, "pdf_sha256": "a",
             "xml_bytes": 5, "xml_sha256": "b", "scanned": True, "congress": 1, "session": 1, "pages": 3},
            {"package_id": "STATUTE-1", "collection": "STATUTE", "volume": 1, "pdf_status": "downloaded"},
            {"package_id": "PLAW-118publ5", "collection": "PLAW", "volume": 137, "pdf_status": "verified"},
        ]
    )
    assert [r["package_id"] for r in rows] == ["STATUTE-2"]
    assert rows[0]["file_name"] == "pdfs/STATUTE-2.pdf" and rows[0]["xml_file"] == "xmls/STATUTE-2.xml"
    assert rows[0]["date_issued"] == "1799-01-01"


def test_plaw_pages_prefers_entry_matching_page_count():
    summary = {
        "packageId": "PLAW-119publ75", "collectionCode": "PLAW", "pages": "3",
        "references": [
            {"collectionCode": "STATUTE", "contents": [
                {"title": "37", "pages": ["736"]},
                {"title": "112", "pages": ["107", "2681-822"]},
                {"title": "140", "pages": ["173", "174", "175"]},
            ]},
        ],
    }
    assert state.plaw_pages_from_summary(summary) == (140, 173, 175)
    summary["pages"] = None  # falls back to the entry with the most pages
    assert state.plaw_pages_from_summary(summary) == (140, 173, 175)


def test_plaw_pages_from_uslm_fixture():
    from pathlib import Path

    xml = (Path(__file__).parent / "fixtures" / "PLAW-114publ176.uslm.xml").read_bytes()
    assert state.plaw_pages_from_uslm(xml) == (130, 430, 430)
    assert state.plaw_pages_from_uslm(b"<pLaw/>") == (None, None, None)
    multi = b'<citableAs>140 Stat. 173</citableAs><page identifier="/us/stat/140/173"/><page identifier="/us/stat/140/739"/>'
    assert state.plaw_pages_from_uslm(multi) == (140, 173, 739)
