"""Conversion profiles: how a PDF (or its page images) becomes a DoclingDocument.

A profile name is `family` or `family:variant`. The registry maps a family to a `ProfileFamily` whose
`options(variant, dpi, num_threads, artifacts_path)` returns Docling `PdfPipelineOptions`. Families
that do not run through Docling (Claude transcription) set `converter` instead and are run by
`pipeline.convert` through that callable. Each profile writes `data/doclang/{profile}/{id}.json` and
`data/generated_xmls/{profile}/{id}.xml`, and `conversions.module_used` carries the profile name.

Built-in families:

    scanned      Tesseract CLI through Docling, orientation detection disabled (pipeline.tesseract),
                 300 dpi, Tesseract page segmentation by variant (`scanned:psm4`, `scanned:psm6`; default automatic)
    digital      no OCR, Docling layout over the PDF text layer

Other modules register their families at import through `register_family`; `FAMILY_MODULES` lists
the modules `load_families()` imports, so a family added in a new module needs one entry here and
nothing else.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from downloader.config import is_scanned_volume

DEFAULT_DPI = 300
DEFAULT_PSM: Optional[int] = None  # Tesseract's own default (3, automatic page segmentation)

# Modules that call register_family() at import time. Missing modules are ignored.
FAMILY_MODULES = (
    "pipeline.textlayer",
    "pipeline.ocr_engines",
    "pipeline.vlm",
    "pipeline.claude_ocr",
    "pipeline.hybrid",
)


@dataclass
class ProfileFamily:
    name: str
    description: str
    # Docling families: build PdfPipelineOptions for a variant.
    options: Optional[Callable[..., object]] = None
    # Non-Docling families: convert(pdf_path, variant, page_range, identity=..., dpi=...) -> DoclingDocument.
    converter: Optional[Callable[..., object]] = None
    # Families that produce USLM themselves (the hybrid builder):
    # uslm_builder(pdf_path, variant, page_range, identity=..., doclang_path=..., xml_path=...) -> (lxml tree, stats dict)
    uslm_builder: Optional[Callable[..., object]] = None
    variants: tuple[str, ...] = ()
    runs_in_container: bool = True
    # Docling input format override: a family that consumes page images sets "image".
    input_kind: str = "pdf"
    extra: dict = field(default_factory=dict)

    @property
    def is_docling(self) -> bool:
        return self.options is not None

    @property
    def builds_uslm(self) -> bool:
        return self.uslm_builder is not None


_FAMILIES: dict[str, ProfileFamily] = {}
_LOADED = False


def register_family(family: ProfileFamily) -> ProfileFamily:
    _FAMILIES[family.name] = family
    return family


def load_families() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    for module in FAMILY_MODULES:
        try:
            importlib.import_module(module)
        except ModuleNotFoundError as exc:
            if exc.name != module:
                raise


def families() -> dict[str, ProfileFamily]:
    load_families()
    return dict(_FAMILIES)


def parse_profile(profile: str) -> tuple[str, Optional[str]]:
    """'tesseract:psm6' -> ('tesseract', 'psm6'); 'digital' -> ('digital', None)."""
    family, _, variant = profile.partition(":")
    family = family.strip()
    if not family:
        raise ValueError(f"empty profile name {profile!r}")
    return family, (variant.strip() or None)


def get_family(profile: str) -> ProfileFamily:
    family, _ = parse_profile(profile)
    fams = families()
    if family not in fams:
        raise ValueError(f"unknown profile {profile!r}; known families: {', '.join(sorted(fams))}")
    return fams[family]


def known_profiles() -> list[str]:
    out = []
    for fam in families().values():
        out.append(fam.name)
        out.extend(f"{fam.name}:{v}" for v in fam.variants)
    return out


def profile_for_volume(volume: Optional[int]) -> str:
    """Volumes 1 to 116 are scanned images; 117 onward and every PLAW file are born digital."""
    if volume is None:
        return "digital"
    return "scanned" if is_scanned_volume(volume) else "digital"


def psm_from_variant(variant: Optional[str], default: Optional[int] = DEFAULT_PSM) -> Optional[int]:
    if not variant:
        return default
    if variant.startswith("psm") and variant[3:].isdigit():
        return int(variant[3:])
    raise ValueError(f"unknown Tesseract variant {variant!r}; expected psm<N>")


# ---------------------------------------------------------------------------- Docling options


def base_pipeline_options(artifacts_path: Optional[str] = None, num_threads: int = 2, dpi: int = DEFAULT_DPI):
    """PdfPipelineOptions shared by the Docling families: CPU, layout and tables on, enrichments off."""
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    opts = PdfPipelineOptions()
    opts.artifacts_path = artifacts_path or os.getenv("DOCLING_ARTIFACTS_PATH") or None
    opts.accelerator_options = AcceleratorOptions(num_threads=num_threads, device=AcceleratorDevice.CPU)
    opts.do_table_structure = True
    opts.generate_page_images = False
    opts.generate_picture_images = False
    opts.do_picture_classification = False
    opts.do_code_enrichment = False
    opts.do_formula_enrichment = False
    opts.allow_external_plugins = True
    opts.images_scale = 2.0  # layout model input; OCR engines render at `dpi` on their own
    return opts


def _scanned_options(variant: Optional[str] = None, dpi: int = DEFAULT_DPI, num_threads: int = 2,
                     artifacts_path: Optional[str] = None):
    from docling.datamodel.pipeline_options import OcrMode

    from pipeline import tesseract

    tesseract.register()
    opts = base_pipeline_options(artifacts_path, num_threads, dpi)
    opts.do_ocr = True
    opts.ocr_options = tesseract.TesseractNoOsdOptions(lang=["eng"], mode=OcrMode.FULL_PAGE,
                                                       psm=psm_from_variant(variant), scale=dpi / 72)
    return opts


def _digital_options(variant: Optional[str] = None, dpi: int = DEFAULT_DPI, num_threads: int = 2,
                     artifacts_path: Optional[str] = None):
    opts = base_pipeline_options(artifacts_path, num_threads, dpi)
    opts.do_ocr = False
    opts.force_backend_text = True
    opts.images_scale = 1.0
    return opts


register_family(ProfileFamily("scanned", "Docling + Tesseract CLI, no orientation detection, 300 dpi",
                              options=_scanned_options, variants=("psm4", "psm6")))
register_family(ProfileFamily("digital", "Docling layout over the PDF text layer, no OCR", options=_digital_options))


def pipeline_options(profile: str, artifacts_path: Optional[str] = None, num_threads: int = 2, dpi: int = DEFAULT_DPI):
    """Build PdfPipelineOptions for a Docling profile. Imported lazily so tests run without torch."""
    family = get_family(profile)
    if not family.is_docling:
        raise ValueError(f"profile {profile!r} does not run through Docling")
    _, variant = parse_profile(profile)
    return family.options(variant=variant, dpi=dpi, num_threads=num_threads, artifacts_path=artifacts_path)


def make_converter(profile: str, artifacts_path: Optional[str] = None, num_threads: int = 2, dpi: int = DEFAULT_DPI):
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = pipeline_options(profile, artifacts_path, num_threads, dpi)
    family = get_family(profile)
    fmt_opts = {InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    if family.input_kind == "image":
        fmt_opts[InputFormat.IMAGE] = PdfFormatOption(pipeline_options=opts)
    return DocumentConverter(format_options=fmt_opts)
