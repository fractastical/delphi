import json
import os
import subprocess

import pytest

from frontier_adapters import p2_lineage as p2
from frontier_adapters.tests.test_run_bundles import ROOT

OUT = os.path.join(ROOT, "frontier_adapters", "examples", "p2_lineage", "p2-lineage.json")
AUDIT = "7605abbb08c24327b74efd763467efc59e2db8bb"
needs = pytest.mark.skipif(subprocess.run(["git", "-C", ROOT, "cat-file", "-e", AUDIT + "^{commit}"], capture_output=True).returncode != 0, reason="audit commit absent")


@needs
def test_counts_and_the_two_unrecoverable_pins_are_the_glide_manifests():
    d = json.load(open(OUT))
    assert d["stale_pins"]["count"] == 20 and d["stale_pins"]["by_resolution"] == {"recoverable_from_git": 18, "bytes_not_found": 2}
    assert {p["evidence"]["id"] for p in d["stale_pins"]["pins"] if p["resolution"] == "bytes_not_found"} == {"viz-glide-evidence-replay", "viz-glide-evidence-sim"}
    assert d["assurance_refs"]["count"] == 13 and not any(r["versions_equal"] for r in d["assurance_refs"]["refs"])


@needs
def test_recoverable_locators_really_hash_to_the_pin_and_a_corrupted_pin_is_not_recoverable():
    d = json.load(open(OUT))
    for p in d["stale_pins"]["pins"]:
        if p["resolution"] == "recoverable_from_git":
            blob = subprocess.check_output(["git", "-C", ROOT, "show", f"{p['pinned_at_commit']}:{p['path']}"])
            assert p2.sha(blob) == p["pinned_sha256"] and p["pinned_byte_size"] == len(blob)
    x = {"evidence": {"id": "e"}, "path": "README.md", "pinned_at_commit": "HEAD", "pinned_sha256": "0" * 64}   # negative control
    assert p2.classify(ROOT, x, "HEAD")["resolution"] == "bytes_not_found"


@needs
def test_output_is_reproduced_from_the_recorded_inputs():
    d = json.load(open(OUT))
    again = p2.build(ROOT, d["audit_input"]["commit"], d["tip"])
    assert again == d
