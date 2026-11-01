"""Print law index (frontier.print-law-index/1): every downloadable print file, the laws and rules it is grounded in,
and the checks run on its bytes.

Covers what the site's model_downloads publishes: every file a print manifest pins (artifacts/print, print-v2,
print-v3, print-v4, glider/<revision>) with an .stl, .glb or .zip suffix, plus the ZIP a download.json sidecar pins.
(print-v4 is new; the site lists it once root adds it to model_downloads.)

Everything about a file is recomputed here from its bytes: sha256, mesh validity, volume, centroid, the mass at the
card density, the build-envelope fit, the left/right mirror pairs, and each glider revision's nominal assembly. What
other agents executed (claude-07's beam, catch and simulated-flight runs; reviewer claude-13's recomputes) is read
from their committed artifacts by sha256 and marked recomputed_in_this_index false. A law with no evidence record was
not executed on these files, and the index says so.

Grounding a file in a law is not evidence that the shape satisfies it. Masses are calculated from mesh volume and a
card density; nothing was weighed. Frozen manifests, bundles and STLs are read, never written.

    python -m engineering.print_law_index            # writes artifacts/print-law-index.json and docs/print-law-index.md
    python -m engineering.print_law_index --check    # exit 1 if either file would change
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np

from engineering.fishprop import build as FP
from engineering.geometry import validate as VAL
from engineering.glider import mass as MP

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/print-law-index.json"
DOC = ROOT / "docs/print-law-index.md"
CODE_PATHS = ["engineering/print_law_index.py", "engineering/glider/mass.py", "engineering/geometry/validate.py",
              "engineering/fishprop/build.py"]

FAMILIES = [("print-v4", "artifacts/print-v4"), ("print-v3", "artifacts/print-v3"), ("print-v2", "artifacts/print-v2"),
            ("print-v1", "artifacts/print")]
GLIDER = ROOT / "artifacts/glider"

# root's material card: not in this branch's tree, read from the commit claude-07's runs pin
CARD = {"path": "data/materials/formlabs-studio-2026-10-31.json", "commit": "f1796ec",
        "sha256": "44b6b07f5ff30f5d072a387745383ea08d375b5170f7448c70b7f6482dc72ebc",
        "id": "alpha-grey-v1-default-post-cure"}
# other agents' committed runs on these bytes (read, not re-run)
DYNAMICS = {"commit": "90e741c46ce882dff821fac08815cd6c6e63857f", "dir": "artifacts/launch-glider",
            "files": {"r1-strong": "r1-dynamics.json", "r1-light": "r1-dynamics.json",
                      "r2-light": "r2-light-dynamics.json", "r3-daane": "r3-daane-dynamics.json",
                      "r4-daane-printfix": "r4-daane-printfix-dynamics.json"}}
REVIEW = {"commit": "1b5afb1d963e68dfc85c68b1ab5bba2bbc1ec349", "dir": "docs/reviews/launchable-fish-review-run",
          "files": {"r1-strong": "r1-check-output.json", "r1-light": "r1-check-output.json",
                    "r3-daane": "r3-daane-361480f-check.json",
                    "r4-daane-printfix": "r4-daane-printfix-bd2fcf31ca46-check.json"},
          "doc": "docs/reviews/launchable-fish-review-r4-first-print.md"}
ROOT_RECEIPT = {"commit": "ea39db4ed503a0ced8d1ebe42045c123443694e7", "path": "deploy/receipts/r4-mass-root-check.json",
                "revision": "r4-daane-printfix"}
MSG = "/data/artifacts/delphi-evolve-rethink/messages/"   # cited by name only; outside the repository

# launch and lift scenario values: claude-07's declared envelope and the builder's hand-trim constants
RHO_AIR, G, CL, V_BUDGET = 1.225, 9.81, 0.5, 8.0
LEGACY_LIMIT_G = 10.5
CAP_KEY = "mass_for_v_trim_8_m_s_at_CL_0.5_on_this_area_g"
LAUNCH_CASES = [{"id": "envelope", "v_m_s": 10.0, "stroke_m": 0.1, "k": 2.0,
                 "basis": "claude-07 print requirements: SPEC-010's 8 m/s x 1.25, shortest stroke, linear band"},
                {"id": "sim-8ms", "v_m_s": 8.0, "stroke_m": 0.2, "k": 2.0,
                 "basis": "claude-07 r3/r4 simulation: 8 m/s, 0.2 m stroke, linear band profile"}]
CG_WINDOWS = {
    "v3a": {"window_mm": [49.2, 56.3], "never_aft_of_mm": 53.2, "reachable_requirement_mm": [44.0, 60.0],
            "source": "claude-07 print requirements R4 (v3a planform hand NP 54.5-59.0 mm)",
            "source_file": MSG + "glider-dynamics-to-fish-glider-print-reqs.md"},
    "v3c": {"window_mm": [49.5, 55.2], "target_mm": 52.4, "never_aft_of_mm": 54.1,
            "source": "claude-07 r3/r4 first-print constraints, item 4 (r3/r4's own hand NP); replaces the 44-60 mm "
                      "window for r3/r4",
            "source_file": MSG + "glider-dynamics-r3-r4-first-print-constraints.md"}}

VOCAB = {
    "relation": {
        "governing": "the law computed a number reported for these bytes (the computation is in the evidence)",
        "checked": "a stated check against this law or rule was executed on these bytes; its outcome is in checks[]",
        "inspired_only": "the law or source shaped the design; nothing here checks these bytes against it",
        "not_applicable": "the law does not apply to this file; the detail says why"},
    "check_status": {
        "pass": "executed on these bytes and met its stated threshold",
        "fail": "executed and did not meet its threshold (never relaxed)",
        "unresolved": "executed, with a reading or reviewer finding that the threshold does not settle",
        "unknown": "not determinable from these bytes (for example the resin is not chosen)",
        "not_applicable": "does not apply; the detail says why",
        "withdrawn": "the file is not to be printed; the detail says why"}}

GROUNDING_NOTE = (
    "A law listed for a file says how the file relates to it (governing, checked, inspired_only, not_applicable); it "
    "is not evidence that the printed shape satisfies the law. Masses are calculated from mesh volume times a card "
    "density and were not weighed. No part has been printed, weighed, glided or thrown; no launch is cleared; the "
    "lift, drag, stability, beam and catch numbers are hand models or simulated scenarios with assumed coefficients "
    "(C_L in particular depends on geometry and flow and generally comes from experiment). Failed thresholds are "
    "reported as failed. Frozen revisions are read, never edited; inconsistencies in their prose are listed under "
    "findings, not corrected.")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True).stdout


def git_json(commit: str, path: str) -> tuple[dict, str]:
    b = git("show", f"{commit}:{path}")
    return json.loads(b), sha(b)


def introduced_in(rel: str) -> str | None:
    out = git("log", "--diff-filter=A", "--format=%h", "--", rel).decode().split()
    return out[-1] if out else None


def r(x, n=6):
    return None if x is None else round(float(x), n)


def chk(cid: str, status: str, detail: str) -> dict:
    return {"id": cid, "status": status, "detail": detail}


def rel(law_id: str, relation: str, detail: str) -> dict:
    return {"law_id": law_id, "relation": relation, "detail": detail}


def code_sha() -> str:
    h = hashlib.sha256()
    for p in CODE_PATHS:
        h.update(p.encode() + b"\0" + (ROOT / p).read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------- laws
def laws(card: dict, dyn_ev: list, rev_ev: list) -> list:
    idx = {"by": "this index", "artifact_path": "artifacts/print-law-index.json", "artifact_sha256": None,
           "commit": None, "recomputed_in_this_index": True}
    def builder(what):
        return {"by": "glider builder (claude-05), recorded in each frozen manifest", "what": what,
                "artifact_path": "artifacts/glider/<revision>/manifest.json", "artifact_sha256": None,
                "commit": None, "recomputed_in_this_index": False}

    def sel(ev, key):
        return [e for e in ev if key in e["what"]]
    return [
        {"id": "mass_from_mesh_volume", "title": "Mass from mesh volume and cured density", "kind": "physical_law",
         "latex": r"m=\rho V,\qquad V=\tfrac{1}{3}\oint_{\partial\Omega}\mathbf{x}\cdot\mathbf{n}\,dA",
         "source_urls": ["https://en.wikipedia.org/wiki/Divergence_theorem", card["source_url"]],
         "code_paths": ["engineering/glider/mass.py", "engineering/print_law_index.py"],
         "scope": "Exact for a closed, consistently oriented mesh. rho is the manufacturer's cured (solid) density "
                  f"{card['solid_density_kg_m3']} kg/m3 from root's card; the liquid density "
                  f"{card['liquid_density_kg_m3_not_for_part_mass']} kg/m3 is not used. Supports, trapped resin, "
                  "cure shrinkage, glue, tape and ballast are not in the mesh; nothing was weighed.",
         "evidence": [dict(idx, what="volume and mass recomputed from every STL in files[]"),
                      builder("per-part mass_properties (analytic controls: offset box, 64-gon prism, hollow box)"),
                      *sel(dyn_ev, "mass"), *sel(rev_ev, "mass")]},
        {"id": "rigid_body_mass_properties", "title": "Centroid, inertia tensor and parallel-axis transfer",
         "kind": "physical_law",
         "latex": r"\bar{\mathbf{x}}=\frac{1}{V}\int_\Omega\mathbf{x}\,dV,\quad "
                  r"\mathbf{I}=\rho\int_\Omega\left(|\mathbf{r}|^2\mathbf{1}-\mathbf{r}\mathbf{r}^{\top}\right)dV,\quad "
                  r"\mathbf{I}_O=\mathbf{I}_G+m\left(|\mathbf{d}|^2\mathbf{1}-\mathbf{d}\mathbf{d}^{\top}\right)",
         "source_urls": ["https://en.wikipedia.org/wiki/Center_of_mass",
                         "https://en.wikipedia.org/wiki/Parallel_axis_theorem"],
         "code_paths": ["engineering/glider/mass.py"],
         "scope": "Uniform density over the mesh; exact for the mesh, not for the print.",
         "evidence": [dict(idx, what="print-pose centroid of every STL; fish-frame assembly CG of every glider "
                                     "revision"), builder("per-part and assembled CG and inertia"),
                      *sel(dyn_ev, "mass"), *sel(rev_ev, "mass")]},
        {"id": "assembly_moment_balance", "title": "Assembly mass and CG as mass-weighted sums",
         "kind": "physical_law", "latex": r"M=\sum_i m_i,\qquad \bar{\mathbf{x}}=\frac{\sum_i m_i\bar{\mathbf{x}}_i}{M}",
         "source_urls": ["https://en.wikipedia.org/wiki/Center_of_mass"],
         "code_paths": ["engineering/glider/mass.py", "engineering/print_law_index.py"],
         "scope": "The nominal assembly's dry mass and CG, from the part meshes moved into the fish frame by each "
                  "part's recorded print_to_fish transform. Glue and tape are not included.",
         "evidence": [dict(idx, what="nominal assembly of every glider revision recombined from its STLs"),
                      builder("nominal_assembly.dry")]},
        {"id": "ballast_lever", "title": "Nose ballast for a target CG (moment balance)", "kind": "physical_law",
         "latex": r"m_b=M\,\frac{\bar x_{\mathrm{dry}}-x_t}{x_t-x_b}",
         "source_urls": ["https://en.wikipedia.org/wiki/Center_of_mass"],
         "code_paths": ["engineering/glider/build.py"],
         "scope": "Fill packed from the front of the bay, point mass at the fill centroid; bulk density 4.7 g/cm3 "
                  "is ASSUMED (steel shot set in glue), not measured.",
         "evidence": [builder("ballast rows; consistency of each row's moment balance is re-checked here")]},
        {"id": "level_flight_lift", "title": "Lift equation for level trim (mass budget and trim speed)",
         "kind": "hand_model",
         "latex": r"L=\tfrac{1}{2}\rho V^2 S\,C_L=mg\;\Rightarrow\; m_{\max}=\frac{\rho V^2 S\,C_L}{2g},\quad "
                  r"V_{\mathrm{trim}}=\sqrt{\frac{2mg}{\rho S\,C_L}}",
         "source_urls": ["https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/lift-equation/"],
         "code_paths": ["engineering/glider/build.py", "engineering/print_law_index.py"],
         "scope": f"rho {RHO_AIR} kg/m3, g {G} m/s2, S = paired flat fin area from the revision's mesh, "
                  f"C_L {CL} ASSUMED (uncited; NASA's page notes C_L depends on geometry and flow and is generally "
                  "found by experiment). A hand budget, not a flight result.",
         "evidence": [dict(idx, what="area-specific mass budget recomputed from each revision's paired area"),
                      builder("trim_speed_hand")]},
        {"id": "drag_equation", "title": "Drag equation", "kind": "hand_model",
         "latex": r"D=\tfrac{1}{2}\rho V^2 S\,C_D",
         "source_urls": ["https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/"],
         "code_paths": [],
         "scope": "No drag coefficient was measured for any file. Drag enters only claude-07's simulated scenarios, "
                  "with declared scenario coefficients.",
         "evidence": sel(dyn_ev, "simulated")},
        {"id": "static_margin_hand_np", "title": "Static margin from a hand neutral-point bracket",
         "kind": "hand_model",
         "latex": r"\mathrm{SM}=\frac{x_{np}-x_{cg}}{\bar c},\quad C_{L\alpha}=\frac{2\pi A}{2+\sqrt{A^2+4}}"
                  r"\ \text{(Helmbold)},\quad \Delta x_{np}\ \text{from the Munk body term }(k_2-k_1)\,\mathcal{V}",
         "source_urls": ["https://en.wikipedia.org/wiki/Longitudinal_static_stability",
                         "https://ntrs.nasa.gov/citations/19930091249"],
         "code_paths": ["engineering/glider/build.py"],
         "scope": "Helmbold unswept lift slopes per fin pair, downwash 0.2-0.6 and Munk k2-k1 0.80-0.95 declared; "
                  "a bracket, not a VLM or a measurement. Helmbold's original is not linked or read here.",
         "evidence": [builder("hand_neutral_point"), *sel(dyn_ev, "hand_np")]},
        {"id": "launch_acceleration", "title": "Launch acceleration and peak band force", "kind": "physical_law",
         "latex": r"a_{\mathrm{mean}}=\frac{V_0^2}{2s},\quad a_{\mathrm{peak}}=k\,a_{\mathrm{mean}},\ "
                  r"k\in\{1,\pi/2,2\},\quad F=m\,a_{\mathrm{peak}}",
         "source_urls": ["https://en.wikipedia.org/wiki/Equations_of_motion"],
         "code_paths": ["engineering/print_law_index.py"],
         "scope": "Constant-mass kinematics over the band stroke; the launcher is not measured, so V0, s and k are "
                  "declared scenarios.",
         "evidence": [dict(idx, what="peak band force for each revision's ballasted mass at the declared cases")]},
        {"id": "euler_bernoulli_fin_root", "title": "Euler-Bernoulli bending of the fin as a root-clamped beam",
         "kind": "physical_law",
         "latex": r"\sigma=\frac{M c}{I},\qquad \frac{d^2}{ds^2}\!\left(EI\,\frac{d^2w}{ds^2}\right)=q(s)",
         "source_urls": ["https://en.wikipedia.org/wiki/Euler%E2%80%93Bernoulli_beam_theory"],
         "code_paths": [],
         "scope": "claude-07's beam (engineering/fin_mechanics/beam.py on work/launch-glider): membrane plus one "
                  "leading-edge spar, allowable UTS/3 (declared), orientation case k_z 0.5 (declared). Not "
                  "recomputed here. Coupon properties are not fin-level verification.",
         "evidence": sel(dyn_ev, "fin")},
        {"id": "catch_bond_shear", "title": "Catch liner bond in shear", "kind": "hand_model",
         "latex": r"\tau=\frac{F}{P\,t}\le\frac{k_z\,\sigma_{\mathrm{UTS}}}{\mathrm{SF}}",
         "source_urls": [], "code_paths": [],
         "scope": "claude-07's catch check; the liner height is not in the record, so the bond perimeter comes from "
                  "the body section. Not recomputed here.",
         "evidence": sel(dyn_ev, "catch")},
        {"id": "closed_oriented_manifold", "title": "Closed, oriented, single-piece mesh", "kind": "manufacturing_rule",
         "latex": r"\text{every edge in exactly two faces, opposite directions};\ V>0;\ \text{one component}",
         "source_urls": [], "code_paths": ["engineering/geometry/validate.py"],
         "scope": "Global self-intersection is not checked.",
         "evidence": [dict(idx, what="every STL re-read and re-checked"), *sel(rev_ev, "closed")]},
        {"id": "min_wall_sampled", "title": "Minimum wall thickness, sampled", "kind": "manufacturing_rule",
         "latex": r"t_{\min}\ge t_{\mathrm{rule}}\quad(\text{glider }0.45\text{ mm; props }1.0\text{ mm; "
                  r"reinforced v4 prop }1.5\text{ mm})",
         "source_urls": [], "code_paths": ["engineering/glider/build.py", "engineering/geometry/validate.py"],
         "scope": "Provisional rules, not printer-certified. Inward rays from sampled faces; a thinner region between "
                  "samples can be missed. The glider builder classes a reading whose exit face does not oppose its "
                  "entry face as edge-limited and reports it without gating; that is how the catch-slot feather "
                  "edges passed its gate (findings).",
         "evidence": [builder("wall sampler (3000 samples, seed 7)"), *sel(rev_ev, "wall"),
                      {"by": "prop builder (claude-05), recorded in each print-v4 design record",
                       "what": "second, denser wall sample on every print-v4 STL (12,000 samples, seed 11)",
                       "artifact_path": "artifacts/print-v4/design/<prop>.json", "artifact_sha256": None,
                       "commit": None, "recomputed_in_this_index": False}]},
        {"id": "build_envelope_fit", "title": "Fits the declared build volume", "kind": "manufacturing_rule",
         "latex": r"\mathrm{sort}(\text{extent})\le\mathrm{sort}(\text{envelope})-2m",
         "source_urls": [], "code_paths": ["engineering/print_law_index.py"],
         "scope": "Axis-aligned permutations only. Glider: 200 x 125 x 235 mm less 5 mm a side (root-confirmed "
                  "envelope, assumed margin). Props: 120 mm box. Printer compatibility is not claimed.",
         "evidence": [dict(idx, what="extents recomputed for every STL")]},
        {"id": "chirality_mirror_pair", "title": "A right part is the mirror image of its left part",
         "kind": "manufacturing_rule",
         "latex": r"\{\mathbf{v}_R\}=\{\mathbf{v}_L\,\mathrm{diag}(1,1,-1)\}\neq\{\mathbf{v}_L\},\qquad "
                  r"\det R_{\mathrm{print}\to\mathrm{fish}}=+1",
         "source_urls": [], "code_paths": ["engineering/print_law_index.py", "engineering/glider/build.py"],
         "scope": "Glider paired fins: a print cannot be reflected, so a right file holding the left part prints a "
                  "second left fin. print-v4 props (one solid each): the solid equals its own y-mirror, "
                  r"vol(M \ mirror_y M) / vol(M) <= 1e-3, so the right fins are the left fins mirrored.",
         "evidence": [dict(idx, what="vertex-set comparison of every _L/_R print pair"), *sel(rev_ev, "pair"),
                      dict(idx, what="y-mirror symmetric difference of every print-v4 STL")]},
        {"id": "extremity_stoutness", "title": "No extremity thinner than the wall rod (no needle tips)",
         "kind": "manufacturing_rule",
         "latex": r"\mathrm{vol}\left(\Omega\cap B_R(\mathbf{h})\right)\ge\pi\left(\tfrac{t_{\mathrm{rule}}}{2}"
                  r"\right)^{2}R\quad\forall\,\mathbf{h}\in\text{hull extremities},\ R=3\text{ mm}",
         "source_urls": [], "code_paths": ["engineering/fishprop/build.py", "engineering/print_law_index.py"],
         "scope": "A design rule (not a printer limit): at every convex-hull vertex cluster (2 mm), the material within "
                  "3 mm is at least a rod of wall-rule diameter and 3 mm length. Extremities inside the hull, such as "
                  "the caudal fork's inner corner, are not tested. Run on print-v4 only.",
         "evidence": [dict(idx, what="extremity test recomputed on every print-v4 STL")]},
        {"id": "source_outline_fidelity", "title": "Fin rays follow the source candidate", "kind": "design_assumption",
         "latex": r"\{\ell_i,\mathbf{r}_i\}_{\mathrm{print}}=\{\ell_i,\mathbf{r}_i\}_{\mathrm{rays.json}}",
         "source_urls": [], "code_paths": ["engineering/glider/build.py"],
         "scope": "The source candidates are source-conditioned models; their biological fidelity is not claimed "
                  "here. Display props are inspired by their candidates and not checked against them.",
         "evidence": [builder("outline_check against the candidate's own rays.json")]},
    ]


# ---------------------------------------------------------------- shared per-STL work
def mesh_record(b: bytes, density: float | None):
    V, T = VAL.read_stl(b)
    c = VAL.check(V, T, None, thickness=False)
    p = MP.properties(V, T, density or 1220.0)
    return V, T, c, p


def validity_check(c: dict) -> dict:
    ok = c["ok"] and c["face_connected_components"] == 1
    return chk("closed_oriented_manifold", "pass" if ok else "fail",
               f"recomputed: closed {c['closed_two_manifold']}, oriented {c['consistently_oriented']}, "
               f"{c['face_connected_components']} component(s), {c['degenerate_triangles']} degenerate triangles, "
               f"signed volume {c['signed_volume_mm3']:.3f} mm3; self-intersection not checked")


def envelope_check(size, envelope, margin) -> dict:
    lim = sorted(e - 2 * margin for e in envelope)
    ok = all(a <= b for a, b in zip(sorted(size), lim))
    return chk("build_envelope_fit", "pass" if ok else "fail",
               f"recomputed extents {[round(x, 2) for x in size]} mm against {envelope} mm less {margin} mm a side")


def sha_check(actual: str, declared: str | None, where: str) -> dict:
    if declared is None:
        return chk("sha256_pinned", "unknown", f"no pin in {where}")
    return chk("sha256_pinned", "pass" if actual == declared else "fail", f"file sha256 against {where}")


# ---------------------------------------------------------------- display props
def prop_files(card: dict) -> tuple[list, list]:
    files, findings = [], []
    for family, d in FAMILIES:
        man = json.loads((ROOT / d / "manifest.json").read_text())
        dl = json.loads((ROOT / d / "downloads.json").read_text())
        by_path = {}
        for f in dl["forms"]:
            for x in f["files"]:
                by_path[x["path"]] = (f, x)
        for relp, pin in sorted(man["files"].items()):
            suffix = Path(relp).suffix.lower()
            if suffix not in {".stl", ".glb"}:
                continue
            path = f"{d}/{relp}"
            b = (ROOT / path).read_bytes()
            form, x = by_path.get(relp, (None, None))
            kind_dl = x["kind"] if x else None
            kind = {"stl_prop": "stl_prop", "stl_stand": "stl_stand", "stl_prop_scale_relief": "stl_prop_relief",
                    "glb_prop": "glb_view"}.get(kind_dl, "glb_view" if suffix == ".glb" else "stl_prop")
            src = [{"path": f"{d}/manifest.json", "sha256": sha((ROOT / d / "manifest.json").read_bytes()),
                    "role": "catalog manifest (pins this file)"},
                   {"path": f"{d}/downloads.json", "sha256": sha((ROOT / d / "downloads.json").read_bytes()),
                    "role": "downloads record (kind, checks)"}]
            if form and form.get("source_candidate"):
                src.append({"path": f"artifacts/fish3d/{form['source_candidate']}/candidate.json",
                            "sha256": form.get("source_candidate_sha256"), "role": "source candidate (inspiration)"})
            if form and (ROOT / d / "design" / f"{form['id']}.json").exists():
                src.append({"path": f"{d}/design/{form['id']}.json",
                            "sha256": sha((ROOT / d / "design" / f"{form['id']}.json").read_bytes()),
                            "role": "prop design record"})
            row = {"path": path, "sha256": sha(b), "bytes": len(b), "family": family,
                   "revision": man.get("edition", {}).get("id") or {"print-v3": "v3", "print-v4": "v4"}.get(family, "v1"),
                   "kind": kind, "part_id": form["id"] if form else None, "withdrawn": None,
                   "introduced_in_commit": introduced_in(path), "source_artifacts": src,
                   "material": {"id": None, "density_kg_m3": None,
                                "status": "unknown: printer and resin not chosen (manifest printer_resin)",
                                "card_path": None, "card_commit": None, "card_sha256": None, "source_url": None}}
            checks = [sha_check(row["sha256"], pin, f"{d}/manifest.json")]
            if kind == "glb_view":
                row.update(law_ids=[], law_relations=[], mass_g=None, volume_mm3=None, cg_mm_print_pose=None,
                           conditional_mass_g_at_1220_kg_m3=None,
                           mass_basis="not a print file: viewer model (GLB); no mass is computed from it")
                row["checks"] = checks
                files.append(row)
                continue
            _, _, c, p = mesh_record(b, None)
            rec = (form or {}).get({"stl_prop": "prop_checks", "stl_stand": "stand_checks",
                                    "stl_prop_relief": "scale_relief_checks"}[kind]) or {}
            checks.append(validity_check(c))
            checks.append(chk("mesh_matches_record", "pass" if rec.get("mesh_sha256") == c["mesh_sha256"] else "fail",
                              f"{d}/downloads.json mesh_sha256"))
            vol_rec = rec.get("signed_volume_mm3")
            checks.append(chk("volume_matches_record",
                              "pass" if vol_rec and abs(vol_rec - p["volume_mm3"]) <= 1e-6 * vol_rec else "fail",
                              f"recomputed {p['volume_mm3']:.4f} mm3 vs recorded {vol_rec}"))
            box = rec.get("fits_box_mm", 120.0)
            checks.append(envelope_check(c["bounds_mm"]["size"], [box] * 3, 0.0))
            if kind == "stl_prop_relief":
                rl = rec.get("relief", {})
                checks.append(chk("min_wall_sampled", "unknown",
                                  f"relief texture {rl.get('heights_mm')} mm is below the 1.0 mm rule by design and "
                                  f"not gated (sampled minimum {r(rec.get('min_sampled_wall_mm'), 3)} mm); whether it "
                                  "resolves depends on the unknown printer. The smooth file is the gated one."))
            else:
                ok = rec.get("min_wall_ok")
                checks.append(chk("min_wall_sampled", "pass" if ok else ("fail" if ok is False else "unknown"),
                                  f"builder record: sampled minimum {r(rec.get('min_sampled_wall_mm'), 3)} mm against "
                                  f"{rec.get('min_wall_mm_required')} mm, {rec.get('wall_samples')} samples; a "
                                  "thinner region between samples can be missed"))
            v4 = family == "print-v4"
            design = json.loads((ROOT / d / "design" / f"{form['id']}.json").read_text()) if v4 else {}
            if v4:
                checks += v4_checks(b, kind, rec, design)
            else:
                checks.append(chk("extremity_stoutness", "unknown", "not run on this family (added with print-v4)"))
            if family == "print-v1":
                checks.append(chk("edition_status", "unresolved",
                                  "superseded by print-v2 (edition v2 corrects the body half-width at single "
                                  "stations); still published as an earlier edition"))
            not_fly = (f"display prop at display scale {form.get('display_scale') if form else '?'}, with fins "
                       "thickened for printing; no flight is intended or modelled for this file")
            law_relations = [
                rel("mass_from_mesh_volume", "governing",
                    "volume computed from these bytes; mass_g is null because the resin is unknown; "
                    "conditional_mass_g_at_1220_kg_m3 assumes the mesh volume printed fully dense in a 1220 kg/m3 resin"),
                rel("rigid_body_mass_properties", "governing", "print-pose volume centroid computed from these bytes"),
                rel("closed_oriented_manifold", "checked", "recomputed here"),
                rel("min_wall_sampled", "checked" if kind != "stl_prop_relief" else "not_applicable",
                    f"builder's sampled {rec.get('min_wall_mm_required')} mm rule" if kind != "stl_prop_relief" else
                    "relief texture is not gated by design"),
                *([rel("extremity_stoutness", "checked", "recomputed here"),
                   rel("chirality_mirror_pair", "checked" if kind != "stl_prop_relief" else "not_applicable",
                       "y-mirror symmetric difference recomputed here" if kind != "stl_prop_relief" else
                       "the scale lattice need not be mirror symmetric; the smooth file carries the fin chirality "
                       "check")] if v4 else []),
                rel("build_envelope_fit", "checked", "120 mm box, recomputed here"),
                rel("source_outline_fidelity", "inspired_only" if kind != "stl_stand" else "not_applicable",
                    "shaped from a source design or candidate; not checked against it here"
                    if kind != "stl_stand" else "a stand, not a fish form"),
                *[rel(lid, "not_applicable", not_fly) for lid in
                  ("level_flight_lift", "drag_equation", "static_margin_hand_np", "launch_acceleration",
                   "catch_bond_shear", "ballast_lever")],
                rel("euler_bernoulli_fin_root", "inspired_only",
                    "the root gusset thickens each fin where a root-clamped cantilever's bending moment is largest; "
                    "no beam check is computed for this prop") if design.get("lineage") and form["id"].endswith(
                    "-reinforced") and kind != "stl_stand" else rel("euler_bernoulli_fin_root", "not_applicable",
                                                                     not_fly)]
            if form and form.get("solver") is not None:
                checks.append(chk("source_design_solver", "not_applicable",
                                  f"the z3 constraint solver reported '{form['solver']}' for the 1:1 source design, "
                                  f"not for this printed prop; glide simulation for that design: "
                                  f"'{form.get('glide_sim')}'"))
            row.update(law_ids=[x["law_id"] for x in law_relations if x["relation"] != "not_applicable"],
                       law_relations=law_relations, checks=checks, mass_g=None,
                       mass_basis="unknown: resin not chosen; volume calculated from the mesh"
                       + ("; the conditional mass uses the Alpha Grey V1 cured density from root's card "
                          f"({CARD['path']} @ {CARD['commit']})" if v4 else ""),
                       conditional_mass_g_at_1220_kg_m3=r(p["volume_mm3"] * 1220e-6, 9),
                       volume_mm3=r(p["volume_mm3"]), cg_mm_print_pose=[r(v, 4) for v in p["cg_mm"]])
            files.append(row)
    return files, findings


def v4_checks(b: bytes, kind: str, rec: dict, design: dict) -> list:
    """print-v4 manufacturing checks: extremities and mirror symmetry recomputed from the bytes; the dense wall
    sample read from the builder record (not re-run: 12,000 rays per file)."""
    V, T = VAL.read_stl(b)
    m = FP.as_manifold(V, T)
    wall = design["wall_rule"]["min_wall_mm"]
    ex = FP.extremities(m, wall)
    out = [chk("extremity_stoutness", "pass" if ex["ok"] else "fail",
               f"recomputed: least material {ex['min_material_mm3']:.3f} mm3 within {ex['ball_radius_mm']} mm of an "
               f"extremity (at {ex['min_at_mm']}) against a {wall:g} mm rod's {ex['rod_reference_mm3']:.3f} mm3; "
               f"{ex['extremities_tested']} extremities")]
    mf_ = FP.mirror_fraction(m)
    if kind == "stl_prop_relief":
        out.append(chk("chirality_mirror_pair", "not_applicable",
                       f"y-mirror fraction {mf_:.2e} reported; the scale lattice need not be mirror symmetric"))
    else:
        out.append(chk("chirality_mirror_pair", "pass" if mf_ <= FP.MIRROR_MAX_FRACTION else "fail",
                       f"recomputed: y-mirror symmetric difference {mf_:.2e} of the volume (limit "
                       f"{FP.MIRROR_MAX_FRACTION:g})"))
    dw = (rec.get("manufacturing") or {}).get("dense_wall") or {}
    if kind == "stl_prop_relief":
        out.append(chk("min_wall_dense", "not_applicable",
                       f"texture file: dense sampled minimum {r(dw.get('min_mm'), 3)} mm reported, not gated"))
    else:
        out.append(chk("min_wall_dense", "pass" if dw.get("ok") else ("fail" if dw.get("ok") is False else "unknown"),
                       f"builder record: {dw.get('samples')} samples (seed {dw.get('seed')}), minimum "
                       f"{r(dw.get('min_mm'), 3)} mm against {wall:g} mm; a thinner region between samples can be "
                       "missed"))
    sl = (rec.get("manufacturing") or {}).get("slivers") or {}
    out.append(chk("sliver_triangles", "pass" if sl.get("count") == 0 else "unresolved",
                   f"builder record: {sl.get('count')} triangles under {sl.get('area_below_mm2')} mm2 (minimum "
                   f"{sl.get('min_area_mm2')} mm2, least angle {r(sl.get('min_angle_deg'), 4)} deg); degenerate "
                   "triangles (area < 1e-10 mm2) are gated separately and are zero"))
    return out


# ---------------------------------------------------------------- glider
def transform_mesh(V, T, A):
    A = np.asarray(A, dtype=float)
    Vf = V @ A[:3, :3].T + A[:3, 3]
    return (Vf, T[:, ::-1]) if np.linalg.det(A[:3, :3]) < 0 else (Vf, T)


def vset(V):
    return {tuple(v) for v in np.round(V, 4)}


def glider(card: dict, dyn: dict, rev_checks: dict, defects: dict, findings_raw: dict, rootchk: dict):
    files, assemblies = [], []
    density = float(card["solid_density_kg_m3"])
    withdrawn_revs = set(defects["right_hand_print_files_are_left_parts"]["revisions"])
    open_wall = {x["id"]: x for x in findings_raw["findings"]}.get("body_thin_wall_near_forward_catch_slot")
    for mpath in sorted(GLIDER.glob("*/manifest.json")):
        revn = mpath.parent.name
        d = f"artifacts/glider/{revn}"
        mb = mpath.read_bytes()
        m = json.loads(mb)
        assert m["material"]["density_kg_m3"] == density, revn
        parts = {p["stl"]: p for p in m["parts"]}
        candidate = m["source_candidate"]
        dy = dyn.get(revn)
        man_src = {"path": f"{d}/manifest.json", "sha256": sha(mb), "role": "frozen revision manifest (pins this file)"}
        cand_src = {"path": candidate["path"], "sha256": candidate["sha256"], "role": "source candidate"}
        card_src = {"path": CARD["path"], "sha256": CARD["sha256"], "role": f"material card @ {CARD['commit']}"}
        material = {"id": card["id"], "density_kg_m3": density,
                    "status": "manufacturer-reported cured density, default post-cure (root's card); provisional "
                              "scenario resin; printer, cartridge and cure hardware unconfirmed",
                    "card_path": CARD["path"], "card_commit": CARD["commit"], "card_sha256": CARD["sha256"],
                    "source_url": card["source_url"]}
        meshes = {}
        for relp, pin in sorted(m["files"].items()):
            suffix = Path(relp).suffix.lower()
            if suffix not in {".stl", ".glb"}:
                continue
            path = f"{d}/{relp}"
            b = (ROOT / path).read_bytes()
            row = {"path": path, "sha256": sha(b), "bytes": len(b), "family": "glider", "revision": revn,
                   "introduced_in_commit": introduced_in(path), "withdrawn": None, "material": material,
                   "source_artifacts": [man_src, cand_src, card_src]}
            checks = [sha_check(row["sha256"], pin, f"{d}/manifest.json")]
            if suffix == ".glb":
                row.update(kind="glb_view", part_id=None, law_ids=[], law_relations=[], checks=checks, mass_g=None,
                           volume_mm3=None, cg_mm_print_pose=None, conditional_mass_g_at_1220_kg_m3=None,
                           mass_basis="not a print file: assembled viewer model (GLB, metres)")
                files.append(row)
                continue
            p = parts[relp]
            V, T, c, mp = mesh_record(b, density)
            meshes[p["id"]] = (V, T, p)
            checks.append(validity_check(c))
            checks.append(chk("mesh_matches_record", "pass" if p["stl_file"]["mesh_sha256"] == c["mesh_sha256"]
                              else "fail", "manifest stl_file.mesh_sha256"))
            dm = abs(mp["mass_g"] - p["mass_properties"]["mass_g"]) / p["mass_properties"]["mass_g"]
            checks.append(chk("mass_matches_record", "pass" if dm <= 1e-4 else "fail",
                              f"recomputed {mp['mass_g']:.6f} g vs manifest {p['mass_properties']['mass_g']:.6f} g "
                              f"(relative difference {dm:.1e}); both are volume x {density:g} kg/m3, not weighed"))
            pr = m["printer"]
            checks.append(envelope_check(c["bounds_mm"]["size"], pr["build_envelope_mm"], pr["margin_mm_per_side"]))
            w = p["wall"]
            if w["wall_min_mm"] < w["rule_mm"] or w["no_hit"]:
                wst, wdet = "fail", "gated reading below the rule"
            elif w.get("edge_limited_below_rule", 0):
                wst, wdet = "unresolved", (f"{w['edge_limited_below_rule']} edge-limited reading(s) below the rule, "
                                           f"min {w['edge_limited_min_mm']:.3f} mm at "
                                           f"{w.get('edge_limited_below_rule_at_mm')}; reported, not gated")
            else:
                wst, wdet = "pass", "no gated or edge-limited reading below the rule"
            wdet = (f"builder sampler: gated minimum {w['wall_min_mm']:.3f} mm against {w['rule_mm']} mm, "
                    f"{w['samples']} samples; {wdet}")
            if p["id"] == "body" and open_wall and revn in open_wall["revisions"]:
                wst = "fail" if revn in ("r3-daane", "r4-daane-printfix") else "unresolved"
                wdet += ("; reviewer claude-13: " + ("dense sampling found readings down to 0.097 mm at the x 20 slot's "
                                                     "lateral openings (feather edges) and 0.115 mm twice on r3"
                                                     if wst == "fail" else "same slot design, not re-measured here"))
            checks.append(chk("min_wall_sampled", wst, wdet))
            kind_part = p["kind"]
            is_fin = kind_part == "fin"
            base = p["id"].split("-")[0]
            if is_fin and base.endswith("_R") and revn in withdrawn_revs:
                row["withdrawn"] = ("holds the LEFT part's vertices (export defect, KNOWN_DEFECTS.json); printing it "
                                    "gives a second left fin; use r4-daane-printfix")
            law_relations = [
                rel("mass_from_mesh_volume", "governing", f"mass = volume x {density:g} kg/m3, recomputed here"),
                rel("rigid_body_mass_properties", "governing", "print-pose centroid recomputed here; fish-frame CG via "
                                                               "the recorded transform (assemblies)"),
                rel("closed_oriented_manifold", "checked", "recomputed here"),
                rel("min_wall_sampled", "checked", "builder's sampler; reviewer readings where they exist"),
                rel("build_envelope_fit", "checked", "recomputed here"),
                rel("source_outline_fidelity", "checked" if kind_part in ("fin", "shell") else "not_applicable",
                    f"builder outline_check against {candidate['id']}/rays.json: "
                    f"{m['biological_constraints']['outline_check']['all']}"
                    if kind_part in ("fin", "shell") else "a catch plug has no biological counterpart"),
                rel("assembly_moment_balance", "governing" if p["id"] in m["nominal_assembly"]["parts"]
                    else "not_applicable", "part of the nominal assembly" if p["id"] in m["nominal_assembly"]["parts"]
                    else "an alternative trim key or plug, not in the nominal assembly")]
            if is_fin:
                fins = (dy or {}).get("fins", {}).get("pectoral" if base.startswith("pectoral") else "pelvic")
                if fins:
                    ok1, ok05 = fins["stress_pass_by_k_z"]["1.0"], fins["stress_pass_by_k_z"]["0.5"]
                    st = "pass" if ok1 and ok05 else ("unresolved" if ok1 else "fail")
                    checks.append(chk("euler_bernoulli_fin_root", st,
                                      f"claude-07 ({dy['path']} sha256 {dy['sha256'][:12]}..., not recomputed here): "
                                      f"worst bending {fins['worst_MPa']:.2f} MPa, in-plane root {fins['inplane_MPa']:.2f} "
                                      f"MPa against {fins['allowable_MPa']:.2f} MPa (UTS/3, declared); passes k_z 1: "
                                      f"{ok1}; passes the declared k_z 0.5 orientation case: {ok05}"))
                    law_relations.append(rel("euler_bernoulli_fin_root", "checked", "executed by claude-07 on this "
                                             "revision's bytes; read from its artifact"))
                else:
                    checks.append(chk("euler_bernoulli_fin_root", "unknown", "no beam run on this revision found"))
                    law_relations.append(rel("euler_bernoulli_fin_root", "inspired_only",
                                             "sections follow claude-07's R1/R2 requirements; not run on these bytes"))
                pair = meshes.get(p["id"].replace("_R", "_L", 1)) if base.endswith("_R") else None
                if pair is not None:
                    Vl = pair[0]
                    identical = vset(Vl) == vset(V)
                    mirror = vset(Vl * [1, 1, -1]) == vset(V)
                    det = float(np.linalg.det(np.asarray(p["print_to_fish_transform"])[:3, :3]))
                    st = "pass" if mirror and not identical and det > 0 else "fail"
                    checks.append(chk("chirality_mirror_pair", st,
                                      f"recomputed: vertex set identical to the _L file {identical}; equal to the _L "
                                      f"file mirrored in z {mirror}; print-to-fish det {det:+.0f}"))
                    law_relations.append(rel("chirality_mirror_pair", "checked", "recomputed here"))
                    if row["withdrawn"]:
                        checks.append(chk("print_status", "withdrawn", row["withdrawn"]))
            for lid in ("level_flight_lift", "drag_equation", "static_margin_hand_np", "launch_acceleration",
                        "ballast_lever", "catch_bond_shear"):
                law_relations.append(rel(lid, "not_applicable", "an assembly-level law; see assemblies[] for "
                                                                f"{revn}"))
            row.update(kind="stl_part", part_id=p["id"], checks=checks, law_relations=law_relations,
                       law_ids=[x["law_id"] for x in law_relations if x["relation"] != "not_applicable"],
                       mass_g=r(mp["mass_g"], 9), volume_mm3=r(mp["volume_mm3"], 6),
                       cg_mm_print_pose=[r(v, 4) for v in mp["cg_mm"]], conditional_mass_g_at_1220_kg_m3=None,
                       mass_basis=f"calculated: mesh volume x {density:g} kg/m3 (cured density, root's card); "
                                  "not weighed")
            files.append(row)
        zrow = bundle_row(d, mb, material, man_src)
        if zrow:
            files.append(zrow)
        assemblies.append(assembly(revn, d, m, meshes, density, dy, rev_checks.get(revn), zrow, rootchk.get(revn)))
    return files, assemblies


def bundle_row(d: str, mb: bytes, material: dict, man_src: dict) -> dict | None:
    side = ROOT / d / "download.json"
    if not side.exists():
        return None
    s = json.loads(side.read_text())
    zb = (ROOT / s["path"]).read_bytes()
    checks = [chk("sha256_pinned", "pass" if sha(zb) == s["sha256"] and len(zb) == s["bytes"] else "fail",
                  f"against {d}/download.json (sha256 and bytes)"),
              chk("manifest_pinned", "pass" if s["manifest_sha256"] == sha(mb) else "fail",
                  "download.json manifest_sha256 against the revision manifest")]
    z = zipfile.ZipFile(io.BytesIO(zb))
    bad = []
    for n in z.namelist():
        relp = n.split("/", 1)[1]
        if relp == "SHA256SUMS":
            continue
        src = ROOT / "artifacts/glider" / relp if relp in ("KNOWN_DEFECTS.json",) else ROOT / d / relp
        if not src.exists() or z.read(n) != src.read_bytes():
            bad.append(relp)
    sums = dict(line.split("  ")[::-1] for line in z.read(next(n for n in z.namelist()
                                                                 if n.endswith("/SHA256SUMS"))).decode().splitlines())
    sums_ok = all(sha(z.read(n)) == sums.get(n.split("/", 1)[1]) for n in z.namelist() if not n.endswith("SHA256SUMS"))
    checks.append(chk("members_equal_sources", "pass" if not bad else "fail",
                      f"{len(z.namelist())} members; differing from the repository files: {bad or 'none'}"))
    checks.append(chk("sha256sums", "pass" if sums_ok else "fail", "every member against the ZIP's SHA256SUMS"))
    checks.append(chk("assembly_md_cg_window", "unresolved",
                      "the frozen ASSEMBLY.md cites claude-07's v3a-planform 44-60 mm window and a 60 mm ballast row; "
                      "for r3/r4 claude-07 replaced it with 49.5-55.2 mm (target 52.4, never aft of 54.1). The ZIP "
                      "is not edited; see findings"))
    return {"path": s["path"], "sha256": sha(zb), "bytes": len(zb), "family": "glider",
            "revision": s["revision"], "kind": "zip_bundle", "part_id": None, "law_ids": [], "law_relations": [],
            "checks": checks, "mass_g": None, "volume_mm3": None, "cg_mm_print_pose": None,
            "conditional_mass_g_at_1220_kg_m3": None,
            "mass_basis": "a bundle; its STLs are listed individually", "material": material,
            "source_artifacts": [man_src, {"path": f"{d}/download.json", "sha256": sha(side.read_bytes()),
                                           "role": "sidecar (pins this ZIP)"}],
            "withdrawn": None, "introduced_in_commit": introduced_in(s["path"])}


def assembly(revn, d, m, meshes, density, dy, rv, zrow, rootc) -> dict:
    na = m["nominal_assembly"]
    props, parts_mass = [], {}
    for pid in na["parts"]:
        V, T, p = meshes[pid]
        Vf, Tf = transform_mesh(V, T, p["print_to_fish_transform"])
        q = MP.properties(Vf, Tf, density)
        props.append(q)
        parts_mass[pid] = r(q["mass_g"], 9)
    tot = MP.combine(props)
    M = tot["mass_g"]
    cg = tot["cg_mm"]
    th = m["trim_speed_hand"]
    S = th["paired_flat_area_mm2"]
    cap = RHO_AIR * V_BUDGET ** 2 * S * 1e-6 * CL / (2 * G) * 1e3
    rows = {row["cg_target_x_mm"]: row for row in m["ballast"]["rows"]}
    nom = rows[52.0]
    ballasted = nom["total_mass_g"]
    def vt(mg):
        return math.sqrt(2 * mg * 1e-3 * G / (RHO_AIR * S * 1e-6 * CL))
    np_b = m["hand_neutral_point"]["np_x_mm_bracket"]
    mac = m["hand_neutral_point"]["pectoral_mac_mm"]
    win = CG_WINDOWS["v3c" if "v3c" in m["source_candidate"]["id"] else "v3a"]
    launch = []
    for case in LAUNCH_CASES:
        a = case["v_m_s"] ** 2 / (2 * case["stroke_m"])
        launch.append({**case, "a_mean_m_s2": r(a, 3),
                       "peak_force_N_by_k": {f"{k:.4g}": r(ballasted * 1e-3 * a * k, 3) for k in (1.0, math.pi / 2, 2.0)}})
    checks = [
        chk("assembly_recombined", "pass" if abs(M - na["dry"]["mass_g"]) <= 1e-6 * M
            and np.allclose(cg, na["dry"]["cg_mm"], atol=1e-3) else "fail",
            f"recombined here from the nominal STL bytes: {M:.9f} g, CG {[round(x, 3) for x in cg]} mm. The frozen "
            f"manifest records {na['dry']['mass_g']:.9f} g (relative difference "
            f"{abs(M - na['dry']['mass_g']) / M:.1e}): it was computed from the float64 fish-frame meshes before "
            "export, and the flat-printed fins' rotated float32 STL coordinates hold slightly different volumes "
            "(parts with an identity print pose agree to 1e-10 g). The STL value is the one a printer receives"),
        chk("budget_legacy_10_5g", "fail" if ballasted > LEGACY_LIMIT_G else "pass",
            f"ballasted {ballasted:.3f} g (dry {M:.3f} g) against the frozen legacy 10.5 g threshold"),
        chk("budget_area_specific", "fail" if ballasted > cap else "pass",
            f"ballasted {ballasted:.3f} g (dry {M:.3f} g) against {cap:.3f} g on this revision's paired area"),
        chk("cg_dry_in_window", "fail" if not (win["window_mm"][0] <= cg[0] <= win["window_mm"][1]) else "pass",
            f"dry CG x {cg[0]:.2f} mm against {win['window_mm']} mm ({win['source']}); nose ballast required"),
        chk("static_stability_dry", "fail" if cg[0] > np_b[1] else ("unresolved" if cg[0] > np_b[0] else "pass"),
            f"dry CG x {cg[0]:.2f} mm against the hand NP bracket {[round(x, 2) for x in np_b]} mm: "
            + ("aft of the whole bracket, statically unstable dry under the hand NP" if cg[0] > np_b[1] else
               "inside the bracket")),
    ]
    xb = (M * cg[0] + nom["ballast_g"] * nom["fill_centroid_mm"][0]) / nom["total_mass_g"]
    checks.append(chk("ballast_row_moment_balance", "pass" if abs(xb - 52.0) <= 0.01
                      and abs(M + nom["ballast_g"] - nom["total_mass_g"]) <= 1e-6 * M else "fail",
                      f"52 mm row re-checked here: (M x_dry + m_b x_fill) / (M + m_b) = {xb:.4f} mm with "
                      f"m_b {nom['ballast_g']:.3f} g at x_fill {nom['fill_centroid_mm'][0]:.2f} mm"))
    if dy:
        checks.append(chk("catch_bond_shear", "pass" if dy["catch_pass"] else "fail",
                          f"claude-07 ({dy['path']}, not recomputed here): passes at k_z 1 and 0.5 "
                          f"{dy['catch_by_kz']}; design force {dy['catch_design_N']:.1f} N"))
        checks.append(chk("glide_simulation", "unresolved",
                          "claude-07's simulated scenarios (evidence_kind simulated_scenario): no physical flight; "
                          "ranges in the 5-8 m band rest on post-stall scenario coefficients, not trimmed glide "
                          f"({MSG}glider-dynamics-r3-r4-first-print-constraints.md for r3/r4; "
                          "glider-dynamics-to-launchable-fish-review.md for r1)"))
    if rootc:
        checks.append(chk("root_mass_recompute", "pass" if abs(rootc["mass_g"] - M) <= 1e-9 * M
                          and abs(rootc["cap_g"] - cap) <= 1e-9 * cap else "fail",
                          f"root ({rootc['path']} sha256 {rootc['sha256'][:12]}..., read here): dry "
                          f"{rootc['mass_g']:.9f} g and cap {rootc['cap_g']:.9f} g, against this index's {M:.9f} g "
                          f"and {cap:.9f} g"))
    if rv:
        checks.append(chk("reviewer_mass_recompute", "pass" if rv["rel"] <= 1e-6 else "fail",
                          f"reviewer claude-13 ({rv['path']} sha256 {rv['sha256'][:12]}..., read here): assembly "
                          f"{rv['mass_g']:.6f} g, relative difference to the manifest {rv['rel']:.1e}"))
    else:
        checks.append(chk("reviewer_mass_recompute", "unknown", "no reviewer recompute of this revision found"))
    if revn in ("r1-strong", "r1-light", "r2-light", "r3-daane"):
        launch_detail = ("not cleared: its _R print files are left parts (withdrawn); over both mass budgets; no "
                         "physical flight")
    else:
        launch_detail = ("not cleared: FIT/BALANCE test print only (root and reviewer claude-13); unresolved thin "
                         "feather edges at the x 20 catch slot; over both mass budgets; no physical flight")
    return {
        "id": f"{revn}/nominal", "revision": revn,
        "nominal_file_paths": [f"{d}/{meshes[pid][2]['stl']}" for pid in na["parts"]],
        "bundle_path": zrow["path"] if zrow else None,
        "parts_mass_g": parts_mass,
        "dry": {"mass_g": r(M, 9), "cg_mm": [r(x, 4) for x in cg],
                "basis": f"calculated: sum of part mesh volumes x {density:g} kg/m3, moved into the fish frame by each "
                         "part's print_to_fish transform; glue, tape and trapped resin excluded; not weighed"},
        "ballasted": {"target_cg_x_mm": 52.0, "ballast_g": r(nom["ballast_g"]), "total_mass_g": r(ballasted),
                      "basis": "the frozen manifest's 52 mm ballast row; shot at 4.7 g/cm3 ASSUMED; fill centroid "
                               "model; not weighed"},
        "budgets": [
            {"id": "legacy_threshold_10_5g", "value_g": LEGACY_LIMIT_G, "compared_mass_g": r(ballasted),
             "dry_mass_g": r(M), "dry_also_fails": M > LEGACY_LIMIT_G,
             "basis": "frozen legacy threshold: claude-07 section 0, V_trim <= 8 m/s at C_L 0.5 on v3a's 52.9 cm2. "
                      "Kept as recorded; it is not this revision's area derivation",
             "verdict": "fail" if ballasted > LEGACY_LIMIT_G else "pass"},
            {"id": "area_specific_8ms_cl05", "value_g": r(cap), "compared_mass_g": r(ballasted), "dry_mass_g": r(M),
             "dry_also_fails": M > cap,
             "basis": f"recomputed here: rho V^2 S C_L / (2 g) with rho {RHO_AIR}, V {V_BUDGET} m/s, C_L {CL} "
                      f"(assumed), g {G}, S {S:.1f} mm2 (this revision's paired flat area); "
                      + (f"the manifest records {th[CAP_KEY]:.6f} g" if CAP_KEY in th
                         else "the manifest predates this field"),
             "verdict": "fail" if ballasted > cap else "pass"}],
        "trim_speed_hand_m_s": {"dry": r(vt(M), 3), "ballasted": r(vt(ballasted), 3),
                                "basis": f"V = sqrt(2 m g / (rho S C_L)), C_L {CL} assumed; a hand number"},
        "cg_window": {**win, "dry_cg_x_mm": r(cg[0], 3)},
        "neutral_point": {"np_x_mm_bracket": [r(x, 3) for x in np_b], "pectoral_mac_mm": r(mac, 3),
                          "static_margin_dry": [r((x - cg[0]) / mac, 3) for x in np_b],
                          "static_margin_at_52mm": [r((x - 52.0) / mac, 3) for x in np_b],
                          "basis": "hand bracket from the frozen manifest; not a VLM"},
        "launch_load": launch,
        "launch_status": {"status": "not_cleared", "detail": launch_detail},
        "flight_status": "no physical print, weighing, glide or throw; only claude-07's simulated scenarios",
        "law_relations": [
            rel("assembly_moment_balance", "governing", "dry mass and CG recombined here"),
            rel("ballast_lever", "governing", "ballast rows from the frozen manifest; moment balance re-checked"),
            rel("level_flight_lift", "governing", "both budgets and the trim speeds; hand model with assumed C_L"),
            rel("static_margin_hand_np", "governing", "hand NP bracket from the manifest; static margin computed here"),
            rel("launch_acceleration", "governing", "peak band forces computed here for declared cases"),
            rel("drag_equation", "checked" if dy else "inspired_only",
                "executed only inside claude-07's simulated scenarios with assumed coefficients" if dy
                else "no run found"),
            rel("catch_bond_shear", "checked" if dy else "inspired_only", "claude-07's catch check"),
            rel("euler_bernoulli_fin_root", "checked" if dy else "inspired_only", "per fin file, claude-07")],
        "checks": checks}


# ---------------------------------------------------------------- external evidence
def external():
    dyn, dyn_ev = {}, []
    for revn, fname in DYNAMICS["files"].items():
        path = f"{DYNAMICS['dir']}/{fname}"
        d, h = git_json(DYNAMICS["commit"], path)
        c = d["checks"][revn]
        s = c["structure"]["heaviest_swept_ballast_plus_non_mesh"]
        f = s["fin"]["fins"]
        dyn[revn] = {"path": path, "sha256": h,
                     "fins": {k: {"stress_pass_by_k_z": f[k]["stress_pass_by_k_z"],
                                  "worst_MPa": f[k]["worst"]["sigma_max_Pa"] / 1e6,
                                  "inplane_MPa": f[k]["inplane_root"]["sigma_Pa"] / 1e6,
                                  "allowable_MPa": f[k]["allowable_Pa"] / 1e6} for k in ("pectoral", "pelvic")},
                     "catch_pass": s["catch"]["pass"], "catch_by_kz": s["catch"]["pass_by_k_z"],
                     "catch_design_N": s["catch"]["design_force_N"]}
        for what in ("mass properties recompute", "fin beam (heaviest swept ballast case)", "catch shear",
                     "hand_np", "simulated launch and glide scenarios"):
            dyn_ev.append({"by": "claude-07 (glider-dynamics)", "what": f"{revn}: {what}", "artifact_path": path,
                           "artifact_sha256": h, "commit": DYNAMICS["commit"], "recomputed_in_this_index": False})
    rev, rev_ev = {}, []
    for revn, fname in REVIEW["files"].items():
        path = f"{REVIEW['dir']}/{fname}"
        d, h = git_json(REVIEW["commit"], path)
        a = (d[revn].get("assembly") or d[revn]["assembly_dry"]) if revn in d else d["assembly"]
        mg = a.get("mass_g", a.get("dry_mass_g"))
        man = a.get("manifest_mass_g", mg)
        if mg is not None:
            rev[revn] = {"path": path, "sha256": h, "mass_g": mg, "rel": abs(mg - man) / man}
        for what in ("mass, CG and inertia recompute", "closed/oriented mesh check", "L/R pair check",
                     "independent wall sampling"):
            rev_ev.append({"by": "reviewer claude-13 (launchable-fish-review)", "what": f"{revn}: {what}",
                           "artifact_path": path, "artifact_sha256": h, "commit": REVIEW["commit"],
                           "recomputed_in_this_index": False})
    d, h = git_json(ROOT_RECEIPT["commit"], ROOT_RECEIPT["path"])
    rev_ev.append({"by": "root (codex03), own binary STL parser", "what": f"{ROOT_RECEIPT['revision']}: mass recompute "
                   "of the six-part set and the area-specific cap", "artifact_path": ROOT_RECEIPT["path"],
                   "artifact_sha256": h, "commit": ROOT_RECEIPT["commit"], "recomputed_in_this_index": False})
    rootchk = {ROOT_RECEIPT["revision"]: {"path": ROOT_RECEIPT["path"], "sha256": h, "mass_g": d["dry_mass_g"],
                                          "cap_g": d["scenario_mass_limit_g"]}}
    return dyn, dyn_ev, rev, rev_ev, rootchk


def findings(card) -> list:
    out = [
        {"id": "right_hand_print_files_are_left_parts", "status": "recorded_defect",
         "applies_to": ["artifacts/glider/" + rv + "/stl/*_R*.stl" for rv in
                        ("r1-strong", "r1-light", "r2-light", "r3-daane")],
         "detail": "Every _R print STL of r1-r3 holds the left part (det -1 export pose). Kept byte for byte; fixed "
                   "in r4-daane-printfix. Fish-frame mass properties, GLBs and flight models were not affected.",
         "source": "artifacts/glider/KNOWN_DEFECTS.json"},
        {"id": "body_thin_wall_near_forward_catch_slot", "status": "unresolved",
         "applies_to": ["artifacts/glider/r3-daane/stl/body.stl", "artifacts/glider/r4-daane-printfix/stl/body.stl",
                        "artifacts/glider/r2-light/stl/body.stl (likely, not re-measured)"],
         "detail": "Reviewer claude-13: readings down to 0.097 mm (0.115 mm twice on r3) at the x 20 slot's lateral "
                   "openings, judged feather edges rather than a thin wall; they can print rough, chip, or cut the "
                   "band. The builder's sampler classed its own 0.31 mm reading there as edge-limited and did not "
                   "gate it. r1's body has a reviewer reading of 0.317 mm aft of its catch slot, also edge-limited.",
         "source": "artifacts/glider/REVIEW_FINDINGS.json; " + REVIEW["doc"] + " @ " + REVIEW["commit"][:7]},
        {"id": "biological_constraints_kept_names_v3a", "status": "frozen_prose_inconsistency",
         "applies_to": ["artifacts/glider/r3-daane/manifest.json", "artifacts/glider/r4-daane-printfix/manifest.json"],
         "detail": "biological_constraints.kept reads 'v3a outline, ray count, ray roots, angles and lengths, fin "
                   "positions and dihedral', but source_candidate is fish3d-v3c-daane-length. The outline_check "
                   "itself compared against the v3c candidate's own rays.json (builder code), so the check result "
                   "refers to v3c; the prose string is stale. The frozen manifests are not edited; a later revision "
                   "will derive the string from the candidate.",
         "source": "engineering/glider/build.py (the 'kept' string is a literal; outline_check reads "
                   "artifacts/fish3d/<candidate>/rays.json)"},
        {"id": "assembly_md_cg_window_superseded", "status": "superseded_guidance",
         "applies_to": ["artifacts/glider/r4-daane-printfix/ASSEMBLY.md",
                        "artifacts/glider/r4-daane-printfix/print-set-r4-daane-printfix.zip"],
         "detail": "The frozen ASSEMBLY.md cites a 44-60 mm CG window and lists a 60 mm ballast row. That window "
                   "came from v3a's planform. For r3/r4 claude-07's constraint is CG x 49.5-55.2 mm, target 52.4, "
                   "never aft of 54.1 mm before the VLM NP, so the 56 and 60 mm rows are outside it.",
         "source": MSG + "glider-dynamics-r3-r4-first-print-constraints.md"},
        {"id": "legacy_mass_threshold", "status": "superseded_guidance",
         "applies_to": ["artifacts/glider/*/manifest.json (trim_speed_hand.mass_limit_g)"],
         "detail": "The frozen 10.5 g threshold was derived on v3a's 52.9 cm2 paired area. It is retained as a "
                   "legacy threshold; each assembly also carries its own area-specific cap, recomputed here. Every "
                   "revision fails both.",
         "source": "trim_speed_hand in each manifest"},
    ]
    return out


def build() -> tuple[dict, str]:
    card_all, card_sha = git_json(CARD["commit"], CARD["path"])
    assert card_sha == CARD["sha256"], "material card bytes changed"
    card = next(x for x in card_all["materials"] if x["id"] == CARD["id"])
    dyn, dyn_ev, rev, rev_ev, rootchk = external()
    defects = json.loads((GLIDER / "KNOWN_DEFECTS.json").read_text())
    rf = json.loads((GLIDER / "REVIEW_FINDINGS.json").read_text())
    pf, _ = prop_files(card)
    gf, asm = glider(card, dyn, rev, defects, rf, rootchk)
    idx = {"schema": "frontier.print-law-index/1",
           "generated_by": {"command": "python -m engineering.print_law_index", "code_paths": CODE_PATHS,
                            "code_sha256": code_sha()},
           "grounding_note": GROUNDING_NOTE, "vocabulary": VOCAB,
           "laws": laws(card, dyn_ev, rev_ev), "files": gf + pf, "assemblies": asm, "findings": findings(card)}
    text = json.dumps(idx, indent=1, sort_keys=False) + "\n"
    return idx, text


# ---------------------------------------------------------------- human-readable page
def doc(idx: dict) -> str:
    L = ["# Print law index: what each downloadable print file is grounded in, and what was checked",
         "",
         ("Generated by `python -m engineering.print_law_index` from `artifacts/print-law-index.json` (schema "
         "`frontier.print-law-index/1`, `artifacts/print-law-index.schema.json`). Do not edit by hand."),
         "",
         "**Read this first.** " + idx["grounding_note"],
         "",
         "## How the mass is calculated",
         ("- **Per part:** mesh volume (divergence theorem on the closed STL) × the cured density. Glider parts use "
         "Alpha Grey V1 at 1220 kg/m³, from root's material card; the card's 1110 kg/m³ liquid density is not used."),
         ("- **Per assembly:** the parts are moved into the fish frame by their recorded transforms and summed. The "
         "CG is the mass-weighted mean."),
         ("- **Ballast:** the dry assembly plus nose ballast from the frozen manifest's 52 mm row, at an assumed "
         "4.7 g/cm³."),
         ("- **Display props:** the resin is not chosen, so their mass is unknown. A conditional mass, assuming a "
         "fully dense print at 1220 kg/m³ (the Alpha Grey V1 card value), is given separately."),
         "- **Nothing was weighed.** Every figure here is calculated from a mesh.",
         "",
         "## Why every glider revision fails its mass budget",
         "There are two budgets. Each comes from the lift equation at 8 m/s with an assumed C_L of 0.5:",
         "- the frozen **legacy 10.5 g**, derived on v3a's 52.9 cm² of paired fin area, and kept as recorded;",
         "- the **area-specific cap**, recomputed here on each revision's own paired area.",
         "",
         "| revision | dry (calc.) | ballasted to CG x 52 | legacy 10.5 g | area cap | V_trim ballasted (hand) | dry CG x vs window | launch |",
         "|---|---|---|---|---|---|---|---|"]
    for a in idx["assemblies"]:
        b = {x["id"]: x for x in a["budgets"]}
        L.append(f"| `{a['revision']}` | {a['dry']['mass_g']:.2f} g | {a['ballasted']['total_mass_g']:.2f} g | "
                 f"{b['legacy_threshold_10_5g']['verdict'].upper()} | "
                 f"{b['area_specific_8ms_cl05']['value_g']:.2f} g, {b['area_specific_8ms_cl05']['verdict'].upper()} | "
                 f"{a['trim_speed_hand_m_s']['ballasted']:.1f} m/s | {a['dry']['cg_mm'][0]:.1f} vs "
                 f"{a['cg_window']['window_mm'][0]}-{a['cg_window']['window_mm'][1]} mm | "
                 f"{a['launch_status']['status'].replace('_', ' ')} |")
    body = [a["parts_mass_g"]["body"] for a in idx["assemblies"]]
    fins = [sum(v for k, v in a["parts_mass_g"].items() if k.startswith(("pectoral", "pelvic"))) for a in idx["assemblies"]]
    ball = [a["ballasted"]["ballast_g"] for a in idx["assemblies"]]
    L += ["",
          (f"- **Where the mass is.** The hollow body is {min(body):.2f}–{max(body):.2f} g. The four paired fins are "
          f"{min(fins):.2f}–{max(fins):.2f} g together."),
          ("- **Why there is ballast.** The dry CG sits behind the hand neutral-point bracket, so the fish is "
          f"statically unstable dry under that bracket. Nose ballast moves the CG forward, and it adds "
          f"{min(ball):.1f}–{max(ball):.1f} g."),
          ("- **What the budget means.** It is a hand trim budget, not a flight result. Passing it would not show that "
          "the fish glides; failing it says the fish would need a faster launch or a higher C_L than assumed."),
          "",
          "## Laws and rules",
          "| id | kind | relation to files | executed on these files by |",
          "|---|---|---|---|"]
    for law in idx["laws"]:
        by = sorted({e["by"].split(" (")[0] for e in law["evidence"]}) or ["**not executed**"]
        rels = sorted({x["relation"] for f in idx["files"] + idx["assemblies"] for x in f["law_relations"]
                       if x["law_id"] == law["id"]})
        L.append(f"| `{law['id']}` | {law['kind'].replace('_', ' ')} | {', '.join(rels) or '-'} | {', '.join(by)} |")
    L += ["", ("The relations are defined in the JSON's `vocabulary`. An assembly-level law is `not_applicable` on a "
              "single part; it appears on the assembly."), "",
          "## Findings (kept visible, not resolved)"]
    for f in idx["findings"]:
        L.append(f"- **{f['id']}** ({f['status'].replace('_', ' ')}): {f['detail']}")
    L += ["", "## Files", ("Status counts per file list each check's outcome. `withdrawn` marks a file that must not "
                          "be printed."), ""]
    fams = {}
    for f in idx["files"]:
        fams.setdefault((f["family"], f["revision"]), []).append(f)
    for (fam, revn), fs in fams.items():
        L += [f"### {fam} / {revn}", "", "| file | kind | sha256 | mass (calc.) | volume mm³ | not pass |",
              "|---|---|---|---|---|---|"]
        for f in fs:
            mass = (f"{f['mass_g']:.3f} g" if f["mass_g"] is not None else
                    (f"unknown ({f['conditional_mass_g_at_1220_kg_m3']:.2f} g if fully dense at 1220 kg/m³)"
                     if f.get("conditional_mass_g_at_1220_kg_m3") is not None else "-"))
            bad = [f"{c['id']}: {c['status']}" for c in f["checks"] if c["status"] != "pass"]
            vol = f"{f['volume_mm3']:.1f}" if f["volume_mm3"] is not None else "-"
            L.append(f"| `{Path(f['path']).name}` | {f['kind']} | `{f['sha256'][:12]}` | {mass} | {vol} | "
                     f"{'; '.join(bad) or 'none'} |")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the index or the page would change")
    a = ap.parse_args(argv)
    idx, text = build()
    page = doc(idx)
    if a.check:
        same = OUT.exists() and OUT.read_text() == text and DOC.exists() and DOC.read_text() == page
        print("up to date" if same else "STALE: re-run python -m engineering.print_law_index")
        return 0 if same else 1
    OUT.write_text(text)
    DOC.write_text(page)
    n = {k: sum(1 for f in idx["files"] if f["kind"] == k) for k in sorted({f["kind"] for f in idx["files"]})}
    print(f"wrote {OUT.relative_to(ROOT)} ({len(idx['files'])} files: {n}; {len(idx['assemblies'])} assemblies) "
          f"and {DOC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
