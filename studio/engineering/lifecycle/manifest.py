"""Pin the fish-lifecycle deliverables by sha256 (data, docs, code). PYTHONPATH=. python3 -m engineering.lifecycle.manifest"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = ["docs/fish-lifecycle.md", "engineering/lifecycle/build.py", "engineering/lifecycle/diffusion.py", "engineering/lifecycle/manifest.py"]


def main() -> int:
    paths = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "data" / "fish-lifecycle").rglob("*") if p.is_file() and p.name != "manifest.json") + FILES
    files = [{"path": p, "sha256": hashlib.sha256((ROOT / p).read_bytes()).hexdigest(), "bytes": (ROOT / p).stat().st_size} for p in paths]
    (ROOT / "data" / "fish-lifecycle" / "manifest.json").write_text(json.dumps({
        "manifest_schema": "fish-lifecycle-manifest-0.1 (connector-local)", "retrieved": "2026-10-31", "organism": "Danio rerio only; not a flying fish", "status": "proposed; single operator; unreviewed",
        "claims_not_made": ["a living whole-fish bioprint is feasible or infeasible", "zebrafish values transfer to any other species", "locomotion or maintenance-cost models exist here"],
        "not_stored": "full text of Parichy 2009 (no licence stated) and Mateus 2020 (CC BY-NC-ND); hashes in sources.json", "files": files}, indent=1, sort_keys=True))
    print(len(files), "files pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
