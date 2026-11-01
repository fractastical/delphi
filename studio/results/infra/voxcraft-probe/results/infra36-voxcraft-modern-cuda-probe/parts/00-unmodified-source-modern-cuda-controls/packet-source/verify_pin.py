#!/usr/bin/env python3
"""Verify the fetched source tree against the frozen per-file hashes in source-pin.json.

Only the load-bearing files are carried in the injected packet, because the
injection budget is ~48 KiB and the full 403-file manifest is 48 KB on its own.
That is sufficient: the tarball's own SHA256 (checked by the caller before this
runs) already covers every byte of the archive, and this check pins the specific
files whose contents the probe's claims depend on.
"""
import argparse, hashlib, json, os, sys
a = argparse.ArgumentParser(); a.add_argument("--root", required=True); a.add_argument("--pin", required=True)
a = a.parse_args()
pin = json.load(open(a.pin))
bad, ok = [], 0
for f, h in pin["load_bearing_files"].items():
    p = os.path.join(a.root, f)
    if not os.path.exists(p):
        bad.append((f, "MISSING", h)); continue
    got = hashlib.sha256(open(p, "rb").read()).hexdigest()
    if got != h: bad.append((f, got, h))
    else: ok += 1
for f, got, exp in bad:
    print(f"MISMATCH {f}\n  got      {got}\n  expected {exp}")
print(f"{ok}/{len(pin['load_bearing_files'])} load-bearing files match the frozen pin")
sys.exit(1 if bad else 0)
