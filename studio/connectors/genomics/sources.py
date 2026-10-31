"""Allow-listed, size-capped, rate-limited HTTP with a hash and a receipt for every download."""

from __future__ import annotations

import hashlib
import re
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
    "api.figshare.com", "ndownloader.figshare.com", "figshare.com", "public.czbiohub.org",
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
    md5: str | None = None
    truncated: bool = False
    redirect_host: str | None = None        # set when the final URL was a signed link and has been withheld

    def to_dict(self) -> dict:
        return asdict(self)


def _check(url: str, via: str | None = None) -> None:
    p = urllib.parse.urlsplit(url)
    # figshare's downloader answers 302 to a short-lived signed S3 URL; allow exactly that hop and nothing else on S3
    if via == "ndownloader.figshare.com" and p.hostname == "s3-eu-west-1.amazonaws.com" and p.path.startswith("/pfigshare-u-files/") and p.scheme == "https":
        return
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
        raise FetchRefused(f"refusing URL outside the allow-list: {url.split('?')[0]}")


def _open(url: str, cap: int):
    _check(url)
    host = urllib.parse.urlsplit(url).hostname
    wait = MIN_INTERVAL_S - (time.monotonic() - _last.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.monotonic()

    class Redirects(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            _check(newurl, urllib.parse.urlsplit(req.full_url).hostname)
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


SIGNED = re.compile(r"(^|&)(x-amz-[^=&]*|signature|credential|awsaccesskeyid|token|sig|key-pair-id|policy)=", re.I)


def public_url(url: str | None) -> str | None:
    """The URL without a temporary credential: None if it carries a signed query (a signed link is not a public address)."""
    if not url:
        return url
    p = urllib.parse.urlsplit(url)
    return None if SIGNED.search(p.query) else url


def _receipt(url: str, resp, h, n: int, md5=None, truncated: bool = False) -> Receipt:
    final = public_url(resp.geturl())
    withheld = urllib.parse.urlsplit(resp.geturl()).hostname if final is None else None
    return Receipt(url, final, datetime.now(timezone.utc).isoformat(timespec="seconds"), resp.status, resp.headers.get("Content-Type"),
                   resp.headers.get("Last-Modified"), resp.headers.get("ETag"), n, h.hexdigest(), md5.hexdigest() if md5 else None, truncated, withheld)


def fetch(url: str, cap: int = 20_000_000) -> tuple[bytes, Receipt]:
    resp = _open(url, cap)
    body = resp.read(cap + 1)
    resp.close()
    if len(body) > cap:
        raise FetchRefused(f"{url}: body exceeds the cap {cap}")
    h, m = hashlib.sha256(body), hashlib.md5(body)
    return body, _receipt(url, resp, h, len(body), m)


def stream_lines(url: str, keep: Callable[[str], bool], cap: int = MAX_BYTES) -> tuple[list[str], list[str], Receipt]:
    """Stream a large text file once, keep matching lines and the leading comment lines, hash every byte read.

    The receipt's sha256 and byte count describe the WHOLE source stream, so the kept subset can be tied to it.
    """
    resp = _open(url, cap)
    h, m, n, kept, comments = hashlib.sha256(), hashlib.md5(), 0, [], []
    for raw in resp:
        n += len(raw)
        if n > cap:
            resp.close()
            raise FetchRefused(f"{url}: stream exceeds the cap {cap}")
        h.update(raw)
        m.update(raw)
        line = raw.decode("utf-8", errors="replace").rstrip("\n")
        if line.startswith("#"):
            if len(comments) < 60:
                comments.append(line)
        elif keep(line):
            kept.append(line)
    resp.close()
    return kept, comments, _receipt(url, resp, h, n, m)
