"""Assemble artifacts/reuse-study-visuals/manifest.json: the voxel render plus the two native epithelial movies.

The voxel entry is built by render_voxel.manifest(). The epithelial entry only HASHES and reads producer files (09's committed
artifacts/epithelial/); it renders nothing and runs no physics. Every number it quotes is read from results-r2.json here.

    python3 -m engineering.reuse_visuals.build_manifest
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engineering.reuse_visuals import render_voxel as V  # noqa: E402

EP = "artifacts/epithelial"
CARD = "docs/epithelial-repair-card.md"
RESULTS = f"{EP}/results-r2.json"
MEDIA = {"video": "A1-baseline.mp4", "poster": "A1-baseline_poster.png", "video_arrest": "A2-motility-off.mp4", "poster_arrest": "A2-motility-off_poster.png"}
ERRATA = "artifacts/reuse-study-visuals/epithelial-card-errata.md"
SOURCES = [CARD, f"{EP}/protocol.json", f"{EP}/protocol-r2.json", f"{EP}/results.json", RESULTS,
           *[f"{EP}/arms/{a}/{f}" for a in ("A1-baseline", "A2-motility-off", "F1-no-drive-NEGATIVE") for f in ("build.json", "run.json")]]
RENDERER = ["engineering/epithelial/render.py", "engineering/epithelial/build_model.py", "engineering/epithelial/analyze.py"]


REMAP = {CARD: "artifacts/reuse-study-visuals/sources/epithelial-repair-card.md"}      # served by the protected static-artifact handler
ERRATA_REQUIRED = {CARD}                                                                 # owner 09's card is offered only beside the errata note


def ent(rel: str, download: bool = False) -> dict:
    p = ROOT / rel
    e = dict(path=rel, sha256=V.sha(p), bytes=p.stat().st_size, download=download and rel.endswith((".json", ".md", ".txt")))
    if rel in REMAP:
        e["site_path"] = REMAP[rel]
    if rel in ERRATA_REQUIRED:
        e["errata_required"] = True
    return e


def epithelial() -> dict:
    res = json.loads((ROOT / RESULTS).read_text())
    gates = res["gates"]
    def status(g):
        if g["passed"] is True:
            return "pass"
        if g["passed"] is False:
            return "fail"
        return {"G1b": "incomplete", "G6": "descriptive", "G8": "unevaluable"}[g["id"]]       # the file leaves passed null for these three

    by = {g["id"]: status(g) for g in gates}
    arms = res["arms"]
    g1b = next(g for g in gates if g["id"] == "G1b")
    run = lambda a: json.loads((ROOT / f"{EP}/arms/{a}/run.json").read_text())      # noqa: E731
    g9 = next(g for g in gates if g["id"] == "G9")["detail"]
    return {
        "id": "epithelial-closes-vs-arrests", "study": "epithelial-repair",
        "title": "Epithelial gap in a Cellular Potts model: the same wound closes, or is left open when motility is off",
        "evidence_kind": "SimulationResult: model-only Cellular Potts lattice frames (Morpheus TiffPlotter) with logged cell-centre tracks; not a chart, not validated",
        "labels": {"model_only": True, "kind": "2D Cellular Potts testbed run on the pinned Morpheus engine, CPU", "time": "model units, not minutes; closure is reported in Monte-Carlo sweeps",
                   "length_scale": "26 um mean cell diameter sets a length scale only; no output was compared with data from any cell line or species",
                   "cell_counts": {"unwounded_A5_initial": arms["A5-unwounded-POSITIVE"]["n_cells"], "wounded_A1_F1_after_4_removed": arms["A1-baseline"]["n_cells"], "nominal_target_nodes_per_cell": 625,
                                   "note": "625 is the nominal target volume and scale anchor, not an observed mean: the unwounded run starts with 65 cells (logger and first TIFF), a mean of 40000/65 = 615.4 nodes"},
                   "not_modelled": ["purse-string closure", "proliferation", "signalling", "substrate stiffness", "ECM", "monolayer thickness"],
                   "not_a_reproduction": "Bai and Zeng 2023 (CC BY 4.0) is used for geometric construction and one length scale only; their mechanics is a 3D continuum finite-element model"},
        "summary": {
            "readout_check": {"G1b": f"INCOMPLETE, not a pass: the frozen rule is every written frame, but only {g1b['evaluable']['frames_comparable']} of {g1b['evaluable']['frames_written']} frames ({g1b['evaluable']['fraction'] * 100:.1f}%) can be compared (logger every 10, TIFF every 25); {g1b['evaluable']['disagreements']} disagreements on those, and the other {g1b['evaluable']['frames_not_comparable']} are not evidence of agreement. Same engine state: a readout-consistency check, not independent biology. G1 is an identity from the gap definition. The earlier reported pass is kept as history."},
            "pair": {"same": "wound, seed and every parameter except motility",
                     "closes": {"arm": "A1-baseline", "state": arms["A1-baseline"]["state"], "closed_fraction": arms["A1-baseline"]["closed_fraction"], "closure_sweeps": arms["A1-baseline"]["closure_sweeps"], "wall_s": run("A1-baseline")["wall_s"]},
                     "arrests": {"arm": "A2-motility-off", "state": arms["A2-motility-off"]["state"], "closed_fraction": arms["A2-motility-off"]["closed_fraction"], "wall_s": run("A2-motility-off")["wall_s"]}},
            "passive_floor": {"arm": "F1-no-drive-NEGATIVE", "closed_fraction": arms["F1-no-drive-NEGATIVE"]["closed_fraction"], "state": arms["F1-no-drive-NEGATIVE"]["state"],
                              "reading": "Observed in this one context (both drives off, same wound): the gap still shrinks by this fraction, consistent with surviving cells relaxing toward target volume under perimeter and Metropolis dynamics. It is a context-specific control, not a universal amount to subtract: show it beside a matched baseline, and no isolated mechanism contribution was measured. The corrected separate volume-accounting estimate is 625 nodes filled versus 1875 residual; it is not an independently measured mechanism contribution."},
            "gates": {"strict": {"ids": by, "pass": sum(v == "pass" for v in by.values()), "fail": sum(v == "fail" for v in by.values()), "descriptive": ["G6"], "incomplete_or_unevaluable": ["G1b", "G8"], "total": len(gates), "no_all_frames_claim": True,
                                 "note": "Counted from the exact results-r2.json published in this manifest (historical reporting at 66f2b95 retained): 7 pass, 3 fail, G6 descriptive, G1b incomplete, G8 unevaluable. The frozen G1b rule is not narrowed to shared times to call a pass; no threshold changed; no physics rerun."},
                      "reported_history": {"original": "8 pass, 3 fail, 2 null (G6, G8), with G1b reported as a pass at " + g1b["reported_history"]["at"], "G1b": g1b["reported_history"], "note": "Kept as the historical record and superseded going forward without being erased."}},
            "j_scaling": {"status": "tested model hypothesis, not a law", "predicted_interval": g9["predicted_interval"], "observed_bracket": g9["measured_bracket"], "bracket_geometric_mean": g9["measured_lambda_star"],
                          "scope": "one doubling of interface energy at k=4, one conditional out-of-sample bracket check; 1.414 is the geometric mean of the observed bracket (1, 2), not an observed point threshold; nothing is established at k=7 or for exact proportionality"},
            "gap_size_scaling": "Untested at this resolution: gate G12 failed because the gap ladder is incomplete (k=1 has no nonclosed bracket at the finite horizon), and G8 is not evaluable. The k=4 and k=7 Phi intervals overlap, so differing geometric-mean summaries do not refute a common threshold. The earlier midpoint-based refutation is withdrawn; the incomplete ladder remains a failed check.",
            "horizon": "CLOSED and ARRESTED are operational labels at a finite 1000 model-unit horizon; permanence of arrest is not shown."},
        "caveats": ["Not a treatment, therapy or clinical result; a mechanism testbed.", "Not a viable engineered organism, and not a step toward one.",
                    "Not validated against any measurement. Where it agrees with a published finding, that is two models agreeing.",
                    "No purse-string closure is modelled; the contractility arm is a perimeter constraint, not an actomyosin cable.",
                    "Movie time axes are model units, never minutes or hours."],
        "records_kept": [f"{g['id']} {by[g['id']]}" + (" (reported as a pass in the history; frozen rule not met)" if g["id"] == "G1b" else "") + (f": {g['detail']}" if g["id"] in ("G4", "G10") and isinstance(g["detail"], str) else "") for g in gates if by[g["id"]] != "pass"]
                        + ["the doubling prediction passed one held-out test and is not a physical law"],
        "media": {k: ent(f"{EP}/media/{v}") for k, v in MEDIA.items()} | {"errata": ent(ERRATA)},
        "sources": [ent(p, download=True) for p in SOURCES], "renderer": [ent(p) for p in RENDERER],
        "source_commit": "Historical 36-run outputs with subsequent reporting corrections; exact source files and hashes are listed in this manifest. No movie or native run was replaced."}


def sweep_manifest() -> dict:
    """Bind the additive 240-run followup to producer and independent-review files."""
    bundle = json.loads((ROOT / EP / "publication-bundle.json").read_text())
    for group in bundle["files"].values():
        for rel, pin in group.items():
            actual = ent(rel)
            if any(actual[k] != pin[k] for k in ("sha256", "bytes")):
                raise ValueError(f"producer bundle changed: {rel}")
    sources = []
    for role, rel, label in [
        ("audit", f"{EP}/sweep-audit.json", "Returned-data audit and threshold intervals"),
        ("review", "artifacts/audits/epithelial-sweep/review.json", "Independent recomputation and source hashes"),
        ("review_report", "docs/audits/epithelial-sweep-review-2026-11-01.md", "Independent review, findings and limits"),
        ("criterion_source", "engineering/epithelial/packet_files/analyze_sweep.py", "Frozen criterion source"),
        ("producer", f"{EP}/publication-bundle.json", "Native result and frozen source bundle"),
        ("card", CARD, "Study report with correction history"),
        ("qualifications", ERRATA, "Reading notes and historical qualifications"),
        ("plot_renderer", "engineering/epithelial/plot_brackets.py", "Figure renderer"),
        ("audit_renderer", "engineering/epithelial/audit_return.py", "Returned-data analysis"),
    ]:
        item = ent(rel, download=True) | {"role": role, "label": label}
        if rel.startswith("docs/audits/"):
            item["site_path"] = "artifacts/reuse-study-visuals/sources/" + Path(rel).name
        sources.append(item)
    return {"schema": "frontier.epithelial-sweep-publication/1", "source_commit": bundle["frozen_at_commit"],
            "sources": sources, "figure": ent(f"{EP}/figures/threshold-brackets-light.png")}


def write() -> str:
    m = V.manifest(ROOT / V.OUT)
    m["visuals"].append(epithelial())
    out = ROOT / "artifacts/reuse-study-visuals/manifest.json"
    out.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    (out.parent / "sweep-manifest.json").write_text(json.dumps(sweep_manifest(), indent=1, sort_keys=True) + "\n")
    return str(out)


if __name__ == "__main__":
    print("ok", write())
