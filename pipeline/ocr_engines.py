"""Profile families for the CPU OCR engines Docling exposes (candidates C2 and C3).

    tesseract    Tesseract CLI through pipeline.tesseract's model (no orientation detection), lang eng,
                 full-page OCR, 300 dpi; variants `psm4` and `psm6` set Tesseract's page segmentation
                 mode. The plain `tesseract` profile equals `scanned`.
    rapidocr     Docling `RapidOcrOptions`: PP-OCR English checkpoints on onnxruntime, full-page OCR,
                 rendered at `dpi` through the options' `scale` (dpi / 72). Needs `rapidocr` and
                 `onnxruntime` (`pip install -e ".[ocr]"`).
    easyocr      Docling `EasyOcrOptions`: EasyOCR on CPU, English, full-page OCR, rendered at `dpi`.
                 Needs `easyocr`.

Every OCR engine renders the page at `scale` times 72 dpi; the layout model input stays at
`base_pipeline_options().images_scale`.

Model files. With `artifacts_path` set (DOCLING_ARTIFACTS_PATH in the container) Docling loads RapidOCR
checkpoints from `<artifacts_path>/RapidOcr` and does not download them, and it turns EasyOCR's own
download off unless `model_storage_directory` is given. `rapidocr_options` and `easyocr_options` fetch
the missing files into those directories under a file lock before returning, so two workers starting
at once do not download the same file twice; pass `prefetch=False` to skip that. The equivalent
one-off command is

    docling-tools models download rapidocr easyocr --rapidocr-backend-lang onnxruntime:en \\
        --easyocr-lang en -o "$DOCLING_ARTIFACTS_PATH"
"""

from __future__ import annotations

import fcntl
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from pipeline import tesseract
from pipeline.profiles import DEFAULT_DPI, ProfileFamily, base_pipeline_options, psm_from_variant, register_family

logger = logging.getLogger(__name__)

TESSERACT_LANG = ["eng"]
RAPIDOCR_LANG = ["en"]
RAPIDOCR_BACKEND = "onnxruntime"
EASYOCR_LANG = ["en"]
EASYOCR_RECOGNITION_MODELS = ["english_g2"]

# Docling's per-engine folders under artifacts_path (RapidOcrModel._model_repo_folder, EasyOcrModel._model_repo_folder).
RAPIDOCR_FOLDER = "RapidOcr"
EASYOCR_FOLDER = "EasyOcr"


def _no_variant(name: str, variant: Optional[str]) -> None:
    if variant:
        raise ValueError(f"profile {name!r} has no variants; got {variant!r}")


def ocr_scale(dpi: int) -> float:
    """Docling OCR `scale` for a render resolution: a multiplier of 72 dpi."""
    return dpi / 72


@contextmanager
def _locked(directory: Path):
    """Exclusive advisory lock on `<directory>/.lock` for the duration of a model download."""
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / ".lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------- tesseract (C2)


def tesseract_options(variant: Optional[str] = None, dpi: int = DEFAULT_DPI, num_threads: int = 2,
                      artifacts_path: Optional[str] = None):
    """PdfPipelineOptions: Tesseract CLI without orientation detection, psm from the variant."""
    from docling.datamodel.pipeline_options import OcrMode

    tesseract.register()
    opts = base_pipeline_options(artifacts_path, num_threads, dpi)
    opts.do_ocr = True
    opts.ocr_options = tesseract.TesseractNoOsdOptions(lang=list(TESSERACT_LANG), mode=OcrMode.FULL_PAGE,
                                                       psm=psm_from_variant(variant), scale=ocr_scale(dpi))
    return opts


# ---------------------------------------------------------------------------- rapidocr (C3)


def rapidocr_model_dir(artifacts_path: Optional[str]) -> Optional[Path]:
    return Path(artifacts_path) / RAPIDOCR_FOLDER if artifacts_path else None


def prefetch_rapidocr(artifacts_path: Optional[str]) -> Optional[Path]:
    """Download the English onnxruntime checkpoints into `<artifacts_path>/RapidOcr` when they are missing.
    Returns the directory, or None when there is no artifacts path (RapidOCR then resolves its own cache)."""
    target = rapidocr_model_dir(artifacts_path)
    if target is None:
        return None
    from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel

    with _locked(target):
        RapidOcrModel.download_models(RAPIDOCR_BACKEND, local_dir=target, lang=RAPIDOCR_LANG[0])
    return target


def rapidocr_options(variant: Optional[str] = None, dpi: int = DEFAULT_DPI, num_threads: int = 2,
                     artifacts_path: Optional[str] = None, prefetch: bool = True):
    """PdfPipelineOptions: RapidOCR (PP-OCR, English) on onnxruntime, full page at `dpi`."""
    from docling.datamodel.pipeline_options import OcrMode, RapidOcrOptions

    _no_variant("rapidocr", variant)
    opts = base_pipeline_options(artifacts_path, num_threads, dpi)
    opts.do_ocr = True
    opts.ocr_options = RapidOcrOptions(lang=list(RAPIDOCR_LANG), backend=RAPIDOCR_BACKEND, mode=OcrMode.FULL_PAGE,
                                       scale=ocr_scale(dpi))
    if prefetch:
        prefetch_rapidocr(opts.artifacts_path)
    return opts


# ---------------------------------------------------------------------------- easyocr (C3)


def easyocr_model_dir(artifacts_path: Optional[str]) -> Optional[Path]:
    return Path(artifacts_path) / EASYOCR_FOLDER if artifacts_path else None


def prefetch_easyocr(artifacts_path: Optional[str]) -> Optional[Path]:
    """Download the CRAFT detector and the `english_g2` recognizer into `<artifacts_path>/EasyOcr` when they
    are missing. Returns the directory, or None when there is no artifacts path (EasyOCR then uses its own cache)."""
    target = easyocr_model_dir(artifacts_path)
    if target is None:
        return None
    from docling.models.stages.ocr.easyocr_model import EasyOcrModel

    with _locked(target):
        expected = [target / "craft_mlt_25k.pth"] + [target / f"{m}.pth" for m in EASYOCR_RECOGNITION_MODELS]
        if not all(p.exists() for p in expected):
            EasyOcrModel.download_models(recognition_models=list(EASYOCR_RECOGNITION_MODELS), local_dir=target)
    return target


def easyocr_options(variant: Optional[str] = None, dpi: int = DEFAULT_DPI, num_threads: int = 2,
                    artifacts_path: Optional[str] = None, prefetch: bool = True):
    """PdfPipelineOptions: EasyOCR on CPU, English, full page at `dpi`, downloads enabled."""
    from docling.datamodel.pipeline_options import EasyOcrOptions, OcrMode

    _no_variant("easyocr", variant)
    opts = base_pipeline_options(artifacts_path, num_threads, dpi)
    opts.do_ocr = True
    model_dir = easyocr_model_dir(opts.artifacts_path)
    opts.ocr_options = EasyOcrOptions(lang=list(EASYOCR_LANG), mode=OcrMode.FULL_PAGE, scale=ocr_scale(dpi),
                                      download_enabled=True,
                                      model_storage_directory=str(model_dir) if model_dir else None)
    if prefetch:
        prefetch_easyocr(opts.artifacts_path)
    return opts


# ---------------------------------------------------------------------------- registry

register_family(ProfileFamily("tesseract", "Docling + Tesseract CLI, no orientation detection, 300 dpi; psm4/psm6 variants",
                              options=tesseract_options, variants=("psm4", "psm6")))
register_family(ProfileFamily("rapidocr", "Docling + RapidOCR (PP-OCR English, onnxruntime), full page, 300 dpi",
                              options=rapidocr_options))
register_family(ProfileFamily("easyocr", "Docling + EasyOCR (CPU, English), full page, 300 dpi",
                              options=easyocr_options))
