"""Per-package state in Postgres and the reconcile decision between local files, the Hub tree, and GovInfo."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Optional

from . import db
from .config import HISTORICAL_DIR, REPO_ROOT, is_scanned_volume

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------- paths


def hub_pdf_path(package_id: str) -> str:
    return f"pdfs/{package_id}.pdf"


def hub_xml_path(package_id: str) -> str:
    return f"xmls/{package_id}.xml"


def local_pdf_path(package_id: str, root: Path = HISTORICAL_DIR) -> Path:
    return Path(root) / "pdfs" / f"{package_id}.pdf"


def local_xml_path(package_id: str, root: Path = HISTORICAL_DIR) -> Path:
    return Path(root) / "xmls" / f"{package_id}.xml"


# ---------------------------------------------------------------------------- reconcile


@dataclass(frozen=True)
class HubEntry:
    size: int
    sha256: Optional[str] = None


@dataclass(frozen=True)
class FileDecision:
    """What to do about one file (pdf or xml) of one package."""

    hub_path: str
    expected: Optional[int]  # Content-Length from GovInfo, None when unknown
    hub: Optional[HubEntry]
    local: Optional[int]  # local byte count, None when absent

    @property
    def on_hub(self) -> bool:
        return self.hub is not None and (self.expected is None or self.hub.size == self.expected)

    @property
    def hub_mismatch(self) -> bool:
        return self.hub is not None and self.expected is not None and self.hub.size != self.expected

    @property
    def local_complete(self) -> bool:
        return self.local is not None and self.expected is not None and self.local == self.expected

    @property
    def local_partial(self) -> bool:
        return self.local is not None and not self.local_complete


@dataclass(frozen=True)
class Decision:
    package_id: str
    action: str  # "skip", "upload-only", "download"
    reason: str
    files: tuple[FileDecision, ...] = field(default_factory=tuple)


def decide(
    package_id: str,
    expected: Mapping[str, Optional[int]],
    hub_tree: Mapping[str, HubEntry],
    local_sizes: Mapping[str, Optional[int]],
    upload_enabled: bool = True,
) -> Decision:
    """Decide skip / upload-only / download for one package.

    `expected` maps hub path -> Content-Length (None when GovInfo has no such file).
    `hub_tree` maps hub path -> HubEntry for every file on the Hub.
    `local_sizes` maps hub path -> local byte count or None.

    skip: every expected file is on the Hub with the expected size (or, with uploads disabled,
          complete locally).
    upload-only: every expected file is complete locally and at least one is missing from the Hub.
    download: at least one expected file is neither on the Hub nor complete locally.
    """
    files = tuple(
        FileDecision(hub_path=path, expected=size, hub=hub_tree.get(path), local=local_sizes.get(path))
        for path, size in expected.items()
        if size is not None
    )
    if not files:
        return Decision(package_id, "skip", "GovInfo lists no files for this package", files)

    if upload_enabled:
        if all(f.on_hub for f in files):
            return Decision(package_id, "skip", "on Hub with matching sizes", files)
        mismatched = [f.hub_path for f in files if f.hub_mismatch]
        if all(f.on_hub or f.local_complete for f in files):
            reason = "complete locally, missing from Hub"
            if mismatched:
                reason = f"Hub size mismatch for {', '.join(mismatched)}; complete locally"
            return Decision(package_id, "upload-only", reason, files)
        missing = [f.hub_path for f in files if not (f.on_hub or f.local_complete)]
        reason = f"missing or incomplete: {', '.join(missing)}"
        if mismatched:
            reason = f"Hub size mismatch for {', '.join(mismatched)}; {reason}"
        return Decision(package_id, "download", reason, files)

    if all(f.local_complete for f in files):
        return Decision(package_id, "skip", "complete locally (uploads disabled)", files)
    missing = [f.hub_path for f in files if not f.local_complete]
    return Decision(package_id, "download", f"missing or incomplete locally: {', '.join(missing)}", files)


def relative_to_repo(path: Path | str) -> str:
    """Store paths relative to the repository root so host and container agree."""
    path = Path(path)
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def local_size(path: Path) -> Optional[int]:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return None


def local_sizes_for(package_id: str, root: Path = HISTORICAL_DIR) -> dict[str, Optional[int]]:
    return {
        hub_pdf_path(package_id): local_size(local_pdf_path(package_id, root)),
        hub_xml_path(package_id): local_size(local_xml_path(package_id, root)),
    }


# ---------------------------------------------------------------------------- summaries -> rows


def _int_or_none(value) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _date_or_none(value) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def package_row_from_summary(summary: dict) -> dict:
    """Map a GovInfo package summary to `packages` columns."""
    package_id = summary["packageId"]
    collection = summary.get("collectionCode") or package_id.split("-")[0]
    volume = _int_or_none(summary.get("volume"))
    if volume is None and collection == "PLAW":
        for ref in summary.get("references", []) or []:
            if ref.get("collectionCode") == "STATUTE":
                for item in ref.get("contents", []) or []:
                    volume = _int_or_none(item.get("title"))
    download = summary.get("download", {}) or {}
    return {
        "package_id": package_id,
        "collection": collection,
        "volume": volume,
        "congress": _int_or_none(summary.get("congress")),
        "session": _int_or_none(summary.get("session")),
        "date_issued": _date_or_none(summary.get("dateIssued")),
        "pages": _int_or_none(summary.get("pages")),
        "title": summary.get("title"),
        "scanned": is_scanned_volume(volume) if (collection == "STATUTE" and volume is not None) else None,
        "pdf_url": download.get("pdfLink"),
        "xml_url": download.get("uslmLink"),
        "summary": summary,
    }


def plaw_pages_from_summary(summary: dict) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """(volume, start_page, end_page) for a public law from its summary's Statutes at Large references.

    The references list every Statutes at Large citation in the law, including earlier statutes it
    amends. The law's own entry is the one whose page count equals the summary's `pages`; when no
    entry matches, the entry with the most pages is used.
    """
    total = _int_or_none(summary.get("pages"))
    candidates = []
    for ref in summary.get("references", []) or []:
        if ref.get("collectionCode") != "STATUTE":
            continue
        for item in ref.get("contents", []) or []:
            volume = _int_or_none(item.get("title"))
            pages = [p for p in (_int_or_none(x) for x in item.get("pages", []) or []) if p is not None]
            candidates.append((volume, pages))
    if not candidates:
        return None, None, None
    exact = [c for c in candidates if total and len(c[1]) == total]
    volume, pages = (exact or sorted(candidates, key=lambda c: len(c[1]), reverse=True))[0]
    if pages:
        return volume, min(pages), max(pages)
    return volume, None, None


_CITABLE_AS = re.compile(r"<citableAs>\s*(\d+)\s+Stat\.\s+(\d+)\s*</citableAs>")
_PAGE_ID = re.compile(r'<page[^>]*identifier="/us/stat/(\d+)/(\d+)"')


def plaw_pages_from_uslm(xml: bytes | str) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """(volume, start_page, end_page) from a PLAW USLM: <citableAs>N Stat. P</citableAs> and <page> markers."""
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8", errors="replace")
    m = _CITABLE_AS.search(xml)
    if not m:
        return None, None, None
    volume, start = int(m.group(1)), int(m.group(2))
    pages = [int(p) for v, p in _PAGE_ID.findall(xml) if int(v) == volume]
    end = max(pages) if pages else start
    return volume, start, max(start, end)


# ---------------------------------------------------------------------------- persistence

PACKAGE_COLUMNS = (
    "package_id", "collection", "volume", "congress", "session", "date_issued", "pages", "title", "scanned",
    "pdf_url", "xml_url", "summary",
)


def upsert_package(conn, row: Mapping) -> None:
    values = [row.get(c) for c in PACKAGE_COLUMNS]
    values[-1] = db.jsonb(row.get("summary"))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in PACKAGE_COLUMNS if c != "package_id")
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO packages ({', '.join(PACKAGE_COLUMNS)}) VALUES ({', '.join(['%s'] * len(PACKAGE_COLUMNS))}) "
            f"ON CONFLICT (package_id) DO UPDATE SET {updates}, updated_at = now()",
            values,
        )
    conn.commit()


def set_file_state(conn, package_id: str, kind: str, *, status: Optional[str] = None, bytes_: Optional[int] = None,
                   sha256: Optional[str] = None, local_path: Optional[str] = None, hub_path: Optional[str] = None,
                   clear_local: bool = False) -> None:
    """Update the pdf_* or xml_* columns of a package. `kind` is 'pdf' or 'xml'."""
    assert kind in ("pdf", "xml")
    sets = ["updated_at = now()"]
    params: list = []
    if status is not None:
        sets.append(f"{kind}_status = %s")
        params.append(status)
        if status == "downloaded":
            sets.append("downloaded_at = now()")
    if bytes_ is not None:
        sets.append(f"{kind}_bytes = %s")
        params.append(bytes_)
    if sha256 is not None:
        sets.append(f"{kind}_sha256 = %s")
        params.append(sha256)
    if local_path is not None:
        sets.append(f"{kind}_local_path = %s")
        params.append(relative_to_repo(local_path))
    if clear_local:
        sets.append(f"{kind}_local_path = NULL")
    if hub_path is not None:
        sets.append(f"hub_{kind}_path = %s")
        params.append(hub_path)
    params.append(package_id)
    with conn.cursor() as cur:
        cur.execute(f"UPDATE packages SET {', '.join(sets)} WHERE package_id = %s", params)
    conn.commit()


def mark_uploaded(conn, package_id: str, commit: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE packages SET hub_commit = %s, uploaded_at = now(), pdf_status = 'uploaded', "
            "xml_status = 'uploaded', hub_pdf_path = %s, hub_xml_path = %s, updated_at = now() WHERE package_id = %s",
            (commit, hub_pdf_path(package_id), hub_xml_path(package_id), package_id),
        )
    conn.commit()


def mark_verified(conn, package_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE packages SET pdf_status = 'verified', xml_status = 'verified', updated_at = now() "
            "WHERE package_id = %s",
            (package_id,),
        )
    conn.commit()


def get_package(conn, package_id: str) -> Optional[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM packages WHERE package_id = %s", (package_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def list_packages(conn, collection: str = "STATUTE") -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM packages WHERE collection = %s ORDER BY volume, package_id", (collection,))
        return [dict(r) for r in cur.fetchall()]


def metadata_rows(packages: Iterable[Mapping]) -> list[dict]:
    """Rows for metadata.jsonl, one per STATUTE volume that has been uploaded and verified."""
    rows = []
    for p in packages:
        if p.get("collection") != "STATUTE":
            continue
        if p.get("pdf_status") not in ("uploaded", "verified"):
            continue
        rows.append(
            {
                "file_name": hub_pdf_path(p["package_id"]),
                "package_id": p["package_id"],
                "volume": p.get("volume"),
                "congress": p.get("congress"),
                "session": p.get("session"),
                "date_issued": p["date_issued"].isoformat() if p.get("date_issued") else None,
                "pages": p.get("pages"),
                "scanned": p.get("scanned"),
                "pdf_bytes": p.get("pdf_bytes"),
                "pdf_sha256": p.get("pdf_sha256"),
                "xml_file": hub_xml_path(p["package_id"]) if p.get("xml_status") in ("uploaded", "verified") else None,
                "xml_bytes": p.get("xml_bytes"),
                "xml_sha256": p.get("xml_sha256"),
                "source_package_url": f"https://www.govinfo.gov/app/details/{p['package_id']}",
            }
        )
    rows.sort(key=lambda r: (r["volume"] or 0, r["package_id"]))
    return rows
