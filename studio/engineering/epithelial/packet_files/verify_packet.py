"""Verify an extracted packet before anything in it runs.

Repair R2 after infra source review of packet 4f33453. The builder previously walked every
member of the staging tree and called tar.add on directories, which recurses by default, so
every file was archived twice. This checks the extracted tree the way the reviewer asked:
every manifest entry is a regular file, listed once, inside the packet, with an exact sha256
match, and nothing in the tree is a symlink, a device or a path that escapes the packet.

Exit 0 only if all of that holds.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args()
    root = Path(a.dir).resolve()
    manifest = root / "SHA256SUMS"
    problems: list[str] = []

    if not manifest.exists():
        print("SHA256SUMS missing; refusing")
        sys.exit(3)

    seen: dict[str, int] = {}
    entries: list[tuple[str, str]] = []
    for ln, line in enumerate(manifest.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            digest, rel = line.split("  ", 1)
        except ValueError:
            problems.append(f"SHA256SUMS line {ln} is malformed")
            continue
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            problems.append(f"SHA256SUMS line {ln} has a malformed digest")
            continue
        seen[rel] = seen.get(rel, 0) + 1
        entries.append((digest, rel))

    for rel, n in seen.items():
        if n > 1:
            problems.append(f"duplicate manifest member listed {n} times: {rel}")

    for digest, rel in entries:
        p = root / rel
        try:
            rp = p.resolve()
        except OSError as e:
            problems.append(f"{rel}: cannot resolve ({e})")
            continue
        if not str(rp).startswith(str(root) + "/") and rp != root:
            problems.append(f"{rel}: path escapes the packet -> {rp}")
            continue
        if p.is_symlink():
            problems.append(f"{rel}: is a symlink")
            continue
        if not p.exists():
            problems.append(f"{rel}: listed in SHA256SUMS but missing")
            continue
        if not p.is_file():
            problems.append(f"{rel}: not a regular file")
            continue
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != digest:
            problems.append(f"{rel}: sha256 {got}, manifest says {digest}")

    listed = set(seen)
    for p in root.rglob("*"):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            problems.append(f"{rel}: symlink present in the packet tree")
        elif p.is_file() and rel != "SHA256SUMS" and rel not in listed:
            problems.append(f"{rel}: present in the tree but absent from SHA256SUMS")
        elif not p.is_file() and not p.is_dir():
            problems.append(f"{rel}: neither a regular file nor a directory")

    for q in problems[:40]:
        print(f"  PACKET PROBLEM {q}")
    if len(problems) > 40:
        print(f"  ... and {len(problems) - 40} more")
    print(f"packet verify: {len(entries)} members, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
