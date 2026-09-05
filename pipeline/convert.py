"""Convert PDFs to DoclingDocument JSON and USLM XML with a pool of Docling workers.

    python -m pipeline.convert --spec benchmark/sample.yaml [--workers 4]        granule PDFs from a sample spec
    python -m pipeline.convert --plaw PLAW-118publ5 [--plaw ...]                 per-law PDFs from data/pdfs/
    python -m pipeline.convert --pdf path.pdf --profile scanned --page-range 1-20 [--volume 64 --start-page 371]

Unit of work: one granule PDF or one PLAW PDF, optionally restricted to a page range. Each worker
process creates one DocumentConverter per profile in its initializer and reuses it. Output:
data/doclang/{id}.json (compact DoclingDocument) and data/generated_xmls/{id}.xml (USLM). A unit is
skipped when both outputs exist and the input sha256 recorded in `conversions` is unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from downloader import db
from downloader.config import DATA_DIR, LOG_DIR, setup_logging
from downloader.fetch_granules import load_spec
from pipeline import uslm
from pipeline.profiles import profile_for_volume

logger = logging.getLogger("convert")

MODULE = "docling_local"
DOCLANG_DIR = DATA_DIR / "doclang"
XML_DIR = DATA_DIR / "generated_xmls"


@dataclass
class Unit:
    unit_id: str  # granule id or package id (plus page range suffix in file names)
    pdf: str
    profile: str
    identity: dict  # uslm.DocIdentity fields
    page_range: Optional[tuple[int, int]] = None
    granule_id: Optional[str] = None
    package_id: Optional[str] = None
    statute_id: Optional[int] = None

    @property
    def stem(self) -> str:
        if self.page_range:
            return f"{self.unit_id}_p{self.page_range[0]}-{self.page_range[1]}"
        return self.unit_id


@dataclass
class UnitResult:
    unit_id: str
    status: str  # success | skipped | failed
    doclang_path: Optional[str] = None
    xml_path: Optional[str] = None
    pages: int = 0
    seconds: float = 0.0
    xsd_valid: Optional[bool] = None
    error: Optional[str] = None
    input_sha256: Optional[str] = None
    xsd_errors: Optional[list[str]] = None


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_page_range(spec: Optional[str]) -> Optional[tuple[int, int]]:
    if not spec:
        return None
    m = re.match(r"^(\d+)-(\d+)$", spec)
    if not m:
        raise ValueError(f"page range must look like 1-20, got {spec!r}")
    a, b = int(m.group(1)), int(m.group(2))
    if a < 1 or b < a:
        raise ValueError(f"bad page range {spec!r}")
    return a, b


DEFAULT_MAX_WORKERS = 2


def workers_for_container(requested: Optional[int]) -> int:
    """min(2, cpu_count // 2) unless overridden.

    Four Docling workers with Tesseract OCR peaked at 6 GB and were OOM-killed in the 8 GB container;
    two workers stay under 4 GB. Raise --workers on hosts with more memory (about 1.5 GB per worker).
    """
    if requested:
        return max(1, requested)
    return max(1, min(DEFAULT_MAX_WORKERS, (os.cpu_count() or 2) // 2))


# ---------------------------------------------------------------------------- skip logic


def previous_success(conn, unit: Unit) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM conversions WHERE COALESCE(granule_id, package_id) = %s AND COALESCE(page_range, '') = %s "
            "AND module_used = %s ORDER BY conversion_date DESC LIMIT 1",
            (unit.granule_id or unit.package_id, f"{unit.page_range[0]}-{unit.page_range[1]}" if unit.page_range else "", MODULE),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def should_skip(unit: Unit, sha: str, doclang_path: Path, xml_path: Path, previous: Optional[dict], force: bool) -> bool:
    if force:
        return False
    if not (doclang_path.exists() and xml_path.exists()):
        return False
    return bool(previous and previous.get("status") == "success" and previous.get("input_sha256") == sha)


def record(conn, unit: Unit, result: UnitResult) -> None:
    page_range = f"{unit.page_range[0]}-{unit.page_range[1]}" if unit.page_range else None
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM conversions WHERE COALESCE(granule_id, package_id) = %s AND COALESCE(page_range, '') = %s AND module_used = %s",
            (unit.granule_id or unit.package_id, page_range or "", MODULE),
        )
        cur.execute(
            """
            INSERT INTO conversions (statute_id, module_used, uslm_xml_path, doclang_json_path, status, error_log,
                                     granule_id, package_id, input_path, input_sha256, profile, page_range, pages,
                                     seconds, xsd_valid)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                unit.statute_id, MODULE, result.xml_path, result.doclang_path, result.status,
                (result.error or "") + ("\n".join(result.xsd_errors[:20]) if result.xsd_errors else "") or None,
                unit.granule_id, unit.package_id, unit.pdf, result.input_sha256, unit.profile, page_range,
                result.pages, result.seconds, result.xsd_valid,
            ),
        )
    conn.commit()


# ---------------------------------------------------------------------------- worker


_CONVERTERS: dict = {}


def _init_worker(num_threads: int) -> None:
    global _CONVERTERS
    _CONVERTERS = {}
    os.environ.setdefault("OMP_NUM_THREADS", str(num_threads))
    logging.getLogger("docling").setLevel(logging.WARNING)


def _converter(profile: str, num_threads: int):
    from pipeline.profiles import make_converter

    if profile not in _CONVERTERS:
        _CONVERTERS[profile] = make_converter(profile, num_threads=num_threads)
    return _CONVERTERS[profile]


def convert_unit(unit: Unit, doclang_path: str, xml_path: str, num_threads: int = 2) -> UnitResult:
    """Runs inside a worker process: Docling convert, write JSON, build USLM, validate."""
    started = time.monotonic()
    try:
        converter = _converter(unit.profile, num_threads)
        kwargs = {}
        if unit.page_range:
            kwargs["page_range"] = unit.page_range
        result = converter.convert(unit.pdf, **kwargs)
        doc = result.document
        Path(doclang_path).parent.mkdir(parents=True, exist_ok=True)
        Path(doclang_path).write_text(json.dumps(doc.export_to_dict(), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        identity = uslm.DocIdentity(**unit.identity)
        if unit.page_range and identity.start_page is not None:
            identity.start_page = identity.start_page + unit.page_range[0] - 1
        tree = uslm.build_uslm(doc, identity)
        uslm.write_uslm(tree, xml_path)
        ok, errors = uslm.validate(tree)
        return UnitResult(
            unit_id=unit.unit_id, status="success", doclang_path=doclang_path, xml_path=xml_path,
            pages=len(doc.pages), seconds=time.monotonic() - started, xsd_valid=ok, xsd_errors=errors or None,
        )
    except Exception as exc:  # recorded in conversions.error_log
        return UnitResult(unit_id=unit.unit_id, status="failed", seconds=time.monotonic() - started, error=f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------- units


def units_from_spec(spec_path: str, page_range: Optional[tuple[int, int]]) -> list[Unit]:
    units = []
    with db.connection() as conn, conn.cursor() as cur:
        for entry in load_spec(spec_path):
            cur.execute("SELECT * FROM granules WHERE granule_id = %s", (entry["granule_id"],))
            row = cur.fetchone()
            if row is None or not row["pdf_local_path"]:
                logger.warning("%s: not downloaded (run downloader.fetch_granules first)", entry["granule_id"])
                continue
            row = dict(row)
            volume = int(row["package_id"].split("-")[1]) if row["package_id"].startswith("STATUTE-") else None
            identity = uslm.identity_from_granule(row)
            units.append(
                Unit(unit_id=row["granule_id"], pdf=row["pdf_local_path"], profile=profile_for_volume(volume),
                     identity=asdict(identity), page_range=page_range, granule_id=row["granule_id"],
                     package_id=row["package_id"])
            )
    return units


def units_from_plaw(package_ids: list[str], page_range: Optional[tuple[int, int]]) -> list[Unit]:
    from downloader.fetch_plaw import pl_number

    units = []
    with db.connection() as conn, conn.cursor() as cur:
        for package_id in package_ids:
            pdf = DATA_DIR / "pdfs" / f"{package_id}.pdf"
            if not pdf.exists():
                logger.warning("%s: %s missing (run downloader.fetch_plaw first)", package_id, pdf)
                continue
            cur.execute("SELECT * FROM statutes WHERE pl_number = %s", (pl_number(package_id),))
            statute = cur.fetchone()
            statute = dict(statute) if statute else None
            identity = uslm.identity_from_plaw(package_id, statute)
            units.append(
                Unit(unit_id=package_id, pdf=str(pdf), profile="digital", identity=asdict(identity),
                     page_range=page_range, package_id=package_id, statute_id=statute["id"] if statute else None)
            )
    return units


def unit_from_pdf(pdf: str, profile: Optional[str], page_range, volume: Optional[int], start_page: Optional[int],
                  congress: Optional[int], law_number: Optional[int]) -> Unit:
    stem = Path(pdf).stem
    identity = uslm.DocIdentity(volume=volume, start_page=start_page, congress=congress, law_number=law_number,
                                package_id=f"STATUTE-{volume}" if volume else None)
    return Unit(unit_id=stem, pdf=pdf, profile=profile or profile_for_volume(volume), identity=asdict(identity),
                page_range=page_range, package_id=f"STATUTE-{volume}" if volume else stem)


# ---------------------------------------------------------------------------- run


def run_units(units: list[Unit], workers: int, force: bool, num_threads: int = 2) -> list[UnitResult]:
    results: list[UnitResult] = []
    todo: list[tuple[Unit, str, Path, Path]] = []
    with db.connection() as conn:
        for unit in units:
            sha = sha256_file(unit.pdf)
            doclang_path = DOCLANG_DIR / f"{unit.stem}.json"
            xml_path = XML_DIR / f"{unit.stem}.xml"
            previous = previous_success(conn, unit)
            if should_skip(unit, sha, doclang_path, xml_path, previous, force):
                logger.info("%s: skip (outputs exist, input unchanged)", unit.unit_id)
                results.append(UnitResult(unit_id=unit.unit_id, status="skipped", doclang_path=str(doclang_path),
                                          xml_path=str(xml_path), xsd_valid=previous.get("xsd_valid") if previous else None))
                continue
            todo.append((unit, sha, doclang_path, xml_path))
    if not todo:
        return results

    logger.info("converting %d unit(s) with %d worker(s)", len(todo), workers)
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(num_threads,)) as pool:
        futures = {
            pool.submit(convert_unit, unit, str(doclang_path), str(xml_path), num_threads): (unit, sha)
            for unit, sha, doclang_path, xml_path in todo
        }
        for fut in as_completed(futures):
            unit, sha = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:  # worker crash
                result = UnitResult(unit_id=unit.unit_id, status="failed", error=f"worker: {exc}")
            result.input_sha256 = sha
            if result.status == "success":
                logger.info("%s: %d pages in %.0fs, xsd_valid=%s%s", unit.unit_id, result.pages, result.seconds,
                            result.xsd_valid, "" if result.xsd_valid else f" ({(result.xsd_errors or [''])[0][:120]})")
            else:
                logger.error("%s: %s", unit.unit_id, result.error)
            with db.connection() as conn:
                record(conn, unit, result)
            results.append(result)
    return results


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m pipeline.convert", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", help="YAML sample spec with granule ids")
    p.add_argument("--plaw", action="append", default=[], help="PLAW package id (repeatable)")
    p.add_argument("--pdf", help="a single PDF path")
    p.add_argument("--profile", choices=["scanned", "digital"], help="override the profile for --pdf")
    p.add_argument("--volume", type=int, help="Statutes at Large volume for --pdf")
    p.add_argument("--start-page", type=int, help="Statutes at Large page of PDF page 1 for --pdf")
    p.add_argument("--congress", type=int)
    p.add_argument("--law-number", type=int)
    p.add_argument("--page-range", help="e.g. 1-20")
    p.add_argument("--workers", type=int, default=None, help="default min(2, cpu_count // 2); about 1.5 GB RAM per worker")
    p.add_argument("--threads", type=int, default=2, help="torch/OMP threads per worker (default 2)")
    p.add_argument("--force", action="store_true", help="convert even when outputs exist")
    p.add_argument("--log-dir", default=str(LOG_DIR))
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging("convert", args.log_dir)
    db.init_db()
    page_range = parse_page_range(args.page_range)
    units: list[Unit] = []
    if args.spec:
        units += units_from_spec(args.spec, page_range)
    if args.plaw:
        units += units_from_plaw(args.plaw, page_range)
    if args.pdf:
        units.append(unit_from_pdf(args.pdf, args.profile, page_range, args.volume, args.start_page, args.congress, args.law_number))
    if not units:
        logger.error("nothing to convert (use --spec, --plaw, or --pdf)")
        return 2
    results = run_units(units, workers_for_container(args.workers), args.force, args.threads)
    ok = sum(r.status == "success" for r in results)
    skipped = sum(r.status == "skipped" for r in results)
    failed = [r for r in results if r.status == "failed"]
    invalid = [r for r in results if r.status == "success" and r.xsd_valid is False]
    logger.info("done: %d converted, %d skipped, %d failed, %d not XSD-valid", ok, skipped, len(failed), len(invalid))
    for r in failed:
        logger.error("FAILED %s: %s", r.unit_id, r.error)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
