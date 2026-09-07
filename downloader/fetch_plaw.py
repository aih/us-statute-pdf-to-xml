"""Download public laws (PLAW collection): per-law PDF and USLM XML, with `statutes` rows.

    python -m downloader.fetch_plaw --since 2023-01-01 --limit 20 [--congress 118] [--doc-class PUBLIC]
                                    [--workers 4] [--congress-gov]

`--since` is passed to `collections/PLAW/{since}` (a lastModified filter) and also used as a
dateIssued floor unless `--any-date` is given. Files land in data/pdfs/ and data/xmls/ under the
package id. `--congress-gov` also fetches https://www.congress.gov/{c}/plaws/publ{n}/PLAW-{c}publ{n}_uslm.xml
into data/xmls/congress/ and reports whether it matches the GovInfo copy byte for byte.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Optional

import httpx

from . import db, state
from .config import DATA_DIR, LOG_DIR, exit_on_missing_env, govinfo_api_key, setup_logging
from .govinfo import GovInfoClient, GovInfoError

logger = logging.getLogger("fetch_plaw")

PLAW_ID = re.compile(r"^PLAW-(\d+)(publ|pvtl)(\d+)$")
CONGRESS_GOV_USER_AGENT = "statute-pdf-to-xml/0.2 (+https://github.com/aih/statute-pdf-to-xml)"


def parse_plaw_id(package_id: str) -> tuple[int, str, int]:
    """'PLAW-118publ5' -> (118, 'publ', 5)."""
    m = PLAW_ID.match(package_id)
    if not m:
        raise ValueError(f"not a PLAW package id: {package_id!r}")
    return int(m.group(1)), m.group(2), int(m.group(3))


def pl_number(package_id: str) -> str:
    congress, kind, number = parse_plaw_id(package_id)
    return f"{congress}-{number}" if kind == "publ" else f"{congress}-pvt{number}"


def congress_gov_url(package_id: str) -> str:
    congress, kind, number = parse_plaw_id(package_id)
    return f"https://www.congress.gov/{congress}/plaws/{kind}{number}/{package_id}_uslm.xml"


def issued_on_or_after(pkg: dict, floor: Optional[date]) -> bool:
    if floor is None:
        return True
    issued = pkg.get("dateIssued")
    if not issued:
        return True
    try:
        return date.fromisoformat(issued[:10]) >= floor
    except ValueError:
        return True


def statute_row(summary: dict, pdf_path: Path, xml_path: Optional[Path] = None) -> dict:
    """statutes row; volume and pages come from the USLM when it is on disk, else from the summary."""
    package_id = summary["packageId"]
    congress, kind, number = parse_plaw_id(package_id)
    volume, start_page, end_page = (None, None, None)
    if xml_path is not None and xml_path.exists():
        volume, start_page, end_page = state.plaw_pages_from_uslm(xml_path.read_bytes())
    if volume is None:
        volume, start_page, end_page = state.plaw_pages_from_summary(summary)
    return {
        "pl_number": pl_number(package_id),
        "congress": congress,
        "law_number": number,
        "title": summary.get("title"),
        "date_enacted": summary.get("dateIssued"),
        "volume": volume,
        "start_page": start_page,
        "end_page": end_page,
        "pdf_path": state.relative_to_repo(pdf_path),
    }


def fetch_congress_gov_copy(package_id: str, dest: Path, govinfo_copy: Path) -> Optional[bool]:
    """Fetch the congress.gov USLM without the GovInfo key. Returns True when identical to the GovInfo copy."""
    url = congress_gov_url(package_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        with httpx.Client(headers={"User-Agent": CONGRESS_GOV_USER_AGENT}, timeout=60, follow_redirects=True) as c:
            response = c.get(url)
            if response.status_code != 200:
                logger.warning("%s: congress.gov returned %d for %s", package_id, response.status_code, url)
                return None
            dest.write_bytes(response.content)
    if govinfo_copy.exists():
        same = dest.read_bytes() == govinfo_copy.read_bytes()
        logger.info("%s: congress.gov USLM %s the GovInfo copy", package_id, "matches" if same else "DIFFERS from")
        return same
    return None


def process_package(client: GovInfoClient, package_id: str, data_dir: Path, parts: int, congress_gov: bool) -> dict:
    summary = client.package_summary(package_id)
    if summary is None:
        raise GovInfoError(f"{package_id}: no summary")
    row = state.package_row_from_summary(summary)
    pdf_path = data_dir / "pdfs" / f"{package_id}.pdf"
    xml_path = data_dir / "xmls" / f"{package_id}.xml"
    with db.connection() as conn:
        state.upsert_package(conn, row)
    downloaded = {}
    for kind, url, path in (("pdf", row["pdf_url"], pdf_path), ("xml", row["xml_url"], xml_path)):
        if not url:
            logger.warning("%s: no %s link", package_id, kind)
            continue
        result = client.download_ranged(url, path, parts=parts)
        downloaded[kind] = result
        with db.connection() as conn:
            state.set_file_state(conn, package_id, kind, status="downloaded", bytes_=result.bytes,
                                 sha256=result.sha256, local_path=str(path))
    row = statute_row(summary, pdf_path, xml_path)
    with db.connection() as conn:
        statute_id = db.insert_statute(**row, conn=conn)
    if congress_gov:
        fetch_congress_gov_copy(package_id, data_dir / "xmls" / "congress" / f"{package_id}_uslm.xml", xml_path)
    volume, start_page, end_page = row["volume"], row["start_page"], row["end_page"]
    logger.info(
        "%s: %s Stat. %s-%s, %d pages, pdf %s, xml %s", package_id, volume, start_page, end_page,
        int(summary.get("pages") or 0),
        "skipped" if downloaded.get("pdf") and downloaded["pdf"].skipped else "downloaded",
        "skipped" if downloaded.get("xml") and downloaded["xml"].skipped else "downloaded",
    )
    return {"package_id": package_id, "statute_id": statute_id, "volume": volume, "pages": (start_page, end_page)}


def select_packages(client: GovInfoClient, since: str, limit: Optional[int], congress: Optional[int],
                    doc_class: Optional[str], any_date: bool) -> list[str]:
    floor = None if any_date else date.fromisoformat(since[:10])
    filters = {}
    if congress:
        filters["congress"] = congress
    if doc_class:
        filters["docClass"] = doc_class
    chosen: list[str] = []
    for pkg in client.iter_collection("PLAW", since, **filters):
        if not issued_on_or_after(pkg, floor):
            continue
        try:
            parse_plaw_id(pkg["packageId"])
        except ValueError:
            continue
        chosen.append(pkg["packageId"])
        if limit and len(chosen) >= limit:
            break
    return chosen


def run(args) -> int:
    log_path = setup_logging("fetch_plaw", args.log_dir)
    logger.info("log file: %s", log_path)
    db.init_db()
    data_dir = Path(args.data_dir)
    failures: dict[str, str] = {}
    with GovInfoClient(govinfo_api_key(), max_connections=args.workers * args.parts + 4) as client:
        if args.package:
            package_ids = list(args.package)
        else:
            package_ids = select_packages(client, args.since, args.limit, args.congress, args.doc_class, args.any_date)
        logger.info("%d package(s) selected", len(package_ids))
        with ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="plaw") as pool:
            futures = {
                pool.submit(process_package, client, pid, data_dir, args.parts, args.congress_gov): pid
                for pid in package_ids
            }
            for fut in as_completed(futures):
                pid = futures[fut]
                try:
                    fut.result()
                except Exception as exc:
                    logger.error("%s: %s", pid, exc)
                    failures[pid] = str(exc)
    logger.info("done: %d ok, %d failed", len(package_ids) - len(failures), len(failures))
    for pid, err in sorted(failures.items()):
        logger.error("FAILED %s: %s", pid, err)
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m downloader.fetch_plaw", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--since", default=None, help="ISO date, e.g. 2023-01-01 (lastModified filter and dateIssued floor)")
    p.add_argument("--package", action="append", default=None, help="explicit package id, e.g. PLAW-118publ5 (repeatable)")
    p.add_argument("--limit", type=int, default=None, help="stop after N laws")
    p.add_argument("--congress", type=int, default=None, help="restrict to one Congress, e.g. 118")
    p.add_argument("--doc-class", default="PUBLIC", help="PUBLIC (default), PRIVATE, or '' for both")
    p.add_argument("--any-date", action="store_true", help="do not apply --since as a dateIssued floor")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--parts", type=int, default=2, help="range requests per file (default 2; PLAW files are small)")
    p.add_argument("--congress-gov", action="store_true", help="also fetch the congress.gov USLM and compare")
    p.add_argument("--data-dir", default=str(DATA_DIR))
    p.add_argument("--log-dir", default=str(LOG_DIR))
    return p


@exit_on_missing_env
def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.since and not args.package:
        build_parser().error("--since or --package is required")
    if args.doc_class == "":
        args.doc_class = None
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
