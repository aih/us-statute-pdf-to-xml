"""HuggingFace Hub uploader: one commit per volume, verification, local cleanup, metadata.jsonl, reconcile.

Verified with huggingface_hub 1.30.0: HfApi.create_commit, CommitOperationAdd, get_paths_info,
list_repo_tree, create_repo, repo_exists. RepoFile exposes path, size, and lfs.sha256 for LFS files.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from huggingface_hub import CommitOperationAdd, HfApi
from huggingface_hub.utils import disable_progress_bars

from . import db, state
from .config import HISTORICAL_DIR
from .state import HubEntry, hub_pdf_path, hub_xml_path, relative_to_repo

logger = logging.getLogger(__name__)

DATASET_CARD = Path(__file__).resolve().parent / "dataset_card.md"
METADATA_PATH = "metadata.jsonl"
REPO_TYPE = "dataset"


class UploadVerificationError(RuntimeError):
    pass


def tree_from_files(files: Iterable) -> dict[str, HubEntry]:
    """Map RepoFile objects (list_repo_tree / get_paths_info) to path -> HubEntry."""
    tree: dict[str, HubEntry] = {}
    for f in files:
        size = getattr(f, "size", None)
        if size is None:  # RepoFolder
            continue
        lfs = getattr(f, "lfs", None)
        sha = getattr(lfs, "sha256", None) if lfs is not None else None
        tree[f.path] = HubEntry(size=size, sha256=sha)
    return tree


@dataclass
class VerifyResult:
    ok: bool
    problems: list[str]


def verify_paths(tree: dict[str, HubEntry], expected: dict[str, tuple[int, Optional[str]]]) -> VerifyResult:
    """Check that every expected path is present with the expected size (and sha256 when both sides have one)."""
    problems = []
    for path, (size, sha) in expected.items():
        entry = tree.get(path)
        if entry is None:
            problems.append(f"{path}: missing from Hub")
            continue
        if entry.size != size:
            problems.append(f"{path}: Hub has {entry.size} bytes, expected {size}")
        if sha and entry.sha256 and entry.sha256 != sha:
            problems.append(f"{path}: Hub sha256 {entry.sha256[:12]} != local {sha[:12]}")
    return VerifyResult(ok=not problems, problems=problems)


def render_metadata(rows: Iterable[dict]) -> str:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


class HubUploader:
    def __init__(self, repo_id: str, token: Optional[str] = None, root: Path | str = HISTORICAL_DIR,
                 api: Optional[HfApi] = None, create: bool = True):
        self.repo_id = repo_id
        self.root = Path(root)
        self.api = api or HfApi(token=token)
        disable_progress_bars()  # progress bars corrupt the log file
        self._tree: Optional[dict[str, HubEntry]] = None
        self._last_metadata: Optional[str] = None
        if create and not self.api.repo_exists(repo_id, repo_type=REPO_TYPE):
            logger.info("creating dataset repo %s", repo_id)
            self.api.create_repo(repo_id, repo_type=REPO_TYPE, private=False, exist_ok=True)

    # ------------------------------------------------------------------ tree

    def hub_tree(self, refresh: bool = False) -> dict[str, HubEntry]:
        if self._tree is None or refresh:
            files = self.api.list_repo_tree(self.repo_id, recursive=True, repo_type=REPO_TYPE)
            self._tree = tree_from_files(files)
            logger.info("Hub tree for %s: %d files", self.repo_id, len(self._tree))
        return self._tree

    def paths_info(self, paths: list[str]) -> dict[str, HubEntry]:
        return tree_from_files(self.api.get_paths_info(self.repo_id, paths, repo_type=REPO_TYPE))

    # ------------------------------------------------------------------ volumes

    def upload_volume(self, item, keep_local: bool = False) -> bool:
        """Commit PDF + XML (+ dataset card on the first commit), verify, record, delete local copies."""
        ops = []
        expected: dict[str, tuple[int, Optional[str]]] = {}
        for kind, path, size, sha in (
            ("pdf", item.pdf, item.pdf_bytes, item.pdf_sha256),
            ("xml", item.xml, item.xml_bytes, item.xml_sha256),
        ):
            hub_path = hub_pdf_path(item.package_id) if kind == "pdf" else hub_xml_path(item.package_id)
            if path.exists():
                if path.stat().st_size != size:
                    raise UploadVerificationError(f"{path} has {path.stat().st_size} bytes, expected {size}")
                ops.append(CommitOperationAdd(path_in_repo=hub_path, path_or_fileobj=str(path)))
                expected[hub_path] = (size, sha)
            elif hub_path in self.hub_tree():
                expected[hub_path] = (size, sha)  # already on the Hub, verified below
            elif size:
                raise UploadVerificationError(f"{item.package_id}: {hub_path} is neither local nor on the Hub")

        if "README.md" not in self.hub_tree() and DATASET_CARD.exists():
            ops.append(CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=str(DATASET_CARD)))

        commit_oid = None
        if ops:
            info = self.api.create_commit(
                self.repo_id, ops, commit_message=f"Add {item.package_id}", repo_type=REPO_TYPE,
            )
            commit_oid = getattr(info, "oid", None)
            logger.info("%s: committed %d file(s) (%s)", item.package_id, len(ops), commit_oid)

        # Verify against the Hub, not against the commit response.
        info_tree = self.paths_info(list(expected))
        result = verify_paths(info_tree, expected)
        if not result.ok:
            raise UploadVerificationError(f"{item.package_id}: " + "; ".join(result.problems))
        self.hub_tree().update(info_tree)
        if "README.md" in [op.path_in_repo for op in ops]:
            self.hub_tree()["README.md"] = HubEntry(size=DATASET_CARD.stat().st_size)

        with db.connection() as conn:
            state.mark_uploaded(conn, item.package_id, commit_oid or "")
            state.mark_verified(conn, item.package_id)
            if not keep_local:
                for kind, path in (("pdf", item.pdf), ("xml", item.xml)):
                    if path.exists():
                        path.unlink()
                        logger.info("%s: deleted local %s", item.package_id, relative_to_repo(path))
                    for stray in path.parent.glob(path.name + ".part*"):
                        stray.unlink(missing_ok=True)
                    state.set_file_state(conn, item.package_id, kind, clear_local=True)
        return True

    # ------------------------------------------------------------------ metadata

    def flush_metadata(self, force: bool = False) -> Optional[str]:
        """Regenerate metadata.jsonl from the packages table and commit it when it changed."""
        with db.connection() as conn:
            rows = state.metadata_rows(state.list_packages(conn, "STATUTE"))
        content = render_metadata(rows)
        if not rows:
            logger.info("metadata.jsonl: no uploaded volumes yet; nothing to commit")
            return None
        if content == self._last_metadata and not force:
            return None
        if self._last_metadata is None and METADATA_PATH in self.hub_tree():
            try:
                current = self.api.hf_hub_download(self.repo_id, METADATA_PATH, repo_type=REPO_TYPE)
                if Path(current).read_text(encoding="utf-8") == content:
                    self._last_metadata = content
                    logger.info("metadata.jsonl: Hub copy is current (%d rows)", len(rows))
                    return None
            except Exception as exc:  # pragma: no cover - network
                logger.warning("could not compare metadata.jsonl on the Hub: %s", exc)
        local = self.root / METADATA_PATH
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(content, encoding="utf-8")
        info = self.api.create_commit(
            self.repo_id,
            [CommitOperationAdd(path_in_repo=METADATA_PATH, path_or_fileobj=content.encode("utf-8"))],
            commit_message=f"Update metadata.jsonl ({len(rows)} volumes)",
            repo_type=REPO_TYPE,
        )
        self._last_metadata = content
        self.hub_tree()[METADATA_PATH] = HubEntry(size=len(content.encode("utf-8")))
        logger.info("metadata.jsonl: committed %d rows (%s)", len(rows), getattr(info, "oid", None))
        return getattr(info, "oid", None)


# ---------------------------------------------------------------------- reconcile


@dataclass
class ReconcileEntry:
    package_id: str
    path: str
    category: str  # local-only, hub-only, size-mismatch, missing
    detail: str


def classify(package_id: str, expected: dict[str, Optional[int]], tree: dict[str, HubEntry],
             local: dict[str, Optional[int]]) -> list[ReconcileEntry]:
    entries = []
    for path, size in expected.items():
        if size is None:
            continue
        hub = tree.get(path)
        loc = local.get(path)
        if hub is not None and hub.size != size:
            entries.append(ReconcileEntry(package_id, path, "size-mismatch", f"Hub {hub.size} != GovInfo {size}"))
        if loc is not None and loc != size:
            entries.append(ReconcileEntry(package_id, path, "size-mismatch", f"local {loc} != GovInfo {size}"))
        if hub is None and loc == size:
            entries.append(ReconcileEntry(package_id, path, "local-only", f"{size} bytes"))
        if hub is None and (loc is None or loc != size):
            entries.append(ReconcileEntry(package_id, path, "missing", "not on Hub, not complete locally"))
    return entries


def hub_only(tree: dict[str, HubEntry], known_packages: set[str]) -> list[ReconcileEntry]:
    entries = []
    for path in sorted(tree):
        if not (path.startswith("pdfs/") or path.startswith("xmls/")):
            continue
        package_id = Path(path).stem
        if package_id not in known_packages:
            entries.append(ReconcileEntry(package_id, path, "hub-only", "no packages row for this file"))
    return entries


def reconcile_cli(args) -> int:
    from .config import govinfo_api_key, require_env
    from .fetch_historical import Context, RunStats, process_volume
    from .govinfo import GovInfoClient, parse_volume_spec
    import threading

    repo_id = require_env("HF_REPO_ID")
    token = require_env("HF_TOKEN")
    root = Path(args.data_dir)
    uploader = HubUploader(repo_id=repo_id, token=token, root=root, create=False)
    tree = uploader.hub_tree()
    volumes = parse_volume_spec(args.volumes)

    with db.connection() as conn:
        packages = {p["package_id"]: p for p in state.list_packages(conn, "STATUTE")}

    entries: list[ReconcileEntry] = []
    to_fix: list[int] = []
    with GovInfoClient(govinfo_api_key()) as client:
        for volume in volumes:
            package_id = f"STATUTE-{volume}"
            row = packages.get(package_id)
            if row is None or row.get("pdf_bytes") is None or row.get("xml_bytes") is None:
                summary = client.package_summary(package_id)
                if summary is None:
                    continue
                r = state.package_row_from_summary(summary)
                sizes = {}
                for kind, url in (("pdf", r["pdf_url"]), ("xml", r["xml_url"])):
                    sizes[kind] = client.head(url).size if url else None
                with db.connection() as conn:
                    state.upsert_package(conn, r)
                    for kind, size in sizes.items():
                        if size is not None:
                            state.set_file_state(conn, package_id, kind, bytes_=size)
                row = {"pdf_bytes": sizes["pdf"], "xml_bytes": sizes["xml"]}
                packages[package_id] = row
            expected = {hub_pdf_path(package_id): row.get("pdf_bytes"), hub_xml_path(package_id): row.get("xml_bytes")}
            found = classify(package_id, expected, tree, state.local_sizes_for(package_id, root))
            entries.extend(found)
            if any(e.category in ("local-only", "size-mismatch") for e in found):
                to_fix.append(volume)
        entries.extend(hub_only(tree, set(packages)))

        by_cat: dict[str, list[ReconcileEntry]] = {}
        for e in entries:
            by_cat.setdefault(e.category, []).append(e)
        for cat in ("local-only", "hub-only", "size-mismatch", "missing"):
            items = by_cat.get(cat, [])
            print(f"{cat}: {len(items)}")
            for e in items:
                print(f"  {e.path}  {e.detail}")
        if not entries:
            print("no differences")

        if args.fix and to_fix:
            print(f"fixing {len(to_fix)} volume(s): {to_fix}")
            stats = RunStats()
            ctx = Context(client=client, root=root, parts=args.parts, upload_enabled=True, hub_tree=tree,
                          stop=threading.Event(), stats=stats)
            for volume in to_fix:
                package_id = f"STATUTE-{volume}"
                for path in (state.local_pdf_path(package_id, root), state.local_xml_path(package_id, root)):
                    expected_size = packages[package_id].get("pdf_bytes" if path.suffix == ".pdf" else "xml_bytes")
                    if path.exists() and expected_size is not None and path.stat().st_size != expected_size:
                        logger.warning("deleting %s (%d bytes, expected %d)", path, path.stat().st_size, expected_size)
                        path.unlink()
                for hub_path in (hub_pdf_path(package_id), hub_xml_path(package_id)):
                    entry = tree.get(hub_path)
                    if entry is not None and entry.size != packages[package_id].get(
                        "pdf_bytes" if hub_path.endswith(".pdf") else "xml_bytes"
                    ):
                        tree.pop(hub_path, None)  # force re-upload
                files = process_volume(volume, ctx)
                if files is not None:
                    uploader.upload_volume(files, keep_local=args.keep_local)
            uploader.flush_metadata(force=True)
            if stats.failed:
                for package_id, error in stats.failed.items():
                    print(f"FAILED {package_id}: {error}")
                return 1
    return 0 if not any(e.category in ("size-mismatch", "local-only") for e in entries) or args.fix else 1
