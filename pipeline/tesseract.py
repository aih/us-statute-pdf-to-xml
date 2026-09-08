"""Tesseract CLI OCR for Docling with orientation detection disabled (defect F1 of the 2026-09-07 plan).

Docling's `TesseractOcrCliModel` runs `tesseract --psm 0 -l osd` on every OCR rectangle and rotates the
image by the reported orientation before OCR. On the scanned Statutes at Large pages the detection
returns 180 or 270 degrees with a confidence below 0.1 on upright pages, and the OCR output is mirrored
text. There is no option to turn the detection off, so `TesseractNoOsdModel` overrides `_perform_osd`
to report orientation 0 and is registered with Docling's OCR factory under the options kind
`tesseract_noosd`.

    from pipeline.tesseract import TesseractNoOsdOptions, register
    register()
    opts.ocr_options = TesseractNoOsdOptions(lang=["eng"], mode=OcrMode.FULL_PAGE, psm=4, scale=300 / 72)
"""

from __future__ import annotations

import io
import logging
from typing import ClassVar, Literal, Optional

logger = logging.getLogger(__name__)

KIND = "tesseract_noosd"
PLUGIN_NAME = "statute-pdf-to-xml"

# The frame Tesseract prints for an upright page. `_parse_orientation` reads "Orientation in degrees".
OSD_UPRIGHT = "Page number: 0\nOrientation in degrees: 0\nRotate: 0\nOrientation confidence: 0.00\nScript: Latin\nScript confidence: 0.00\n"


def _options_class():
    from docling.datamodel.pipeline_options import TesseractCliOcrOptions

    class TesseractNoOsdOptions(TesseractCliOcrOptions):
        """TesseractCliOcrOptions whose model skips orientation and script detection."""

        kind: ClassVar[Literal["tesseract_noosd"]] = KIND  # type: ignore[assignment]

    return TesseractNoOsdOptions


def _model_class():
    import pandas as pd
    from docling.models.stages.ocr.tesseract_ocr_cli_model import TesseractOcrCliModel

    Options = _options_class()

    class TesseractNoOsdModel(TesseractOcrCliModel):
        """Docling's Tesseract CLI model without `tesseract --psm 0` orientation detection."""

        def _perform_osd(self, ifilename: str) -> pd.DataFrame:  # type: ignore[override]
            return pd.read_csv(io.StringIO(OSD_UPRIGHT), sep=":", header=None, names=["key", "value"])

        @classmethod
        def get_options_type(cls):
            return Options

    return TesseractNoOsdModel


_CLASSES: dict = {}


def classes() -> tuple[type, type]:
    """(options class, model class), created once per process."""
    if not _CLASSES:
        model = _model_class()
        _CLASSES["options"] = model.get_options_type()
        _CLASSES["model"] = model
    return _CLASSES["options"], _CLASSES["model"]


def TesseractNoOsdOptions(**kwargs):  # noqa: N802 - constructor-like helper
    return classes()[0](**kwargs)


def register(allow_external_plugins: Optional[bool] = None) -> None:
    """Register the model with Docling's cached OCR factories so `ocr_options` of kind
    `tesseract_noosd` resolves to it. Idempotent."""
    from docling.models.factories import get_ocr_factory

    options_cls, model_cls = classes()
    flags = (True, False) if allow_external_plugins is None else (allow_external_plugins,)
    for flag in flags:
        factory = get_ocr_factory(allow_external_plugins=flag)
        if options_cls in factory.classes:
            continue
        factory.register(model_cls, PLUGIN_NAME, __name__)
        logger.info("registered OCR engine %r (allow_external_plugins=%s)", KIND, flag)


def osd_orientation(image_path: str) -> tuple[int, float]:
    """(orientation degrees, confidence) as Tesseract's own detection reports it, for diagnostics."""
    import re
    import subprocess

    out = subprocess.run(["tesseract", "--psm", "0", "-l", "osd", image_path, "stdout"], capture_output=True, text=True, check=True)
    m = re.search(r"Orientation in degrees:\s*(\d+).*?Orientation confidence:\s*([\d.]+)", out.stdout, re.S)
    if not m:
        raise RuntimeError(f"no orientation in OSD output: {out.stdout[:200]!r}")
    return int(m.group(1)), float(m.group(2))
