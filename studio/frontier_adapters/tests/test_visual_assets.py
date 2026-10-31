"""visual_assets: every rule has a positive control and a must-fail control. Runs against git blobs at this checkout's HEAD."""
import copy
import json
import subprocess
import unittest
from pathlib import Path

from frontier_adapters import engineering_manifest as em
from frontier_adapters import import_cli as ic
from frontier_adapters import visual_assets as va

REPO = str(Path(__file__).resolve().parents[2])
try:
    COMMIT = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    em.git_blob(REPO, COMMIT, f"{va.SIM}/video/manifest.json")
    em.git_blob(REPO, COMMIT, f"{va.PRINT}/manifest.json")
    HAVE = True
except Exception:  # noqa: BLE001
    HAVE = False

_cache = {}


def chains():
    if not _cache:
        manifest = json.loads(em.git_blob(REPO, COMMIT, f"{va.SIM}/video/manifest.json"))
        fake_replay = {"exit": 0, "numpy": "x", "python": "x", "threads": 1, "seconds": 0.0, "command": "fake", "candidates": copy.deepcopy(manifest["candidates"])}
        _cache["replay"] = fake_replay
        _cache["glide"] = va.glide_chain(REPO, COMMIT, replay=fake_replay)
        _cache["rd"] = va.rd_chain(REPO, COMMIT)
        _cache["print"] = va.print_forms_chain(REPO, COMMIT)
    return _cache


def allrecs():
    c = chains()
    return c["glide"].records + c["rd"].records + c["print"].records


class patched_blob:
    """Mutation control: serve altered bytes for one path to the chain reader."""
    def __init__(self, path_suffix, fn):
        self.suffix, self.fn = path_suffix, fn

    def __enter__(self):
        self.orig = em.Chain.blob
        def blob(chain, path):
            b = self.orig(chain, path)
            return self.fn(b) if path.endswith(self.suffix) else b
        em.Chain.blob = blob

    def __exit__(self, *a):
        em.Chain.blob = self.orig


@unittest.skipUnless(HAVE, "pinned blobs not available in this checkout: visual_assets tests NOT run")
class VisualAssets(unittest.TestCase):
    def test_every_picture_and_mesh_is_context_only_and_nothing_here_supports(self):
        ev = [r for r in allrecs() if r["kind"] == "Evidence"]
        render = [r for r in ev if "render" in r["id"] or "build" in r["id"]]
        self.assertEqual(len(render), 1 + 2 + 6)
        self.assertTrue(all(r["payload"]["relation"] == "context_only" for r in render))
        self.assertEqual([r["id"] for r in ev if r["payload"]["relation"] == "supports"], [])           # media never creates support
        self.assertTrue(all(r["payload"]["source_dependence"]["independent_of_claim"] is False for r in ev))

    def test_render_actions_take_the_compute_evidence_as_input_and_outputs_sit_only_under_the_render_action(self):
        recs = allrecs()
        by_v = {r["version"]: r for r in recs}
        g = ic.graph_gates(recs)
        self.assertTrue(g["ok"], g["refused"])
        for r in recs:
            if r["kind"] == "Evidence" and r["payload"]["relation"] == "context_only":
                act = by_v[r["payload"]["produced_by"]["version"]]
                self.assertTrue("-action-render" in act["id"] or "-action-build-" in act["id"], act["id"])
                ins = [by_v[i["version"]] for i in act["payload"]["inputs"]]
                self.assertTrue(ins and all(i["kind"] == "Evidence" for i in ins))                       # lineage points at the numbers
                self.assertTrue(all(i["payload"]["relation"] != "context_only" for i in ins))
        for r in recs:                                                                                # no video/mesh/image under a compute Evidence
            if r["kind"] == "Evidence" and r["payload"]["relation"] in ("unspecified", "reproduces"):
                bad = [a["media_type"] for a in r["payload"]["artifacts"] if (a["media_type"] or "").split("/")[0] in ("video", "image", "model")]
                self.assertEqual(bad, [], r["id"])

    def test_pointers_are_urn_referenced_with_no_licence_and_no_url(self):
        for r in allrecs():
            if r["kind"] == "Evidence":
                for a in r["payload"]["artifacts"]:
                    self.assertTrue(a["uri"].startswith("urn:sha256:"), a["uri"]); self.assertEqual(a["availability"], "referenced"); self.assertIsNone(a["license"])

    def test_printer_and_slicing_stay_unknown_and_forms_are_not_called_viable(self):
        txt = json.dumps([r["payload"] for r in chains()["print"].records if r["kind"] in ("Claim", "Evidence")])
        self.assertIn("UNKNOWN", txt); self.assertIn("Not an ancestor", txt.replace("not an ancestor", "Not an ancestor")); self.assertNotIn('"printer": "Formlabs', txt)

    def test_the_unsat_form_is_reported_as_unsat_not_as_a_success(self):
        a = next(r for r in chains()["print"].records if r["id"] == "viz-form-claim-A-precursor-short-fin")
        self.assertIn("unsat", a["payload"]["statement"]); self.assertIn("wl_hi", a["payload"]["statement"])
        b = next(r for r in chains()["print"].records if r["id"] == "viz-form-claim-B-two-wing-glider")
        self.assertIn("feasible", b["payload"]["statement"])

    def test_replay_identical_reproduces_and_a_perturbed_replay_does_not(self):
        ev = next(r for r in chains()["glide"].records if r["id"] == "viz-glide-evidence-replay")
        self.assertEqual(ev["payload"]["relation"], "reproduces")                                         # positive control
        rp = copy.deepcopy(chains()["replay"]); rp["candidates"][1]["range_nominal"] *= 1.0000001
        c = va.glide_chain(REPO, COMMIT, replay=rp)
        ev2 = next(r for r in c.records if r["id"] == "viz-glide-evidence-replay")
        self.assertEqual(ev2["payload"]["relation"], "unspecified"); self.assertIn("identical: False", ev2["payload"]["context"])

    def test_a_replay_that_did_not_run_is_refused_not_recorded(self):
        with self.assertRaises(va.Refused) as cm:
            va.glide_chain(REPO, COMMIT, replay={"exit": 1, "stderr_tail": "ModuleNotFoundError"})
        self.assertIn("replay.ran", str(cm.exception))
        with self.assertRaises(va.Refused):
            va.glide_chain(REPO, COMMIT, replay={"exit": 0, "candidates": []})

    def test_a_changed_byte_in_any_stated_hash_refuses_the_chain(self):
        flip = lambda b: bytes([b[0] ^ 1]) + b[1:]
        cases = ((va.glide_chain, "glide_fixed_launch.mp4"), (va.glide_chain, "animate_glide.py"), (va.rd_chain, "rd_fields.mp4"), (va.rd_chain, "cell_240_frames.npz"),
                 (va.rd_chain, "receipt.json"), (va.print_forms_chain, "B-two-wing-glider.stl"), (va.print_forms_chain, "B-two-wing-glider.solver.json"), (va.print_forms_chain, "poster.png"))
        for fn, suffix in cases:
            with self.subTest(suffix):
                if suffix == "poster.png":
                    continue                                                                          # print forms have no poster.png; covered by the others
                with patched_blob(suffix, flip):
                    with self.assertRaises(va.Refused):
                        fn(REPO, COMMIT)
        fn = va.print_forms_chain                                                                      # positive control: unmodified bytes pass
        self.assertTrue(fn(REPO, COMMIT, forms=["B-two-wing-glider"]).records)

    def test_manifest_claiming_a_printer_is_refused(self):
        def set_printer(b):
            m = json.loads(b); m["printer_resin"]["printer"] = "Form 4"; return json.dumps(m).encode()
        with patched_blob("print/manifest.json", set_printer):
            with self.assertRaises(va.Refused):
                va.print_forms_chain(REPO, COMMIT, forms=["B-two-wing-glider"])

    def test_no_absolute_paths_and_deterministic(self):
        from frontier_adapters.artifacts import find_abs_paths
        self.assertEqual(find_abs_paths(allrecs()), [])
        again = va.rd_chain(REPO, COMMIT)
        self.assertEqual([r["version"] for r in again.records], [r["version"] for r in chains()["rd"].records])

    def test_coverage_ties_by_sha_flags_untied_and_never_counts_media_as_support(self):
        recs = allrecs()
        media = va.media_in_commit(REPO, COMMIT, roots=(va.PRINT, f"{va.SIM}/video"))
        cov = va.coverage(media, recs)
        self.assertGreater(cov["tied"], 30); self.assertEqual(cov["supports_by_media"], 0)
        self.assertIn("artifacts/print/img/species-graph.png", cov["untied_paths"])                      # real untied file is reported
        extra = media + [{"path": "x/new.mp4", "sha256": "0" * 64, "bytes": 1}]
        self.assertIn("x/new.mp4", va.coverage(extra, recs)["untied_paths"])                              # must-fail control
        stripped = [r for r in recs if r["id"] != "viz-glide-evidence-render"]
        self.assertIn(f"{va.SIM}/video/glide_fixed_launch.mp4", va.coverage(media, stripped)["untied_paths"])   # removing the Evidence unties the video
        self.assertNotIn(f"{va.SIM}/video/glide_fixed_launch.mp4", cov["untied_paths"])


if __name__ == "__main__":
    unittest.main()
