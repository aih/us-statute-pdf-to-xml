import json
from pathlib import Path

import pytest

from pipeline import profiles, vlm


def test_variants_and_engine_choice():
    assert set(vlm.VARIANTS) == {"granite_docling", "glm_ocr", "lightonocr", "nanonets_ocr2", "deepseek_ocr"}
    assert vlm.get_variant(None).name == "granite_docling"
    with pytest.raises(ValueError):
        vlm.get_variant("smoldocling")
    v = vlm.get_variant("deepseek_ocr")
    assert v.engines == ("api_ollama",) and not v.mlx and v.response == "deepseekocr_markdown"
    assert vlm.default_engine(v, env="") == "api_ollama"
    assert vlm.default_engine(vlm.get_variant("glm_ocr"), env="transformers") == "transformers"
    assert vlm.default_engine(vlm.get_variant("glm_ocr"), env="auto") in ("mlx", "transformers")
    for v in vlm.VARIANTS.values():
        assert v.flavor and v.preset


def test_family_registered_with_vlm_pipeline():
    fam = profiles.get_family("vlm:glm_ocr")
    assert fam.name == "vlm" and fam.is_docling and not fam.runs_in_container
    assert set(vlm.VARIANTS) <= set(fam.variants)
    assert {"vlm", "vlm:granite_docling", "vlm:deepseek_ocr"} <= set(profiles.known_profiles())
    assert vlm.output_path("glm_ocr", "STATUTE-72-Pg983-2", Path("/d")) == Path("/d/doclang/vlm-glm_ocr/STATUTE-72-Pg983-2.json")
    assert vlm.timing_sidecar(Path("/d/doclang/vlm-glm_ocr/X.json")) == Path("/d/doclang/vlm-glm_ocr/X.timing.json")


def test_spec_mapping_uses_docling_presets():
    pytest.importorskip("docling")
    expected = {
        ("granite_docling", "mlx"): ("ibm-granite/granite-docling-258M-mlx", "doctags"),
        ("granite_docling", "transformers"): ("ibm-granite/granite-docling-258M", "doctags"),
        ("glm_ocr", "mlx"): ("mlx-community/GLM-OCR-bf16", "markdown"),
        ("glm_ocr", "transformers"): ("zai-org/GLM-OCR", "markdown"),
        ("lightonocr", "mlx"): ("mlx-community/LightOnOCR-2-1B-bf16", "markdown"),
        ("lightonocr", "transformers"): ("lightonai/LightOnOCR-2-1B", "markdown"),
        ("nanonets_ocr2", "mlx"): ("mlx-community/Nanonets-OCR2-3B-bf16", "markdown"),
        ("nanonets_ocr2", "transformers"): ("nanonets/Nanonets-OCR2-3B", "markdown"),
        ("deepseek_ocr", "api_ollama"): ("deepseek-ocr:3b", "deepseekocr_markdown"),
    }
    for (name, engine), (repo, fmt) in expected.items():
        s = vlm.spec_info(vlm.get_variant(name), engine)
        assert (s["repo_id"], s["response_format"]) == (repo, fmt), (name, engine, s)
        assert s["revision"] == "main" and s["max_new_tokens"] >= 4096 and s["scale"] == 2.0
    assert vlm.spec_info(vlm.get_variant("deepseek_ocr"), "api_ollama")["api_params"]["model"] == "deepseek-ocr:3b"
    with pytest.raises(ValueError):
        vlm.engine_options("vllm-serve")
    quant = vlm.spec_info(vlm.get_variant("nanonets_ocr2"), "mlx", repo_id="mlx-community/Nanonets-OCR2-3B-4bit")
    assert quant["repo_id"] == "mlx-community/Nanonets-OCR2-3B-4bit" and quant["repo_id_override"] == quant["repo_id"]
    assert quant["prompt"] == vlm.spec_info(vlm.get_variant("nanonets_ocr2"), "mlx")["prompt"] and quant["max_new_tokens"] == 15000
    assert vlm.spec_info(vlm.get_variant("nanonets_ocr2"), "transformers")["repo_id"] == "nanonets/Nanonets-OCR2-3B"  # untouched


def test_pipeline_options_and_converter_class():
    pytest.importorskip("docling")
    from docling.datamodel.pipeline_options import VlmPipelineOptions
    from docling.pipeline.vlm_pipeline import VlmPipeline

    opts = profiles.pipeline_options("vlm:lightonocr")
    assert isinstance(opts, VlmPipelineOptions)
    assert opts.generate_page_images is False and opts.generate_picture_images is False
    assert opts.vlm_options.model_spec.get_repo_id(opts.vlm_options.engine_options.engine_type).lower().startswith(("lightonai", "mlx-community"))
    cls = profiles.get_family("vlm").pipeline_cls()
    assert issubclass(cls, VlmPipeline) and cls is vlm._pipeline_cls()
    api = vlm._vlm_options("deepseek_ocr", engine="api_ollama", ollama_url="http://gpu:11434/v1/chat/completions")
    assert api.enable_remote_services is True and str(api.vlm_options.engine_options.url).startswith("http://gpu:11434")


def _doc_with_boxes():
    from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument, ProvenanceItem, Size

    doc = DoclingDocument(name="t")
    doc.add_page(page_no=1, size=Size(width=400, height=800))
    doc.add_page(page_no=2, size=Size(width=400, height=800))
    top_left = ProvenanceItem(page_no=1, bbox=BoundingBox(l=10, t=20, r=200, b=40, coord_origin=CoordOrigin.TOPLEFT), charspan=(0, 5))
    doc.add_text(label=DocItemLabel.PAGE_HEADER, text="72 STAT.", prov=top_left, content_layer="furniture")
    zero = lambda page: ProvenanceItem(page_no=page, bbox=BoundingBox(l=0, t=0, r=0, b=0), charspan=(0, 0))  # noqa: E731
    doc.add_text(label=DocItemLabel.TEXT, text="AN ACT", prov=zero(2))
    doc.add_text(label=DocItemLabel.TEXT, text="Be it enacted", prov=zero(2))
    doc.add_text(label=DocItemLabel.TEXT, text="Approved.", prov=zero(2))
    return doc


def test_finalize_document_normalizes_geometry_and_keeps_text():
    pytest.importorskip("docling_core")
    from docling_core.types.doc import CoordOrigin

    from pipeline import uslm

    doc = _doc_with_boxes()
    stats = vlm.finalize_document(doc)
    assert stats == {"items": 4, "text_chars": len("72 STAT.AN ACTBe it enactedApproved."), "synthesized_geometry": 3, "pages": 2}
    header = doc.texts[0].prov[0].bbox
    assert header.coord_origin == CoordOrigin.BOTTOMLEFT and header.t == 780 and header.b == 760
    boxes = [t.prov[0].bbox for t in doc.texts[1:]]
    assert all(b.coord_origin == CoordOrigin.BOTTOMLEFT and b.l == 40 and b.r == 360 for b in boxes)
    assert boxes[0].t > boxes[1].t > boxes[2].t and boxes[2].b > 0  # stacked in reading order
    pages = uslm.load_pages(doc)
    assert [it.text for it in pages[1].items] == ["AN ACT", "Be it enacted", "Approved."]
    assert all(it.kind == "body" for it in pages[1].items)
    assert pages[0].items == []  # furniture items stay in the JSON; the builder reads the body layer
    # a second pass changes nothing
    again = vlm.finalize_document(doc)
    assert again["synthesized_geometry"] == 0 and doc.texts[0].prov[0].bbox.t == 780


def test_write_outputs_and_notes(tmp_path):
    pytest.importorskip("docling_core")
    doc = _doc_with_boxes()
    stats = vlm.finalize_document(doc)
    timing = vlm.VlmTiming(stem="STATUTE-1-Pg1", variant="glm_ocr", engine="mlx", pages=2, seconds=10.0, model_seconds=8.0,
                           tokens=500, stats={**stats, "tier": "B", "era": "scanned-pre-1951"}, host={"node": "mac"},
                           page_times=[{"page": 1, "seconds": 1.0, "tokens": 4096, "stop_reason": "unspecified"},
                                       {"page": 2, "seconds": 7.0, "tokens": 400, "stop_reason": "stop_string"}],
                           spec=vlm.spec_info(vlm.get_variant("glm_ocr"), "mlx") if _has_docling() else
                           {"variant": "glm_ocr", "engine": "mlx", "preset": "glm_ocr", "repo_id": "r", "revision": "main",
                            "response_format": "markdown", "scale": 2.0, "max_size": None, "max_new_tokens": 4096})
    out = vlm.output_path("glm_ocr", timing.stem, tmp_path)
    written, sidecar = vlm.write_outputs(doc, timing, out)
    assert written == out and sidecar == tmp_path / "doclang" / "vlm-glm_ocr" / "STATUTE-1-Pg1.timing.json"
    data = json.loads(out.read_text())
    assert len(data["texts"]) == 4 and data["pages"]["2"]["size"]["height"] == 800 and "image" not in (data["pages"]["1"] or {}) or data["pages"]["1"].get("image") is None
    side = json.loads(sidecar.read_text())
    assert side["profile"] == "vlm:glm_ocr" and side["seconds_per_page"] == 5.0 and side["stats"]["synthesized_geometry"] == 3
    from docling_core.types.doc import DoclingDocument

    reloaded = DoclingDocument.load_from_json(out)
    assert [t.text for t in reloaded.texts] == [t.text for t in doc.texts]
    # notes from sidecars
    rows = vlm.load_timings(tmp_path, ["glm_ocr"])
    assert len(rows) == 1
    report = tmp_path / "r.md"
    report.write_text("# Benchmark x\n\n| a |\n\n## Notes\n\nold\n")
    vlm.append_notes(report, rows, extra="### Run\n\nextra line\n")
    text = report.read_text()
    assert text.count("## Notes") == 1 and "old" not in text and text.endswith("### Run\n\nextra line\n")
    assert "| glm_ocr | mlx | B | scanned-pre-1951 | 1 | 2 | 5.0 | 4.0 | 250 | 1 | 0 | 0 | 3 | mac |" in text
    # failed sidecars do not divide by zero
    failed = vlm.VlmTiming(stem="X", variant="glm_ocr", engine="mlx", status="failed", errors=["boom"])
    vlm.write_outputs(None, failed, vlm.output_path("glm_ocr", "X", tmp_path))
    assert not vlm.output_path("glm_ocr", "X", tmp_path).exists()
    notes = vlm.notes_markdown(vlm.load_timings(tmp_path, ["glm_ocr"]))
    assert "X [glm_ocr]: failed; boom" in notes


def _has_docling() -> bool:
    try:
        import docling  # noqa: F401
    except ImportError:
        return False
    return True


def test_select_units_filters(tmp_path, monkeypatch):
    pytest.importorskip("pypdfium2")
    img2pdf = pytest.importorskip("img2pdf")
    Image = pytest.importorskip("PIL.Image")
    gdir = tmp_path / "granules" / "STATUTE-9"
    gdir.mkdir(parents=True)
    pages = []
    for n in (1, 2):
        p = tmp_path / f"p{n}.png"
        Image.new("RGB", (100, 100), "white").save(p)
        pages.append(str(p))
    (gdir / "STATUTE-9-Pg1.pdf").write_bytes(img2pdf.convert(pages[:1], dpi=72))
    (gdir / "STATUTE-9-Pg2.pdf").write_bytes(img2pdf.convert(pages, dpi=72))
    entries = [
        {"granule_id": "STATUTE-9-Pg1", "granule_class": "PUBLICLAW", "era": "scanned-pre-1951"},
        {"granule_id": "STATUTE-9-Pg2", "granule_class": "TREATY", "era": "scanned-pre-1951"},
        {"granule_id": "STATUTE-9-Pg3", "granule_class": "PUBLICLAW", "era": "scanned-pre-1951"},  # no PDF
    ]
    units = vlm.select_units(entries, tmp_path)
    assert [u.stem for u in units] == ["STATUTE-9-Pg1", "STATUTE-9-Pg2"] and units[1].pages == 2
    assert [u.stem for u in vlm.select_units(entries, tmp_path, classes=["PUBLICLAW"])] == ["STATUTE-9-Pg1"]
    assert [u.stem for u in vlm.select_units(entries, tmp_path, max_pages=1)] == ["STATUTE-9-Pg1"]
    assert [u.stem for u in vlm.select_units(entries, tmp_path, granules=["STATUTE-9-Pg2"], limit=5)] == ["STATUTE-9-Pg2"]
    assert vlm.select_units(entries, tmp_path, tier_a=True) == []  # no born-digital entries
    assert vlm.build_parser().parse_args(["run", "--spec", "s.yaml", "--variant", "glm_ocr", "--max-pages", "3"]).max_pages == 3
    spec = tmp_path / "spec.yaml"
    spec.write_text("seed: 1\ngranules:\n" + "".join(f"- granule_id: {e['granule_id']}\n  granule_class: {e['granule_class']}\n  era: {e['era']}\n" for e in entries))
    out = tmp_path / "sub.yaml"
    assert vlm.main(["spec", "--spec", str(spec), "--out", str(out), "--classes", "PUBLICLAW", "--data-dir", str(tmp_path)]) == 0
    import yaml

    sub = yaml.safe_load(out.read_text())
    assert [g["granule_id"] for g in sub["granules"]] == ["STATUTE-9-Pg1"] and sub["seed"] == 1 and sub["source_spec"] == str(spec)


@pytest.mark.integration
def test_granite_docling_mlx_one_page(tmp_path):
    """Runs GraniteDocling through MLX on a generated one-page PDF; needs mlx-vlm and the cached model."""
    if not (vlm.is_apple_silicon() and vlm.mlx_available()):
        pytest.skip("MLX not available")
    pytest.importorskip("docling")
    from huggingface_hub import try_to_load_from_cache

    if not try_to_load_from_cache("ibm-granite/granite-docling-258M-mlx", "config.json"):
        pytest.skip("granite-docling MLX model not cached")
    img2pdf = pytest.importorskip("img2pdf")
    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")
    im = Image.new("RGB", (850, 1100), "white")
    ImageDraw.Draw(im).text((100, 100), "AN ACT\nTo provide for the relief of John Smith.", fill="black")
    png = tmp_path / "p.png"
    im.save(png)
    pdf = tmp_path / "one.pdf"
    pdf.write_bytes(img2pdf.convert([str(png)], dpi=100))
    v = vlm.get_variant("granite_docling")
    conv = vlm.make_vlm_converter(v, "mlx")
    doc, timing = vlm.convert_pdf(pdf, v, "mlx", conv, stem="one")
    assert timing.status != "failed" and timing.pages == 1 and timing.seconds > 0
    assert doc is not None and all(t.prov[0].bbox.coord_origin.value == "BOTTOMLEFT" for t in doc.texts)
