"""Download granule PDFs and MODS records listed in a benchmark sample spec.

    python -m downloader.fetch_granules --spec benchmark/sample.yaml [--workers 4]

Spec format (YAML), written by benchmark/sample.py:

    granules:
      - granule_id: STATUTE-64-Pg371      # required
        package_id: STATUTE-64            # optional, derived from granule_id
        era: scanned-1951-2002            # optional, stored on the granules row
        granule_class: PUBLICLAW          # optional, informational

Files land in data/granules/STATUTE-{n}/{granuleId}.pdf and {granuleId}.mods.xml. A PDF whose size
matches GovInfo's Content-Length is not downloaded again; MODS is fetched once.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import yaml

from . import db, state
from .config import DATA_DIR, LOG_DIR, exit_on_missing_env, govinfo_api_key, setup_logging
from .govinfo import GovInfoClient, GovInfoError
from .mods import parse_mods

logger = logging.getLogger("fetch_granules")

GRANULE_ID = re.compile(r"^(STATUTE-\d+)-Pg(.+)$")


def package_id_for(granule_id: str) -> str:
    m = GRANULE_ID.match(granule_id)
    if not m:
        raise ValueError(f"not a STATUTE granule id: {granule_id!r}")
    return m.group(1)


def load_spec(path: Path | str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        spec = yaml.safe_load(f) or {}
    granules = spec.get("granules") or []
    out = []
    seen = set()
    for g in granules:
        if isinstance(g, str):
            g = {"granule_id": g}
        gid = g["granule_id"]
        if gid in seen:
            continue
        seen.add(gid)
        out.append({**g, "package_id": g.get("package_id") or package_id_for(gid)})
    return out


def granule_paths(granule_id: str, root: Path) -> tuple[Path, Path]:
    package_id = package_id_for(granule_id)
    d = Path(root) / package_id
    return d / f"{granule_id}.pdf", d / f"{granule_id}.mods.xml"


def upsert_granule(conn, row: dict) -> None:
    cols = (
        "granule_id", "package_id", "granule_class", "title", "number", "date_issued", "page_start", "page_end",
        "page_range", "total_pages", "citation", "congress", "era", "pdf_url", "mods_url", "pdf_bytes", "pdf_sha256",
        "pdf_local_path", "mods_local_path", "status", "summary", "mods",
    )
    values = [row.get(c) for c in cols]
    values[cols.index("summary")] = db.jsonb(row.get("summary"))
    values[cols.index("mods")] = db.jsonb(row.get("mods"))
    updates = ", ".join(f"{c} = COALESCE(EXCLUDED.{c}, granules.{c})" for c in cols if c != "granule_id")
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO granules ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
            f"ON CONFLICT (granule_id) DO UPDATE SET {updates}, updated_at = now()",
            values,
        )
    conn.commit()


def ensure_package(client: GovInfoClient, package_id: str) -> None:
    with db.connection() as conn:
        if state.get_package(conn, package_id):
            return
    summary = client.package_summary(package_id)
    if summary is None:
        raise GovInfoError(f"{package_id}: no summary")
    with db.connection() as conn:
        state.upsert_package(conn, state.package_row_from_summary(summary))


def process_granule(client: GovInfoClient, spec: dict, root: Path, parts: int) -> dict:
    granule_id = spec["granule_id"]
    package_id = spec["package_id"]
    ensure_package(client, package_id)
    pdf_path, mods_path = granule_paths(granule_id, root)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    summary = client.granule_summary(package_id, granule_id)
    if summary is None:
        raise GovInfoError(f"{granule_id}: no granule summary")
    download = summary.get("download", {}) or {}
    pdf_url, mods_url = download.get("pdfLink"), download.get("modsLink")

    if not mods_path.exists() and mods_url:
        mods_path.write_bytes(client.fetch_bytes(mods_url))
    mods = parse_mods(mods_path.read_bytes()) if mods_path.exists() else {}

    result = None
    if pdf_url:
        result = client.download_ranged(pdf_url, pdf_path, parts=parts)

    row = {
        "granule_id": granule_id,
        "package_id": package_id,
        "granule_class": summary.get("granuleClass") or mods.get("granule_class"),
        "title": summary.get("title") or mods.get("title"),
        "number": summary.get("number") or mods.get("number"),
        "date_issued": mods.get("granule_date") or summary.get("granuleDate") or summary.get("dateIssued"),
        "page_start": mods.get("page_start"),
        "page_end": mods.get("page_end"),
        "page_range": mods.get("page_range"),
        "total_pages": mods.get("total_pages"),
        "citation": mods.get("citation"),
        "congress": mods.get("congress"),
        "era": spec.get("era"),
        "pdf_url": pdf_url,
        "mods_url": mods_url,
        "pdf_bytes": result.bytes if result else None,
        "pdf_sha256": result.sha256 if (result and result.sha256) else None,
        "pdf_local_path": state.relative_to_repo(pdf_path) if pdf_path.exists() else None,
        "mods_local_path": state.relative_to_repo(mods_path) if mods_path.exists() else None,
        "status": "downloaded" if pdf_path.exists() else "pending",
        "summary": summary,
        "mods": mods or None,
    }
    with db.connection() as conn:
        upsert_granule(conn, row)
    logger.info(
        "%s: %s pages %s (%s), pdf %s", granule_id, row["granule_class"], row["page_range"], row["total_pages"],
        "skipped" if (result and result.skipped) else ("%.1f MB" % (result.bytes / 1e6) if result else "none"),
    )
    return row


def run(args) -> int:
    log_path = setup_logging("fetch_granules", args.log_dir)
    logger.info("log file: %s", log_path)
    db.init_db()
    specs = load_spec(args.spec)
    root = Path(args.data_dir)
    logger.info("%d granule(s) in %s", len(specs), args.spec)
    failures: dict[str, str] = {}
    with GovInfoClient(govinfo_api_key(), max_connections=args.workers * args.parts + 4) as client:
        with ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="granule") as pool:
            futures = {pool.submit(process_granule, client, s, root, args.parts): s["granule_id"] for s in specs}
            for fut in as_completed(futures):
                gid = futures[fut]
                try:
                    fut.result()
                except Exception as exc:
                    logger.error("%s: %s", gid, exc)
                    failures[gid] = str(exc)
    logger.info("done: %d ok, %d failed", len(specs) - len(failures), len(failures))
    for gid, err in sorted(failures.items()):
        logger.error("FAILED %s: %s", gid, err)
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m downloader.fetch_granules", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", required=True, help="YAML sample spec (benchmark/sample.yaml)")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--parts", type=int, default=2)
    p.add_argument("--data-dir", default=str(DATA_DIR / "granules"))
    p.add_argument("--log-dir", default=str(LOG_DIR))
    return p


@exit_on_missing_env
def main(argv: Optional[list[str]] = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
