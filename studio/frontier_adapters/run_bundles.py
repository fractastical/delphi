"""Finished local runs (fish3d geometry, scale Erk-wave model, behavior CPG controller, lifecycle sources) -> PROPOSED Claim / Action / Evidence.

Same rules as `visual_assets` and `sim_bundles` (read their docstrings first); this module only adds the producers they did not cover.
Uses only kinds the deployed store has (Claim, Action, Evidence). There is no Equation or Model kind here and none is invented: the model
and its equations are named in the Action's `cache_key.model` and in the Claim's `context` / `assumptions`, with the file locators.

  * Every hash a producer states is recomputed from an immutable git blob. A mismatch refuses the chain.
  * Compute and render are different Actions; render Evidence is always `context_only`.
  * An Action exists only where a producer receipt supports one, and its title says what the receipt does and does not record.
    Lifecycle is a source assessment and has NO simulator Action on purpose.
  * Misses, failed gates and refusals stay in the record: the scale model's out-of-band rise time, the synchronous-pulse control that does
    not reproduce the measured impairment, and the behavior run's render.py hash that differs from the one its simulation arms embedded.
  * Nothing here is a calibration of any fish. Pointers are `urn:sha256` / `referenced`; no URL, no licence is asserted.

Reads git blobs only; never the working tree; never writes to a store (importing is `import_cli`'s job).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess

from . import engineering_manifest as em
from .common import sha_bytes
from .visual_assets import AssetChain, RENDER_NOTE, _action, _evidence, _prov

ADAPTER_ID = "frontier_adapters.run_bundles"
ADAPTER_VERSION = "0.1.0"
NOT_CALIBRATED = "Not calibrated to any fish. Nothing here is a whole-fish result."
SRC = "urn:frontier:adapter:run-bundles"
ACCEPT_REPLAY = "A clean re-execution from the pinned code reproduces the digests the receipt lists."
ACCEPT_REVIEW = "An independent reviewer checks the model against its cited sources before any number is used."


def _claim(c: AssetChain, id_: str, title: str, statement: str, context: str, assumptions: list[str], limitations: list[str],
           path: str, data: bytes, what: str, *, origin: str = "derived") -> dict:
    return c.add(c.draft("Claim", id_, {
        "title": title, "statement": statement, "context": context, "assumptions": assumptions, "limitations": limitations,
        "source": em._source(c, path, data, what), "source_record_version": None,
        "prior_review": {"status": "none: not reviewed by anyone"}, "origin": origin}, SRC))


def _tree_py(repo: str, commit: str, directory: str) -> list[str]:
    r = subprocess.run(["git", "-C", repo, "ls-tree", "--name-only", f"{commit}:{directory}"], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise em.Refused(f"cannot list {directory} at {commit[:12]}: {r.stderr.strip()[:100]}")
    return sorted(n for n in r.stdout.split() if n.endswith(".py"))


# ---------------------------------------------------------------------------------------------------------------------------- fish3d
F3 = "artifacts/fish3d/fish3d-N1-cypselurus-baseline"
F3_CODE = "engineering/fish3d"


def fish3d_code_hash(c: AssetChain) -> str:
    """The producer's `code_hash()` (engineering/fish3d/build.py:85): sorted *.py as name+bytes, then three geometry modules."""
    h = hashlib.sha256()
    for n in _tree_py(c.repo, c.commit, F3_CODE):
        h.update(n.encode() + c.blob(f"{F3_CODE}/{n}"))
    for n in ("forms.py", "mesh.py", "sources.py"):
        h.update(n.encode() + c.blob(f"engineering/geometry/{n}"))
    return h.hexdigest()


def fish3d_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "fish3d")
    build = c.jblob(f"{F3}/build.json")
    c.check("build.schema", build.get("schema") == "frontier.fish3d.build/1" and build.get("all_closed") is True, f"schema {build.get('schema')!r} all_closed {build.get('all_closed')!r}")
    blobs = {rel: c.same_hash(f"file.{rel}", f"{F3}/{rel}", h) for rel, h in build["files"].items()}
    cand_b = c.same_hash("candidate", f"{F3}/candidate.json", build["candidate_sha256"])
    code_h = fish3d_code_hash(c)
    c.check("code.build_hash", code_h == build["code_sha256"], f"producer states {build['code_sha256'][:16]}..., recomputed from the pinned tree {code_h[:16]}...")
    rr = c.jblob(f"{F3}/render/render.json")
    c.check("render.schema", rr.get("schema") == "frontier.fish3d.render/1" and all(rr["checks"].values()), f"schema {rr.get('schema')!r} checks {rr.get('checks')}")
    c.check("render.same_candidate", rr["candidate_sha256"] == build["candidate_sha256"] and rr["build_code_sha256"] == build["code_sha256"] and rr["glb_sha256"] == build["files"]["fish.glb"],
            "render receipt names the same candidate, build code and glb as the build receipt")
    media = {k: c.same_hash(f"render.{k}", f"{F3}/render/{rr[k]['file']}", rr[k]["sha256"]) for k in ("still", "video", "gif")}
    media["poster"] = c.same_hash("render.poster", f"{F3}/render/{rr['poster']}", rr["poster_sha256"])
    present = c.blob(f"{F3_CODE}/present.py")
    blender_py = c.blob(f"{F3_CODE}/blender_render.py")
    ph = hashlib.sha256(present + blender_py).hexdigest()       # the producer's present.code_hash(): present.py then blender_render.py
    c.check("code.present", ph == rr["present_code_sha256"], f"producer states {rr['present_code_sha256'][:16]}..., recomputed (present.py+blender_render.py) {ph[:16]}...")
    render_b = c.blob(f"{F3}/render/render.json")
    cand = json.loads(cand_b)
    bio = cand["biology"]
    chk = build["checks"]
    parts = sorted(chk)
    tri = sum(v.get("triangles", 0) for v in chk.values())
    kinds = sorted({v["kind"] for v in bio.values() if isinstance(v, dict) and "kind" in v})
    assumed = sorted(k for k, v in bio.items() if isinstance(v, dict) and v.get("kind") == "design_assumption")
    caption = list(rr["caption"])
    lim = [em.IMPORT_NOTE, NOT_CALIBRATED, "An engineered 3D form sized from stated fits (Fish 1990, Daane 2021 S1A, the NCA comparison set); fin thickness, eyes and gill covers are assumed.",
           "The scale lattice is assumed (not a grown or measured pattern).", "Mesh checks are geometric (closed two-manifold, orientation); they say nothing about aerodynamics or biology."] + [f"Producer states it does not claim: {x}" for x in rr["not_claimed"]]
    if assumed:
        lim.append("Candidate parameters the producer labels design_assumption: " + ", ".join(assumed) + ".")
    asm = [f"Candidate fish3d-N1 (candidate.json sha256 {build['candidate_sha256'][:16]}...); parameter kinds in candidate.json: {', '.join(kinds)}.", *caption[1:2]]
    claim = _claim(c, "run-fish3d-claim-candidate-geometry", "fish3d-N1: a constructed 3D flying-fish form of 14 closed components at biological scale",
                   f"The producer's build produced {len(parts)} mesh pieces ({', '.join(parts)}) with {tri} triangles in all, and its checks report every piece closed, two-manifold and consistently oriented "
                   f"(all_closed {build['all_closed']}); candidate parameters are in candidate.json. {caption[0]}",
                   "A geometric construction, not a measurement and not a simulation of physics. The producer's caption: " + " ".join(caption), asm, lim, f"{F3}/build.json", c.blob(f"{F3}/build.json"),
                   "Build receipt: per-component mesh checks and the sha256 of every output file.")
    act = _action(c, SRC, "run-fish3d-action-build", claim,
                  "Imported record of a producer-reported build (NOT executed by Frontier): candidate mesh construction; the receipt carries hashes and library versions but NO exit code and NO elapsed time",
                  [ACCEPT_REPLAY, "An independent reviewer checks the sizing fits and the assumed parameters."], ["python3 with numpy, trimesh, manifold3d"],
                  dict(input=f"candidate.json sha256 {build['candidate_sha256']}", code=f"git:{em.REPO_LABEL}@{commit}; producer code hash {build['code_sha256'][:16]} (recomputed here)",
                       model="fish3d parametric construction (deterministic geometry; no language model)", environment=f"libraries {json.dumps(build['libraries'], sort_keys=True)}; interpreter NOT RECORDED",
                       parameters=f"candidate.json; fin layout and sizing kinds {', '.join(kinds)}", scope="engineered geometry; not an organism or a physics result"), [])
    arts = ([c.artifact("geometry", f"{F3}/fish.glb", blobs["fish.glb"], "assembled candidate mesh"), c.artifact("input", f"{F3}/candidate.json", cand_b, "candidate parameters with per-field provenance kind"),
             c.artifact("log", f"{F3}/build.json", c.blob(f"{F3}/build.json"), "build receipt: per-component checks and file hashes"), c.artifact("code", f"{F3_CODE}/build.py", c.blob(f"{F3_CODE}/build.py"))]
            + [c.artifact("geometry", f"{F3}/components/{n}.stl", blobs[f"components/{n}.stl"]) for n in ("body", "pectoral_L", "pectoral_R", "pelvic_L", "pelvic_R", "caudal", "dorsal")])
    ev = _evidence(c, SRC, "run-fish3d-evidence-build", claim, kind="simulated", relation="unspecified", produced_by=act,
                   source=em._source(c, f"{F3}/build.json", c.blob(f"{F3}/build.json"), "Build receipt."),
                   method="Producer's deterministic mesh construction and geometric checks. No evidence_kind value names a constructed geometry, so 'simulated' is the closest: a computed construct, not an observation.",
                   context="Applicability: this candidate only. " + em.IMPORT_NOTE, assumptions=asm,
                   provenance=_prov(c, libraries=build["libraries"], files_hashed=len(build["files"]), code_hash_recomputed=True, candidate_sha256=build["candidate_sha256"]), limitations=lim, artifacts=arts,
                   uncertainty="None quantified: parameters are fits, figure reads and assumptions (see candidate.json kinds).")
    ract = _action(c, SRC, "run-fish3d-action-render", claim,
                   "Imported record of a producer-reported render (NOT executed by Frontier): Blender Cycles path-traced still, turntable and poster from fish.glb",
                   ["Re-rendering fish.glb with the pinned present.py and Blender 4.2.3 reproduces the frames; mp4 and gif bytes can differ across builds.", "Pictures are read as views of a mesh, not as evidence."], ["Blender 4.2.3 LTS; ffmpeg"],
                   dict(input=f"build evidence version {ev['version']}; glb sha256 {rr['glb_sha256'][:16]}", code=f"git:{em.REPO_LABEL}@{commit}; present.py+blender_render.py {rr['present_code_sha256'][:12]}", model="none: path-traced rendering",
                        environment=f"Blender {rr['blender']['still']['blender']}", parameters=f"still 1 frame; turntable {rr['blender']['turntable']['frames']} frames at {rr['video']['fps']} fps", scope="visualisation of a constructed mesh"), [ev])
    _evidence(c, SRC, "run-fish3d-evidence-render", claim, kind="simulated", relation="context_only", produced_by=ract,
              source=em._source(c, f"{F3}/render/render.json", render_b, "Render receipt."),
              method="Producer's Blender 4.2.3 Cycles path-traced render of fish.glb; its own evidence_kind line: " + rr["evidence_kind"] + ".", context=RENDER_NOTE + " " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, blender=rr["blender"]["still"]["blender"], video={k: rr["video"][k] for k in ("codec", "fps", "n_frames", "width", "height")}, render_checks=rr["checks"]),
              limitations=[em.IMPORT_NOTE, RENDER_NOTE, NOT_CALIBRATED],
              artifacts=[c.artifact("output", f"{F3}/render/{rr[k]['file']}", media[k], d) for k, d in (("video", "turntable video"), ("still", "still image"), ("gif", "turntable gif"))]
              + [c.artifact("output", f"{F3}/render/poster.png", media["poster"], "poster"), c.artifact("log", f"{F3}/render/render.json", render_b, "render receipt"), c.artifact("code", f"{F3_CODE}/present.py", present),
                                                                                                            c.artifact("code", f"{F3_CODE}/blender_render.py", blender_py)])
    return c


# ----------------------------------------------------------------------------------------------------------------------------- scales
SC = "artifacts/scales/erk-wave"
SC_CODE = "engineering/scales"


def scales_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "scales")
    rc = c.jblob(f"{SC}/receipt.json")
    c.check("receipt.schema", rc.get("schema") == "frontier.scales.receipt/1" and rc.get("controls_pass") is True, f"schema {rc.get('schema')!r} controls_pass {rc.get('controls_pass')!r}")
    blobs = {n: c.same_hash(f"file.{n}", f"{SC}/{n}", m["sha256"]) for n, m in rc["files"].items()}
    for n, m in rc["files"].items():
        c.check(f"size.{n}", len(blobs[n]) == m["bytes"], f"{n}: receipt {m['bytes']} bytes, blob {len(blobs[n])}")
    h = hashlib.sha256()
    code = {n: c.blob(f"{SC_CODE}/{n}") for n in ("erk_wave.py", "run.py", "render.py")}
    for n in ("erk_wave.py", "run.py", "render.py"):
        h.update(code[n])
    c.check("code.hash", h.hexdigest() == rc["code_sha256"], f"producer states {rc['code_sha256'][:16]}..., recomputed (erk_wave.py+run.py+render.py) {h.hexdigest()[:16]}...")
    c.check("media.same_files", rc["media"]["video"]["sha256"] == rc["files"]["erk_growth.mp4"]["sha256"] and rc["media"]["gif"]["sha256"] == rc["files"]["erk_growth.gif"]["sha256"]
            and rc["media"]["poster_sha256"] == rc["files"]["poster.png"]["sha256"], "media block hashes equal the files block")
    src_b = c.blob(f"{SC_CODE}/sources.json")
    rcb = c.blob(f"{SC}/receipt.json")
    s, ru, cmp_ = rc["summary"], rc["run"], rc["measured_comparison"]
    ctl = rc["controls"]
    misses = rc["measured_comparison_misses"]
    c.check("misses.consistent", (not rc["measured_comparison_all_in_band"]) == bool(misses) and set(misses) == {k for k, v in cmp_.items() if not v["in_band"]}, f"misses {misses}")
    sync = ctl["synchronous"]
    cites = "; ".join(x["citation"][:140] for x in rc["sources"])
    asm = [f"Model: {rc['model']}. Cited sources: {cites}.", f"Run: {json.dumps(ru['params'], sort_keys=True)}, geometry {json.dumps(ru['geometry'], sort_keys=True)}, {ru['hours']} h, mode {ru['mode']}.",
           f"Growth coupling is ASSUMED: {rc['growth_coupling']['assumed']['form']}. {rc['growth_coupling']['assumed']['note']}. Measured slope it was set from: {rc['growth_coupling']['measured']['quantity']} = {rc['growth_coupling']['measured']['value_per_h']} per h (+-{rc['growth_coupling']['measured']['ci68_per_h']}), {rc['growth_coupling']['measured']['n']}."]
    lim = [em.IMPORT_NOTE, NOT_CALIBRATED] + [f"Producer states it does not claim: {x}" for x in rc["not_claimed"]]
    wave = c.add(c.draft("Claim", "run-scales-claim-erk-wave-growth", {
        "title": "Zebrafish regenerating-scale Erk trigger-wave model with wave-gated growth, one 520 um scale, standard run",
        "statement": (f"In the producer's reaction-diffusion model with the Hayden 2021 Table 1 parameters, a source at {ru['geometry']['source_offset_um']} um from the centre produces peaks every {cmp_['source_period_h']['simulated']} h, "
                      f"a wave speed of {s['wave_speed']['speed_um_per_h']:.2f} um/h, a front FWHM of {s['front_fwhm_um_median']} um, and reaches {s['cells_reached_fraction']*100:.0f}% of cells; with the ASSUMED growth law the disc area goes from {s['area_initial_um2']:.0f} to {s['area_final_um2']:.0f} um^2 (ratio {s['area_ratio']:.3f})."),
        "context": "A deterministic model outcome on a zebrafish regenerating scale, with the model's own measured-value bands from the cited papers. " + asm[0],
        "assumptions": asm, "limitations": lim, "source": em._source(c, f"{SC}/receipt.json", rcb, "Run receipt: parameters, summary, controls and the measured-value comparison."),
        "source_record_version": None, "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "derived"}, SRC))
    act = _action(c, SRC, "run-scales-action-sim", wave,
                  f"Imported record of a producer-reported run (NOT executed by Frontier): Erk wave model, wall time {rc['wall_s']} s reported; the receipt carries NO exit code",
                  [ACCEPT_REPLAY, ACCEPT_REVIEW], ["python3 with numpy"],
                  dict(input=f"run parameters in receipt.json sha256 {sha_bytes(rcb)[:16]}", code=f"git:{em.REPO_LABEL}@{commit}; producer code hash {rc['code_sha256'][:16]} (recomputed here)",
                       model=f"{rc['model']} (finite-difference reaction-diffusion; no language model)", environment="NOT RECORDED by the producer (interpreter, numpy version)",
                       parameters=json.dumps(ru["params"], sort_keys=True), scope="simulated; zebrafish regenerating scale, not a flying fish"), [])
    ctl_txt = "; ".join(f"{k}: pass {v.get('pass')}" for k, v in ctl.items())
    ev = _evidence(c, SRC, "run-scales-evidence-sim", wave, kind="simulated", relation="unspecified", produced_by=act, source=em._source(c, f"{SC}/receipt.json", rcb, "Run receipt."),
                   method=f"Finite-difference solve of the cited reaction-diffusion model; controls ({ctl_txt}); wall time {rc['wall_s']} s.",
                   context="Applicability: this model, these parameters. " + em.IMPORT_NOTE, assumptions=asm,
                   provenance=_prov(c, code_hash_recomputed=True, controls_pass=rc["controls_pass"], states_sha256=rc["files"]["states.npz"]["sha256"], wall_s=rc["wall_s"]), limitations=lim,
                   artifacts=[c.artifact("output", f"{SC}/states.npz", blobs["states.npz"], "saved model states (hourly)"), c.artifact("log", f"{SC}/receipt.json", rcb, "run receipt with controls"),
                              c.artifact("input", f"{SC_CODE}/sources.json", src_b, "cited sources"), c.artifact("code", f"{SC_CODE}/erk_wave.py", code["erk_wave.py"]), c.artifact("code", f"{SC_CODE}/run.py", code["run.py"])],
                   uncertainty="Deterministic run; numerical step screen only (dt halved changes speed by "
                               f"{ctl['step_halved']['speed_rel']:.2g} relative). No parameter or biological uncertainty.")
    # second claim: the comparison, including the miss and the control that did not reproduce the measurement
    rows = "; ".join(f"{k}: simulated {v['simulated']:.4g} vs band {v['band'][0]}-{v['band'][1]} ({'in' if v['in_band'] else 'OUT of'} band)" for k, v in sorted(cmp_.items()))
    cl2 = c.add(c.draft("Claim", "run-scales-claim-measured-comparison", {
        "title": "Erk-wave model against the measured values its authors cite: one of six outside its band, and the synchronous-pulse control does not reproduce the measured impairment",
        "statement": (f"Against the measured values the producer cites, the model's six quantities are: {rows}. The producer's synchronous-pulse control (daily tissue-wide activation) gives area ratio {sync['area_ratio']:.3f} against {sync['standard_area_ratio']:.3f} "
                      f"for the wave, and reproduces_measured_impairment is {sync['reproduces_measured_impairment']}."),
        "context": "The miss and the non-reproduction are reported as the producer wrote them; neither was tuned away. " + sync["note"],
        "assumptions": asm, "limitations": lim + [f"Out-of-band quantity (producer's measured_comparison_misses): {', '.join(misses)}.", "The growth law cannot tell a wave from a synchronous pulse at equal peak count, so the area outcome does not discriminate the two."],
        "source": em._source(c, f"{SC}/receipt.json", rcb, "measured_comparison and controls.synchronous blocks."), "source_record_version": None, "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "derived"}, SRC))
    act2 = _action(c, SRC, "run-scales-action-compare", cl2,
                   "Imported record of a producer-reported comparison (NOT executed by Frontier): model summary against cited measured bands and the synchronous-pulse control",
                   [ACCEPT_REPLAY, "A reviewer re-reads each band against the cited paper's own wording."], ["python3 with numpy"],
                   dict(input=f"bands and controls in receipt.json sha256 {sha_bytes(rcb)[:16]}", code=f"git:{em.REPO_LABEL}@{commit}; producer code hash {rc['code_sha256'][:16]}", model=f"{rc['model']} (no language model)",
                        environment="NOT RECORDED by the producer", parameters=json.dumps(ru["params"], sort_keys=True), scope="comparison with quoted measured values; bands are the producer's reading"), [ev])
    _evidence(c, SRC, "run-scales-evidence-compare", cl2, kind="simulated", relation="unspecified", produced_by=act2, source=em._source(c, f"{SC}/receipt.json", rcb, "Run receipt."),
              method="Producer's in-band test of six simulated quantities against bands it reads from the cited papers, plus the synchronous control.", context="Applicability: this model against this reading of the papers. " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, all_in_band=rc["measured_comparison_all_in_band"], misses=misses, synchronous_reproduces_impairment=sync["reproduces_measured_impairment"]),
              limitations=lim + [f"Out-of-band: {', '.join(misses)}.", "The bands are the producer's reading of the quoted text; no one else has checked them."],
              artifacts=[c.artifact("log", f"{SC}/receipt.json", rcb, "receipt with measured_comparison and controls")])
    ract = _action(c, SRC, "run-scales-action-render", wave, "Imported record of a producer-reported render (NOT executed by Frontier): Erk activity video, gif and poster from the saved states",
                   ["Re-rendering states.npz with the pinned render.py reproduces the frames; mp4 bytes can differ across ffmpeg builds.", "Pictures are read as views of computed states, not as evidence."], ["python3 with matplotlib; ffmpeg"],
                   dict(input=f"simulation evidence version {ev['version']}; states.npz {rc['files']['states.npz']['sha256'][:16]}", code=f"git:{em.REPO_LABEL}@{commit}; render.py {sha_bytes(code['render.py'])[:12]}", model="none: deterministic rendering",
                        environment="NOT RECORDED by the producer", parameters=f"{rc['media']['video']['n_frames']} frames at {rc['media']['video']['fps']} fps", scope="visualisation of a simulated model"), [ev])
    _evidence(c, SRC, "run-scales-evidence-render", wave, kind="simulated", relation="context_only", produced_by=ract, source=em._source(c, f"{SC}/receipt.json", rcb, "Run receipt (media block)."),
              method="Producer renders hourly saved states to video, gif and poster. Caption: " + " ".join(rc["media"]["caption"]), context=RENDER_NOTE + " " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, media_checks=rc["media"]["checks"], settings_keys=sorted(rc["media"]["settings"])), limitations=[em.IMPORT_NOTE, RENDER_NOTE, NOT_CALIBRATED],
              artifacts=[c.artifact("output", f"{SC}/{n}", blobs[n], d) for n, d in (("erk_growth.mp4", "video"), ("erk_growth.gif", "gif"), ("poster.png", "poster"))]
              + [c.artifact("log", f"{SC}/receipt.json", rcb, "run receipt (media block)"), c.artifact("code", f"{SC_CODE}/render.py", code["render.py"])])
    return c


# --------------------------------------------------------------------------------------------------------------------------- behavior
BH = "artifacts/behavior"
BH_CODE = "engineering/behavior"
ARMS = ("baseline", "changed_frequency", "feedback_removed", "coupling_removed", "feedback_sign_mutant")


def behavior_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "behavior")
    man = c.jblob(f"{BH}/manifest.json")
    c.check("manifest.schema", man.get("schema") == "frontier.behavior.manifest/1" and man.get("status") == "completed" and man.get("exit_status") == 0,
            f"schema {man.get('schema')!r} status {man.get('status')!r} exit {man.get('exit_status')!r}")
    blobs = {n: c.same_hash(f"file.{n}", f"{BH}/{n}", m["sha256"]) for n, m in man["files"].items() if n != "manifest.json"}
    for n, m in man["files"].items():
        if n in blobs:
            c.check(f"size.{n}", len(blobs[n]) == m["byte_size"], f"{n}: manifest {m['byte_size']} bytes, blob {len(blobs[n])}")
    code = {n: c.same_hash(f"code.{n}", f"{BH_CODE}/{n}", h) for n, h in man["code_sha256"].items()}
    manifest_b = c.blob(f"{BH}/manifest.json")
    ctl = json.loads(blobs["controls.json"])
    c.check("controls.passed", ctl.get("passed") is True and all(x["passed"] for x in ctl["checks"]), f"controls passed {ctl.get('passed')!r}, {sum(1 for x in ctl['checks'] if x['passed'])}/{len(ctl['checks'])} checks")
    rr = json.loads(blobs["render_receipt.json"])
    c.check("render.receipt", rr["kind"] == "render" and rr["render_code_sha256"] == man["code_sha256"]["render.py"], "render receipt names the manifest's render.py hash")
    for k, h in rr["input_hashes"].items():
        c.check(f"render.input.{k}", sha_bytes(blobs[k]) == h, f"render receipt input {k}")
    arms = {a: json.loads(blobs[f"{a}.json"]) for a in ARMS}
    for a, d in arms.items():
        sa = d["simulationAction"]
        c.check(f"arm.{a}", d["status"] == "simulated" and sa["input_sha256"] and sa["state_sha256"], f"arm {a} status {d['status']!r}")
    # the per-arm simulationAction embeds the code hashes at simulation time; render.py is the one that differs from the final manifest
    sim_render = {a: d["simulationAction"]["code_sha256"]["render.py"] for a, d in arms.items()}
    drift = sorted({h for h in sim_render.values() if h != man["code_sha256"]["render.py"]})
    non_render_same = all(d["simulationAction"]["code_sha256"][n] == man["code_sha256"][n] for d in arms.values() for n in man["code_sha256"] if n != "render.py")
    c.check("code.nonrender_uniform", non_render_same, "every arm embeds the manifest's hash for model.py, run.py, protocol.json, sources.json, __init__.py")
    src = json.loads(blobs["sources.json"])
    prob = json.loads(blobs["problems.json"])
    b = arms["baseline"]
    rq = b["request"]
    sources = f"Oscillator: {src['oscillator']['title']} (DOI {src['oscillator']['doi']}; {src['oscillator']['organism_context']}). Zebrafish context: DOI {src['zebrafish_context']['doi']}, {src['zebrafish_context']['accession']}. {src['transfer']}"
    lim = [em.IMPORT_NOTE, NOT_CALIBRATED, f"Biological accuracy per the producer: {man['biological_accuracy']}.", f"Controls cover: {ctl['scope']}."] + list(b["limitations"])
    if drift:
        lim.append(f"Provenance wrinkle kept as found: the five simulation arms embed render.py hash {drift[0][:16]}..., while the final manifest and render receipt state {man['code_sha256']['render.py'][:16]}...; "
                   "render.py is not an input to the simulation (the other five code hashes are identical in every arm), so the simulation is unaffected, but render.py changed between the runs and the render.")
    asm = [sources, f"Baseline request: {json.dumps(rq, sort_keys=True)}.", f"Interface (not a calibrated mapping): {json.loads(blobs['interface.json'])['membership']}."]
    mt = b["metrics"]
    base = _claim(c, "run-behavior-claim-cpg-baseline", "Reduced phase-CPG joint controller: baseline tracking and phase recovery under declared values",
                  (f"In the producer's phase-oscillator controller with an independent joint servo ({rq['frequency_Hz']} Hz, amplitude {rq['amplitude_rad']} rad, feedback on, coupling {rq['coupling_s']} per s, dt {rq['dt_s']} s, {rq['duration_s']} s), "
                   f"the relative tracking RMS after 0.5 s is {mt['tracking_relative_rms_after_0_5s']:.4f}, the final-0.3-s phase-error RMS is {mt['phase_error_rms_final_0_3s_rad']:.2e} rad, "
                   f"the peak joint angle is {mt['peak_abs_angle_rad']:.4f} rad (outside the proposed static angle envelope: {mt['outside_proposed_static_angle_envelope']}) and torque saturates in {mt['sampled_torque_saturation_fraction']*100:.3f}% of samples."),
                  "A designed controller's numerical behavior, not a zebrafish circuit and not swimming. " + sources, asm, lim, f"{BH}/baseline.json", blobs["baseline.json"], "Baseline arm: actual saved joint states and metrics.")
    ctlc = _claim(c, "run-behavior-claim-controls-discriminate", "Behavior controller controls: removing feedback or coupling, or flipping the feedback sign, is detected by the frozen predicates",
                  ("The producer's frozen predicates pass on all {n} checks ({names}); they are: feedback-removed tracking error is {fr:.1f}x the baseline, coupling-removed phase error is {cr:.3g}x the baseline, the feedback-sign mutant is rejected (relative tracking RMS {mt:.1f}), "
                   "and halving the time step moves the angle by at most {dt:.2g} rad.").format(
                      n=len(ctl["checks"]), names=", ".join(x["name"] for x in ctl["checks"]),
                      fr=next(x["ratio"] for x in ctl["checks"] if x["name"] == "feedback_removed_discriminates"), cr=next(x["ratio"] for x in ctl["checks"] if x["name"] == "coupling_removed_discriminates"),
                      mt=arms["feedback_sign_mutant"]["metrics"]["tracking_relative_rms_after_0_5s"], dt=next(x["max_angle_difference_rad"] for x in ctl["checks"] if x["name"] == "time_step_halving")),
                  "An implementation-sensitivity control. It shows these predicates can fail, not that the controller matches any animal. " + ctl["scope"], asm, lim, f"{BH}/controls.json", blobs["controls.json"], "Frozen control predicates and their values.")
    cache_code = f"git:{em.REPO_LABEL}@{commit}; " + ", ".join(f"{k}:{v[:12]}" for k, v in sorted(man["code_sha256"].items()))
    env = man["environment"]
    ev_arm: dict[str, dict] = {}
    for a in ARMS:
        d = arms[a]
        sa = d["simulationAction"]
        tgt = base if a == "baseline" else ctlc
        act = _action(c, SRC, f"run-behavior-action-sim-{a.replace('_', '-')}", tgt,
                      f"Imported record of a producer-reported run (not re-run by Frontier): {sa['method']}, arm {a}; manifest records command, exit status {man['exit_status']} and elapsed {sa['elapsed_s']:.1f} s",
                      [ACCEPT_REPLAY, ACCEPT_REVIEW], ["python3 with numpy"],
                      dict(input=f"request sha256 {sa['input_sha256']}; arm {a}", code=cache_code, model=f"{d['model_id']} (phase oscillator + joint servo; no language model)",
                           environment=f"python {env['python']}, numpy {env['numpy']}, threads {json.dumps(env['threads'], sort_keys=True)}", parameters=json.dumps(d["request"], sort_keys=True), scope="simulated controller; not a fish"), [])
        arts = [c.artifact("output", f"{BH}/{a}.json", blobs[f"{a}.json"], f"arm {a}: actual saved joint states"), c.artifact("log", f"{BH}/manifest.json", manifest_b, "manifest: command, exit status, environment, hashes of every file"),
                c.artifact("protocol", f"{BH}/protocol.json", blobs["protocol.json"]), c.artifact("code", f"{BH_CODE}/model.py", code["model.py"]), c.artifact("code", f"{BH_CODE}/run.py", code["run.py"])]
        if a == "baseline":
            arts += [c.artifact("certificate", f"{BH}/controls.json", blobs["controls.json"], "frozen control predicates"), c.artifact("input", f"{BH}/sources.json", blobs["sources.json"], "cited sources")]
        ev_arm[a] = _evidence(c, SRC, f"run-behavior-evidence-sim-{a.replace('_', '-')}", tgt, kind="simulated", relation="unspecified", produced_by=act,
                              source=em._source(c, f"{BH}/{a}.json", blobs[f"{a}.json"], "Arm result with metrics."), method=f"{sa['method']}; arm {a}; metrics {json.dumps(d['metrics'], sort_keys=True)}.",
                              context="Applicability: this controller with these assumed values. " + em.IMPORT_NOTE, assumptions=asm,
                              provenance=_prov(c, elapsed_s=sa["elapsed_s"], state_sha256=sa["state_sha256"], command_recorded=True, exit_status=man["exit_status"], timestamp_seattle=man["timestamp_seattle"], render_py_hash_in_arm=sim_render[a][:16]),
                              limitations=lim, artifacts=arts, uncertainty="Deterministic runs; time-step halving control only. No parameter or biological uncertainty.")
    ract = _action(c, SRC, "run-behavior-action-render", base, "Imported record of a producer-reported render (not re-run by Frontier): video and poster from actual saved joint states drawn as a normalized kinematic glyph",
                   ["Re-rendering from the pinned render.py and the three input arms reproduces the frames; mp4 bytes can differ across ffmpeg builds.", "The glyph is a view of computed states, not of fish motion."], ["python3 with matplotlib; ffmpeg"],
                   dict(input="simulation evidence versions " + ", ".join(ev_arm[a]["version"][:20] for a in ("baseline", "feedback_removed", "coupling_removed")), code=f"git:{em.REPO_LABEL}@{commit}; render.py {man['code_sha256']['render.py'][:12]}",
                        model="none: deterministic rendering", environment=f"ffmpeg command recorded; frames {rr['frames']} at {rr['fps']} fps", parameters=f"model window {rr['model_window_s']} s, time interpolation {rr['time_interpolation']}", scope=rr["scope"]),
                   [ev_arm["baseline"], ev_arm["feedback_removed"], ev_arm["coupling_removed"]])
    _evidence(c, SRC, "run-behavior-evidence-render", base, kind="simulated", relation="context_only", produced_by=ract, source=em._source(c, f"{BH}/render_receipt.json", blobs["render_receipt.json"], "Render receipt."),
              method=f"Producer draws {rr['frames']} frames from saved states (indices recorded) and encodes them with ffmpeg. {rr['scope']}.", context=RENDER_NOTE + " " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, frames=rr["frames"], fps=rr["fps"], time_interpolation=rr["time_interpolation"], input_hashes=rr["input_hashes"]), limitations=[em.IMPORT_NOTE, RENDER_NOTE, NOT_CALIBRATED],
              artifacts=[c.artifact("output", f"{BH}/{n}", blobs[n], d) for n, d in (("behavior.mp4", "video of saved joint states"), ("poster.png", "poster"))]
              + [c.artifact("log", f"{BH}/render_receipt.json", blobs["render_receipt.json"], "render receipt"), c.artifact("code", f"{BH_CODE}/render.py", code["render.py"])])
    c.open_problems = [{"id": p["id"], "question": p["question"], "blocks": p["blocks"], "next_action": p["next_action"], "scale": p["scale"]} for p in prob["problems"]]
    return c


# -------------------------------------------------------------------------------------------------------------------------- lifecycle
LC = "data/fish-lifecycle"


def lifecycle_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    """Source assessment, no simulator Action: the lifecycle slice reads papers and states what each stage's processes are known to be.

    Its manifest pins the files by sha256; the one calculation (nutrient diffusion sizing) is closed-form algebra on borrowed parameters and is
    recorded as `predicted` with no Action, because the producer holds no execution receipt for it.
    """
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "lifecycle")
    man = c.jblob(f"{LC}/manifest.json")
    c.check("manifest.schema", str(man.get("manifest_schema", "")).startswith("fish-lifecycle-manifest-0.1") and man.get("status", "").startswith("proposed"), f"manifest {man.get('manifest_schema')!r} status {man.get('status')!r}")
    pinned = {f["path"]: c.same_hash(f"file.{f['path']}", f["path"], f["sha256"]) for f in man["files"]}
    for f in man["files"]:
        c.check(f"size.{f['path']}", len(pinned[f["path"]]) == f["bytes"], f"{f['path']}: manifest {f['bytes']} bytes, blob {len(pinned[f['path']])}")
    assur, srcs, stages, eqs, diff = (json.loads(pinned[f"{LC}/{n}.json"]) for n in ("assurance", "sources", "stages", "equations", "nutrient_diffusion_check"))
    counts: dict[str, int] = {}
    for proc in assur["processes"].values():
        for stage, cell in proc.items():
            if isinstance(cell, dict) and "status" in cell:
                counts[cell["status"]] = counts.get(cell["status"], 0) + 1
    c.check("assurance.statuses", set(counts) <= set(assur["statuses"]) and sum(counts.values()) > 0, f"cells {sum(counts.values())}, statuses {counts}")
    lim = [em.IMPORT_NOTE, man["organism"] + ". " + "; ".join(f"not claimed: {x}" for x in man["claims_not_made"]), man["not_stored"] and ("Not stored: " + man["not_stored"])]
    lim = [x for x in lim if x]
    asm = [f"Single operator, unreviewed; retrieved {man['retrieved']}; {len(srcs['cards'])} source cards read, {len(srcs.get('not_used', []))} sources found and not used.", "Stage boundaries are Parichy 2009's laboratory conventions."]
    src_cov = _claim(c, "run-lifecycle-claim-assurance-map", "Zebrafish life-cycle assurance map: which stage-by-process cells are measured in fish, borrowed or unknown",
                     (f"The producer's assurance map has {sum(counts.values())} stage-by-process cells over stages {', '.join(assur['stages'])}: "
                      + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + f". Gaps it lists first: {'; '.join(assur['gaps_first'])}."),
                     "A source-reading result about Danio rerio, not a model and not a flying fish. " + "; ".join(assur["claims_not_made"]), asm, lim, f"{LC}/assurance.json", pinned[f"{LC}/assurance.json"],
                     "Assurance map: per stage and process, the status and the source read.")
    _evidence(c, SRC, "run-lifecycle-evidence-assurance-map", src_cov, kind="source_assessment", relation="context_only", produced_by=None,
              source=em._source(c, f"{LC}/assurance.json", pinned[f"{LC}/assurance.json"], "Assurance map."),
              method="One operator read the cited papers (full text via Europe PMC where stored; hashes in sources.json) and recorded, per cell, what status the source supports. No simulator ran.",
              context="A source assessment: it records what sources say and what is unknown, and has no simulator Action by design. " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, status_counts=counts, source_cards=len(srcs["cards"]), stage_count=len(stages["stages"]), equation_rows=len(eqs["equations"]), manifest_files=len(man["files"])),
              limitations=lim + ["Cells the producer did not read are marked unknown, not zero or absent."],
              artifacts=[c.artifact("input", f"{LC}/{n}.json", pinned[f"{LC}/{n}.json"], d) for n, d in (("assurance", "assurance map"), ("sources", "source cards with locators and hashes"), ("stages", "stage definitions and interfaces"), ("equations", "equations as the sources state them"))]
              + [c.artifact("log", f"{LC}/manifest.json", c.blob(f"{LC}/manifest.json"), "manifest pinning every file by sha256")],
              uncertainty="Single reader; no interval. A status is the reader's reading of a source, not a measurement by this project.")
    d = diff["derived"]
    sz = _claim(c, "run-lifecycle-claim-diffusion-sizing", "Oxygen diffusion sizing aid under borrowed parameters: a solid, perfusion-free slab has a one-sided limit of about 135 um",
                (f"With diffusion-only, uniform-consumption, steady-state geometry and the borrowed inputs recorded in the check, the producer derives a one-sided slab limit of {d['slab_one_sided_limit_um']:.1f} um (C0/(a*s) = {d['c0_over_a_s']:.3f}, range {d['c0_over_a_s_range'][0]:.2f}-{d['c0_over_a_s_range'][1]:.2f})."),
                diff["status"] + " " + diff["comparison_with_fish_body_height"]["reading"], asm + [f"Geometry: {'; '.join(diff['geometry_assumptions'])}"], lim + [f"Producer states it does not know: {'; '.join(diff['not_known'])}."] + [f"Not claimed: {x}" for x in diff["claims_not_made"]],
                f"{LC}/nutrient_diffusion_check.json", pinned[f"{LC}/nutrient_diffusion_check.json"], "Closed-form sizing check with its inputs and what is not known.")
    _evidence(c, SRC, "run-lifecycle-evidence-diffusion-sizing", sz, kind="predicted", relation="context_only", produced_by=None,
              source=em._source(c, f"{LC}/nutrient_diffusion_check.json", pinned[f"{LC}/nutrient_diffusion_check.json"], "Diffusion sizing check."),
              method="Closed-form algebra on borrowed parameters (no simulation). No Action is recorded because the producer holds no execution receipt for it.",
              context=diff["status"] + " " + em.IMPORT_NOTE, assumptions=asm, provenance=_prov(c, inputs=diff["inputs"], derived=d), limitations=lim + [f"Producer states it does not know: {'; '.join(diff['not_known'])}."],
              artifacts=[c.artifact("input", f"{LC}/nutrient_diffusion_check.json", pinned[f"{LC}/nutrient_diffusion_check.json"], "check with its inputs and derived values"), c.artifact("code", "engineering/lifecycle/diffusion.py", c.blob("engineering/lifecycle/diffusion.py"))],
              uncertainty="Only the range over the borrowed inputs is given; the inputs themselves are not measured for fish tissue.")
    return c


CHAINS = {"fish3d": fish3d_chain, "scales": scales_chain, "behavior": behavior_chain, "lifecycle": lifecycle_chain}


# ------------------------------------------------------------------------------------------------------------------------- BETSE tissue
BT = "artifacts/bioelectric-tissue"
BT_CODE = "engineering/bioelectric_tissue"
BT_SCENARIOS = ("baseline", "k_up", "gj_block", "k_up_gj_block", "baseline_dt")
BT_CHECKS = ("charge_consistency", "coupling_contrast_expectation", "finite_and_physical", "gj_block_control", "impermeant_P_total_conserved", "k_control_direction_and_reversal", "time_step_sensitivity")


def betse_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    """BETSE 1.5.0 generic 2-D cell patch: five scenarios, seven checks, one video. Generic tissue; no fin or fish calibration.

    The summary carries scenario config and trajectory hashes, the BETSE version, the check values and a label. It does NOT carry an exit code, a
    command, a wall time or an interpreter version, and it states no hash for the video or poster; the Action titles say so, and the video and
    poster digests are computed here from the blobs (not producer-stated).
    """
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "betse")
    sm = c.jblob(f"{BT}/summary.json")
    c.check("summary.schema", sm.get("schema") == "frontier.bioelectric-tissue.summary/1" and sm.get("all_checks_ok") is True and sm["label"].startswith("SIMULATED"),
            f"schema {sm.get('schema')!r} all_checks_ok {sm.get('all_checks_ok')!r} label {sm.get('label')!r}")
    c.check("summary.scenarios", tuple(sorted(sm["files"])) == tuple(sorted(BT_SCENARIOS)), f"scenarios {sorted(sm['files'])}")
    c.check("summary.checks", tuple(sorted(sm["checks"])) == BT_CHECKS and all(v["ok"] is True for v in sm["checks"].values()), f"checks {sorted(sm['checks'])} ok {[k for k, v in sm['checks'].items() if not v['ok']]}")
    blobs = {}
    for sc, f in sm["files"].items():
        blobs[f"{sc}.cfg"] = c.same_hash(f"config.{sc}", f"{BT}/{f['config']}", f["config_sha256"])
        blobs[f"{sc}.traj"] = c.same_hash(f"trajectory.{sc}", f"{BT}/{f['trajectory']}", f["trajectory_sha256"])
    code = {n: c.blob(f"{BT_CODE}/{n}") for n in ("run.py", "analysis.py", "betse_stage.py", "render.py", "requirements-betse.txt")}
    smb, itf_b = c.blob(f"{BT}/summary.json"), c.blob(f"{BT}/model_interface.json")
    itf = json.loads(itf_b)
    c.check("interface.status", itf["status"].startswith("SIMULATED") and "Fin applicability: UNKNOWN" in itf["status"], itf["status"][:120])
    mp4, poster = c.blob(f"{BT}/bioelectric_tissue.mp4"), c.blob(f"{BT}/poster.png")
    tests_b = c.blob("tests/test_bioelectric_tissue.py")
    n_tests = sum(1 for ln in tests_b.decode().splitlines() if ln.startswith("def test_"))
    ef, ch, rg = sm["effects"], sm["checks"], sm["reference_ghk"]
    ku, gj, kg = ef["k_up"], ef["gj_block"], ef["k_up_gj_block"]
    cands = itf.get("candidate_channel_links", [])
    lim = [em.IMPORT_NOTE, "GENERIC 2-D tissue patch with BETSE default parameters; no sourced fin or fish tissue parameters. Fin applicability: UNKNOWN. " + NOT_CALIBRATED,
           f"Temperature is the BETSE default 310 K; a fish fin is not at that temperature.",
           f"Simulated mean resting Vm is {rg['simulated_mean_resting_Vm_mV']:.1f} mV against a leak-only GHK reference of {rg['ghk_leak_only_mV']:.2f} mV; the producer states the GHK number ignores the pump and gap junctions and the difference is not decomposed. Kept as found.",
           "Gap-junction conductance in siemens, channel conductance and growth coupling are not exposed (BETSE parameterizes junctions by a surface fraction); their values are UNKNOWN.",
           "No ion depletion in the environment, no flow, no deformation, no gene regulation."]
    lim += [f"Channel candidate {x['candidate'].split(' (')[0]}: listed as a source link only; used_to_set_any_parameter {x['used_to_set_any_parameter']}; conductance, gating and copy number UNKNOWN." for x in cands]
    asm = [f"BETSE {sm['betse']}; {sm['n_cells']} cells, {sm['n_membranes']} membranes, intervention window {sm['intervention_window_s']} s, {sm['samples']} saved samples.",
           "Scenarios: baseline; k_up (K+ membrane permeability x5 in the 2 cells of the Spot profile, a generic scale, not Kir2.1); gj_block (all gap junctions blocked); k_up_gj_block; baseline_dt (half solver step, a numerical control).",
           f"Environment pins: {code['requirements-betse.txt'].decode().splitlines()[1]} and the rest of requirements-betse.txt; interpreter NOT RECORDED in the receipt."]
    claim = _claim(c, "run-betse-claim-k-gap-junction-contrast", "Generic BETSE tissue patch: K+ permeability change spreads through gap junctions and is confined when they are blocked",
                   (f"In BETSE {sm['betse']} on a {sm['n_cells']}-cell generic patch (default parameters), raising K+ permeability x5 in {ku['n_targeted_cells']} cells over {sm['intervention_window_s']} s moves the targeted cells by at most {ku['targeted_peak_dVm_mV']:.2f} mV "
                    f"and the {ku['n_other_cells']} other cells by up to {ku['other_peak_dVm_mV']:.2f} mV; with gap junctions blocked as well the targeted cells move by {kg['targeted_peak_dVm_mV']:.1f} mV and the others by {kg['other_peak_dVm_mV']:.2f} mV; "
                    f"blocking junctions alone moves Vm by at most {max(abs(gj['targeted_peak_dVm_mV']), abs(gj['other_peak_dVm_mV'])):.2f} mV. Simulated mean resting Vm is {rg['simulated_mean_resting_Vm_mV']:.1f} mV."),
                   "A deterministic simulated outcome of a generic tissue model under declared perturbations; not an observation and not a fish fin. " + sm["label"], asm, lim, f"{BT}/summary.json", smb,
                   "Summary: per-scenario effects, checks, hashes and the producer's label.")
    cfg_code = f"git:{em.REPO_LABEL}@{commit}; " + ", ".join(f"{n}:{sha_bytes(b)[:12]}" for n, b in sorted(code.items()) if n != "render.py")
    act = _action(c, SRC, "run-betse-action-sim", claim,
                  f"Imported record of a producer-reported run (NOT executed by Frontier): five BETSE {sm['betse'].split()[1]} scenarios; the receipt carries NO exit code, command or wall time (the producer's doc reports about 1-2 min per run)",
                  [ACCEPT_REPLAY, "An independent reviewer checks the BETSE configuration against tissue sources before any number is applied to a fin."], ["python3.12 with betse==1.5.0 (isolated venv)"],
                  dict(input="five scenario configs " + ", ".join(f"{k}:{v['config_sha256'][:10]}" for k, v in sorted(sm["files"].items())), code=cfg_code, model=f"{sm['betse']} (ion, pump and gap-junction cell-patch simulator; no language model)",
                       environment="requirements-betse.txt pins betse==1.5.0 and dependencies; interpreter and platform NOT RECORDED", parameters="BETSE defaults; K_permeability_multiplier 5.0 in the Spot profile; gap-junction block as in the configs",
                       scope="simulated generic tissue; not a fin"), [])
    ev = _evidence(c, SRC, "run-betse-evidence-sim", claim, kind="simulated", relation="unspecified", produced_by=act, source=em._source(c, f"{BT}/summary.json", smb, "Summary."),
                   method=f"BETSE {sm['betse']} runs of five scenarios; effects are differences from the baseline run. " + sm["label"], context="Applicability: this generic patch with BETSE defaults. " + em.IMPORT_NOTE, assumptions=asm,
                   provenance=_prov(c, betse=sm["betse"], scenarios=sorted(sm["files"]), trajectories_sha256={k: v["trajectory_sha256"] for k, v in sorted(sm["files"].items())}, exit_status_recorded=False, command_recorded=False),
                   limitations=lim, uncertainty="Deterministic runs; solver-step sensitivity control only (max |dVm| %.2g mV). No parameter or biological uncertainty." % ch["time_step_sensitivity"]["max_abs_dVm_mV"],
                   artifacts=[c.artifact("output", f"{BT}/{f['trajectory']}", blobs[f"{sc}.traj"], f"scenario {sc}: saved Vm, concentrations, gap-junction state") for sc, f in sorted(sm["files"].items())]
                   + [c.artifact("input", f"{BT}/{f['config']}", blobs[f"{sc}.cfg"], f"scenario {sc} BETSE configuration") for sc, f in sorted(sm["files"].items())]
                   + [c.artifact("log", f"{BT}/summary.json", smb, "summary with effects and checks"), c.artifact("protocol", f"{BT}/model_interface.json", itf_b, "model interface: inputs used, outputs, what is not exposed"),
                      c.artifact("code", f"{BT_CODE}/run.py", code["run.py"]), c.artifact("code", f"{BT_CODE}/betse_stage.py", code["betse_stage.py"]),
                      c.artifact("environment", f"{BT_CODE}/requirements-betse.txt", code["requirements-betse.txt"], "pinned BETSE environment")])
    cl2 = _claim(c, "run-betse-claim-checks", "BETSE tissue patch: seven computational checks pass, one of them a definitional consistency and one an expectation",
                 (f"The producer's {len(ch)} checks all pass: {', '.join(sorted(ch))}. Time-step halving changes Vm by at most {ch['time_step_sensitivity']['max_abs_dVm_mV']:.2g} mV ({ch['time_step_sensitivity']['ratio_to_K_control_peak']:.2g} of the K-control peak); "
                  f"total impermeant P is conserved to relative range 0 in every scenario; the K control direction and reversal and the gap-junction block control are met."),
                 "Implementation checks of a simulator output. " + ch["charge_consistency"]["note"] + ". " + ch["coupling_contrast_expectation"]["note"] + ".", asm,
                 lim + [f"Charge consistency: {ch['charge_consistency']['note']}.", f"Coupling contrast is an expectation, not a law: {ch['coupling_contrast_expectation']['criterion']}.", f"Mass: {ch['impermeant_P_total_conserved']['note']}.",
                        f"The repository's tests/test_bioelectric_tissue.py defines {n_tests} tests that recompute the committed checks from the committed trajectories; this adapter did not run them or recompute the checks."],
                 f"{BT}/summary.json", smb, "The checks block with criteria and values.")
    act2 = _action(c, SRC, "run-betse-action-checks", cl2, "Imported record of producer-reported checks (NOT executed by Frontier): seven predicates over the saved trajectories",
                   [ACCEPT_REPLAY, "A reviewer reads each criterion and confirms it tests what its name says."], ["python3 with numpy"],
                   dict(input="saved trajectories of the five scenarios (see the simulation Evidence)", code=f"git:{em.REPO_LABEL}@{commit}; analysis.py {sha_bytes(code['analysis.py'])[:12]}", model="none: numerical predicates",
                        environment="NOT RECORDED by the producer", parameters="thresholds are check criteria, not statistics", scope="checks of a simulator output"), [ev])
    _evidence(c, SRC, "run-betse-evidence-checks", cl2, kind="simulated", relation="unspecified", produced_by=act2, source=em._source(c, f"{BT}/summary.json", smb, "Checks block."),
              method="Seven predicates over saved trajectories; values and criteria are in the summary.", context="Applicability: these trajectories only. " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, checks=sorted(ch), all_checks_ok=sm["all_checks_ok"], repo_test_defs=n_tests, tests_run_by_adapter=False), limitations=lim + ["Producer check, not independent."],
              artifacts=[c.artifact("certificate", f"{BT}/summary.json", smb, "checks with criteria and values"), c.artifact("code", f"{BT_CODE}/analysis.py", code["analysis.py"]), c.artifact("code", "tests/test_bioelectric_tissue.py", tests_b)])
    ract = _action(c, SRC, "run-betse-action-render", claim, "Imported record of a producer-reported render (NOT executed by Frontier): video and poster from the saved trajectories; the producer states NO hash for either, so the digests here were computed by this adapter",
                   ["Re-rendering the trajectories with render.py reproduces the frames; mp4 bytes can differ across ffmpeg builds.", "Pictures are read as views of computed states, not as evidence."], ["python3 with matplotlib; ffmpeg"],
                   dict(input=f"simulation evidence version {ev['version']}", code=f"git:{em.REPO_LABEL}@{commit}; render.py {sha_bytes(code['render.py'])[:12]}", model="none: deterministic rendering", environment="NOT RECORDED by the producer",
                        parameters="NOT RECORDED (frame count and fps are not in the receipt)", scope="visualisation of a simulated generic tissue patch"), [ev])
    _evidence(c, SRC, "run-betse-evidence-render", claim, kind="simulated", relation="context_only", produced_by=ract, source=em._source(c, f"{BT}/model_interface.json", itf_b, "Interface and status label."),
              method="Producer renders the saved trajectories to a video and poster (render.py). No render receipt exists; hashes are adapter-computed.", context=RENDER_NOTE + " " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, hashes_stated_by_producer=False, mp4_sha256=sha_bytes(mp4), poster_sha256=sha_bytes(poster)), limitations=[em.IMPORT_NOTE, RENDER_NOTE, NOT_CALIBRATED, "No producer-stated hash for the video or poster; the digests are computed from the committed bytes."],
              artifacts=[c.artifact("output", f"{BT}/bioelectric_tissue.mp4", mp4, "video of simulated states"), c.artifact("output", f"{BT}/poster.png", poster, "poster"), c.artifact("code", f"{BT_CODE}/render.py", code["render.py"])])
    return c


LATER = {"betse": betse_chain}
ALL_CHAINS = {**CHAINS, **LATER}


# ---------------------------------------------------------------------------------------------------------------------------- bundles
# Root is making the repository public after a credential/history audit: no curated output may carry a presigned URL or a secret-looking field.
SECRETISH = re.compile(r"X-Amz|Signature=|Expires=|presign|[?&]token=|access[_-]?key|secret|passw(?:or)?d|api[_-]?key|bearer|authorization|AKIA[0-9A-Z]{8}|sk-[A-Za-z0-9]{16}|BEGIN [A-Z ]*PRIVATE|\.credentials|https?://[^\"\s]*\?", re.I)


def find_secretish(text: str) -> list[str]:
    return sorted({m.group(0) for m in SECRETISH.finditer(text)})


STATUS = "PROPOSED. Not submitted, accepted or published. Single-reader (artifact-curation worker), not Codex-reviewed, not independently reviewed."


def chain_summary(ch: AssetChain, bundle: dict) -> dict:
    recs = ch.records
    return {"name": ch.name, "bundle_sha256": bundle["bundle_sha256"],
            "records": [{"kind": r["kind"], "id": r["id"], "version": r["version"],
                         **({"evidence_kind": r["payload"]["evidence_kind"], "relation": r["payload"]["relation"], "has_action": r["payload"].get("produced_by") is not None} if r["kind"] == "Evidence" else {})} for r in recs],
            "counts": {k: sum(1 for r in recs if r["kind"] == k) for k in ("Claim", "Action", "Evidence")},
            "checks": ch.checks, "checks_failed": [x["id"] for x in ch.checks if not x["ok"]],
            "open_problems_not_in_bundle": getattr(ch, "open_problems", [])}


def write_frozen(out_dir: str, chains: list[AssetChain]) -> dict:
    """One frozen `frontier-bundle-0.1` per chain (each imports atomically and stays under the store's 2 MB / 100-record limits)."""
    import os
    from .artifacts import find_abs_paths
    os.makedirs(out_dir, exist_ok=True)
    chains = sorted(chains, key=lambda ch: ch.name)             # the frozen bytes must not depend on the caller's order
    files, summaries = {}, []
    for ch in chains:
        bundle = em.build_bundle([ch], limit=AssetChain.max_records)
        files[f"bundle.{ch.name}.frontier-bundle-0.1.json"] = json.dumps(bundle, indent=1, sort_keys=True) + "\n"
        summaries.append(chain_summary(ch, bundle))
    report = {"status": STATUS, "adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION},
              "source": {"repo_label": em.REPO_LABEL, "commit": chains[0].commit, "read": "immutable git blobs only; working tree not read"},
              "execution_statement": "Every Action is an IMPORTED RECORD of what the producer reports. None was executed by Frontier or by this adapter, none was replayed, none was reviewed. "
                                     "Lifecycle records are source assessments and carry no Action by design.",
              "artifact_policy": "All artifacts are ArtifactRef with availability 'referenced' and a urn:sha256 pointer; no URL is claimed, no licence asserted, bytes not embedded.",
              "chains": summaries, "link_checks": em.link_checks([r for ch in chains for r in ch.records])}
    bad = find_abs_paths(report) + [x for t in files.values() for x in find_abs_paths(t)]
    if bad:
        raise em.Refused(f"absolute local paths in output at {bad}")
    files["chain.json"] = json.dumps(report, indent=1, sort_keys=True) + "\n"
    leaks = {n: find_secretish(t) for n, t in files.items() if find_secretish(t)}
    if leaks:
        raise em.Refused(f"secret-like or presigned-URL text in curated output: {leaks}")
    for n, t in files.items():
        with open(os.path.join(out_dir, n), "w") as fh:
            fh.write(t)
    manifest = {"status": STATUS, "file_sha256": {n: sha_bytes(t.encode()) for n, t in sorted(files.items())},
                "records": [{"kind": r["kind"], "id": r["id"], "namespace": r["namespace"], "version": r["version"]} for ch in chains for r in ch.records],
                "publication": "none. Not written to any store; root handles production imports."}
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        fh.write(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return {"report": report, "manifest": manifest}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m frontier_adapters.run_bundles",
                                 description="Freeze fish3d / scales / behavior / lifecycle bundles from immutable git blobs. Writes files only; never touches a store.")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*", choices=sorted(ALL_CHAINS), default=sorted(CHAINS))
    ap.add_argument("--namespace", default="node-a")
    ap.add_argument("--issuer", default="importer")
    ap.add_argument("--created-at", default=None)
    a = ap.parse_args(argv)
    commit = em.resolve_commit(a.repo, a.source_commit)
    chains = [ALL_CHAINS[n](a.repo, commit, namespace=a.namespace, issuer=a.issuer, created_at=a.created_at) for n in a.only]
    out = write_frozen(a.out, chains)
    print(json.dumps({"chains": {c["name"]: c["counts"] for c in out["report"]["chains"]}, "commit": commit, "out": a.out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
