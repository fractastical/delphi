"""Shared helpers: cached HTTP, checksums, timestamps, paths."""
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
SLICE = HERE.parent
REPO = HERE.parents[3]
CACHE = Path(os.environ.get("ORGANISMS_CACHE", "/tmp/organisms-cache"))
DATA = Path(os.environ.get("ORGANISMS_DATA", "/tmp/organisms-data"))  # downloads live outside the repo
CACHE.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "delphi-organisms/0.1 (https://github.com/fractastical/delphi; cloud agent)"}
SESSION = requests.Session()
SESSION.headers.update(UA)

VENDORED_BY = {
    "kind": "cloud-agent",
    "model": "claude-fable-5.1",
    "run": "cursor/thompson-organisms-ch12-epilogue-859f",
    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _key(url: str) -> Path:
    return CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".json")


def get_json(url: str, *, params=None, retries=4, sleep=0.4, refresh=False):
    """GET a JSON document, caching the body (and the final URL) on disk."""
    full = requests.Request("GET", url, params=params).prepare().url
    k = _key(full)
    if k.exists() and not refresh:
        return json.loads(k.read_text())["body"]
    last = None
    for attempt in range(retries):
        try:
            r = SESSION.get(full, timeout=60)
            if r.status_code in (404, 204) or not r.content:
                body = None
            elif r.status_code == 429:
                time.sleep(15 * (attempt + 1))
                raise requests.HTTPError(f"{r.status_code} {full}")
            elif r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code} {full}")
            else:
                r.raise_for_status()
                body = r.json()
            k.write_text(json.dumps({"url": full, "retrieved_at": now_iso(), "body": body}))
            time.sleep(sleep)
            return body
        except (requests.RequestException, ValueError) as e:  # noqa: PERF203
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed {full}: {last}")


def cached_meta(url: str, params=None):
    full = requests.Request("GET", url, params=params).prepare().url
    k = _key(full)
    if k.exists():
        d = json.loads(k.read_text())
        return d["url"], d["retrieved_at"]
    return full, None


def download(url: str, dest_name: str, *, refresh=False) -> dict:
    """Download a file into DATA (outside the repo) and return byte_size / sha256 / retrieved_at."""
    dest = DATA / dest_name
    meta = dest.with_suffix(dest.suffix + ".meta.json")
    if dest.exists() and meta.exists() and not refresh:
        return json.loads(meta.read_text())
    with SESSION.get(url, stream=True, timeout=300, allow_redirects=True) as r:
        r.raise_for_status()
        h = hashlib.sha256()
        n = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
                h.update(chunk)
                n += len(chunk)
        ctype = r.headers.get("Content-Type", "").split(";")[0]
    info = {"download_url": url, "path": str(dest), "byte_size": n, "sha256": h.hexdigest(),
            "retrieved_at": now_iso(), "media_type": ctype}
    meta.write_text(json.dumps(info, indent=1))
    return info


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
