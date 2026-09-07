"""GovInfo API client: retries, rate-limit logging, collection and granule iterators, ranged downloads.

Download endpoints throttle at about 1 MB/s per connection and honor HTTP Range requests, so
`download_ranged` opens several connections on one file and writes each range to its own
`<dest>.part.<n>` file. Completed parts are concatenated into `<dest>.part` while the sha256 is
computed, the byte count is checked against Content-Length, and the file is renamed into place.
An interrupted download resumes from the bytes already in the part files.
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Optional

import httpx

from .config import GOVINFO_BASE_URL

logger = logging.getLogger(__name__)

RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}
MIN_PART_SIZE = 1024 * 1024  # do not split files smaller than 2 MiB
STREAM_CHUNK = 1024 * 1024


class GovInfoError(RuntimeError):
    pass


class RetryExhausted(GovInfoError):
    pass


class SizeMismatch(GovInfoError):
    pass


class RangeNotSupported(GovInfoError):
    pass


@dataclass(frozen=True)
class RemoteFile:
    url: str
    size: int
    accept_ranges: bool
    content_type: str = ""


@dataclass
class DownloadResult:
    path: Path
    bytes: int
    sha256: Optional[str]
    skipped: bool = False
    parts: int = 0
    seconds: float = 0.0


@dataclass(frozen=True)
class PartStatus:
    """Result of checking a .part file against its expected byte count."""

    exists: bool
    size: int
    expected: int

    @property
    def complete(self) -> bool:
        return self.exists and self.size == self.expected

    @property
    def resumable(self) -> bool:
        return self.exists and 0 < self.size < self.expected

    @property
    def oversize(self) -> bool:
        return self.exists and self.size > self.expected


def plan_ranges(size: int, parts: int, min_part_size: int = MIN_PART_SIZE) -> list[tuple[int, int]]:
    """Split [0, size) into at most `parts` inclusive byte ranges of near-equal length.

    A file smaller than 2 * min_part_size is one range. No part is smaller than min_part_size
    except when the file itself is smaller.
    """
    if size < 0:
        raise ValueError("size must be non-negative")
    if size == 0:
        return []
    parts = max(1, int(parts))
    parts = min(parts, max(1, size // min_part_size))
    base, rem = divmod(size, parts)
    ranges = []
    start = 0
    for i in range(parts):
        length = base + (1 if i < rem else 0)
        end = start + length - 1
        ranges.append((start, end))
        start = end + 1
    assert start == size
    return ranges


def check_part(path: Path, expected: int) -> PartStatus:
    if not path.exists():
        return PartStatus(False, 0, expected)
    return PartStatus(True, path.stat().st_size, expected)


def verify_download(path: Path, expected: int) -> bool:
    """True when `path` exists and has exactly `expected` bytes."""
    return path.exists() and path.stat().st_size == expected


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(STREAM_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _backoff(attempt: int, base: float, cap: float = 60.0) -> float:
    return min(cap, base * (2**attempt)) * (0.5 + random.random())


class GovInfoClient:
    """Thin httpx wrapper. One instance is shared by all threads; httpx.Client is thread-safe."""

    def __init__(
        self,
        api_key: str,
        base_url: str = GOVINFO_BASE_URL,
        max_retries: int = 6,
        backoff_base: float = 1.0,
        timeout: httpx.Timeout | float = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=60.0),
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_connections: int = 16,
    ):
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._sleep = sleep
        self._client = httpx.Client(
            headers={
                "X-Api-Key": api_key,
                "User-Agent": "statute-pdf-to-xml/0.2",
                # GovInfo omits Content-Length and Accept-Ranges when it may gzip the body (XML).
                "Accept-Encoding": "identity",
            },
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
            limits=httpx.Limits(max_connections=max_connections, max_keepalive_connections=max_connections),
        )
        self._ratelimit_lock = threading.Lock()
        self.ratelimit_remaining: Optional[int] = None

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------------ requests

    def _note_ratelimit(self, response: httpx.Response):
        remaining = response.headers.get("x-ratelimit-remaining")
        if remaining is None:
            return
        try:
            remaining_int = int(remaining)
        except ValueError:
            return
        with self._ratelimit_lock:
            previous = self.ratelimit_remaining
            self.ratelimit_remaining = remaining_int
        if remaining_int < 1000 and (previous is None or previous >= 1000):
            logger.warning("GovInfo rate limit remaining: %s of %s", remaining, response.headers.get("x-ratelimit-limit"))

    def _retry_delay(self, response: Optional[httpx.Response], attempt: int) -> float:
        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    return max(0.0, float(retry_after))
                except ValueError:
                    pass
        return _backoff(attempt, self.backoff_base)

    def request(self, method: str, url: str, *, stream: bool = False, **kwargs) -> httpx.Response:
        """Send a request, retrying on 429, 5xx, and transport errors. Non-retryable statuses are returned as-is."""
        if url.startswith("/"):
            url = self.base_url + url
        last_error: Optional[BaseException] = None
        for attempt in range(self.max_retries + 1):
            response: Optional[httpx.Response] = None
            try:
                if stream:
                    request = self._client.build_request(method, url, **kwargs)
                    response = self._client.send(request, stream=True)
                else:
                    response = self._client.request(method, url, **kwargs)
                self._note_ratelimit(response)
                if response.status_code not in RETRY_STATUSES:
                    return response
                last_error = httpx.HTTPStatusError(
                    f"{response.status_code} from {url}", request=response.request, response=response
                )
                if stream:
                    response.close()
            except (httpx.TransportError, httpx.RemoteProtocolError) as exc:
                last_error = exc
            if attempt < self.max_retries:
                delay = self._retry_delay(response, attempt)
                logger.warning("retry %d/%d for %s %s in %.1fs: %s", attempt + 1, self.max_retries, method, url, delay, last_error)
                self._sleep(delay)
        raise RetryExhausted(f"{method} {url} failed after {self.max_retries + 1} attempts: {last_error}")

    def get_json(self, url: str, **kwargs) -> Optional[dict]:
        """GET a JSON document. 404 and 400 return None (GovInfo answers 400 for some unknown ids)."""
        response = self.request("GET", url, **kwargs)
        if response.status_code in (400, 404):
            return None
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------ API surface

    def package_summary(self, package_id: str) -> Optional[dict]:
        return self.get_json(f"/packages/{package_id}/summary")

    def granule_summary(self, package_id: str, granule_id: str) -> Optional[dict]:
        return self.get_json(f"/packages/{package_id}/granules/{granule_id}/summary")

    def iter_granules(self, package_id: str, page_size: int = 100) -> Iterator[dict]:
        url = f"{self.base_url}/packages/{package_id}/granules"
        params: Optional[dict] = {"offsetMark": "*", "pageSize": page_size}
        while url:
            data = self.get_json(url, params=params)
            params = None  # nextPage carries its own query string
            if not data:
                return
            yield from data.get("granules", [])
            url = data.get("nextPage")

    def iter_collection(self, collection: str, since: str, page_size: int = 100, **filters) -> Iterator[dict]:
        """Iterate `collections/{collection}/{since}`; `since` filters on lastModified (ISO 8601)."""
        if len(since) == 10:
            since = f"{since}T00:00:00Z"
        url = f"{self.base_url}/collections/{collection}/{since}"
        params: Optional[dict] = {"offsetMark": "*", "pageSize": page_size, **filters}
        while url:
            data = self.get_json(url, params=params)
            params = None
            if not data:
                return
            yield from data.get("packages", [])
            url = data.get("nextPage")

    def head(self, url: str) -> RemoteFile:
        response = self.request("HEAD", url)
        response.raise_for_status()
        length = response.headers.get("content-length")
        if length is None:
            raise GovInfoError(f"no Content-Length for {url}")
        return RemoteFile(
            url=url,
            size=int(length),
            accept_ranges=response.headers.get("accept-ranges", "").lower() == "bytes",
            content_type=response.headers.get("content-type", ""),
        )

    def fetch_bytes(self, url: str) -> bytes:
        response = self.request("GET", url)
        response.raise_for_status()
        return response.content

    # ------------------------------------------------------------------ downloads

    def _stream_to(self, url: str, part_path: Path, start: int, end: int, ranged: bool) -> int:
        """Append bytes [start+existing, end] of url to part_path. Returns the final part size."""
        expected = end - start + 1
        for attempt in range(self.max_retries + 1):
            status = check_part(part_path, expected)
            if status.complete:
                return status.size
            if status.oversize:
                part_path.unlink()
                status = check_part(part_path, expected)
            headers = {}
            if ranged:
                headers["Range"] = f"bytes={start + status.size}-{end}"
            try:
                response = self.request("GET", url, stream=True, headers=headers)
                try:
                    if ranged and response.status_code != 206:
                        raise RangeNotSupported(f"{response.status_code} for ranged GET {url}")
                    if not ranged and response.status_code != 200:
                        response.raise_for_status()
                    with open(part_path, "ab") as f:
                        for chunk in response.iter_bytes(STREAM_CHUNK):
                            f.write(chunk)
                finally:
                    response.close()
            except RangeNotSupported:
                raise
            except (httpx.HTTPError, OSError) as exc:
                if attempt >= self.max_retries:
                    raise RetryExhausted(f"stream {url} range {start}-{end}: {exc}") from exc
                delay = _backoff(attempt, self.backoff_base)
                logger.warning("stream retry %d for %s [%d-%d] in %.1fs: %s", attempt + 1, url, start, end, delay, exc)
                self._sleep(delay)
                continue
            status = check_part(part_path, expected)
            if status.complete:
                return status.size
            if status.oversize:
                raise SizeMismatch(f"part {part_path} has {status.size} bytes, expected {expected}")
            # short read: loop and resume
        raise RetryExhausted(f"stream {url} range {start}-{end} did not complete")

    def download_ranged(self, url: str, dest: Path | str, parts: int = 4, expected_size: Optional[int] = None,
                        remote: Optional[RemoteFile] = None) -> DownloadResult:
        """Download url to dest using up to `parts` parallel range requests.

        Skips the download when dest already has Content-Length bytes. Writes to dest.part and
        per-range dest.part.N files, verifies the byte count, computes sha256, renames atomically.
        """
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        if remote is None:
            remote = self.head(url)
        size = remote.size
        if expected_size is not None and expected_size != size:
            raise SizeMismatch(f"expected {expected_size} bytes but server reports {size} for {url}")
        if verify_download(dest, size):
            return DownloadResult(path=dest, bytes=size, sha256=None, skipped=True)
        if dest.exists():
            logger.warning("%s has %d bytes, expected %d; re-downloading", dest, dest.stat().st_size, size)
            dest.unlink()

        ranges = plan_ranges(size, parts if remote.accept_ranges else 1)
        ranged = len(ranges) > 1 or remote.accept_ranges
        part_paths = [dest.with_name(f"{dest.name}.part.{i}") for i in range(len(ranges))]

        def fetch(i: int):
            self._stream_to(url, part_paths[i], ranges[i][0], ranges[i][1], ranged=ranged)

        try:
            if len(ranges) > 1:
                with ThreadPoolExecutor(max_workers=len(ranges), thread_name_prefix="range") as pool:
                    for _ in pool.map(fetch, range(len(ranges))):
                        pass
            elif ranges:
                fetch(0)
        except RangeNotSupported:
            logger.warning("server refused Range for %s; falling back to a single stream", url)
            for p in part_paths:
                p.unlink(missing_ok=True)
            part_paths = [dest.with_name(f"{dest.name}.part.0")]
            ranges = [(0, size - 1)]
            self._stream_to(url, part_paths[0], 0, size - 1, ranged=False)

        tmp = dest.with_name(dest.name + ".part")
        digest = hashlib.sha256()
        total = 0
        with open(tmp, "wb") as out:
            for p in part_paths:
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(STREAM_CHUNK), b""):
                        digest.update(chunk)
                        out.write(chunk)
                        total += len(chunk)
            out.flush()
            os.fsync(out.fileno())
        if total != size:
            tmp.unlink(missing_ok=True)
            raise SizeMismatch(f"{dest}: assembled {total} bytes, Content-Length {size}")
        os.replace(tmp, dest)
        for p in part_paths:
            p.unlink(missing_ok=True)
        return DownloadResult(
            path=dest, bytes=total, sha256=digest.hexdigest(), skipped=False, parts=len(part_paths),
            seconds=time.monotonic() - started,
        )


def parse_volume_spec(spec: str) -> list[int]:
    """'1-3,7,10-12' -> [1, 2, 3, 7, 10, 11, 12]."""
    volumes: set[int] = set()
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            lo, hi = token.split("-", 1)
            lo_i, hi_i = int(lo), int(hi)
            if hi_i < lo_i:
                raise ValueError(f"bad range {token!r}")
            volumes.update(range(lo_i, hi_i + 1))
        else:
            volumes.add(int(token))
    return sorted(volumes)
