"""OpenFold2, Morpheus and atomistic-MD chains (root tip 17edd44): shape, honesty, determinism, secret scan, link checks, ephemeral import."""
import json
import os
import subprocess

import pytest

from frontier_adapters import engineering_manifest as em
from frontier_adapters import run_bundles as rb
from frontier_adapters.tests.test_run_bundles import ROOT, pgstore  # noqa: F401  (fixture)

COMMIT = "17edd4480f4616de0e930cec02e8453fb237e40f"
EXAMPLE = os.path.join(ROOT, "frontier_adapters", "examples", "run_bundles_molecular_multicell")
NAMES = ["openfold2", "morpheus", "md"]
needs = pytest.mark.skipif(subprocess.run(["git", "-C", ROOT, "cat-file", "-e", COMMIT + "^{commit}"], capture_output=True).returncode != 0,
                           reason="source commit 17edd44 not present in this checkout")


@pytest.fixture(scope="module")
def chains():
    return {n: rb.ALL_CHAINS[n](ROOT, COMMIT) for n in NAMES}


def kinds(c):
    k = [r["kind"] for r in c.records]
    return k.count("Claim"), k.count("Action"), k.count("Evidence")


def text(c):
    return json.dumps(c.records)


@needs
def test_counts_and_kinds(chains):
    assert {n: kinds(c) for n, c in chains.items()} == {"openfold2": (2, 1, 2), "morpheus": (2, 3, 3), "md": (3, 4, 4)}
    for c in chains.values():
        assert {r["kind"] for r in c.records} <= {"Claim", "Action", "Evidence"}
        assert {r["payload"]["evidence_kind"] for r in c.records if r["kind"] == "Evidence"} <= {"simulated", "predicted", "source_assessment"}


@needs
def test_md_keeps_the_failed_attempt_the_gate_refusal_and_context_only_render(chains):
    c = chains["md"]
    ev = {r["id"]: r["payload"] for r in c.records if r["kind"] == "Evidence"}
    assert ev["run-md-evidence-cuda-render"]["relation"] == "context_only"
    assert all(p["relation"] != "supports" for p in ev.values())
    t = text(c)
    assert "no CUDA trajectory" in t.lower() or "No CUDA trajectory" in t
    assert "refused 1" in t or "composable 0" in t
    assert "estimates fin stiffness" not in t.lower()


@needs
def test_morpheus_is_reported_partial_and_openfold_is_not_a_validation(chains):
    m = text(chains["morpheus"]).lower()
    assert "partial" in m or "cap" in m
    o = text(chains["openfold2"]).lower()
    assert "not a" in o or "unknown" in o


@needs
def test_every_pointer_resolves_and_no_secrets_urls_or_abs_paths(chains):
    for c in chains.values():
        b = em.build_bundle([c], limit=rb.AssetChain.max_records)
        assert b["review_claims"] == [] and all(x["ok"] for x in em.link_checks(b["records"]))
        assert rb.find_secretish(json.dumps(b)) == []
        assert "/home/" not in json.dumps(b) and "/data/" not in json.dumps(b)
        for r in b["records"]:
            for a in r["payload"].get("artifacts", []):
                assert a["availability"] == "referenced" and not a.get("url")


@needs
def test_frozen_files_reproduce_from_a_fresh_build(chains, tmp_path):
    rb.write_frozen(str(tmp_path), [chains[n] for n in NAMES])
    frozen = sorted(n for n in os.listdir(EXAMPLE) if n != "README.md")
    assert frozen == sorted(os.listdir(tmp_path))
    for n in frozen:
        assert open(os.path.join(EXAMPLE, n), "rb").read() == open(tmp_path / n, "rb").read(), n


@needs
def test_a_corrupted_producer_file_is_refused(tmp_path):
    d = str(tmp_path)
    subprocess.run(f"git -C {ROOT} archive {COMMIT} artifacts/molecular | tar -x -C {d}", shell=True, check=True)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e.org", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e.org"}
    g = lambda *a: subprocess.run(["git", "-C", d, *a], check=True, capture_output=True, env=env, text=True).stdout.strip()  # noqa: E731
    g("init", "-q"); g("add", "-A"); g("commit", "-q", "-m", "b")
    rb.md_chain(d, g("rev-parse", "HEAD"))                                    # positive control: unedited copy builds
    open(os.path.join(d, "artifacts/molecular/cuda-v2/production/receipt.json"), "ab").write(b" ")
    g("add", "-A"); g("commit", "-q", "-m", "m")
    with pytest.raises(Exception):
        rb.md_chain(d, g("rev-parse", "HEAD"))


@needs
def test_import_into_an_ephemeral_store_has_zero_forks(chains, pgstore):  # noqa: F811
    for n, c in chains.items():
        out = pgstore.import_bundle("test-only-local-token-for-alice", "mol-import-" + n, em.build_bundle([c], limit=rb.AssetChain.max_records))
        assert len(out["inserted"]) == len(c.records) and out["forks"] == []
