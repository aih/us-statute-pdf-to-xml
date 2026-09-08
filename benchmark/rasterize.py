"""Tier A inputs: page images of a born-digital PDF, clean and degraded, plus a PDF wrapper per variant.

    python -m benchmark.rasterize --granule STATUTE-124-Pg2256 [--granule ...] [--plaw PLAW-118publ5]
    python -m benchmark.rasterize --pdf path.pdf --id NAME [--dpi 300] [--variants clean,degraded] [--pages 1-3]

Output under data/raster/{id}/:

    p{n}.png                  clean render at `--dpi` (default 300), RGB
    p{n}.degraded.jpg         JPEG quality 60, 0.5 degree skew, Gaussian noise (sigma 8)
    {id}.clean.pdf            the clean pages wrapped with img2pdf (no text layer)
    {id}.degraded.pdf         the degraded pages wrapped with img2pdf
    manifest.json             dpi, pages, variants, sha256 of every image

Docling reads the wrapper PDFs like any scanned PDF, so a candidate profile runs on the images only and
never sees the born-digital text layer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from downloader.config import DATA_DIR, LOG_DIR, setup_logging

logger = logging.getLogger("rasterize")

RASTER_DIR = DATA_DIR / "raster"
DEFAULT_DPI = 300
VARIANTS = ("clean", "degraded")
JPEG_QUALITY = 60
SKEW_DEGREES = 0.5
NOISE_SIGMA = 8.0


@dataclass
class RasterResult:
    doc_id: str
    out_dir: Path
    dpi: int
    pages: list[int] = field(default_factory=list)
    images: dict[str, list[Path]] = field(default_factory=dict)  # variant -> image paths
    pdfs: dict[str, Path] = field(default_factory=dict)  # variant -> wrapper pdf


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render_pages(pdf_path: Path | str, dpi: int = DEFAULT_DPI, pages: Optional[Iterable[int]] = None):
    """Yield (page_no, PIL RGB image) for the 1-based pages of a PDF at `dpi`."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    wanted = list(pages) if pages else range(1, len(pdf) + 1)
    for no in wanted:
        if no < 1 or no > len(pdf):
            raise ValueError(f"page {no} outside 1-{len(pdf)} of {pdf_path}")
        yield no, pdf[no - 1].render(scale=dpi / 72).to_pil().convert("RGB")


def degrade(image, seed: int = 0, skew: float = SKEW_DEGREES, sigma: float = NOISE_SIGMA):
    """Approximate a scan: rotate by `skew` degrees on white, add Gaussian noise, return an RGB image.
    JPEG quality is applied when the image is saved (see `write_variant`)."""
    import numpy as np
    from PIL import Image

    rotated = image.rotate(skew, resample=Image.BICUBIC, expand=False, fillcolor=(255, 255, 255))
    arr = np.asarray(rotated).astype(np.float32)
    rng = np.random.default_rng(seed)
    arr += rng.normal(0.0, sigma, arr.shape).astype(np.float32)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def write_variant(image, path: Path, variant: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if variant == "degraded":
        image.save(path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    else:
        image.save(path, format="PNG", optimize=False)
    return path


def wrap_pdf(images: list[Path], out: Path, dpi: int) -> Path:
    import img2pdf

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(img2pdf.convert([str(p) for p in images], dpi=dpi))
    return out


def rasterize(pdf_path: Path | str, doc_id: str, out_root: Path = RASTER_DIR, dpi: int = DEFAULT_DPI,
              variants: Iterable[str] = VARIANTS, pages: Optional[Iterable[int]] = None, force: bool = False) -> RasterResult:
    variants = tuple(variants)
    unknown = set(variants) - set(VARIANTS)
    if unknown:
        raise ValueError(f"unknown variants {sorted(unknown)}; expected {VARIANTS}")
    out_dir = Path(out_root) / doc_id
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists() and not force:
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        if m.get("dpi") == dpi and set(m.get("variants", [])) >= set(variants) and (pages is None or list(pages) == m.get("pages")):
            result = RasterResult(doc_id, out_dir, dpi, m["pages"])
            for v in variants:
                result.images[v] = [out_dir / name for name in m["images"][v]]
                result.pdfs[v] = out_dir / m["pdfs"][v]
            logger.info("%s: raster exists (%d pages, %s)", doc_id, len(m["pages"]), ", ".join(variants))
            return result
    result = RasterResult(doc_id, out_dir, dpi)
    for v in variants:
        result.images[v] = []
    for no, image in render_pages(pdf_path, dpi, pages):
        result.pages.append(no)
        if "clean" in variants:
            result.images["clean"].append(write_variant(image, out_dir / f"p{no}.png", "clean"))
        if "degraded" in variants:
            result.images["degraded"].append(write_variant(degrade(image, seed=no), out_dir / f"p{no}.degraded.jpg", "degraded"))
    for v in variants:
        result.pdfs[v] = wrap_pdf(result.images[v], out_dir / f"{doc_id}.{v}.pdf", dpi)
    manifest = {
        "id": doc_id, "source": str(pdf_path), "dpi": dpi, "pages": result.pages, "variants": list(variants),
        "images": {v: [p.name for p in result.images[v]] for v in variants},
        "pdfs": {v: result.pdfs[v].name for v in variants},
        "sha256": {p.name: sha256_file(p) for v in variants for p in result.images[v]},
    }
    manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    logger.info("%s: %d page(s) at %d dpi -> %s (%s)", doc_id, len(result.pages), dpi, out_dir, ", ".join(variants))
    return result


def raster_pdf(doc_id: str, variant: str = "clean", out_root: Path = RASTER_DIR) -> Optional[Path]:
    path = Path(out_root) / doc_id / f"{doc_id}.{variant}.pdf"
    return path if path.exists() else None


# ---------------------------------------------------------------------------- CLI


def granule_pdf(granule_id: str) -> Path:
    from downloader.fetch_granules import granule_paths

    pdf, _ = granule_paths(granule_id, DATA_DIR / "granules")
    if not pdf.exists():
        raise FileNotFoundError(f"{pdf} (run benchmark.evaluate or downloader.fetch_granules first)")
    return pdf


def parse_pages(spec: Optional[str]) -> Optional[list[int]]:
    if not spec:
        return None
    a, _, b = spec.partition("-")
    return list(range(int(a), int(b or a) + 1))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m benchmark.rasterize", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--granule", action="append", default=[], help="STATUTE granule id (repeatable)")
    p.add_argument("--plaw", action="append", default=[], help="PLAW package id from data/pdfs/ (repeatable)")
    p.add_argument("--pdf", help="any PDF path")
    p.add_argument("--id", help="output id for --pdf (default: file stem)")
    p.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    p.add_argument("--variants", default=",".join(VARIANTS))
    p.add_argument("--pages", default=None, help="1-based page range, e.g. 1-3")
    p.add_argument("--force", action="store_true")
    p.add_argument("--log-dir", default=str(LOG_DIR))
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging("rasterize", args.log_dir)
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    jobs: list[tuple[str, Path]] = []
    for gid in args.granule:
        jobs.append((gid, granule_pdf(gid)))
    for pid in args.plaw:
        jobs.append((pid, DATA_DIR / "pdfs" / f"{pid}.pdf"))
    if args.pdf:
        jobs.append((args.id or Path(args.pdf).stem, Path(args.pdf)))
    if not jobs:
        logger.error("nothing to rasterize (use --granule, --plaw, or --pdf)")
        return 2
    failed = 0
    for doc_id, pdf in jobs:
        try:
            rasterize(pdf, doc_id, dpi=args.dpi, variants=variants, pages=parse_pages(args.pages), force=args.force)
        except Exception as exc:
            failed += 1
            logger.error("%s: %s", doc_id, exc)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
