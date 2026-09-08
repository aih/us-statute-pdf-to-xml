import json
from pathlib import Path

import pytest

from benchmark import rasterize


@pytest.fixture
def small_pdf(tmp_path):
    """A two-page PDF built from images, so the test does not depend on a committed PDF."""
    img2pdf = pytest.importorskip("img2pdf")
    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")
    pages = []
    for n in (1, 2):
        im = Image.new("RGB", (300, 400), "white")
        ImageDraw.Draw(im).rectangle((40, 40 * n, 200, 60 * n), fill="black")
        p = tmp_path / f"src{n}.png"
        im.save(p)
        pages.append(str(p))
    pdf = tmp_path / "two.pdf"
    pdf.write_bytes(img2pdf.convert(pages, dpi=72))
    return pdf


def test_degrade_keeps_size_and_changes_pixels():
    Image = pytest.importorskip("PIL.Image")
    np = pytest.importorskip("numpy")
    im = Image.new("RGB", (120, 80), "white")
    out = rasterize.degrade(im, seed=1)
    assert out.size == im.size and out.mode == "RGB"
    assert np.asarray(out).std() > 0  # noise added
    assert np.array_equal(np.asarray(rasterize.degrade(im, seed=1)), np.asarray(out))  # seeded


def test_rasterize_writes_variants_wrappers_and_manifest(small_pdf, tmp_path):
    pytest.importorskip("pypdfium2")
    out_root = tmp_path / "raster"
    r = rasterize.rasterize(small_pdf, "TEST-1", out_root=out_root, dpi=72)
    assert r.pages == [1, 2]
    assert [p.name for p in r.images["clean"]] == ["p1.png", "p2.png"]
    assert [p.name for p in r.images["degraded"]] == ["p1.degraded.jpg", "p2.degraded.jpg"]
    assert r.pdfs["clean"].name == "TEST-1.clean.pdf" and r.pdfs["degraded"].exists()
    manifest = json.loads((out_root / "TEST-1" / "manifest.json").read_text())
    assert manifest["dpi"] == 72 and set(manifest["sha256"]) == {"p1.png", "p2.png", "p1.degraded.jpg", "p2.degraded.jpg"}
    # the wrapper has the same page count and can be rendered again
    import pypdfium2 as pdfium

    assert len(pdfium.PdfDocument(str(r.pdfs["clean"]))) == 2
    # a second call reuses the manifest
    again = rasterize.rasterize(small_pdf, "TEST-1", out_root=out_root, dpi=72)
    assert again.images["clean"] == r.images["clean"]
    assert rasterize.raster_pdf("TEST-1", "degraded", out_root) == r.pdfs["degraded"]


def test_rasterize_page_subset_and_bad_variant(small_pdf, tmp_path):
    pytest.importorskip("pypdfium2")
    r = rasterize.rasterize(small_pdf, "TEST-2", out_root=tmp_path, dpi=72, variants=("clean",), pages=[2])
    assert r.pages == [2] and "degraded" not in r.images
    with pytest.raises(ValueError):
        rasterize.rasterize(small_pdf, "TEST-3", out_root=tmp_path, variants=("blurry",))
    assert rasterize.parse_pages("3-5") == [3, 4, 5] and rasterize.parse_pages("4") == [4] and rasterize.parse_pages(None) is None
