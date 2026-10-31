"""Remove signed-URL queries and temporary credentials from receipt JSON files, keeping the public request URL and the content hashes.

A receipt's `url` is the public address that was requested. Its `final_url` can be a short-lived signed link (figshare redirects to S3); that is
withheld (null) and the host is kept as `redirect_host`. Nothing else is changed.

  python3 -m connectors.genomics.scrub_receipts FILE...        (rewrites in place; exit 1 if any file still matches the credential pattern)
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

from .sources import public_url

CRED = re.compile(r"X-Amz-|AKIA[0-9A-Z]{12,}|Signature=|Credential=|AWSAccessKeyId", re.I)


def scrub(node):
    n = 0
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if k == "final_url" and isinstance(v, str) and public_url(v) is None:
                node["redirect_host"] = urllib.parse.urlsplit(v).hostname
                node[k] = None
                n += 1
            else:
                n += scrub(v)
    elif isinstance(node, list):
        for v in node:
            n += scrub(v)
    return n


def scrub_text(text: str) -> tuple[str, int]:
    data = json.loads(text)
    n = scrub(data)
    return json.dumps(data, indent=1, sort_keys=True), n


def main(argv=None) -> int:
    bad = 0
    for f in (argv if argv is not None else sys.argv[1:]):
        p = Path(f)
        out, n = scrub_text(p.read_text())
        p.write_text(out)
        left = CRED.findall(out)
        print(f"{p.name}: withheld {n} signed final_url value(s); credential-pattern matches left: {len(left)}")
        bad += bool(left)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
