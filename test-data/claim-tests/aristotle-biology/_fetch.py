"""Download a public file and record its size and SHA-256. Stdlib only."""

import hashlib
import urllib.request
from datetime import datetime, timezone


UA = "delphi-claim-test/1.0 (aristotle-biology; pre-registered claim test)"


def fetch(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read()
        final = response.geturl()
        ctype = response.headers.get("Content-Type", "")
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "download_url": url,
        "final_url": final,
        "retrieved_at": retrieved,
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "content_type": ctype,
        "data": data,
    }
