"""Defect F1: Docling's Tesseract CLI model rotates pages on a wrong orientation detection.

The fixture STATUTE-72-Pg1751-p1-top.png is the top half of page 1 of that granule as Docling renders
it for Tesseract (216 dpi, grayscale, halved). Tesseract's `--psm 0` reports it upside down with a
confidence near zero; Docling would rotate the image by 180 degrees before OCR. The page is upright.
"""

from pathlib import Path
import shutil

import pytest

from pipeline import tesseract

FIXTURES = Path(__file__).parent / "fixtures"
PAGE = FIXTURES / "STATUTE-72-Pg1751-p1-top.png"


def test_no_osd_model_reports_upright():
    pytest.importorskip("docling")
    from docling.models.stages.ocr.tesseract_ocr_cli_model import _parse_orientation

    options_cls, model_cls = tesseract.classes()
    assert options_cls.kind == "tesseract_noosd"
    assert model_cls.get_options_type() is options_cls
    model = model_cls(enabled=False, artifacts_path=None, options=options_cls(lang=["eng"]), accelerator_options=None)
    df = model._perform_osd(str(PAGE))
    assert _parse_orientation(df) == 0


def test_options_carry_psm_and_scale():
    pytest.importorskip("docling")
    from docling.datamodel.pipeline_options import OcrMode

    opts = tesseract.TesseractNoOsdOptions(lang=["eng"], mode=OcrMode.FULL_PAGE, psm=6, scale=300 / 72)
    assert opts.kind == "tesseract_noosd" and opts.psm == 6 and abs(opts.scale - 4.1667) < 0.001
    assert opts.mode == OcrMode.FULL_PAGE


def test_register_is_idempotent_and_resolves_kind():
    pytest.importorskip("docling")
    from docling.models.factories import get_ocr_factory

    tesseract.register()
    tesseract.register()
    factory = get_ocr_factory(allow_external_plugins=True)
    assert "tesseract_noosd" in factory.registered_kind
    opts = factory.create_options("tesseract_noosd", lang=["eng"])
    assert type(opts) is tesseract.classes()[0]


@pytest.mark.integration
def test_f1_reproduction_tesseract_misreads_upright_page():
    """Reproduction: Tesseract's own detection calls the upright fixture rotated; ours does not."""
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract binary not installed")
    degrees, confidence = tesseract.osd_orientation(str(PAGE))
    assert degrees != 0, "Tesseract OSD now reads this page as upright; the fixture no longer reproduces F1"
    assert confidence < 2.0
    pytest.importorskip("docling")
    from docling.models.stages.ocr.tesseract_ocr_cli_model import _parse_orientation

    options_cls, model_cls = tesseract.classes()
    model = model_cls(enabled=False, artifacts_path=None, options=options_cls(lang=["eng"]), accelerator_options=None)
    assert _parse_orientation(model._perform_osd(str(PAGE))) == 0
