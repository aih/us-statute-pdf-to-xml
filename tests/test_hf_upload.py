import hashlib
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from downloader import hf_upload, state
from downloader.hf_upload import HubUploader, UploadVerificationError, classify, hub_only, verify_paths
from downloader.state import HubEntry


class FakeApi:
    """Minimal HfApi stand-in: an in-memory tree plus a record of commits."""

    def __init__(self, tree=None, exists=True):
        self.tree = dict(tree or {})
        self.exists = exists
        self.commits = []
        self.created = []

    def repo_exists(self, repo_id, repo_type=None):
        return self.exists

    def create_repo(self, repo_id, repo_type=None, private=None, exist_ok=False):
        self.created.append(repo_id)
        self.exists = True

    def _files(self, paths):
        out = []
        for p in paths:
            if p in self.tree:
                size, sha = self.tree[p]
                out.append(SimpleNamespace(path=p, size=size, lfs=SimpleNamespace(sha256=sha) if sha else None))
        return out

    def list_repo_tree(self, repo_id, recursive=False, repo_type=None):
        return self._files(sorted(self.tree)) + [SimpleNamespace(path="pdfs")]  # a folder has no size

    def get_paths_info(self, repo_id, paths, repo_type=None):
        return self._files(paths)

    def create_commit(self, repo_id, operations, commit_message, repo_type=None):
        ops = list(operations)
        self.commits.append((commit_message, [op.path_in_repo for op in ops]))
        for op in ops:
            src = op.path_or_fileobj
            data = Path(src).read_bytes() if isinstance(src, str) else src
            self.tree[op.path_in_repo] = (len(data), hashlib.sha256(data).hexdigest())
        return SimpleNamespace(oid=f"oid{len(self.commits)}")


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.sql.append((sql, params))

    def fetchall(self):
        return self.conn.rows

    def fetchone(self):
        return None


class FakeConn:
    def __init__(self, rows=()):
        self.sql = []
        self.rows = list(rows)

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        pass


@pytest.fixture
def fake_db(monkeypatch):
    conn = FakeConn()

    @contextmanager
    def connection():
        yield conn

    monkeypatch.setattr(hf_upload.db, "connection", connection)
    return conn


def make_item(tmp_path, pdf=b"%PDF-1.4 fake pdf", xml=b"<statutesAtLarge/>"):
    pdf_path = tmp_path / "pdfs" / "STATUTE-118.pdf"
    xml_path = tmp_path / "xmls" / "STATUTE-118.xml"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(pdf)
    xml_path.write_bytes(xml)
    return SimpleNamespace(
        package_id="STATUTE-118", volume=118, pdf=pdf_path, xml=xml_path, pdf_bytes=len(pdf), xml_bytes=len(xml),
        pdf_sha256=hashlib.sha256(pdf).hexdigest(), xml_sha256=hashlib.sha256(xml).hexdigest(),
    )


def test_verify_paths_reports_missing_size_and_sha():
    tree = {"a": HubEntry(10, "x" * 64), "b": HubEntry(5, None)}
    result = verify_paths(tree, {"a": (10, "y" * 64), "b": (6, None), "c": (1, None)})
    assert not result.ok
    assert any("c: missing" in p for p in result.problems)
    assert any("b: Hub has 5" in p for p in result.problems)
    assert any("a: Hub sha256" in p for p in result.problems)
    assert verify_paths(tree, {"a": (10, "x" * 64), "b": (5, "ignored-since-hub-has-none")}).ok


def test_first_upload_creates_repo_commits_card_and_deletes_local(tmp_path, fake_db):
    api = FakeApi(exists=False)
    up = HubUploader("org/repo", root=tmp_path, api=api)
    assert api.created == ["org/repo"]
    item = make_item(tmp_path)
    assert up.upload_volume(item, keep_local=False) is True
    message, paths = api.commits[0]
    assert message == "Add STATUTE-118"
    assert set(paths) == {"pdfs/STATUTE-118.pdf", "xmls/STATUTE-118.xml", "README.md"}
    assert not item.pdf.exists() and not item.xml.exists()
    assert up.hub_tree()["pdfs/STATUTE-118.pdf"].size == item.pdf_bytes
    sql = " ".join(s for s, _ in fake_db.sql)
    assert "hub_commit" in sql and "verified" in sql and "pdf_local_path = NULL" in sql


def test_keep_local_retains_files_and_second_volume_skips_card(tmp_path, fake_db):
    api = FakeApi(tree={"README.md": (10, None)})
    up = HubUploader("org/repo", root=tmp_path, api=api)
    item = make_item(tmp_path)
    up.upload_volume(item, keep_local=True)
    assert item.pdf.exists() and item.xml.exists()
    assert "README.md" not in api.commits[0][1]


def test_failed_verification_keeps_local_files(tmp_path, fake_db):
    class LyingApi(FakeApi):
        def get_paths_info(self, repo_id, paths, repo_type=None):
            files = super().get_paths_info(repo_id, paths, repo_type)
            for f in files:
                f.size = f.size + 1
            return files

    api = LyingApi()
    up = HubUploader("org/repo", root=tmp_path, api=api)
    item = make_item(tmp_path)
    with pytest.raises(UploadVerificationError, match="bytes"):
        up.upload_volume(item, keep_local=False)
    assert item.pdf.exists() and item.xml.exists()
    assert not any("hub_commit" in s for s, _ in fake_db.sql)


def test_local_size_mismatch_refuses_upload(tmp_path, fake_db):
    api = FakeApi()
    up = HubUploader("org/repo", root=tmp_path, api=api)
    item = make_item(tmp_path)
    item.pdf_bytes += 1
    with pytest.raises(UploadVerificationError):
        up.upload_volume(item)
    assert api.commits == []


def test_flush_metadata_commits_only_when_changed(tmp_path, fake_db):
    import datetime as dt

    fake_db.rows = [
        {"package_id": "STATUTE-118", "collection": "STATUTE", "volume": 118, "pdf_status": "verified",
         "xml_status": "verified", "date_issued": dt.date(2004, 12, 8), "pdf_bytes": 1, "pdf_sha256": "a",
         "xml_bytes": 2, "xml_sha256": "b", "scanned": False, "congress": 108, "session": 2, "pages": 4277},
    ]
    api = FakeApi()
    up = HubUploader("org/repo", root=tmp_path, api=api)
    assert up.flush_metadata() == "oid1"
    assert up.flush_metadata() is None
    assert up.flush_metadata(force=True) == "oid2"
    text = (tmp_path / "metadata.jsonl").read_text()
    assert '"file_name": "pdfs/STATUTE-118.pdf"' in text and '"pdf_sha256": "a"' in text
    assert "metadata.jsonl" in api.tree


def test_flush_metadata_with_no_rows_is_noop(tmp_path, fake_db):
    api = FakeApi()
    up = HubUploader("org/repo", root=tmp_path, api=api)
    assert up.flush_metadata(force=True) is None
    assert api.commits == []


def test_classify_and_hub_only():
    tree = {"pdfs/STATUTE-1.pdf": HubEntry(10), "xmls/STATUTE-1.xml": HubEntry(99), "pdfs/STATUTE-9.pdf": HubEntry(1)}
    entries = classify("STATUTE-1", {"pdfs/STATUTE-1.pdf": 10, "xmls/STATUTE-1.xml": 20}, tree,
                       {"pdfs/STATUTE-1.pdf": None, "xmls/STATUTE-1.xml": 20})
    cats = {(e.path, e.category) for e in entries}
    assert ("xmls/STATUTE-1.xml", "size-mismatch") in cats
    assert ("pdfs/STATUTE-1.pdf", "size-mismatch") not in cats
    entries = classify("STATUTE-2", {"pdfs/STATUTE-2.pdf": 10}, tree, {"pdfs/STATUTE-2.pdf": 10})
    assert [e.category for e in entries] == ["local-only"]
    entries = classify("STATUTE-3", {"pdfs/STATUTE-3.pdf": 10}, tree, {"pdfs/STATUTE-3.pdf": None})
    assert [e.category for e in entries] == ["missing"]
    assert [e.package_id for e in hub_only(tree, {"STATUTE-1"})] == ["STATUTE-9"]
