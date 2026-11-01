"""Bounded, read-only HTTP access to BioModels.

Hosts are allow-listed, responses are size-capped, requests are rate-limited, and a retrieved
file is refused unless its size and SHA-256 match what BioModels' own metadata declares. Nothing
here executes a model or writes outside the directory the caller names.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_HOSTS = frozenset({"www.biomodels.org", "biomodels.org", "www.ebi.ac.uk"})
BASE = "https://www.biomodels.org"
EBI_SEARCH = "https://www.ebi.ac.uk/ebisearch/ws/rest/biomodels"
ACCESSION = re.compile(r"^(BIOMD|MODEL)\d{10}$")
USER_AGENT = "delphi-frontier-biomodels/0.1 (read-only connector)"
MAX_JSON_BYTES = 2_000_000
MAX_MODEL_BYTES = 5_000_000
MIN_INTERVAL_S = 1.0
MAX_LIMIT = 25


class ConnectorError(RuntimeError):
    """Anything the connector refuses or cannot establish; never swallowed into a default."""


@dataclass(frozen=True)
class Licence:
    spdx_claimed: str
    claim_source: str
    claim_read_on: str
    terms_page_read: bool
    per_model_licence_in_metadata: bool
    note: str


LICENCE = Licence(
    spdx_claimed="CC0-1.0",
    claim_source="https://www.biomodels.org/faq (section 'Licence')",
    claim_read_on="2026-10-31",
    terms_page_read=False,
    per_model_licence_in_metadata=False,
    note=(
        "The FAQ states all models are under the CC0 Public Domain Dedication and points at the "
        "terms of use. https://www.biomodels.org/terms-of-use redirected to a login form on "
        "2026-10-31, so the terms themselves were not read, and no model's own metadata carries "
        "a licence field. The CC0 statement is BioModels' claim about its models, not a reading "
        "of the terms."
    ),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _HostRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _check_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise ConnectorError(f"refusing URL outside the allow-list: {url}")


@dataclass
class SearchHit:
    accession: str
    name: str
    url: str


@dataclass
class SearchResult:
    query: str
    retrieved_at: str
    source: str
    primary_status: str
    total: int | None
    hits: list[SearchHit] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Retrieval:
    accession: str
    file_name: str
    path: str
    size_bytes: int
    sha256: str
    declared_sha256: str
    declared_size_bytes: int
    source_url: str
    retrieved_at: str
    revision: int | None
    format: str
    licence: Licence

    def to_dict(self) -> dict:
        return asdict(self)


class BioModelsClient:
    def __init__(self, *, timeout: float = 30.0, min_interval: float = MIN_INTERVAL_S):
        self.timeout = timeout
        self.min_interval = min_interval
        self._last = 0.0
        self._opener = urllib.request.build_opener(_HostRedirects())

    def _get(self, url: str, cap: int) -> bytes:
        _check_url(url)
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/xml"})
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                body = resp.read(cap + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ConnectorError(f"{type(exc).__name__}: {exc} ({url})") from exc
        if len(body) > cap:
            raise ConnectorError(f"response exceeds {cap} bytes: {url}")
        return body

    def _json(self, url: str) -> dict:
        try:
            return json.loads(self._get(url, MAX_JSON_BYTES))
        except json.JSONDecodeError as exc:
            raise ConnectorError(f"non-JSON response from {url}: {exc}") from exc

    def search(self, query: str, limit: int = 10) -> SearchResult:
        """Search BioModels; fall back to EBI Search when the primary index is degraded.

        On 2026-10-31 www.biomodels.org/search answered 200 with `matches: -1` and no models for
        every query, including an exact accession. That is a degraded index, not an empty
        result, so it is reported as `primary_status` and never as a verified zero.
        """
        if not query.strip():
            raise ConnectorError("empty query")
        limit = max(1, min(int(limit), MAX_LIMIT))
        stamp = _now()
        params = urllib.parse.urlencode({"query": query, "format": "json", "numResults": limit})
        try:
            primary = self._json(f"{BASE}/search?{params}")
        except ConnectorError as exc:
            primary, status = None, f"error: {exc}"
        else:
            total = primary.get("matches")
            if isinstance(total, int) and total >= 0:
                hits = [SearchHit(m["id"], m.get("name", ""), f"{BASE}/{m['id']}") for m in primary.get("models", [])[:limit]]
                return SearchResult(query, stamp, "www.biomodels.org/search", "ok", total, hits)
            status = f"degraded: matches={total!r}, models={len(primary.get('models', []))}"
        fb = urllib.parse.urlencode({"query": query, "format": "json", "size": limit, "fields": "name"})
        data = self._json(f"{EBI_SEARCH}?{fb}")
        hits = [
            SearchHit(e["id"], (e.get("fields", {}).get("name") or [""])[0], f"{BASE}/{e['id']}")
            for e in data.get("entries", [])[:limit]
        ]
        return SearchResult(query, stamp, "www.ebi.ac.uk/ebisearch (BioModels domain)", status, data.get("hitCount"), hits)

    def metadata(self, accession: str) -> dict:
        _accession(accession)
        return self._json(f"{BASE}/{accession}?format=json")

    def fetch(self, accession: str, dest: Path) -> Retrieval:
        """Download the model's main file into `dest`, verified against BioModels' declared hash."""
        meta = self.metadata(accession)
        main = (meta.get("files") or {}).get("main") or []
        if len(main) != 1:
            raise ConnectorError(f"{accession}: expected one main file, metadata lists {len(main)}")
        entry = main[0]
        name = entry.get("name", "")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name.startswith("."):
            raise ConnectorError(f"{accession}: unsafe file name {name!r}")
        declared_sha, declared_size = entry.get("sha256sum"), int(entry.get("fileSize", -1))
        if not declared_sha or declared_size < 0:
            raise ConnectorError(f"{accession}: metadata declares no sha256/size to verify against")
        if declared_size > MAX_MODEL_BYTES:
            raise ConnectorError(f"{accession}: declared size {declared_size} exceeds {MAX_MODEL_BYTES}")
        url = f"{BASE}/model/download/{accession}?{urllib.parse.urlencode({'filename': name})}"
        body = self._get(url, MAX_MODEL_BYTES)
        digest = sha256_bytes(body)
        if digest != declared_sha or len(body) != declared_size:
            raise ConnectorError(
                f"{accession}: received {len(body)} bytes sha256 {digest}; metadata declares "
                f"{declared_size} bytes sha256 {declared_sha}; refusing to keep it"
            )
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / name
        path.write_bytes(body)
        revisions = (meta.get("history") or {}).get("revisions") or []
        return Retrieval(
            accession, name, str(path), len(body), digest, declared_sha, declared_size, url, _now(),
            revisions[-1].get("version") if revisions else None,
            "{name} {version}".format(**{"name": (meta.get("format") or {}).get("name"), "version": (meta.get("format") or {}).get("version")}),
            LICENCE,
        )


def _accession(accession: str) -> None:
    if not ACCESSION.match(accession):
        raise ConnectorError(f"not a BioModels accession: {accession!r}")
