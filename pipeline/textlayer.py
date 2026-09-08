"""Profile family `textlayer` (candidate C1): Docling layout over the PDF text layer, no OCR.

The scanned granule PDFs from GovInfo carry a text layer from the digitization vendor. This family
reads that layer (`do_ocr=False`, `force_backend_text=True`) and runs Docling's layout model over the
page images at scale 1.0. The options are those of the `digital` family; `textlayer` is its own family
so the benchmark report shows it as its own profile row on the scanned eras.

A rasterized input (tier A) has no text layer, so this family produces a document without text there.
"""

from __future__ import annotations

from typing import Optional

from pipeline.profiles import DEFAULT_DPI, ProfileFamily, base_pipeline_options, register_family

NAME = "textlayer"


def textlayer_options(variant: Optional[str] = None, dpi: int = DEFAULT_DPI, num_threads: int = 2,
                      artifacts_path: Optional[str] = None):
    """PdfPipelineOptions: no OCR, backend text forced, layout at scale 1.0."""
    if variant:
        raise ValueError(f"profile {NAME!r} has no variants; got {variant!r}")
    opts = base_pipeline_options(artifacts_path, num_threads, dpi)
    opts.do_ocr = False
    opts.force_backend_text = True
    opts.images_scale = 1.0
    return opts


FAMILY = register_family(ProfileFamily(NAME, "Docling layout over the PDF text layer of scanned granules, no OCR",
                                       options=textlayer_options))
