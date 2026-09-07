"""Docling pipeline profiles: `scanned` (OCR with the Tesseract CLI) and `digital` (text layer, no OCR)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from downloader.config import is_scanned_volume

PROFILES = ("scanned", "digital")


def profile_for_volume(volume: Optional[int]) -> str:
    """Volumes 1 to 116 are scanned images; 117 onward and every PLAW file are born digital."""
    if volume is None:
        return "digital"
    return "scanned" if is_scanned_volume(volume) else "digital"


def pipeline_options(profile: str, artifacts_path: Optional[str] = None, num_threads: int = 2):
    """Build PdfPipelineOptions for a profile. Imported lazily so tests run without torch."""
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions

    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; expected one of {PROFILES}")
    opts = PdfPipelineOptions()
    opts.artifacts_path = artifacts_path or os.getenv("DOCLING_ARTIFACTS_PATH") or None
    opts.accelerator_options = AcceleratorOptions(num_threads=num_threads, device=AcceleratorDevice.CPU)
    opts.do_table_structure = True
    opts.generate_page_images = False
    opts.generate_picture_images = False
    opts.do_picture_classification = False
    opts.do_code_enrichment = False
    opts.do_formula_enrichment = False
    if profile == "scanned":
        opts.do_ocr = True
        opts.ocr_options = TesseractCliOcrOptions(lang=["eng"], force_full_page_ocr=True)
        opts.images_scale = 2.0  # 144 dpi rendering for OCR of 1950s type
    else:
        opts.do_ocr = False
        opts.force_backend_text = True
        opts.images_scale = 1.0
    return opts


def make_converter(profile: str, artifacts_path: Optional[str] = None, num_threads: int = 2):
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = pipeline_options(profile, artifacts_path, num_threads)
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
