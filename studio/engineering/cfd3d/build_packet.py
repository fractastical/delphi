"""Build the portable cfd3d GPU packet from git objects (no copied code in the tree).

    python engineering/cfd3d/build_packet.py [--fish3d-rev 994aac4] [--out artifacts/cfd3d/packet]

The tarball holds this branch's committed engineering/cfd3d files at HEAD and fish3d's geometry builder at the
pinned revision under fish3d_src/, so the container rebuilds the exact STLs instead of carrying 1.9 MB of mesh.
Writes cfd3d-packet.tar.xz (deterministic) and packet-manifest.json (per-file git blob + sha256, archive sha256).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import lzma
import subprocess
import tarfile
from pathlib import Path

OWN = ["engineering/cfd3d/gpu_entry.py", "engineering/cfd3d/packet.json", "engineering/cfd3d/controls.jl",
       "engineering/cfd3d/fish.jl", "engineering/cfd3d/render.py", "engineering/cfd3d/gates_cpu.json",
       "engineering/cfd3d/env_gpu/Project.toml", "engineering/cfd3d/env_gpu/pins.tsv"]   # pins, not the 34 KB Manifest
LAUNCHER = "engineering/cfd3d/cfd3d_launch.py"
FISH3D = ["engineering/__init__.py", "engineering/fish3d/__init__.py", "engineering/fish3d/build.py",
          "engineering/geometry/__init__.py", "engineering/geometry/mesh.py", "engineering/geometry/forms.py",
          "engineering/geometry/sources.py", "artifacts/print/sources/daane2021-S1A-summary.json"]
INJECT_LIMIT = 45_000   # compute_ops: SUM of injected files (archive + launcher) must stay under ~60 KB after base64


def git(*a: str) -> bytes:
    return subprocess.run(["git", *a], capture_output=True, check=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fish3d-rev", default="994aac4")
    ap.add_argument("--out", default="artifacts/cfd3d/packet")
    a = ap.parse_args()
    head = git("rev-parse", "HEAD").decode().strip()
    fish = git("rev-parse", a.fish3d_rev).decode().strip()
    if git("status", "--porcelain", "--", *OWN, LAUNCHER):
        raise SystemExit("refusing: packet files differ from HEAD; commit first so the packet is reproducible")
    entries = [(p, head, p) for p in OWN] + [(f"fish3d_src/{p}", fish, p) for p in FISH3D]
    buf, rows = io.BytesIO(), []
    with lzma.LZMAFile(buf, mode="wb", preset=9 | lzma.PRESET_EXTREME) as xz, \
            tarfile.open(fileobj=xz, mode="w", format=tarfile.PAX_FORMAT) as tf:
        for arc, rev, path in entries:
            data = git("show", f"{rev}:{path}")
            ti = tarfile.TarInfo(arc)
            ti.size, ti.mtime, ti.mode, ti.uname, ti.gname = len(data), 0, 0o644, "", ""
            tf.addfile(ti, io.BytesIO(data))
            rows.append({"path": arc, "rev": rev, "blob": git("rev-parse", f"{rev}:{path}").decode().strip(),
                         "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    blob = buf.getvalue()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "cfd3d-packet.tar.xz").write_bytes(blob)
    man = {"schema": "cfd3d-packet-manifest-0.1", "head": head, "fish3d_rev": fish,
           "archive": "cfd3d-packet.tar.xz", "archive_bytes": len(blob),
           "archive_sha256": hashlib.sha256(blob).hexdigest(), "base64_bytes": (len(blob) + 2) // 3 * 4,
           "raw_bytes": sum(r["bytes"] for r in rows), "files": rows,
           "launcher": LAUNCHER, "launcher_bytes": len(git("show", f"HEAD:{LAUNCHER}")),
           "launcher_sha256": hashlib.sha256(git("show", f"HEAD:{LAUNCHER}")).hexdigest()}
    man["inject_total_raw"] = len(blob) + man["launcher_bytes"]
    man["fits_inject_limit"] = man["inject_total_raw"] <= INJECT_LIMIT
    (out / "packet-manifest.json").write_text(json.dumps(man, indent=1))
    print(json.dumps({k: man[k] for k in ("archive_bytes", "inject_total_raw", "raw_bytes",
                                          "archive_sha256", "fits_inject_limit")}))
    return 0 if man["fits_inject_limit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
