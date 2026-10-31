"""Allow-listed, size-capped, rate-limited HTTP with a hash and a receipt for every download."""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Iterator

ALLOWED_HOSTS = frozenset({
    "zfin.org", "daniocell.nichd.nih.gov", "eutils.ncbi.nlm.nih.gov", "api.genome.ucsc.edu", "www.ebi.ac.uk", "rest.uniprot.org",
    "rest.ensembl.org", "www.ncbi.nlm.nih.gov", "zebrahub.sf.czbiohub.org", "danio-code.zfin.org",
})
USER_AGENT = "delphi-frontier-genomics/0.1 (read-only bounded connector)"
MAX_BYTES = 200_000_000          # the task's ceiling for any single download
MIN_INTERVAL_S = 0.4
TIMEOUT_S = 90
_last: dict[str, float] = {}


class FetchRefused(RuntimeError):
    """A URL or size outside the bounds; never turned into an empty result."""


@dataclass
class Receipt:
    url: str
    final_url: str
    retrieved_at: str
    http_status: int
    content_type: str | None
    last_modified: str | None
    etag: str | None
    bytes: int
    sha256: str
    truncated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _check(url: str) -> None:
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
        raise FetchRefused(f"refusing URL outside the allow-list: {url}")


def _open(url: str, cap: int):
    _check(url)
    host = urllib.parse.urlsplit(url).hostname
    wait = MIN_INTERVAL_S - (time.monotonic() - _last.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.monotonic()

    class Redirects(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            _check(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        resp = urllib.request.build_opener(Redirects()).open(req, timeout=TIMEOUT_S)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchRefused(f"{type(exc).__name__}: {exc} ({url})") from exc
    declared = resp.headers.get("Content-Length")
    if declared and int(declared) > cap:
        resp.close()
        raise FetchRefused(f"{url}: declared {declared} bytes exceeds the cap {cap}")
    return resp


def _receipt(url: str, resp, h, n: int, truncated: bool = False) -> Receipt:
    return Receipt(url, resp.geturl(), datetime.now(timezone.utc).isoformat(timespec="seconds"), resp.status, resp.headers.get("Content-Type"),
                   resp.headers.get("Last-Modified"), resp.headers.get("ETag"), n, h.hexdigest(), truncated)


def fetch(url: str, cap: int = 20_000_000) -> tuple[bytes, Receipt]:
    resp = _open(url, cap)
    body = resp.read(cap + 1)
    resp.close()
    if len(body) > cap:
        raise FetchRefused(f"{url}: body exceeds the cap {cap}")
    h = hashlib.sha256(body)
    return body, _receipt(url, resp, h, len(body))


def stream_lines(url: str, keep: Callable[[str], bool], cap: int = MAX_BYTES) -> tuple[list[str], list[str], Receipt]:
    """Stream a large text file once, keep matching lines and the leading comment lines, hash every byte read.

    The receipt's sha256 and byte count describe the WHOLE source stream, so the kept subset can be tied to it.
    """
    resp = _open(url, cap)
    h, n, kept, comments = hashlib.sha256(), 0, [], []
    for raw in resp:
        n += len(raw)
        if n > cap:
            resp.close()
            raise FetchRefused(f"{url}: stream exceeds the cap {cap}")
        h.update(raw)
        line = raw.decode("utf-8", errors="replace").rstrip("\n")
        if line.startswith("#"):
            if len(comments) < 60:
                comments.append(line)
        elif keep(line):
            kept.append(line)
    resp.close()
    return kept, comments, _receipt(url, resp, h, n)
