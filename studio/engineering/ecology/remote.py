"""Public-source, CPU-only packet entry; exact byte gates before any computation."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from urllib.request import urlopen

import mujoco
import numpy as np

from .batch import run
from .model import ART, ROOT
from .run import controls


def source_inputs():
    manifest = json.loads((ART / "source-downloads.json").read_text())
    total = 0
    receipts = []
    for item in manifest["files"]:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or item["path"].startswith("/"):
            raise ValueError("source path escapes packet root")
        if path.exists():
            data = path.read_bytes()
            method = "existing exact input"
        else:
            with urlopen(item["url"], timeout=30) as response:
                if response.status != 200:
                    raise ValueError("public source unavailable")
                data = response.read(8 * 1024 * 1024 + 1)
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("source byte cap")
            method = "public HTTPS; no credentials"
        total += len(data)
        if total > 32 * 1024 * 1024:
            raise ValueError("total source input cap")
        if len(data) != item["bytes"] or sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("public source hash mismatch")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        receipts.append(
            {
                "path": item["path"],
                "url": item["url"],
                "sha256": item["sha256"],
                "bytes": len(data),
                "method": method,
            }
        )
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise ValueError("Python>=3.12 required; do not replace NumPy pin")
    if mujoco.__version__ != "3.17.0" or np.__version__ != "2.5.4":
        raise ValueError("Exact dependency pins required")
    receipts = source_inputs()
    if args.preflight:
        result = controls(json.loads((ART / "protocol-refinement.json").read_text()))
        print(
            json.dumps(
                {
                    "preflight": "passed" if result["passed"] else "failed",
                    "input_files": len(receipts),
                    "input_bytes": sum(x["bytes"] for x in receipts),
                    "controls": result,
                },
                default=lambda x: (
                    x.item() if isinstance(x, np.generic) else str(type(x))
                ),
            )
        )
        return 0 if result["passed"] else 1
    if args.out is None:
        raise ValueError("--out required for batch")
    run(args.out, args.workers)
    (args.out / "source-download-receipt.json").write_text(
        json.dumps(receipts, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
