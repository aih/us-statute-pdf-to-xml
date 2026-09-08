"""Profile family `textlayer` (C1): the PDF text layer through Docling layout, no OCR."""

import pytest

from downloader.config import DATA_DIR
from pipeline import profiles

PDF = DATA_DIR / "granules" / "STATUTE-72" / "STATUTE-72-Pg1751.pdf"


def test_registered_as_its_own_family():
    fams = profiles.families()
    assert "textlayer" in fams and fams["textlayer"].is_docling
    assert fams["textlayer"].variants == ()
    assert "textlayer" in profiles.known_profiles()
    assert profiles.get_family("textlayer") is not fams["digital"]


def test_options_read_the_text_layer_without_ocr():
    pytest.importorskip("docling")
    opts = profiles.pipeline_options("textlayer")
    assert opts.do_ocr is False and opts.force_backend_text is True
    assert opts.images_scale == 1.0 and opts.generate_page_images is False
    assert opts == profiles.pipeline_options("digital")
    with pytest.raises(ValueError):
        profiles.pipeline_options("textlayer:fast")


@pytest.mark.integration
def test_page_one_of_pl_85_910_from_the_text_layer():
    pytest.importorskip("docling")
    if not PDF.exists():
        pytest.skip(f"{PDF} not downloaded")
    doc = profiles.make_converter("textlayer").convert(str(PDF), page_range=(1, 1)).document
    text = " ".join(" ".join((getattr(item, "text", "") or "").split()) for item, _ in doc.iterate_items())
    # the vendor text layer renders the title line differently per pdf backend; the body heading and the
    # enacting formula are stable across hosts
    assert "NORTHWEST COMPANY AREA" in text and "Be it enacted" in text
