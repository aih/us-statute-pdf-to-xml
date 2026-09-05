import pytest

from pipeline import profiles
from pipeline.convert import Unit, parse_page_range, should_skip, workers_for_container


def test_profile_for_volume():
    assert profiles.profile_for_volume(64) == "scanned"
    assert profiles.profile_for_volume(116) == "scanned"
    assert profiles.profile_for_volume(117) == "digital"
    assert profiles.profile_for_volume(None) == "digital"


def test_pipeline_options_per_profile():
    pytest.importorskip("docling")
    scanned = profiles.pipeline_options("scanned")
    digital = profiles.pipeline_options("digital")
    assert scanned.do_ocr is True and type(scanned.ocr_options).__name__ == "TesseractCliOcrOptions"
    assert scanned.ocr_options.lang == ["eng"]
    assert digital.do_ocr is False and digital.force_backend_text is True
    assert scanned.generate_page_images is False and digital.generate_page_images is False
    with pytest.raises(ValueError):
        profiles.pipeline_options("other")


def test_parse_page_range():
    assert parse_page_range("1-20") == (1, 20)
    assert parse_page_range(None) is None
    with pytest.raises(ValueError):
        parse_page_range("20-1")


def test_workers_default_capped_for_memory():
    assert 1 <= workers_for_container(None) <= 2
    assert workers_for_container(7) == 7


def test_should_skip_requires_outputs_and_matching_sha(tmp_path):
    unit = Unit(unit_id="x", pdf="x.pdf", profile="digital", identity={})
    j, x = tmp_path / "x.json", tmp_path / "x.xml"
    prev = {"status": "success", "input_sha256": "abc"}
    assert not should_skip(unit, "abc", j, x, prev, force=False)  # outputs missing
    j.write_text("{}"); x.write_text("<a/>")
    assert should_skip(unit, "abc", j, x, prev, force=False)
    assert not should_skip(unit, "def", j, x, prev, force=False)  # input changed
    assert not should_skip(unit, "abc", j, x, prev, force=True)
    assert not should_skip(unit, "abc", j, x, {"status": "failed", "input_sha256": "abc"}, force=False)
    assert Unit(unit_id="x", pdf="", profile="digital", identity={}, page_range=(1, 20)).stem == "x_p1-20"
