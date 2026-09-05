"""Download Statutes at Large volumes (PDF + USLM XML) from GovInfo and upload them to the Hub.

    python -m downloader.fetch_historical [fetch] --volumes 1-137 --parts 4 --files 2 [--no-upload] [--keep-local]
    python -m downloader.fetch_historical reconcile [--fix]

Stages: a thread pool downloads volumes (`--files` at a time, `--parts` connections per file), a
bounded queue holds at most `--queue-size` downloaded volumes, and one uploader thread commits each
volume to the Hub, verifies it, and deletes the local copy. Every volume decision (skip,
upload-only, download) comes from `state.decide` after comparing GovInfo Content-Length, the Hub
tree, and local files.
"""

from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import db, state
from .config import HISTORICAL_DIR, LOG_DIR, exit_on_missing_env, govinfo_api_key, require_env, setup_logging
from .govinfo import GovInfoClient, GovInfoError, RemoteFile, parse_volume_spec, sha256_file

logger = logging.getLogger("fetch_historical")

DEFAULT_VOLUMES = "1-137"


@dataclass
class VolumeFiles:
    """A volume whose PDF and XML are complete on disk and ready for upload."""

    package_id: str
    volume: int
    pdf: Path
    xml: Path
    pdf_bytes: int
    xml_bytes: int
    pdf_sha256: Optional[str]
    xml_sha256: Optional[str]


@dataclass
class RunStats:
    skipped: list[str] = field(default_factory=list)
    downloaded: list[str] = field(default_factory=list)
    upload_only: list[str] = field(default_factory=list)
    uploaded: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, bucket: str, package_id: str, error: str = ""):
        with self.lock:
            if bucket == "failed":
                self.failed[package_id] = error
            else:
                getattr(self, bucket).append(package_id)


class NullUploader:
    """Upload sink used with --no-upload: records nothing on the Hub."""

    def hub_tree(self) -> dict[str, state.HubEntry]:
        return {}

    def upload_volume(self, item: VolumeFiles, keep_local: bool) -> bool:
        logger.info("%s: upload disabled; local files kept", item.package_id)
        return False

    def flush_metadata(self, force: bool = False) -> None:
        return None


@dataclass
class Context:
    client: GovInfoClient
    root: Path
    parts: int
    upload_enabled: bool
    hub_tree: dict[str, state.HubEntry]
    stop: threading.Event
    stats: RunStats


def _head_or_none(client: GovInfoClient, url: Optional[str]) -> Optional[RemoteFile]:
    if not url:
        return None
    return client.head(url)


def process_volume(volume: int, ctx: Context) -> Optional[VolumeFiles]:
    """Fetch summary and sizes, decide, download what is missing. Returns files ready for upload or None."""
    package_id = f"STATUTE-{volume}"
    if ctx.stop.is_set():
        return None
    summary = ctx.client.package_summary(package_id)
    if summary is None:
        logger.warning("%s: not found on GovInfo", package_id)
        ctx.stats.add("missing", package_id)
        return None

    row = state.package_row_from_summary(summary)
    remotes = {
        "pdf": _head_or_none(ctx.client, row["pdf_url"]),
        "xml": _head_or_none(ctx.client, row["xml_url"]),
    }
    hub_paths = {"pdf": state.hub_pdf_path(package_id), "xml": state.hub_xml_path(package_id)}
    local_paths = {"pdf": state.local_pdf_path(package_id, ctx.root), "xml": state.local_xml_path(package_id, ctx.root)}
    expected = {hub_paths[k]: (r.size if r else None) for k, r in remotes.items()}

    with db.connection() as conn:
        state.upsert_package(conn, row)
        existing = state.get_package(conn, package_id) or {}
        for kind, remote in remotes.items():
            if remote:
                state.set_file_state(conn, package_id, kind, bytes_=remote.size)

    local_sizes = {hub_paths[k]: state.local_size(p) for k, p in local_paths.items()}
    decision = state.decide(package_id, expected, ctx.hub_tree, local_sizes, ctx.upload_enabled)
    logger.info("%s: %s (%s)", package_id, decision.action, decision.reason)

    if decision.action == "skip":
        ctx.stats.add("skipped", package_id)
        return None

    if decision.action == "download":
        for kind in ("pdf", "xml"):
            remote = remotes[kind]
            if remote is None:
                continue
            fd = next(f for f in decision.files if f.hub_path == hub_paths[kind])
            if fd.on_hub or fd.local_complete:
                continue
            if ctx.stop.is_set():
                return None
            logger.info("%s: downloading %s (%.1f MB, %d parts)", package_id, kind, remote.size / 1e6, ctx.parts)
            result = ctx.client.download_ranged(remote.url, local_paths[kind], parts=ctx.parts, remote=remote)
            logger.info(
                "%s: %s done, %.1f MB in %.0fs (%.2f MB/s)", package_id, kind, result.bytes / 1e6, result.seconds,
                result.bytes / 1e6 / max(result.seconds, 0.001),
            )
            with db.connection() as conn:
                state.set_file_state(
                    conn, package_id, kind, status="downloaded", bytes_=result.bytes, sha256=result.sha256,
                    local_path=str(result.path),
                )
        ctx.stats.add("downloaded", package_id)
    else:
        ctx.stats.add("upload_only", package_id)

    # Both files are now complete locally (or on the Hub). Fill in hashes for anything downloaded earlier.
    hashes = {}
    for kind in ("pdf", "xml"):
        path = local_paths[kind]
        stored = existing.get(f"{kind}_sha256")
        if path.exists():
            if stored and existing.get(f"{kind}_bytes") == path.stat().st_size:
                hashes[kind] = stored
            else:
                hashes[kind] = sha256_file(path)
                with db.connection() as conn:
                    state.set_file_state(conn, package_id, kind, status="downloaded", bytes_=path.stat().st_size,
                                         sha256=hashes[kind], local_path=str(path))
        else:
            hashes[kind] = stored

    return VolumeFiles(
        package_id=package_id,
        volume=volume,
        pdf=local_paths["pdf"],
        xml=local_paths["xml"],
        pdf_bytes=remotes["pdf"].size if remotes["pdf"] else 0,
        xml_bytes=remotes["xml"].size if remotes["xml"] else 0,
        pdf_sha256=hashes.get("pdf"),
        xml_sha256=hashes.get("xml"),
    )


def uploader_loop(q: "queue.Queue[Optional[VolumeFiles]]", uploader, keep_local: bool, stats: RunStats,
                  metadata_every: int) -> None:
    count = 0
    while True:
        item = q.get()
        try:
            if item is None:
                break
            try:
                if uploader.upload_volume(item, keep_local=keep_local):
                    stats.add("uploaded", item.package_id)
                    count += 1
                    if metadata_every and count % metadata_every == 0:
                        uploader.flush_metadata()
            except Exception as exc:  # keep the pipeline running; the failure is recorded
                logger.exception("%s: upload failed", item.package_id)
                stats.add("failed", item.package_id, f"upload: {exc}")
                with db.connection() as conn:
                    state.set_file_state(conn, item.package_id, "pdf", status="upload-failed")
                    state.set_file_state(conn, item.package_id, "xml", status="upload-failed")
        finally:
            q.task_done()
    try:
        uploader.flush_metadata(force=True)
    except Exception:
        logger.exception("final metadata flush failed")


def build_uploader(args, client: GovInfoClient):
    if args.no_upload:
        return NullUploader()
    token = require_env("HF_TOKEN", "Uploads need a HuggingFace token with repo.write on HF_REPO_ID, or pass --no-upload.")
    repo_id = require_env("HF_REPO_ID")
    try:
        from .hf_upload import HubUploader
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(f"Hub uploads are unavailable: {exc}. Use --no-upload.")
    return HubUploader(repo_id=repo_id, token=token, root=Path(args.data_dir))


def run_fetch(args) -> int:
    log_path = setup_logging("fetch_historical", args.log_dir)
    logger.info("log file: %s", log_path)
    applied = db.init_db()
    if applied:
        logger.info("applied migrations: %s", applied)

    volumes = parse_volume_spec(args.volumes)
    root = Path(args.data_dir)
    (root / "pdfs").mkdir(parents=True, exist_ok=True)
    (root / "xmls").mkdir(parents=True, exist_ok=True)

    stats = RunStats()
    stop = threading.Event()
    started = time.monotonic()

    with GovInfoClient(govinfo_api_key(), max_connections=max(16, args.files * args.parts + 4)) as client:
        uploader = build_uploader(args, client)
        hub_tree = uploader.hub_tree()
        logger.info("Hub tree: %d files; volumes requested: %d (%s)", len(hub_tree), len(volumes), args.volumes)
        ctx = Context(client=client, root=root, parts=args.parts, upload_enabled=not args.no_upload,
                      hub_tree=hub_tree, stop=stop, stats=stats)

        q: "queue.Queue[Optional[VolumeFiles]]" = queue.Queue(maxsize=args.queue_size)
        uploader_thread = threading.Thread(
            target=uploader_loop, args=(q, uploader, args.keep_local, stats, args.metadata_every),
            name="uploader", daemon=True,
        )
        uploader_thread.start()

        def work(volume: int) -> None:
            try:
                files = process_volume(volume, ctx)
            except (GovInfoError, OSError) as exc:
                logger.error("STATUTE-%d: %s", volume, exc)
                stats.add("failed", f"STATUTE-{volume}", str(exc))
                return
            if files is not None:
                q.put(files)  # blocks when the queue is full, which bounds disk use

        pool = ThreadPoolExecutor(max_workers=args.files, thread_name_prefix="volume")
        futures = [pool.submit(work, v) for v in volumes]
        try:
            for fut in as_completed(futures):
                exc = fut.exception()
                if exc is not None:
                    logger.exception("worker crashed", exc_info=exc)
        except KeyboardInterrupt:
            logger.warning("interrupted; part files are kept for resume")
            stop.set()
            pool.shutdown(wait=False, cancel_futures=True)
            q.put(None)
            uploader_thread.join(timeout=30)
            return 130
        pool.shutdown(wait=True)
        q.put(None)
        uploader_thread.join()

    elapsed = time.monotonic() - started
    logger.info(
        "done in %.0fs: skipped %d, downloaded %d, upload-only %d, uploaded %d, missing %d, failed %d",
        elapsed, len(stats.skipped), len(stats.downloaded), len(stats.upload_only), len(stats.uploaded),
        len(stats.missing), len(stats.failed),
    )
    for package_id, error in sorted(stats.failed.items()):
        logger.error("FAILED %s: %s", package_id, error)
    return 1 if stats.failed else 0


def run_reconcile(args) -> int:
    from .hf_upload import reconcile_cli

    setup_logging("reconcile", args.log_dir)
    db.init_db()
    return reconcile_cli(args)


def add_common_args(p: argparse.ArgumentParser):
    p.add_argument("--data-dir", default=str(HISTORICAL_DIR), help="local root with pdfs/ and xmls/ (default data/historical)")
    p.add_argument("--log-dir", default=str(LOG_DIR), help="directory for <script>-<date>.log (default data/logs)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m downloader.fetch_historical", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")

    fetch = sub.add_parser("fetch", help="download volumes and upload them (default command)")
    fetch.add_argument("--volumes", default=DEFAULT_VOLUMES, help="e.g. 1-137 or 118-119,64 (default 1-137)")
    fetch.add_argument("--parts", type=int, default=4, help="parallel range requests per file (default 4)")
    fetch.add_argument("--files", type=int, default=2, help="volumes downloaded concurrently (default 2)")
    fetch.add_argument("--queue-size", type=int, default=3, help="downloaded volumes waiting for upload (default 3)")
    fetch.add_argument("--metadata-every", type=int, default=10, help="commit metadata.jsonl every N uploads (default 10)")
    fetch.add_argument("--no-upload", action="store_true", help="download only; leave files under --data-dir")
    fetch.add_argument("--keep-local", action="store_true", help="do not delete local files after a verified upload")
    add_common_args(fetch)
    fetch.set_defaults(func=run_fetch)

    rec = sub.add_parser("reconcile", help="compare local files, the Hub tree, and GovInfo sizes")
    rec.add_argument("--volumes", default=DEFAULT_VOLUMES)
    rec.add_argument("--fix", action="store_true", help="upload local-only volumes and re-download mismatches")
    rec.add_argument("--parts", type=int, default=4)
    rec.add_argument("--keep-local", action="store_true")
    add_common_args(rec)
    rec.set_defaults(func=run_reconcile)
    return parser


@exit_on_missing_env
def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        argv.insert(0, "fetch")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
