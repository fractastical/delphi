"""sim_bundles: positive and must-fail controls. Bioelectric blobs come from this checkout's HEAD, mechanobio from work/mechanobio@76a93e7."""
import json
import subprocess
import unittest
from pathlib import Path

from frontier_adapters import engineering_manifest as em
from frontier_adapters import import_cli as ic
from frontier_adapters import sim_bundles as sb

REPO = str(Path(__file__).resolve().parents[2])
MECH = "76a93e7"
try:
    HEAD = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    em.git_blob(REPO, HEAD, f"{sb.BIO}/manifest.json")
    em.git_blob(REPO, MECH, f"{sb.MECH}/sweep.json")
    HAVE = True
except Exception:  # noqa: BLE001
    HAVE = False
_c = {}


def chains():
    if not _c:
        _c["bio"], _c["mech"] = sb.bioelectric_chain(REPO, HEAD), sb.mechanobio_chain(REPO, MECH)
    return _c


class patched:
    def __init__(self, suffix, fn):
        self.suffix, self.fn = suffix, fn

    def __enter__(self):
        self.o = em.Chain.blob
        o, suffix, fn = self.o, self.suffix, self.fn
        em.Chain.blob = lambda ch, p: fn(o(ch, p)) if p.endswith(suffix) else o(ch, p)

    def __exit__(self, *a):
        em.Chain.blob = self.o


@unittest.skipUnless(HAVE, "pinned blobs (HEAD bioelectric, work/mechanobio@76a93e7) not available: sim_bundles tests NOT run")
class SimBundles(unittest.TestCase):
    def recs(self):
        return chains()["bio"].records + chains()["mech"].records

    def test_graph_closes_and_no_media_is_support(self):
        g = ic.graph_gates(self.recs())
        self.assertTrue(g["ok"], g["refused"])
        ev = [r for r in self.recs() if r["kind"] == "Evidence"]
        self.assertEqual([r["id"] for r in ev if r["payload"]["relation"] == "supports"], [])
        render = [r for r in ev if "-render-" in r["id"]]
        self.assertEqual(len(render), 4 + 2)
        self.assertTrue(all(r["payload"]["relation"] == "context_only" for r in render))

    def test_render_actions_take_compute_evidence_and_media_sits_only_under_render(self):
        by_v = {r["version"]: r for r in self.recs()}
        for r in self.recs():
            if r["kind"] != "Evidence":
                continue
            media = [a for a in r["payload"]["artifacts"] if (a["media_type"] or "").split("/")[0] in ("video", "image")]
            if "-render-" in r["id"]:
                act = by_v[r["payload"]["produced_by"]["version"]]
                self.assertTrue(act["payload"]["inputs"] and all(by_v[i["version"]]["payload"]["relation"] == "unspecified" for i in act["payload"]["inputs"]))
                self.assertTrue(media)
                self.assertTrue(any(a["media_type"] in ("video/mp4", "image/png") for a in media))             # media really typed, so the check below is not vacuous
            else:
                self.assertEqual(media, [], r["id"])

    def test_conditions_source_context_and_open_questions_are_kept(self):
        c = next(r for r in self.recs() if r["id"] == "sim-bioelectric-claim-baseline")["payload"]
        txt = json.dumps(c)
        for needle in ("10.1113/jphysiol.1952.sp004764", "NOT measured fin voltages", "OPEN (bioelectric-cell-tissue", "sodium_scale", "law mutant"):
            self.assertIn(needle, txt)
        m = next(r for r in self.recs() if r["id"] == "sim-mechanobio-claim-sweep")["payload"]
        self.assertIn("10.1073/pnas.1716620115", json.dumps(m)); self.assertIn("NOT claimed executed", json.dumps(m)); self.assertIn("Supplementary Table S1 was NOT retrieved", json.dumps(m))

    def test_the_stale_render_listing_is_recorded_not_hidden(self):
        lim = json.dumps(next(r for r in self.recs() if r["id"] == "sim-mechanobio-claim-sweep")["payload"]["limitations"])
        self.assertIn("Producer inconsistency kept visible", lim); self.assertIn("c893405680b8c835", lim)

    def test_changed_bytes_refuse_each_chain(self):
        flip = lambda b: bytes([b[0] ^ 1]) + b[1:]
        for fn, args, suffix in ((sb.bioelectric_chain, (REPO, HEAD), "baseline.json"), (sb.bioelectric_chain, (REPO, HEAD), "bioelectric.mp4"), (sb.bioelectric_chain, (REPO, HEAD), "model.py"),
                                 (sb.mechanobio_chain, (REPO, MECH), "sweep.json"), (sb.mechanobio_chain, (REPO, MECH), "mechanobio.mp4"), (sb.mechanobio_chain, (REPO, MECH), "model.py")):
            with self.subTest(suffix):
                with patched(suffix, flip):
                    with self.assertRaises(em.Refused):
                        fn(*args)

    def test_failed_producer_status_is_refused(self):
        def bad(b):
            m = json.loads(b); m["exit_status"] = 1; return json.dumps(m).encode()
        with patched("bioelectric/manifest.json", bad):
            with self.assertRaises(em.Refused):
                sb.bioelectric_chain(REPO, HEAD)

    def test_pointers_urn_referenced_no_licence_no_paths(self):
        from frontier_adapters.artifacts import find_abs_paths
        self.assertEqual(find_abs_paths(self.recs()), [])
        for r in self.recs():
            for a in (r["payload"].get("artifacts") or []):
                self.assertTrue(a["uri"].startswith("urn:sha256:")); self.assertEqual(a["availability"], "referenced"); self.assertIsNone(a["license"])


if __name__ == "__main__":
    unittest.main()
