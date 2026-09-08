"""Profile families `tesseract` (C2), `rapidocr`, and `easyocr` (C3)."""

import shutil

import pytest

from downloader.config import DATA_DIR
from pipeline import profiles

PDF = DATA_DIR / "granules" / "STATUTE-72" / "STATUTE-72-Pg1751.pdf"


@pytest.fixture
def no_prefetch(monkeypatch):
    """Option builders without the model downloads."""
    from pipeline import ocr_engines

    monkeypatch.setattr(ocr_engines, "prefetch_rapidocr", lambda artifacts_path: None)
    monkeypatch.setattr(ocr_engines, "prefetch_easyocr", lambda artifacts_path: None)


def test_families_registered():
    fams = profiles.families()
    assert {"tesseract", "rapidocr", "easyocr"} <= set(fams)
    assert all(fams[n].is_docling for n in ("tesseract", "rapidocr", "easyocr"))
    assert fams["tesseract"].variants == ("psm4", "psm6")
    assert {"tesseract", "tesseract:psm4", "tesseract:psm6", "rapidocr", "easyocr"} <= set(profiles.known_profiles())


def test_tesseract_options_match_scanned():
    pytest.importorskip("docling")
    plain = profiles.pipeline_options("tesseract")
    assert plain.do_ocr is True and plain.ocr_options.kind == "tesseract_noosd"
    assert plain.ocr_options.lang == ["eng"] and plain.ocr_options.mode.value == "full_page"
    assert plain.ocr_options.psm is None and plain.ocr_options.scale == pytest.approx(300 / 72)
    assert plain == profiles.pipeline_options("scanned")
    assert profiles.pipeline_options("tesseract:psm4").ocr_options.psm == 4
    assert profiles.pipeline_options("tesseract:psm6").ocr_options.psm == 6
    assert profiles.pipeline_options("tesseract:psm6", dpi=400).ocr_options.scale == pytest.approx(400 / 72)
    with pytest.raises(ValueError):
        profiles.pipeline_options("tesseract:fast")


def test_rapidocr_options(no_prefetch):
    pytest.importorskip("docling")
    from docling.datamodel.pipeline_options import RapidOcrOptions

    opts = profiles.pipeline_options("rapidocr")
    assert opts.do_ocr is True and isinstance(opts.ocr_options, RapidOcrOptions)
    assert opts.ocr_options.lang == ["en"] and opts.ocr_options.backend == "onnxruntime"
    assert opts.ocr_options.mode.value == "full_page" and opts.ocr_options.scale == pytest.approx(300 / 72)
    assert profiles.pipeline_options("rapidocr", dpi=200).ocr_options.scale == pytest.approx(200 / 72)
    assert opts.accelerator_options.device.value == "cpu"
    with pytest.raises(ValueError):
        profiles.pipeline_options("rapidocr:v4")


def test_easyocr_options(no_prefetch, tmp_path):
    pytest.importorskip("docling")
    from docling.datamodel.pipeline_options import EasyOcrOptions
    from pipeline import ocr_engines

    opts = profiles.pipeline_options("easyocr")
    assert opts.do_ocr is True and isinstance(opts.ocr_options, EasyOcrOptions)
    assert opts.ocr_options.lang == ["en"] and opts.ocr_options.download_enabled is True
    assert opts.ocr_options.mode.value == "full_page" and opts.ocr_options.scale == pytest.approx(300 / 72)
    assert opts.ocr_options.use_gpu is None and opts.accelerator_options.device.value == "cpu"
    with_artifacts = ocr_engines.easyocr_options(artifacts_path=str(tmp_path), prefetch=False)
    assert with_artifacts.ocr_options.model_storage_directory == str(tmp_path / "EasyOcr")
    with pytest.raises(ValueError):
        profiles.pipeline_options("easyocr:gpu")


def test_model_dirs_follow_artifacts_path(tmp_path):
    from pipeline import ocr_engines

    assert ocr_engines.rapidocr_model_dir(None) is None and ocr_engines.easyocr_model_dir(None) is None
    assert ocr_engines.rapidocr_model_dir(str(tmp_path)) == tmp_path / "RapidOcr"
    assert ocr_engines.easyocr_model_dir(str(tmp_path)) == tmp_path / "EasyOcr"
    assert ocr_engines.ocr_scale(216) == pytest.approx(3.0)


# ---------------------------------------------------------------------------- integration


def _page_one_text(profile: str) -> str:
    doc = profiles.make_converter(profile).convert(str(PDF), page_range=(1, 1)).document
    return doc.export_to_text()


def _need_pdf():
    if not PDF.exists():
        pytest.skip(f"{PDF} not downloaded")


@pytest.mark.integration
def test_tesseract_psm4_reads_page_one():
    pytest.importorskip("docling")
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract binary not installed")
    _need_pdf()
    assert "Grand Portage" in _page_one_text("tesseract:psm4")


@pytest.mark.integration
def test_rapidocr_reads_page_one():
    pytest.importorskip("docling")
    pytest.importorskip("rapidocr")
    pytest.importorskip("onnxruntime")
    _need_pdf()
    assert "Grand Portage" in _page_one_text("rapidocr")


@pytest.mark.integration
def test_easyocr_reads_page_one():
    pytest.importorskip("docling")
    pytest.importorskip("easyocr")
    _need_pdf()
    assert "Grand Portage" in _page_one_text("easyocr")
