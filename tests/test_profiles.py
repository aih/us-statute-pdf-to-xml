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
    assert scanned.do_ocr is True and scanned.ocr_options.kind == "tesseract_noosd"  # F1: no orientation detection
    assert scanned.ocr_options.lang == ["eng"] and scanned.ocr_options.mode.value == "full_page"
    assert abs(scanned.ocr_options.scale - 300 / 72) < 1e-6  # 300 dpi
    assert scanned.ocr_options.psm is None
    assert scanned.allow_external_plugins is True
    assert profiles.pipeline_options("scanned:psm6").ocr_options.psm == 6
    assert profiles.pipeline_options("scanned", dpi=400).ocr_options.scale == pytest.approx(400 / 72)
    assert digital.do_ocr is False and digital.force_backend_text is True
    assert scanned.generate_page_images is False and digital.generate_page_images is False
    with pytest.raises(ValueError):
        profiles.pipeline_options("other")
    with pytest.raises(ValueError):
        profiles.pipeline_options("scanned:fast")


def test_profile_registry():
    assert profiles.parse_profile("tesseract:psm6") == ("tesseract", "psm6")
    assert profiles.parse_profile("digital") == ("digital", None)
    with pytest.raises(ValueError):
        profiles.parse_profile(":x")
    fams = profiles.families()
    assert {"scanned", "digital"} <= set(fams) and fams["scanned"].is_docling
    assert {"scanned", "scanned:psm4", "scanned:psm6", "digital"} <= set(profiles.known_profiles())
    with pytest.raises(ValueError):
        profiles.get_family("nope:x")
    fam = profiles.register_family(profiles.ProfileFamily("_test", "x", converter=lambda *a, **k: None))
    try:
        assert not profiles.get_family("_test:v").is_docling
        with pytest.raises(ValueError):
            profiles.pipeline_options("_test")
    finally:
        profiles._FAMILIES.pop("_test", None)
    assert profiles.psm_from_variant(None) is None and profiles.psm_from_variant("psm4") == 4


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
    tagged = Unit(unit_id="x", pdf="", profile="scanned:psm6", identity={}, tag="A-clean")
    assert tagged.stem == "x_A-clean" and tagged.module == "scanned:psm6@A-clean"
    assert unit.module == "digital"


def test_output_paths_per_profile():
    from pipeline.convert import DOCLANG_DIR, XML_DIR, output_paths, profile_dirname

    assert profile_dirname("scanned:psm6") == "scanned-psm6"
    j, x = output_paths("scanned:psm6", "STATUTE-72-Pg1751")
    assert j == DOCLANG_DIR / "scanned-psm6" / "STATUTE-72-Pg1751.json"
    assert x == XML_DIR / "scanned-psm6" / "STATUTE-72-Pg1751.xml"
