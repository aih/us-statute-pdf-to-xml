import hashlib
import json
import re
import threading

import httpx
import pytest

from downloader import govinfo
from downloader.govinfo import GovInfoClient, PartStatus, RangeNotSupported, RetryExhausted, SizeMismatch, plan_ranges


# ---------------------------------------------------------------- range planning


def test_plan_ranges_covers_file_contiguously():
    size = 10 * 1024 * 1024 + 17
    ranges = plan_ranges(size, 4)
    assert len(ranges) == 4
    assert ranges[0][0] == 0
    assert ranges[-1][1] == size - 1
    for (s1, e1), (s2, _) in zip(ranges, ranges[1:]):
        assert s2 == e1 + 1
    assert sum(e - s + 1 for s, e in ranges) == size
    lengths = [e - s + 1 for s, e in ranges]
    assert max(lengths) - min(lengths) <= 1


def test_plan_ranges_small_file_is_single_range():
    assert plan_ranges(1000, 4) == [(0, 999)]
    assert plan_ranges(2 * 1024 * 1024 - 1, 4) == [(0, 2 * 1024 * 1024 - 2)]


def test_plan_ranges_respects_min_part_size():
    size = 3 * 1024 * 1024
    assert len(plan_ranges(size, 8)) == 3
    assert len(plan_ranges(size, 2)) == 2


def test_plan_ranges_edge_cases():
    assert plan_ranges(0, 4) == []
    assert plan_ranges(5, 1) == [(0, 4)]
    assert plan_ranges(5, 0) == [(0, 4)]
    with pytest.raises(ValueError):
        plan_ranges(-1, 4)


# ---------------------------------------------------------------- part verification


def test_check_part_states(tmp_path):
    p = tmp_path / "f.part.0"
    assert govinfo.check_part(p, 10) == PartStatus(False, 0, 10)
    p.write_bytes(b"x" * 4)
    st = govinfo.check_part(p, 10)
    assert st.resumable and not st.complete and not st.oversize
    p.write_bytes(b"x" * 10)
    assert govinfo.check_part(p, 10).complete
    p.write_bytes(b"x" * 11)
    assert govinfo.check_part(p, 10).oversize


def test_verify_download(tmp_path):
    p = tmp_path / "f.pdf"
    assert not govinfo.verify_download(p, 3)
    p.write_bytes(b"abc")
    assert govinfo.verify_download(p, 3)
    assert not govinfo.verify_download(p, 4)


def test_parse_volume_spec():
    assert govinfo.parse_volume_spec("1-3,7,10-12") == [1, 2, 3, 7, 10, 11, 12]
    assert govinfo.parse_volume_spec("119,118") == [118, 119]
    with pytest.raises(ValueError):
        govinfo.parse_volume_spec("5-3")


# ---------------------------------------------------------------- fake GovInfo server


class FakeServer:
    """Serves one file with HEAD, GET, and Range support; scripted failures per path."""

    def __init__(self, blob: bytes, accept_ranges=True, fail_first=None, fail_status=503, retry_after=None,
                 ignore_range=False):
        self.blob = blob
        self.accept_ranges = accept_ranges
        self.fail_first = dict(fail_first or {})  # path -> number of failing responses
        self.fail_status = fail_status
        self.retry_after = retry_after
        self.ignore_range = ignore_range
        self.requests = []
        self.lock = threading.Lock()

    def transport(self):
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        with self.lock:
            self.requests.append((request.method, request.url.path, request.headers.get("range")))
            remaining = self.fail_first.get(request.url.path, 0)
            if remaining:
                self.fail_first[request.url.path] = remaining - 1
                headers = {"retry-after": str(self.retry_after)} if self.retry_after is not None else {}
                return httpx.Response(self.fail_status, headers=headers)
        assert request.headers.get("x-api-key") == "test-key"
        if request.url.path.endswith("/summary"):
            return httpx.Response(200, json={"packageId": "STATUTE-1", "volume": "1"})
        if request.url.path.endswith("/missing"):
            return httpx.Response(404)
        headers = {"content-length": str(len(self.blob)), "x-ratelimit-remaining": "999"}
        if self.accept_ranges:
            headers["accept-ranges"] = "bytes"
        if request.method == "HEAD":
            return httpx.Response(200, headers=headers)
        rng = request.headers.get("range")
        if rng and self.accept_ranges and not self.ignore_range:
            m = re.match(r"bytes=(\d+)-(\d+)", rng)
            start, end = int(m.group(1)), int(m.group(2))
            body = self.blob[start:end + 1]
            headers["content-length"] = str(len(body))
            headers["content-range"] = f"bytes {start}-{end}/{len(self.blob)}"
            return httpx.Response(206, content=body, headers=headers)
        return httpx.Response(200, content=self.blob, headers=headers)


def make_client(server, **kw):
    return GovInfoClient("test-key", base_url="https://fake.test", transport=server.transport(), sleep=lambda s: None,
                         backoff_base=0, **kw)


@pytest.fixture
def blob():
    return bytes(range(256)) * (5 * 1024 * 1024 // 256 + 3)  # a little over 5 MiB


def test_download_ranged_assembles_verifies_and_hashes(tmp_path, blob):
    server = FakeServer(blob)
    dest = tmp_path / "pdfs" / "STATUTE-1.pdf"
    with make_client(server) as client:
        result = client.download_ranged("https://fake.test/packages/STATUTE-1/pdf", dest, parts=4)
    assert result.skipped is False
    assert result.parts == 4
    assert result.bytes == len(blob)
    assert result.sha256 == hashlib.sha256(blob).hexdigest()
    assert dest.read_bytes() == blob
    assert not list(dest.parent.glob("*.part*"))
    gets = [r for r in server.requests if r[0] == "GET"]
    assert len(gets) == 4 and all(r[2] for r in gets)


def test_download_ranged_skips_complete_file(tmp_path, blob):
    server = FakeServer(blob)
    dest = tmp_path / "STATUTE-1.pdf"
    dest.write_bytes(blob)
    with make_client(server) as client:
        result = client.download_ranged("https://fake.test/packages/STATUTE-1/pdf", dest, parts=4)
    assert result.skipped is True
    assert [r[0] for r in server.requests] == ["HEAD"]


def test_download_ranged_replaces_truncated_file(tmp_path, blob):
    server = FakeServer(blob)
    dest = tmp_path / "STATUTE-1.pdf"
    dest.write_bytes(blob[:1000])
    with make_client(server) as client:
        result = client.download_ranged("https://fake.test/packages/STATUTE-1/pdf", dest, parts=2)
    assert not result.skipped and dest.read_bytes() == blob


def test_download_ranged_resumes_partial_parts(tmp_path, blob):
    server = FakeServer(blob)
    dest = tmp_path / "STATUTE-1.pdf"
    ranges = plan_ranges(len(blob), 4)
    # part 0 complete, part 1 half done, part 2 oversize garbage, part 3 absent
    (tmp_path / "STATUTE-1.pdf.part.0").write_bytes(blob[ranges[0][0]:ranges[0][1] + 1])
    half = (ranges[1][1] - ranges[1][0] + 1) // 2
    (tmp_path / "STATUTE-1.pdf.part.1").write_bytes(blob[ranges[1][0]:ranges[1][0] + half])
    (tmp_path / "STATUTE-1.pdf.part.2").write_bytes(b"junk" * 1_000_000)
    with make_client(server) as client:
        result = client.download_ranged("https://fake.test/packages/STATUTE-1/pdf", dest, parts=4)
    assert dest.read_bytes() == blob
    assert result.sha256 == hashlib.sha256(blob).hexdigest()
    gets = {r[2] for r in server.requests if r[0] == "GET"}
    assert f"bytes={ranges[1][0] + half}-{ranges[1][1]}" in gets  # resumed mid-part
    assert not any(r.startswith(f"bytes={ranges[0][0]}-") for r in gets)  # complete part not refetched


def test_download_falls_back_when_server_ignores_range(tmp_path, blob):
    server = FakeServer(blob, ignore_range=True)
    dest = tmp_path / "STATUTE-1.pdf"
    with make_client(server) as client:
        result = client.download_ranged("https://fake.test/packages/STATUTE-1/pdf", dest, parts=4)
    assert dest.read_bytes() == blob and result.parts == 1


def test_download_single_stream_without_accept_ranges(tmp_path, blob):
    server = FakeServer(blob, accept_ranges=False)
    dest = tmp_path / "STATUTE-1.pdf"
    with make_client(server) as client:
        result = client.download_ranged("https://fake.test/packages/STATUTE-1/pdf", dest, parts=4)
    assert result.parts == 1 and dest.read_bytes() == blob


def test_download_rejects_expected_size_mismatch(tmp_path, blob):
    server = FakeServer(blob)
    with make_client(server) as client:
        with pytest.raises(SizeMismatch):
            client.download_ranged("https://fake.test/packages/STATUTE-1/pdf", tmp_path / "x.pdf", parts=2,
                                   expected_size=len(blob) + 1)


# ---------------------------------------------------------------- retries


def test_request_retries_5xx_then_succeeds(blob):
    server = FakeServer(blob, fail_first={"/packages/STATUTE-1/summary": 2})
    with make_client(server, max_retries=3) as client:
        assert client.package_summary("STATUTE-1") == {"packageId": "STATUTE-1", "volume": "1"}
    assert len(server.requests) == 3


def test_request_honors_retry_after(blob):
    slept = []
    server = FakeServer(blob, fail_first={"/packages/STATUTE-1/summary": 1}, fail_status=429, retry_after=7)
    client = GovInfoClient("test-key", base_url="https://fake.test", transport=server.transport(),
                           sleep=slept.append, backoff_base=0)
    assert client.package_summary("STATUTE-1") is not None
    assert slept == [7.0]


def test_request_gives_up_after_max_retries(blob):
    server = FakeServer(blob, fail_first={"/packages/STATUTE-1/summary": 10})
    with make_client(server, max_retries=2) as client:
        with pytest.raises(RetryExhausted):
            client.package_summary("STATUTE-1")
    assert len(server.requests) == 3


def test_404_returns_none_without_retry(blob):
    server = FakeServer(blob)
    with make_client(server) as client:
        assert client.get_json("/packages/STATUTE-1/missing") is None
    assert len(server.requests) == 1


def test_head_reports_size_and_ranges(blob):
    server = FakeServer(blob)
    with make_client(server) as client:
        remote = client.head("https://fake.test/packages/STATUTE-1/pdf")
    assert remote.size == len(blob) and remote.accept_ranges
