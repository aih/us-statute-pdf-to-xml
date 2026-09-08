"""VLM profiles (`vlm:<variant>`): Docling's VlmPipeline with a model preset, run outside the container.

    python -m pipeline.vlm run --spec benchmark/sample.yaml --variant granite_docling [--limit N] [--granule ID ...]
                               [--classes PUBLICLAW,PRIVATELAW] [--max-pages 3] [--tier-a] [--engine mlx]
                               [--time-budget MIN] [--force]
    python -m pipeline.vlm run --pdf path.pdf --stem NAME --variant glm_ocr
    python -m pipeline.vlm spec --spec benchmark/sample.yaml --classes PUBLICLAW,PRIVATELAW --max-pages 3 --out benchmark/sample_vlm.yaml
    python -m pipeline.vlm specs
    python -m pipeline.vlm notes --report data/reports/2026-09-08-wp9b-vlm.md

The runner reads granule PDFs and MODS from data/granules/STATUTE-{v}/ and needs no database. Output per unit:
data/doclang/vlm-<variant>/{stem}.json (compact DoclingDocument, as pipeline.convert writes it) and
{stem}.timing.json (pages, wall seconds, model seconds, tokens per page, model spec, host). The container then
scores the JSON: `python -m benchmark.evaluate --profiles vlm:<variant> --rebuild ...`. `--tier-a` converts the
clean raster of each born-digital granule (data/raster/{id}/{id}.clean.pdf) under the stem `{id}_A-clean`.
`spec` writes the same selection (`--classes`, `--max-pages`, `--granule`, `--limit`) as a sample spec for
benchmark.evaluate, so scoring covers exactly the converted granules.

Variants map to Docling 2.126 `VlmConvertOptions` presets (`python -m pipeline.vlm specs` prints repo ids):

    granite_docling   DocTags with bounding boxes from the model; MLX build on Apple silicon
    glm_ocr           markdown; MLX build on Apple silicon
    lightonocr        markdown; MLX build on Apple silicon
    nanonets_ocr2     markdown; MLX build on Apple silicon
    deepseek_ocr      grounded markdown through an Ollama server; Docling 2.126 has no inline engine for it,
                      so it runs on HF Jobs (benchmark.jobs)

Document normalization (StatuteVlmPipeline): bounding boxes are stored with a bottom-left origin, as the standard
pipeline stores them; items a markdown model returns without geometry get a synthesized box (full column width,
stacked in reading order down the page) and the sidecar counts them under `synthesized_geometry`; page images are
dropped. Every text item the model returned is kept. The preset's render scale is used (2.0, about 144 dpi;
`--dpi` of pipeline.convert does not apply).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from downloader.config import DATA_DIR, LOG_DIR, setup_logging
from pipeline import profiles
from pipeline.profiles import DEFAULT_DPI, ProfileFamily, register_family

logger = logging.getLogger("vlm")

FAMILY = "vlm"
DEFAULT_VARIANT = "granite_docling"
DEFAULT_RASTER_VARIANT = "clean"
ENGINE_ENV = "VLM_ENGINE"  # overrides the engine chosen for the host (mlx | transformers | api_ollama | auto)


@dataclass(frozen=True)
class VlmVariant:
    name: str
    preset: str  # Docling VlmConvertOptions preset id
    description: str
    engines: tuple[str, ...]  # usable Docling engines, preferred first for a GPU host
    mlx: bool  # has an MLX checkpoint (runs on Apple silicon)
    flavor: str  # HF Jobs hardware for benchmark.jobs
    response: str  # doctags | markdown | deepseekocr_markdown


VARIANTS: dict[str, VlmVariant] = {
    v.name: v
    for v in (
        VlmVariant("granite_docling", "granite_docling", "IBM Granite-Docling 258M, DocTags with geometry",
                   ("transformers",), mlx=True, flavor="t4-small", response="doctags"),
        VlmVariant("glm_ocr", "glm_ocr", "Zhipu GLM-OCR 0.9B, markdown", ("transformers",), mlx=True, flavor="l4x1",
                   response="markdown"),
        VlmVariant("lightonocr", "lightonocr", "LightOn LightOnOCR-2 1B, markdown", ("transformers",), mlx=True,
                   flavor="l4x1", response="markdown"),
        VlmVariant("nanonets_ocr2", "nanonets_ocr2", "Nanonets-OCR2 3B, markdown", ("transformers",), mlx=True,
                   flavor="l4x1", response="markdown"),
        VlmVariant("deepseek_ocr", "deepseek_ocr", "DeepSeek-OCR 3B through Ollama, grounded markdown with geometry",
                   ("api_ollama",), mlx=False, flavor="l4x1", response="deepseekocr_markdown"),
    )
}


def get_variant(name: Optional[str]) -> VlmVariant:
    name = name or DEFAULT_VARIANT
    if name not in VARIANTS:
        raise ValueError(f"unknown vlm variant {name!r}; known: {', '.join(VARIANTS)}")
    return VARIANTS[name]


def is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def mlx_available() -> bool:
    try:
        import mlx_vlm  # noqa: F401
    except Exception:
        return False
    return True


def default_engine(variant: VlmVariant, env: Optional[str] = None) -> str:
    """Engine for this host: `VLM_ENGINE` when set, MLX on Apple silicon for variants with an MLX checkpoint,
    else the variant's first engine."""
    env = env if env is not None else os.getenv(ENGINE_ENV, "")
    if env and env != "auto":
        return env
    if variant.mlx and is_apple_silicon() and mlx_available():
        return "mlx"
    return variant.engines[0]


def engine_options(engine: str, ollama_url: Optional[str] = None):
    """Docling engine options for an engine name (mlx | transformers | api_ollama | auto)."""
    from docling.datamodel.vlm_engine_options import (
        ApiVlmEngineOptions,
        AutoInlineVlmEngineOptions,
        MlxVlmEngineOptions,
        TransformersVlmEngineOptions,
    )
    from docling.models.inference_engines.vlm.base import VlmEngineType

    if engine == "mlx":
        return MlxVlmEngineOptions()
    if engine == "transformers":
        return TransformersVlmEngineOptions(load_in_8bit=False)  # bf16 weights as the presets declare; no bitsandbytes
    if engine == "api_ollama":
        kwargs = {"engine_type": VlmEngineType.API_OLLAMA, "timeout": 600.0}
        if ollama_url:
            kwargs["url"] = ollama_url
        return ApiVlmEngineOptions(**kwargs)
    if engine == "auto":
        return AutoInlineVlmEngineOptions()
    raise ValueError(f"unknown engine {engine!r}; expected mlx, transformers, api_ollama, or auto")


def convert_options(variant: VlmVariant, engine: str, ollama_url: Optional[str] = None, repo_id: Optional[str] = None):
    """The preset's VlmConvertOptions for an engine. `repo_id` replaces the checkpoint the preset names for that
    engine (for example a quantized MLX build); prompt, response format, and limits stay the preset's."""
    from docling.datamodel.pipeline_options import VlmConvertOptions

    vc = VlmConvertOptions.from_preset(variant.preset, engine_options=engine_options(engine, ollama_url))
    if repo_id:
        from docling.datamodel.stage_model_specs import EngineModelConfig

        et = vc.engine_options.engine_type
        current = vc.model_spec.engine_overrides.get(et)
        override = current.model_copy(update={"repo_id": repo_id}) if current is not None else EngineModelConfig(repo_id=repo_id)
        vc.model_spec = vc.model_spec.model_copy(update={"engine_overrides": {**vc.model_spec.engine_overrides, et: override}})
    return vc


def spec_info(variant: VlmVariant, engine: str, repo_id: Optional[str] = None) -> dict:
    """Model spec actually used for a variant and engine: preset, repo id, revision, prompt, limits."""
    vc = convert_options(variant, engine, repo_id=repo_id)
    et = vc.engine_options.engine_type
    spec = vc.model_spec
    return {
        "variant": variant.name, "preset": variant.preset, "engine": et.value, "repo_id": spec.get_repo_id(et),
        "revision": spec.get_revision(et), "response_format": spec.response_format.value, "scale": vc.scale,
        "max_size": vc.max_size, "max_new_tokens": spec.max_new_tokens, "prompt": spec.prompt,
        "api_params": spec.get_api_params(et) if et.value.startswith("api") else None,
        "repo_id_override": repo_id or None,
    }


def _vlm_options(variant: Optional[str] = None, dpi: int = DEFAULT_DPI, num_threads: int = 2,
                 artifacts_path: Optional[str] = None, engine: Optional[str] = None, ollama_url: Optional[str] = None,
                 repo_id: Optional[str] = None):
    """VlmPipelineOptions for a variant: the preset's model spec and scale, no stored page images, no OCR stages.
    `dpi` is accepted for the profile interface and not used (the preset's `scale` sets the render resolution)."""
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.pipeline_options import VlmPipelineOptions

    v = get_variant(variant)
    engine = engine or default_engine(v)
    opts = VlmPipelineOptions(vlm_options=convert_options(v, engine, ollama_url, repo_id))
    opts.artifacts_path = artifacts_path or os.getenv("DOCLING_ARTIFACTS_PATH") or None
    opts.accelerator_options = AcceleratorOptions(num_threads=num_threads)
    opts.generate_page_images = False
    opts.generate_picture_images = False
    opts.enable_remote_services = engine.startswith("api")
    return opts


_PIPELINE_CLS: Optional[type] = None
STATS_ATTR = "_statute_vlm_stats"  # finalize_document counts, attached to the DoclingDocument for convert_pdf


def _pipeline_cls():
    global _PIPELINE_CLS
    if _PIPELINE_CLS is None:
        from docling.pipeline.vlm_pipeline import VlmPipeline

        class StatuteVlmPipeline(VlmPipeline):
            """VlmPipeline whose documents are normalized for the USLM builder (see finalize_document)."""

            def _assemble_document(self, conv_res):
                conv_res = super()._assemble_document(conv_res)
                if conv_res.document is not None:
                    object.__setattr__(conv_res.document, STATS_ATTR, finalize_document(conv_res.document))
                return conv_res

        _PIPELINE_CLS = StatuteVlmPipeline
    return _PIPELINE_CLS


register_family(ProfileFamily(
    FAMILY, "Docling VlmPipeline with a model preset (MLX on Apple silicon, transformers or Ollama elsewhere)",
    options=_vlm_options, variants=tuple(VARIANTS), pipeline_cls=_pipeline_cls, runs_in_container=False,
))


# ---------------------------------------------------------------------------- document normalization


def _is_empty_box(bbox) -> bool:
    return bbox.l == bbox.r == bbox.t == bbox.b == 0


def finalize_document(doc) -> dict:
    """Normalize a VlmPipeline document in place: bottom-left origin boxes, synthesized boxes for items without
    geometry, no page images. Returns counts: items, text_chars, synthesized_geometry, pages."""
    from docling_core.types.doc import BoundingBox, ContentLayer, CoordOrigin, DocItem

    stats = {"items": 0, "text_chars": 0, "synthesized_geometry": 0, "pages": len(doc.pages)}
    for page in doc.pages.values():
        page.image = None
    missing: dict[int, list] = defaultdict(list)
    for item, _level in doc.iterate_items(with_groups=False, traverse_pictures=True, included_content_layers=set(ContentLayer)):
        if not isinstance(item, DocItem) or not item.prov:
            continue
        stats["items"] += 1
        stats["text_chars"] += len(getattr(item, "text", "") or "")
        for prov in item.prov:
            page = doc.pages.get(prov.page_no)
            height = float(page.size.height) if page is not None else 792.0
            if _is_empty_box(prov.bbox):
                missing[prov.page_no].append(prov)
            elif prov.bbox.coord_origin == CoordOrigin.TOPLEFT:
                prov.bbox = prov.bbox.to_bottom_left_origin(height)
    for page_no, provs in missing.items():
        page = doc.pages.get(page_no)
        width = float(page.size.width) if page is not None else 612.0
        height = float(page.size.height) if page is not None else 792.0
        slot = 0.87 * height / len(provs)
        for i, prov in enumerate(provs):
            top = 0.95 * height - i * slot
            prov.bbox = BoundingBox(l=0.1 * width, r=0.9 * width, t=top, b=top - slot, coord_origin=CoordOrigin.BOTTOMLEFT)
            stats["synthesized_geometry"] += 1
    return stats


# ---------------------------------------------------------------------------- conversion


@dataclass
class VlmTiming:
    stem: str
    variant: str
    engine: str
    status: str = "success"
    pages: int = 0
    seconds: float = 0.0  # wall time of the conversion call
    model_seconds: float = 0.0  # generation time reported by the engine, summed over pages
    tokens: int = 0
    page_times: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    spec: dict = field(default_factory=dict)
    granule_id: Optional[str] = None
    input: Optional[str] = None
    input_sha256: Optional[str] = None
    started: Optional[str] = None
    model_load_seconds: Optional[float] = None  # set on the first unit of a run: converter creation, download, load
    host: dict = field(default_factory=dict)
    versions: dict = field(default_factory=dict)

    @property
    def seconds_per_page(self) -> Optional[float]:
        return self.seconds / self.pages if self.pages else None

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["seconds_per_page"] = self.seconds_per_page
        d["profile"] = f"{FAMILY}:{self.variant}"
        return d


def host_info() -> dict:
    return {"node": platform.node(), "system": platform.system(), "machine": platform.machine(),
            "python": platform.python_version()}


def versions() -> dict:
    import importlib.metadata as md

    out = {}
    for name in ("docling", "docling-core", "mlx-vlm", "mlx", "transformers", "torch"):
        try:
            out[name] = md.version(name)
        except md.PackageNotFoundError:
            pass
    return out


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_vlm_converter(variant: VlmVariant, engine: str, num_threads: int = 2, ollama_url: Optional[str] = None,
                       repo_id: Optional[str] = None):
    """DocumentConverter for a variant and engine; one instance loads the model once and converts many PDFs."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.settings import settings
    from docling.document_converter import DocumentConverter, PdfFormatOption

    settings.debug.profile_pipeline_timings = True
    opts = _vlm_options(variant.name, num_threads=num_threads, engine=engine, ollama_url=ollama_url, repo_id=repo_id)
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts, pipeline_cls=_pipeline_cls())})
    converter.initialize_pipeline(InputFormat.PDF)  # download and load the model now, not inside the first conversion
    return converter


def convert_pdf(pdf: Path | str, variant: VlmVariant, engine: str, converter, stem: Optional[str] = None,
                page_range: Optional[tuple[int, int]] = None, granule_id: Optional[str] = None):
    """Convert one PDF; returns (DoclingDocument or None, VlmTiming)."""
    pdf = Path(pdf)
    timing = VlmTiming(stem=stem or pdf.stem, variant=variant.name, engine=engine, granule_id=granule_id, input=str(pdf),
                       input_sha256=sha256_file(pdf), started=datetime.now().isoformat(timespec="seconds"),
                       host=host_info(), versions=versions())
    kwargs = {"page_range": page_range} if page_range else {}
    started = time.monotonic()
    try:
        res = converter.convert(str(pdf), raises_on_error=False, **kwargs)
    except Exception as exc:
        timing.status, timing.seconds = "failed", time.monotonic() - started
        timing.errors.append(f"{type(exc).__name__}: {exc}")
        return None, timing
    timing.seconds = time.monotonic() - started
    timing.errors = [f"page {e.page_no}: {e.error_message}" if e.page_no else e.error_message for e in res.errors]
    status = str(res.status.value) if hasattr(res.status, "value") else str(res.status)
    doc = res.document
    if doc is None or status == "failure":
        timing.status = "failed"
        return None, timing
    timing.status = "success" if status == "success" else "partial"
    for page in res.pages:
        r = page.predictions.vlm_response
        if r is None:
            timing.page_times.append({"page": page.page_no, "seconds": None, "tokens": None, "stop_reason": "none"})
            continue
        gen = float(r.generation_time) if r.generation_time and r.generation_time > 0 else 0.0
        timing.model_seconds += gen
        timing.tokens += int(r.num_tokens or 0)
        timing.page_times.append({"page": page.page_no, "seconds": round(gen, 2), "tokens": r.num_tokens,
                                  "stop_reason": getattr(r.stop_reason, "value", str(r.stop_reason))})
    timing.pages = len(doc.pages)
    timing.stats = dict(getattr(doc, STATS_ATTR, None) or finalize_document(doc))
    return doc, timing


def write_outputs(doc, timing: VlmTiming, doclang_path: Path | str) -> tuple[Optional[Path], Path]:
    """Write the compact DoclingDocument JSON (when there is a document) and the timing sidecar next to it."""
    doclang_path = Path(doclang_path)
    doclang_path.parent.mkdir(parents=True, exist_ok=True)
    written = None
    if doc is not None:
        doclang_path.write_text(json.dumps(doc.export_to_dict(), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        written = doclang_path
    timing_path = timing_sidecar(doclang_path)
    timing_path.write_text(json.dumps(timing.as_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
    return written, timing_path


def timing_sidecar(doclang_path: Path | str) -> Path:
    p = Path(doclang_path)
    return p.with_name(f"{p.stem}.timing.json")


def output_path(variant: str, stem: str, data_dir: Path = DATA_DIR) -> Path:
    from pipeline.convert import profile_dirname

    return Path(data_dir) / "doclang" / profile_dirname(f"{FAMILY}:{variant}") / f"{stem}.json"


# ---------------------------------------------------------------------------- units from the sample spec


@dataclass
class VlmUnit:
    stem: str
    pdf: Path
    granule_id: Optional[str] = None
    granule_class: Optional[str] = None
    era: Optional[str] = None
    pages: Optional[int] = None
    tier: str = "B"


def pdf_page_count(pdf: Path | str) -> int:
    import pypdfium2 as pdfium

    return len(pdfium.PdfDocument(str(pdf)))


def granule_identity(granule_id: str, data_dir: Path = DATA_DIR) -> tuple[Path, dict]:
    """PDF path and MODS fields (downloader.mods.parse_mods) for a granule under data/granules/."""
    from downloader.fetch_granules import granule_paths
    from downloader.mods import parse_mods

    pdf, mods = granule_paths(granule_id, Path(data_dir) / "granules")
    meta = parse_mods(mods.read_bytes()) if mods.exists() else {}
    return pdf, meta


def load_spec_entries(spec_path: str) -> list[dict]:
    from downloader.fetch_granules import load_spec

    return load_spec(spec_path)


def select_units(entries: list[dict], data_dir: Path = DATA_DIR, granules: Optional[list[str]] = None,
                 classes: Optional[list[str]] = None, max_pages: Optional[int] = None, limit: Optional[int] = None,
                 tier_a: bool = False, raster_variant: str = DEFAULT_RASTER_VARIANT) -> list[VlmUnit]:
    """Units for the spec entries with a downloaded PDF, filtered by id, class, and PDF page count.
    With `tier_a`, born-digital entries are replaced by their clean raster (`{id}_A-{variant}`)."""
    units: list[VlmUnit] = []
    wanted = set(granules or [])
    for e in entries:
        gid = e["granule_id"]
        if wanted and gid not in wanted:
            continue
        if classes and e.get("granule_class") not in classes:
            continue
        pdf, meta = granule_identity(gid, data_dir)
        if not pdf.exists():
            logger.warning("%s: %s missing (run benchmark.evaluate or downloader.fetch_granules first)", gid, pdf)
            continue
        pages = pdf_page_count(pdf)
        if max_pages and pages > max_pages:
            continue
        unit = VlmUnit(stem=gid, pdf=pdf, granule_id=gid, granule_class=e.get("granule_class") or meta.get("granule_class"),
                       era=e.get("era"), pages=pages)
        if tier_a:
            if e.get("era") != "digital-2003+":
                continue
            from benchmark import rasterize

            r = rasterize.rasterize(pdf, gid, out_root=Path(data_dir) / "raster", variants=(raster_variant,))
            unit = VlmUnit(stem=f"{gid}_A-{raster_variant}", pdf=r.pdfs[raster_variant], granule_id=gid,
                           granule_class=unit.granule_class, era=unit.era, pages=len(r.pages), tier="A")
        units.append(unit)
    if limit:
        units = units[:limit]
    return units


def run_units(units: list[VlmUnit], variant: VlmVariant, engine: str, data_dir: Path = DATA_DIR, force: bool = False,
              num_threads: int = 2, time_budget_s: Optional[float] = None, ollama_url: Optional[str] = None,
              repo_id: Optional[str] = None) -> list[VlmTiming]:
    """Convert units one after another with one converter; skip units whose JSON and sidecar exist unless `force`.
    Stops starting new units once `time_budget_s` of wall time has passed."""
    todo = []
    results: list[VlmTiming] = []
    for u in units:
        out = output_path(variant.name, u.stem, data_dir)
        if not force and out.exists() and timing_sidecar(out).exists():
            logger.info("%s: skip (exists: %s)", u.stem, out)
            continue
        todo.append((u, out))
    if not todo:
        return results
    logger.info("vlm:%s [%s]: %d unit(s), %d page(s)", variant.name, engine, len(todo), sum(u.pages or 0 for u, _ in todo))
    t_load = time.monotonic()
    converter = make_vlm_converter(variant, engine, num_threads=num_threads, ollama_url=ollama_url, repo_id=repo_id)
    started = time.monotonic()
    load_seconds: Optional[float] = started - t_load
    for u, out in todo:
        if time_budget_s and time.monotonic() - started > time_budget_s:
            logger.warning("time budget reached; %s and later units not started", u.stem)
            break
        doc, timing = convert_pdf(u.pdf, variant, engine, converter, stem=u.stem, granule_id=u.granule_id)
        timing.spec = spec_info(variant, engine, repo_id)
        timing.model_load_seconds, load_seconds = load_seconds, None
        timing.stats.update({"granule_class": u.granule_class, "era": u.era, "tier": u.tier})
        write_outputs(doc, timing, out)
        results.append(timing)
        if timing.status == "failed":
            logger.error("%s: failed: %s", u.stem, "; ".join(timing.errors)[:300])
        else:
            logger.info("%s: %s, %d page(s) in %.0fs (%.1f s/page, model %.0fs, %d tokens, %d items, %d synthesized boxes)%s",
                        u.stem, timing.status, timing.pages, timing.seconds, timing.seconds_per_page or 0, timing.model_seconds,
                        timing.tokens, timing.stats.get("items", 0), timing.stats.get("synthesized_geometry", 0),
                        f"; errors: {timing.errors[0][:120]}" if timing.errors else "")
    logger.info("model load %.0fs; %d unit(s) converted", started - t_load, len(results))
    return results


def write_subset_spec(spec_path: str, out: Path, granule_ids: list[str]) -> Path:
    """Copy of a sample spec restricted to `granule_ids` (order kept)."""
    import yaml

    data = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8"))
    keep = set(granule_ids)
    data["granules"] = [g for g in data["granules"] if g["granule_id"] in keep]
    data["source_spec"] = str(spec_path)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------- report notes


def load_timings(data_dir: Path = DATA_DIR, variants: Optional[list[str]] = None) -> list[dict]:
    rows = []
    for name in variants or list(VARIANTS):
        d = output_path(name, "x", data_dir).parent
        for p in sorted(d.glob("*.timing.json")) if d.exists() else []:
            try:
                rows.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception as exc:
                logger.warning("%s: unreadable sidecar (%s)", p, exc)
    return rows


def capped_pages(row: dict) -> int:
    """Pages whose generation reached the spec's max_new_tokens (the MLX engine reports no `length` stop reason)."""
    limit = (row.get("spec") or {}).get("max_new_tokens")
    return sum(1 for p in row.get("page_times") or [] if (p.get("stop_reason") == "length") or
               (limit and p.get("tokens") and p["tokens"] >= limit))


def notes_markdown(rows: list[dict]) -> str:
    """Wall time per page per variant, engine, and tier from the timing sidecars, plus the specs used."""
    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for r in rows:
        st = r.get("stats") or {}
        groups[(r["variant"], r["engine"], st.get("tier") or "B", st.get("era") or "?")].append(r)
    lines = ["## Notes", "",
             "Model wall time per page from the `.timing.json` sidecars written by `pipeline.vlm` (the s/page column above is "
             "the `--rebuild` time). Wall seconds include page rendering and parsing; model seconds are the engine's "
             "generation time. Capped pages stopped at the model's `max_new_tokens`. Host names the machine that ran the model.", "",
             "| Variant | Engine | Tier | Era | Units | Pages | Wall s/page | Model s/page | Tokens/page | Capped pages | Partial | Failed | Synthesized boxes | Host |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(groups):
        rs = groups[key]
        ok = [r for r in rs if r["status"] != "failed"]
        pages = sum(r["pages"] for r in ok)
        wall = sum(r["seconds"] for r in ok)
        model = sum(r["model_seconds"] for r in ok)
        tokens = sum(r["tokens"] for r in ok)
        synth = sum((r.get("stats") or {}).get("synthesized_geometry", 0) for r in ok)
        capped = sum(capped_pages(r) for r in ok)
        hosts = sorted({(r.get("host") or {}).get("node") or "?" for r in rs})
        lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {key[3]} | {len(rs)} | {pages} | "
                     f"{wall / pages:.1f} | {model / pages:.1f} | {tokens / pages:.0f} | " if pages else
                     f"| {key[0]} | {key[1]} | {key[2]} | {key[3]} | {len(rs)} | 0 | - | - | - | ")
        lines[-1] += (f"{capped} | {sum(1 for r in rs if r['status'] == 'partial')} | {sum(1 for r in rs if r['status'] == 'failed')} | "
                      f"{synth} | {', '.join(hosts)} |")
    specs = {}
    for r in rows:
        s = r.get("spec") or {}
        if s:
            specs[(s["variant"], s["engine"])] = s
    if specs:
        lines += ["", "| Variant | Engine | Preset | Model | Revision | Response | Scale | Max size | Max new tokens |", "|---|---|---|---|---|---|---|---|---|"]
        for key in sorted(specs):
            s = specs[key]
            lines.append(f"| {s['variant']} | {s['engine']} | {s['preset']} | {s['repo_id']} | {s['revision']} | {s['response_format']} | "
                         f"{s['scale']} | {s.get('max_size') or '-'} | {s['max_new_tokens']} |")
    partial = [r for r in rows if r["status"] == "partial" or r.get("errors")]
    if partial:
        lines += ["", "Conversions with errors or truncated pages:", ""]
        for r in sorted(partial, key=lambda r: (r["variant"], r["stem"])):
            lines.append(f"- {r['stem']} [{r['variant']}]: {r['status']}; " + "; ".join(r.get("errors") or [])[:300])
    return "\n".join(lines) + "\n"


def append_notes(report: Path, rows: list[dict], extra: Optional[str] = None) -> None:
    """Replace or add the report's `## Notes` section: the timing tables, then `extra` markdown."""
    text = report.read_text(encoding="utf-8")
    marker = "\n## Notes\n"
    if marker in text:
        text = text[: text.index(marker) + 1]
    notes = notes_markdown(rows) + (("\n" + extra.strip() + "\n") if extra else "")
    report.write_text(text.rstrip("\n") + "\n\n" + notes, encoding="utf-8")


# ---------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m pipeline.vlm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="convert granule PDFs with a VLM variant")
    r.add_argument("--spec", help="YAML sample spec")
    r.add_argument("--variant", default=DEFAULT_VARIANT, choices=sorted(VARIANTS))
    r.add_argument("--engine", default=None, help="mlx | transformers | api_ollama | auto (default: per host)")
    r.add_argument("--ollama-url", default=None, help="chat completions URL for api_ollama")
    r.add_argument("--repo-id", default=None, help="checkpoint replacing the preset's for this engine (e.g. a 4-bit MLX build)")
    r.add_argument("--granule", action="append", default=[], help="granule id from the spec (repeatable)")
    r.add_argument("--classes", default=None, help="comma-separated granule classes to keep")
    r.add_argument("--max-pages", type=int, default=None, help="skip granules whose PDF has more pages")
    r.add_argument("--limit", type=int, default=None, help="at most N units")
    r.add_argument("--tier-a", action="store_true", help="convert the clean rasters of the born-digital granules")
    r.add_argument("--raster-variant", default=DEFAULT_RASTER_VARIANT, choices=("clean", "degraded"))
    r.add_argument("--pdf", help="a single PDF instead of a spec")
    r.add_argument("--stem", help="output stem for --pdf (default: file stem)")
    r.add_argument("--page-range", default=None, help="e.g. 1-2, for --pdf")
    r.add_argument("--time-budget", type=float, default=None, help="minutes; no new unit starts after this")
    r.add_argument("--threads", type=int, default=2)
    r.add_argument("--force", action="store_true")
    r.add_argument("--data-dir", default=str(DATA_DIR))
    r.add_argument("--log-dir", default=str(LOG_DIR))
    w = sub.add_parser("spec", help="write the selected granules as a sample spec for benchmark.evaluate")
    w.add_argument("--spec", required=True)
    w.add_argument("--out", required=True)
    w.add_argument("--granule", action="append", default=[])
    w.add_argument("--classes", default=None)
    w.add_argument("--max-pages", type=int, default=None)
    w.add_argument("--limit", type=int, default=None)
    w.add_argument("--data-dir", default=str(DATA_DIR))
    s = sub.add_parser("specs", help="print the model spec per variant and engine")
    s.add_argument("--engine", default=None)
    n = sub.add_parser("notes", help="append the timing notes section to an evaluate report")
    n.add_argument("--report", required=True)
    n.add_argument("--data-dir", default=str(DATA_DIR))
    n.add_argument("--variants", default=None, help="comma-separated (default all)")
    n.add_argument("--extra", default=None, help="markdown file appended after the tables")
    return p


def cmd_run(args) -> int:
    setup_logging("vlm", args.log_dir)
    data_dir = Path(args.data_dir)
    variant = get_variant(args.variant)
    engine = args.engine or default_engine(variant)
    if args.pdf:
        from pipeline.convert import parse_page_range

        pdf = Path(args.pdf)
        stem = args.stem or pdf.stem
        out = output_path(variant.name, stem, data_dir)
        converter = make_vlm_converter(variant, engine, num_threads=args.threads, ollama_url=args.ollama_url, repo_id=args.repo_id)
        doc, timing = convert_pdf(pdf, variant, engine, converter, stem=stem, page_range=parse_page_range(args.page_range))
        timing.spec = spec_info(variant, engine, args.repo_id)
        write_outputs(doc, timing, out)
        logger.info("%s: %s, %d page(s) in %.0fs -> %s", stem, timing.status, timing.pages, timing.seconds, out)
        return 0 if timing.status != "failed" else 1
    if not args.spec:
        logger.error("nothing to convert (use --spec or --pdf)")
        return 2
    classes = [c.strip() for c in args.classes.split(",")] if args.classes else None
    units = select_units(load_spec_entries(args.spec), data_dir, granules=args.granule or None, classes=classes,
                         max_pages=args.max_pages, limit=args.limit, tier_a=args.tier_a, raster_variant=args.raster_variant)
    if not units:
        logger.error("no units selected")
        return 2
    results = run_units(units, variant, engine, data_dir, force=args.force, num_threads=args.threads,
                        time_budget_s=args.time_budget * 60 if args.time_budget else None, ollama_url=args.ollama_url,
                        repo_id=args.repo_id)
    ok = [r for r in results if r.status != "failed"]
    pages = sum(r.pages for r in ok)
    secs = sum(r.seconds for r in ok)
    logger.info("done: %d converted (%d partial), %d failed, %d page(s), %.0fs, %.1f s/page", len(ok),
                sum(1 for r in ok if r.status == "partial"), len(results) - len(ok), pages, secs, secs / pages if pages else 0)
    return 1 if len(results) - len(ok) else 0


def cmd_specs(args) -> int:
    print("| Variant | Engine | Preset | Model | Revision | Response | Scale | Max size | Max new tokens | HF Jobs flavor |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for v in VARIANTS.values():
        engines = [args.engine] if args.engine else ((["mlx"] if v.mlx else []) + list(v.engines))
        for engine in engines:
            s = spec_info(v, engine)
            print(f"| {v.name} | {engine} | {s['preset']} | {s['repo_id']} | {s['revision']} | {s['response_format']} | "
                  f"{s['scale']} | {s['max_size'] or '-'} | {s['max_new_tokens']} | {v.flavor} |")
    return 0


def cmd_spec(args) -> int:
    classes = [c.strip() for c in args.classes.split(",")] if args.classes else None
    units = select_units(load_spec_entries(args.spec), Path(args.data_dir), granules=args.granule or None, classes=classes,
                         max_pages=args.max_pages, limit=args.limit)
    out = write_subset_spec(args.spec, Path(args.out), [u.granule_id for u in units if u.granule_id])
    print(f"{len(units)} granule(s), {sum(u.pages or 0 for u in units)} page(s) -> {out}")
    return 0 if units else 2


def cmd_notes(args) -> int:
    variants = [v.strip() for v in args.variants.split(",")] if args.variants else None
    rows = load_timings(Path(args.data_dir), variants)
    append_notes(Path(args.report), rows, Path(args.extra).read_text(encoding="utf-8") if args.extra else None)
    print(f"{len(rows)} sidecar(s) -> {args.report}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return {"run": cmd_run, "spec": cmd_spec, "specs": cmd_specs, "notes": cmd_notes}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
