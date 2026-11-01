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


# ------------------------------------------------------------------------------------------------------------------------ OpenFold2 Kcnj13
OF = "artifacts/bio-services/kcnj13_openfold2"
OFS = "artifacts/bio-services/kcnj13_source"


def openfold_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    """Hosted OpenFold2, exact unmodified Kcnj13 BAF03613.1 sequence. A provider operation with a real receipt, and a LOW-confidence prediction.

    Not copied into any record: the provider's storage bucket, object keys and prefix (`customer_storage`, `provider_reported_*`), the request
    payload, and source URLs (accessions are cited instead). Structure is not function: no conductance, gating or phenotype follows.
    """
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "openfold2")
    op = c.jblob(f"{OF}/operation_receipt.json")
    c.check("op.status", op.get("final_status") == "SUCCEEDED" and op.get("model_id") == "openfold2" and op["states"][-1]["status"] == "SUCCEEDED", f"final {op.get('final_status')!r} model {op.get('model_id')!r}")
    pdb = c.same_hash("rank1.pdb", f"{OF}/rank1.pdb", op["rank1_structure_sha256"])
    met_b = c.same_hash("metrics", f"{OF}/metrics.json", op["metrics_sha256"])
    res_b = c.same_hash("result", f"{OF}/result.json", op["result_sha256"])
    met = json.loads(met_b)
    src = c.jblob(f"{OFS}/source_manifest.json")
    fa = c.blob(f"{OFS}/ncbi_baf03613_fasta.txt")
    seq = "".join(ln.strip() for ln in fa.decode().splitlines() if not ln.startswith(">"))
    c.check("sequence.hash", sha_bytes(seq.encode()) == op["sequence_sha256"] == src["selected_sequence"]["sequence_sha256"] == met["input_sequence_sha256"] and len(seq) == op["sequence_length_aa"] == 362,
            f"{len(seq)} aa, recomputed sha256 {sha_bytes(seq.encode())[:16]}..., receipt {op['sequence_sha256'][:16]}...")
    c.check("sequence.unmodified", src["inference_eligibility"]["only_unmodified_source_sequence"] is True and src["inference_eligibility"]["mutation_or_design"] is False, "source manifest: unmodified, no mutation or design")
    c.check("coordinates", op["coordinate_check"]["sequence_exact_match"] is True and op["coordinate_check"]["ca_residue_count"] == 362, f"coordinate_check {op['coordinate_check']['ca_residue_count']} CA, exact {op['coordinate_check']['sequence_exact_match']}")
    pm = met["provider_metrics"]
    pl = pm["plddt"]
    c.check("metrics.consistent", abs(pl["mean"] - op["confidence"]) < 1e-9 and abs(pm["ptm_score"] - op["ptm_score"]) < 1e-12, f"pLDDT mean {pl['mean']:.4f} vs receipt confidence {op['confidence']:.4f}")
    opb = c.blob(f"{OF}/operation_receipt.json")
    srcb = c.blob(f"{OFS}/source_manifest.json")
    disc = src["discrepancy"]
    c.check("discrepancy.recorded", disc["exact_match_to_selected"] is False and disc["length_aa"] == 358, f"RefSeq variant {disc['ncbi_refseq_accession']} {disc['length_aa']} aa differs from the selected 362 aa")
    lim = [em.IMPORT_NOTE, "A PREDICTED structure, not an observed one: " + met["epistemic_status"] + ".", *met["limits"],
           "Structure does not establish conductance, gating, a pigment pattern or any phenotype. Not used to set any BETSE parameter.", NOT_CALIBRATED]
    asm = [f"Input: the exact unmodified source sequence {src['selected_sequence']['accession']} ({len(seq)} aa, sha256 {op['sequence_sha256'][:16]}...), matched to UniProt {src['crosscheck']['uniprot_accession']}; selected for the exact match, not labelled canonical.",
           f"Tool {op['tool']} on {op['provider']}; model parameter set {met['model_parameter_set']}; relaxed {met['relaxed']}.",
           f"Provider-reported runtime image {op['runtime_reported'].split('@')[-1][:19]}... with origin {op['reported_runtime_origin']}."]
    claim = _claim(c, "run-openfold2-claim-kcnj13-low-confidence", "OpenFold2 single-sequence monomer of zebrafish Kcnj13 (BAF03613.1) has low model-internal confidence",
                   (f"The hosted OpenFold2 monomer prediction for the 362-aa Kcnj13 sequence has mean pLDDT {pl['mean']:.1f} (min {pl['min']:.1f}, max {pl['max']:.1f}); {pl['fraction_below_50']*100:.1f}% of residues are below 50 and {pl['fraction_at_least_70']*100:.1f}% are at least 70; "
                    f"pTM is {pm['ptm_score']:.3f}; mean predicted aligned error is {pm['predicted_aligned_error']['mean_A']:.1f} A (max {pm['predicted_aligned_error']['max_A']:.1f} A)."),
                   "A model-internal confidence summary of a predicted structure with a dummy single-sequence MSA; these are not calibrated probabilities of correctness. " + "; ".join(met["limits"][:2]), asm, lim,
                   f"{OF}/metrics.json", met_b, "Provider metrics: pLDDT and PAE summaries, pTM, coordinate check.")
    act = _action(c, SRC, "run-openfold2-action-infer", claim,
                  f"Provider-executed operation (hosted OpenFold2, {op['operation_id']}): submitted by the producer, completion reported by the provider receipt (states QUEUED, RUNNING, SUCCEEDED); the provider returned NO hardware or GPU allocation and is not counted as our H100 allocation",
                  [ACCEPT_REPLAY.replace("a clean re-execution from the pinned code", "a re-run of the same sequence on the same provider operation, or any independent OpenFold2 run,"), "An independent reviewer treats the confidence metrics as model-internal and not as evidence of function."],
                  ["hosted OpenFold2 via Nebius Scientific AI MCP"],
                  dict(input=f"sequence sha256 {op['sequence_sha256']} (362 aa, unmodified)", code=f"git:{em.REPO_LABEL}@{commit}; result and metrics files hashed in operation_receipt.json", model=f"openfold2 {op['tool']} (single-sequence dummy MSA, monomer, unrelaxed)",
                       environment=f"provider runtime image {op['runtime_reported'].split('@')[-1][:19]}...; hardware NOT RETURNED", parameters=f"model_parameter_set {met['model_parameter_set']}; relaxed {met['relaxed']}", scope="predicted monomer structure of one sequence"), [])
    _evidence(c, SRC, "run-openfold2-evidence-predicted-structure", claim, kind="predicted", relation="unspecified", produced_by=act, source=em._source(c, f"{OF}/operation_receipt.json", opb, "Provider operation receipt."),
              method=f"Provider-hosted OpenFold2 inference; operation {op['operation_id']} reached {op['final_status']}; pLDDT, PAE and pTM are the provider's own summaries; the C-alpha order was parsed from the returned PDB and matches the input sequence ({op['coordinate_check']['ca_residue_count']} residues). No structural alignment was done.",
              context="Applicability: this one sequence, single-sequence mode. " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, operation_id=op["operation_id"], states=[{"status": x["status"], "elapsed_s": x["elapsed_s"]} for x in op["states"]], provider_reported_inference_seconds=op["provider_reported_inference_seconds"],
                               poll_elapsed_s=op["poll_elapsed_s"], submitted_utc=op["submitted_utc"], completed_utc=op["completed_utc"], tool=op["tool"], hashes_recomputed=["rank1.pdb", "metrics.json", "result.json", "sequence"]),
              limitations=lim, uncertainty="No uncertainty beyond the model's own pLDDT and PAE, which are not calibrated.",
              artifacts=[c.artifact("geometry", f"{OF}/rank1.pdb", pdb, "predicted structure, rank 1 (PDB text)"), c.artifact("output", f"{OF}/metrics.json", met_b, "pLDDT, PAE and pTM summaries"),
                         c.artifact("log", f"{OF}/operation_receipt.json", opb, "provider operation receipt (bucket and keys not carried into this record)"), c.artifact("output", f"{OF}/result.json", res_b, "provider result envelope"),
                         c.artifact("input", f"{OFS}/source_manifest.json", srcb, "source sequence packet with the RefSeq discrepancy"), c.artifact("input", f"{OFS}/ncbi_baf03613_fasta.txt", fa, "selected source sequence")])
    sc = _claim(c, "run-openfold2-claim-kcnj13-sequence-discrepancy", "Kcnj13 source records disagree: the current RefSeq variant (358 aa) differs from the sequence that was predicted (BAF03613.1 = UniProt Q0KIZ7, 362 aa)",
                f"The selected sequence BAF03613.1 ({len(seq)} aa) matches UniProt {src['crosscheck']['uniprot_accession']} exactly; RefSeq {disc['ncbi_refseq_accession']} ({disc['transcript_variant']}) is {disc['length_aa']} aa and differs at the N-terminus. {disc['description']}",
                "A source disagreement kept as found: the two records are not claimed interchangeable and neither is claimed canonical. The prediction above used the 362-aa sequence only.", asm,
                [em.IMPORT_NOTE, "Only the N-terminal difference is described by the source manifest; this record did not align the sequences."], f"{OFS}/source_manifest.json", srcb, "Source manifest: selected sequence, crosscheck and discrepancy.")
    _evidence(c, SRC, "run-openfold2-evidence-source-discrepancy", sc, kind="source_assessment", relation="context_only", produced_by=None, source=em._source(c, f"{OFS}/source_manifest.json", srcb, "Source manifest."),
              method="Comparison of the NCBI protein record, the UniProt entry and the current RefSeq variant as recorded in the source packet. No simulator ran.", context="A source assessment; no Action by design. " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, selected_sha256=op["sequence_sha256"], refseq_sha256=disc["sequence_sha256"], refseq_accession=disc["ncbi_refseq_accession"], uniprot=src["crosscheck"]["uniprot_accession"]),
              limitations=[em.IMPORT_NOTE, "Single reader; the sequences were not re-fetched or aligned by this adapter."], uncertainty="None quantified.",
              artifacts=[c.artifact("input", f"{OFS}/source_manifest.json", srcb, "source sequence packet"), c.artifact("input", f"{OFS}/ncbi_baf03613_fasta.txt", fa, "selected source sequence")])
    return c


LATER["openfold2"] = openfold_chain
ALL_CHAINS = {**CHAINS, **LATER}


# ----------------------------------------------------------------------------------------------------------------------------- Morpheus
MC = "artifacts/multicell"
MI = "results/infra/morpheus"
MI_RUN = f"{MI}/results/infra16-morpheus-full-horizon/parts/00-morpheus-three-arms/baseline"
MC_ARMS = ("baseline", "nofeedback", "seed2")


def morpheus_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    """Morpheus v2.3.9 generic multiscale example: two different runs, kept apart.

    (1) Three local arms stopped by a 600 s cap (SIGTERM, exit -15) at t=0.456 of a configured stop 0.6: NEVER COMPLETED. The record says so.
    (2) A provider job whose state is FAILED (an output wrapper raised IndexError on blank logger lines) but whose BASELINE arm logged all of
        t=0..2.0 with simulator exit 0 and was recovered. Only the baseline timecourse exists; nofeedback and seed2 report exit 0 in stdout but have
        no recovered trajectories, so completion evidence for them is insufficient. These two runs use different XML (stop 0.6 vs 2.0): they are not
        replicates. Generic example; not calibrated to any fish or tissue.
    """
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "morpheus")
    sm = c.jblob(f"{MC}/summary.json")
    arms = sm["arms"]
    c.check("local.arms", tuple(sorted(arms)) == tuple(sorted(MC_ARMS)), f"arms {sorted(arms)}")
    c.check("local.not_completed", all(a["manifest"]["exit"] == -15 for a in arms.values()) and all(a["reached_t"] < a["manifest"]["stop"] for a in arms.values()),
            "every local arm has exit -15 and reached_t below its configured stop (the run did NOT complete)")
    mp4_hash = {ln.split()[1].rsplit("/", 1)[-1]: ln.split()[0] for ln in c.blob(f"{MC}/mp4.sha256").decode().splitlines() if ln.strip()}
    mp4 = {a: c.same_hash(f"local.mp4.{a}", f"{MC}/{a}.mp4", mp4_hash[f"{a}.mp4"]) for a in MC_ARMS}
    xml = {a: c.blob(f"{MC}/{a}/model.xml") for a in MC_ARMS}
    logger = {a: c.blob(f"{MC}/{a}/logger.csv") for a in MC_ARMS}
    smb = c.blob(f"{MC}/summary.json")
    pins = {a["manifest"]["source_sha256"] for a in arms.values()}, {a["manifest"]["binary_sha256"] for a in arms.values()}
    c.check("local.pins", all(len(x) == 1 for x in pins), "one upstream XML sha256 and one binary sha256 across arms (stated by the producer; the upstream bytes are not in this repo and are not re-verified)")
    code = {n: c.blob(f"engineering/multicell/{n}") for n in ("run_morpheus.py", "analyze.py")}
    b0, nf, s2 = arms["baseline"], arms["nofeedback"], arms["seed2"]
    lim = [em.IMPORT_NOTE, "GENERIC Morpheus example (Ferrell-Tsai-Yang cell-cycle ODE + CPM + cytokine PDE); not calibrated to any fish, cell type or tissue; nothing here is fin growth. " + NOT_CALIBRATED,
           "Upstream XML was edited by recorded exact-once replacements (including a hand-made version 1 to 2 fix); the model is not byte-for-byte the shipped one.",
           "Units are the example's own; no dimensional mapping to seconds or micrometres.", "One seed per arm; the seed repeat is a noise check on the CPM, not an independent replicate; no time-step or lattice refinement was run."]
    asm = ["Source: Morpheus v2.3.9 `Examples/Multiscale/MultiscaleModel.xml`; upstream XML sha256 %s and static binary sha256 %s are stated by the producer (BSD 3-clause)." % (b0["manifest"]["source_sha256"][:16] + "...", b0["manifest"]["binary_sha256"][:16] + "..."),
           "Edits: " + ", ".join(b0["manifest"]["edits"]) + "; feedback-off additionally multiplies g_l by 0 inside the CDK1 equation only."]
    claim = _claim(c, "run-morpheus-claim-local-capped-arms", "Morpheus generic multiscale example: three local arms were stopped by the time cap at t=0.456 and never completed",
                   (f"All three local arms were stopped by the 600 s cap (SIGTERM, exit -15) before their configured stop of {b0['manifest']['stop']}; the common reached horizon is t={sm['common_horizon_t']}. At that horizon: baseline (feedback on, seed {b0['manifest']['seed']}) has {b0['cells_at_common_horizon']} cells "
                    f"with division events at {b0['division_event_times_to_horizon']}; feedback-off has {nf['cells_at_common_horizon']} cells with division events at {nf['division_event_times_to_horizon']}; the seed repeat has {s2['cells_at_common_horizon']} cells with division events at {s2['division_event_times_to_horizon']}. "
                    f"No arm reached its configured stop, and the upstream example's own stop is 2.0."),
                   "A partial run reported as partial: within this short window and one seed each, the second division came earlier with the cytokine term in the CDK1 equation than without it. Whether feedback-off divides later or never was not run to the end.", asm,
                   lim + ["NOT COMPLETED: every arm ended by SIGTERM at the cap."], f"{MC}/summary.json", smb, "Summary: per-arm horizon, division events and each arm's manifest.")
    act = _action(c, SRC, "run-morpheus-action-local-arms", claim,
                  "Imported record of a producer-reported run (executed locally by the producer; each arm ended with exit -15 at the 600 s cap; NOT COMPLETED; threads env was not applied to these arms)",
                  [ACCEPT_REPLAY.replace("the digests the receipt lists", "the division-event times to the common horizon"), "A full-horizon run (stop 0.6 or 2.0) completes with exit 0 before any conclusion about feedback-off is drawn."], ["Morpheus v2.3.9 static binary; gnuplot for frames"],
                  dict(input=f"upstream XML sha256 {b0['manifest']['source_sha256']}; per-arm model.xml {', '.join(a + ':' + sha_bytes(xml[a])[:10] for a in MC_ARMS)}", code=f"git:{em.REPO_LABEL}@{commit}; run_morpheus.py {sha_bytes(code['run_morpheus.py'])[:12]}",
                       model="Morpheus v2.3.9 cell-cycle ODE + CPM + cytokine PDE (no language model)", environment=f"binary sha256 {b0['manifest']['binary_sha256'][:16]}...; 1 CPU quota, TasksMax 128, MemoryMax 4G, RuntimeMaxSec 600; OMP_NUM_THREADS not applied",
                       parameters="; ".join(f"{a}: seed {arms[a]['manifest']['seed']}, feedback {arms[a]['manifest']['feedback']}, stop {arms[a]['manifest']['stop']}" for a in MC_ARMS), scope="generic multiscale example; partial window only"), [])
    ev = _evidence(c, SRC, "run-morpheus-evidence-local-arms", claim, kind="simulated", relation="unspecified", produced_by=act, source=em._source(c, f"{MC}/summary.json", smb, "Summary."),
                   method="Morpheus v2.3.9 headless runs of three arms; division events read from the logger; analysis by analyze.py. All three arms ended by SIGTERM at the cap.", context="Applicability: this window of this generic example. " + em.IMPORT_NOTE, assumptions=asm,
                   provenance=_prov(c, arms={a: {"exit": arms[a]["manifest"]["exit"], "reached_t": arms[a]["reached_t"], "seed": arms[a]["manifest"]["seed"]} for a in MC_ARMS}, common_horizon_t=sm["common_horizon_t"], completed=False),
                   limitations=lim + ["NOT COMPLETED: every arm ended by SIGTERM at the cap."], uncertainty="One seed per arm; no refinement; the window ends mid-run.",
                   artifacts=[c.artifact("output", f"{MC}/{a}/logger.csv", logger[a], f"arm {a}: logged CDK1, APC, g_l, volume per cell (partial window)") for a in MC_ARMS]
                   + [c.artifact("input", f"{MC}/{a}/model.xml", xml[a], f"arm {a}: edited Morpheus XML") for a in MC_ARMS] + [c.artifact("log", f"{MC}/summary.json", smb, "summary with per-arm manifests"),
                      c.artifact("code", "engineering/multicell/run_morpheus.py", code["run_morpheus.py"]), c.artifact("code", "engineering/multicell/analyze.py", code["analyze.py"])])
    ract = _action(c, SRC, "run-morpheus-action-local-render", claim, "Imported record of a producer-reported render (not re-run by Frontier): Morpheus Gnuplotter frames of the partial runs, concatenated at 4 fps; the last truncated frame is dropped",
                   ["Re-rendering the logged frames reproduces the videos; mp4 bytes can differ across ffmpeg builds.", "Pictures are views of partial computed states, not evidence."], ["Morpheus Gnuplotter; gnuplot; ffmpeg"],
                   dict(input=f"simulation evidence version {ev['version']}", code=f"git:{em.REPO_LABEL}@{commit}; mp4.sha256 pins three videos", model="none: rendering", environment="gnuplot 6.0.5 (conda-forge); a set-colorbox warning at each frame, frames render",
                        parameters="22 frames per arm at 4 fps", scope="visualisation of partial runs"), [ev])
    _evidence(c, SRC, "run-morpheus-evidence-local-render", claim, kind="simulated", relation="context_only", produced_by=ract, source=em._source(c, f"{MC}/mp4.sha256", c.blob(f"{MC}/mp4.sha256"), "Video hashes."),
              method="Frames drawn by Morpheus' Gnuplotter from the partial runs and encoded with ffmpeg; hashes from mp4.sha256 were recomputed.", context=RENDER_NOTE + " The videos show partial runs. " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, mp4_sha256={a: sha_bytes(mp4[a]) for a in MC_ARMS}, completed=False), limitations=[em.IMPORT_NOTE, RENDER_NOTE, "The videos show runs that never completed.", NOT_CALIBRATED],
              artifacts=[c.artifact("output", f"{MC}/{a}.mp4", mp4[a], f"arm {a}: video of the partial run") for a in MC_ARMS] + [c.artifact("log", f"{MC}/mp4.sha256", c.blob(f"{MC}/mp4.sha256"), "video hashes")])
    # (2) the provider full-horizon attempt
    rec = c.jblob("results/infra/morpheus-failure-recovery.json")
    mf = c.jblob(f"{MI}/manifest-infra16.json")
    job = mf["owned"][0]
    c.check("infra.failed", rec["provider_state"] == "FAILED" and job["status"] == "failed" and job["result"]["job_state"] == "FAILED" and job["result"]["parts"][0]["rc"] == 1, f"provider state {rec['provider_state']!r}, part rc {job['result']['parts'][0]['rc']}")
    lg = c.same_hash("infra.logger", f"{MI_RUN}/logger.csv", rec["logger_sha256"])
    rows = [ln.split("\t") for ln in lg.decode().split("\n")[1:] if ln.strip()]
    ts = sorted({float(r[0]) for r in rows})
    blank = sum(1 for ln in lg.decode().split("\n") if not ln.strip())
    c.check("infra.rows", len(rows) == rec["data_rows"] and ts[-1] == rec["last_time"] == 2.0 and all(len(r) == 7 for r in rows), f"{len(rows)} non-blank rows (note says {rec['data_rows']}), last t {ts[-1]}, {len(ts)} time points, {blank} blank lines")
    last = [r for r in rows if float(r[0]) == ts[-1]]
    ex = c.blob(f"{MI_RUN}/exit.txt").decode().strip()
    c.check("infra.exit", ex == "exit=0", f"baseline exit.txt {ex!r}")
    stop = re.search(r'StopTime value="([^"]*)"', c.blob(f"{MI_RUN}/model.xml").decode())
    c.check("infra.stop", stop is not None and float(stop.group(1)) == 2.0, f"model.xml StopTime {stop.group(1) if stop else None}")
    recb, mfb, xmlb = c.blob("results/infra/morpheus-failure-recovery.json"), c.blob(f"{MI}/manifest-infra16.json"), c.blob(f"{MI_RUN}/model.xml")
    cl2 = _claim(c, "run-morpheus-claim-provider-baseline-recovered", "Morpheus baseline reached t=2.0 in a provider job whose state is FAILED; only the baseline timecourse was recovered",
                 (f"In provider job {job['id']} (state FAILED; an output wrapper raised IndexError on blank logger lines), the baseline arm (StopTime 2.0, seed 3445) logged {len(ts)} time points from t=0 to t={ts[-1]:g} ({len(rows)} non-blank rows, {len(last)} cells at t={ts[-1]:g}) and its stdout reports simulator exit 0. "
                  f"The nofeedback and seed2 arms report exit 0 in stdout but no trajectories were recovered, so completion evidence for them is insufficient. This is a different run from the capped local arms (different XML, stop 2.0 against 0.6); the two are not replicates."),
                 "A provider run reported as it ended: failed at the job level, recovered for one arm. " + rec["interpretation"], asm,
                 lim + [f"Job state FAILED: {rec['failure']}.", f"Missing artifacts: {', '.join(rec['missing_artifacts'])}.", f"The logger has {blank} blank separator lines between time blocks; the {len(rows)} non-blank rows match the recovery note's data_rows.",
                        "One seed, no refinement, one arm recovered: no feedback comparison can be drawn from this record."], "results/infra/morpheus-failure-recovery.json", recb, "Failure and recovery note: provider state, recovered arm, missing arms.")
    act2 = _action(c, SRC, "run-morpheus-action-provider-job", cl2,
                   f"Provider-executed CPU job {job['id']} (state FAILED, part rc 1 after {job['result']['parts'][0]['wall_s']} s); the baseline simulator's own stdout and exit.txt report exit 0 and the logger was recovered after the wrapper error",
                   ["A rerun with the wrapper fixed (blank lines skipped, all arms preserved before parsing) completes all three arms and returns all three trajectories.", ACCEPT_REVIEW], ["Morpheus v2.3.9 static binary on a provider CPU job"],
                   dict(input=f"model.xml sha256 {sha_bytes(xmlb)}; StopTime 2.0; seed 3445", code=f"git:{em.REPO_LABEL}@{commit}; recovery note and manifest-infra16.json", model="Morpheus v2.3.9 cell-cycle ODE + CPM + cytokine PDE (no language model)",
                        environment="provider CPU job; image and interpreter NOT RECORDED in the files read", parameters="baseline arm; feedback on; seed 3445", scope="generic multiscale example; baseline arm only"), [])
    _evidence(c, SRC, "run-morpheus-evidence-provider-baseline", cl2, kind="simulated", relation="unspecified", produced_by=act2, source=em._source(c, "results/infra/morpheus-failure-recovery.json", recb, "Recovery note."),
              method=f"Provider CPU job ran Morpheus v2.3.9; the baseline logger ({len(rows)} rows) was recovered and its sha256 recomputed from the committed file. The job state is FAILED.", context="Applicability: this baseline arm only. " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, job_id=job["id"], job_state=job["result"]["job_state"], part_rc=job["result"]["parts"][0]["rc"], part_wall_s=job["result"]["parts"][0]["wall_s"], baseline_exit_txt=ex, logger_sha256=rec["logger_sha256"], time_points=len(ts),
                               non_blank_rows=len(rows), blank_lines=blank, cells_at_last_time=len(last), missing_arms=rec["missing_artifacts"]),
              limitations=lim + [f"Job state FAILED: {rec['failure']}.", f"Missing artifacts: {', '.join(rec['missing_artifacts'])}."], uncertainty="One seed, one arm, no refinement.",
              artifacts=[c.artifact("output", f"{MI_RUN}/logger.csv", lg, "baseline logger, t=0 to 2.0 (recovered)"), c.artifact("input", f"{MI_RUN}/model.xml", xmlb, "baseline Morpheus XML, StopTime 2.0"),
                         c.artifact("log", f"{MI_RUN}/exit.txt", c.blob(f"{MI_RUN}/exit.txt"), "simulator exit report"), c.artifact("log", "results/infra/morpheus-failure-recovery.json", recb, "failure and recovery note"),
                         c.artifact("log", f"{MI}/manifest-infra16.json", mfb, "provider batch manifest: job state FAILED, part rc 1")])
    return c


LATER["morpheus"] = morpheus_chain
ALL_CHAINS = {**CHAINS, **LATER}


# ------------------------------------------------------------------------------------------------------------------------------- MD
MD = "artifacts/molecular"


def md_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    """Collagen-mimetic atomistic MD (OpenMM 8.4): a CPU run, a first GPU attempt that FAILED its numerical gate, and a CUDA retry on an H100.

    Kept apart: the 0.2 ps CPU run, the failed attempt (no CUDA trajectory was produced), and the 3 x 100 ps CUDA production. A short peptide trajectory
    does not estimate fin stiffness; the cross-scale gate refuses the transfer and this record does not make it.
    """
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "md")
    cpu_dir, cuda_dir = f"{MD}/cpu-trajectory-final", f"{MD}/cuda-v2"
    cr = c.jblob(f"{cpu_dir}/receipt.json")
    c.check("cpu.receipt", cr["schema"] == "frontier.molecular.run/1" and len(cr["runs"]) == 1 and cr["runs"][0]["backend"] == "CPU", f"runs {[(r['backend'], r['seed']) for r in cr['runs']]}")
    cpu_blobs = {n: c.same_hash(f"cpu.{n}", f"{cpu_dir}/{n}", h) for n, h in cr["files"].items() if _has(c, f"{cpu_dir}/{n}")}
    pr = c.jblob(f"{cuda_dir}/production/receipt.json")
    c.check("cuda.receipt", pr["schema"] == "frontier.molecular.run/1" and {r["backend"] for r in pr["runs"]} == {"CUDA"} and sorted(r["seed"] for r in pr["runs"]) == [1731, 1732, 1733], f"runs {[(r['backend'], r['seed']) for r in pr['runs']]}")
    prod = {n: c.same_hash(f"cuda.{n}", f"{cuda_dir}/production/{n}", h) for n, h in pr["files"].items() if _has(c, f"{cuda_dir}/production/{n}")}
    jr = c.jblob(f"{cuda_dir}/job-receipt.json")
    c.check("job.cuda_required", jr["CUDA_required"] is True and "H100" in jr["GPU"], f"CUDA_required {jr['CUDA_required']!r}, GPU {jr['GPU']!r}")
    present = {n: c.same_hash(f"job.{n}", f"{cuda_dir}/{n}", h) for n, h in jr["files"].items() if _has(c, f"{cuda_dir}/{n}")}
    not_here = sorted(n for n in jr["files"] if n not in present)
    par = c.jblob(f"{cuda_dir}/cpu-cuda-parity.json")
    c.check("parity", par["passed"] is True and par["energy_abs_difference_kJ_mol_per_atom"] <= par["frozen_limits"]["energy_per_atom_max"] and par["force_relative_L2_difference"] <= par["frozen_limits"]["force_relative_L2_max"],
            f"energy diff {par['energy_abs_difference_kJ_mol_per_atom']:.3g}, force rel L2 {par['force_relative_L2_difference']:.3g}")
    ret = c.jblob(f"{cuda_dir}/return-provenance.json")
    g1 = c.jblob(f"{MD}/gpu-attempt-1/receipt.json")
    c.check("attempt1.failed", g1["status"].startswith("failed") and g1["CUDA_trajectory_produced"] is False, f"status {g1['status']!r}, CUDA trajectory produced {g1['CUDA_trajectory_produced']!r}")
    dg = c.jblob(f"{MD}/gpu-attempt-1/derivative-diagnosis.json")
    gate = c.jblob(f"{MD}/cross-scale-gate.json")
    c.check("gate.refused", gate["counts"]["refused"] == 1 and gate["counts"]["composable"] == 0, f"gate counts {gate['counts']}")
    an = c.jblob(f"{MD}/cuda-analysis/ensemble.json")
    rn = c.jblob(f"{MD}/cuda-render/render.json")
    rn_out = {n: c.same_hash(f"render.{n}", f"{MD}/cuda-render/{n}", h) for n, h in rn["outputs"].items() if _has(c, f"{MD}/cuda-render/{n}")}
    c.check("render.same_trajectory", rn["trajectory_sha256"] == an["runs"][0]["trajectory_sha256"] and rn["simulation_receipt_sha256"] == an["simulation_receipt_sha256"], "render and analysis name the same trajectory and receipt")
    r0 = cr["runs"][0]
    gate_text = "refused (composable 0, scenario 0, refused 1): no conversion of an atomistic peptide trajectory to tissue modulus or fin function"
    lim = [em.IMPORT_NOTE, "Classical atomistic MD of a collagen-mimetic peptide in solvent; empirical accuracy UNKNOWN; cross-scale transfer UNKNOWN: " + cr["cross_scale_transfer"].replace("unknown: ", "") + ". " + NOT_CALIBRATED,
           f"The cross-scale coupling gate for this model is {gate_text}.", "Short trajectories (0.2 ps CPU; 3 x 100 ps CUDA) do not sample collagen fibril or tissue mechanics."]
    asm = [f"OpenMM {cr['openmm_version']}; protocol sha256 CPU {cr['protocol_sha256'][:16]}... and CUDA {pr['protocol_sha256'][:16]}... (different frozen protocols); prepared system sha256 {par['same_prepared_system_sha256'][:16]}... for the CUDA parity."]
    cmd_cpu = _claim(c, "run-md-claim-cpu-short-trajectory", "Collagen-mimetic MD: a 0.2 ps CPU production run from one seed",
                     f"The producer's CPU run (seed {r0['seed']}, {r0['equilibration_ps']} ps equilibration then {r0['production_ps']} ps production, {r0['frames']} frames, {r0['wall_seconds']:.1f} s wall on {r0['platform_properties']['Threads']} threads) ends at a C-alpha RMSD of {r0['final_CA_RMSD_nm']:.4f} nm from the production start.",
                     "A short computed trajectory used as the CPU reference stage. " + cr["simulation_kind"] + ". " + cr["cross_scale_transfer"], asm, lim, f"{cpu_dir}/receipt.json", c.blob(f"{cpu_dir}/receipt.json"), "Run receipt: versions, protocol, seed, wall time, file hashes.")
    a1 = _action(c, SRC, "run-md-action-cpu", cmd_cpu, f"Imported record of a producer-reported run (executed by the producer on CPU; receipt records OpenMM {cr['openmm_version']}, python, platform and wall time, not an exit code)",
                 [ACCEPT_REPLAY, ACCEPT_REVIEW], ["python3 with OpenMM 8.4"], dict(input=f"preparation sha256 {cr['preparation_sha256']}; protocol sha256 {cr['protocol_sha256']}", code=f"git:{em.REPO_LABEL}@{commit}; producer code sha256 {cr['code_sha256'][:16]}",
                 model="OpenMM 8.4 classical MD (no language model)", environment=f"python {cr['python'].split('|')[0].strip()}; numpy {cr['numpy_version']}; {cr['platform']}", parameters=f"seed {r0['seed']}; {r0['production_steps']} production steps; threads {r0['platform_properties']['Threads']}", scope="short atomistic trajectory"), [])
    _evidence(c, SRC, "run-md-evidence-cpu", cmd_cpu, kind="simulated", relation="unspecified", produced_by=a1, source=em._source(c, f"{cpu_dir}/receipt.json", c.blob(f"{cpu_dir}/receipt.json"), "Run receipt."),
              method="OpenMM 8.4 classical MD on CPU; file hashes in the receipt were recomputed.", context="Applicability: this prepared system and protocol. " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, run=r0, code_sha256=cr["code_sha256"], files_recomputed=sorted(cpu_blobs)), limitations=lim, uncertainty="One seed; no ensemble; no convergence claim.",
              artifacts=[c.artifact("output", f"{cpu_dir}/{n}", b, d) for n, b, d in ((n, cpu_blobs[n], "producer file") for n in sorted(cpu_blobs)) if n.endswith((".npz", ".xml", ".json"))][:6] + [c.artifact("log", f"{cpu_dir}/receipt.json", c.blob(f"{cpu_dir}/receipt.json"), "run receipt")])
    scan = dg["observations"]["CPU"]["gradient_scan"]
    cl_f = _claim(c, "run-md-claim-gpu-attempt-failed-gate", "Collagen-mimetic MD: the first GPU attempt failed its CPU force-derivative gate and produced no CUDA trajectory",
                  (f"Job {g1['job_id']} ended '{g1['status']}': passed controls {g1['passed_controls']}; failed control: {g1['failed_control']}. CUDA trajectory produced: {g1['CUDA_trajectory_produced']}. The producer's diagnosis of one force component {dg['component']} found the finite-difference relative error depends on the step: "
                   + "; ".join(f"h={x['h_nm']:g} nm: {x['relative_error']*100:.2f}%" for x in scan) + "."),
                  "A failed run kept as a result. The diagnosis records the step dependence; this record does not say which step is right. " + dg["scope"], asm, lim + ["No CUDA trajectory exists from this attempt."], f"{MD}/gpu-attempt-1/receipt.json", c.blob(f"{MD}/gpu-attempt-1/receipt.json"), "Attempt receipt and failed control.")
    a2 = _action(c, SRC, "run-md-action-gpu-attempt-1", cl_f, f"Provider-executed job {g1['job_id']} (failed before CUDA production); the control file was reconstructed from exact stdout JSON and its sha256 matches the returned manifest",
                 ["A rerun with a derivative oracle that is stable across steps passes the CPU gate on the same system.", ACCEPT_REVIEW], ["OpenMM 8.4 on a provider job"],
                 dict(input=f"system sha256 {dg['system_sha256']}; state sha256 {dg['state_sha256']}", code=f"git:{em.REPO_LABEL}@{commit}; diagnosis code sha256 {dg['code_sha256'][:16]}", model="OpenMM 8.4 force-derivative controls", environment="see the receipt; interpreter NOT RECORDED in the files read",
                      parameters="frozen relative-error limit 0.005; step h=1e-5 nm", scope="numerical gate of one system"), [])
    _evidence(c, SRC, "run-md-evidence-gpu-attempt-1", cl_f, kind="simulated", relation="unspecified", produced_by=a2, source=em._source(c, f"{MD}/gpu-attempt-1/derivative-diagnosis.json", c.blob(f"{MD}/gpu-attempt-1/derivative-diagnosis.json"), "Derivative diagnosis."),
              method="Frozen controls on the CPU before production; the failed control and the step scan are recorded. Hashes of the receipt files were not all present locally.", context="Applicability: this system and these controls. " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, job_id=g1["job_id"], status=g1["status"], passed_controls=g1["passed_controls"], failed_control=g1["failed_control"], cuda_trajectory_produced=False), limitations=lim + ["No CUDA trajectory exists from this attempt."], uncertainty="Numerical gate only.",
              artifacts=[c.artifact("log", f"{MD}/gpu-attempt-1/receipt.json", c.blob(f"{MD}/gpu-attempt-1/receipt.json"), "attempt receipt"), c.artifact("certificate", f"{MD}/gpu-attempt-1/derivative-diagnosis.json", c.blob(f"{MD}/gpu-attempt-1/derivative-diagnosis.json"), "derivative step scan"),
                         c.artifact("log", f"{MD}/gpu-attempt-1/controls.json", c.blob(f"{MD}/gpu-attempt-1/controls.json"), "controls")])
    runs = pr["runs"]
    cl_c = _claim(c, "run-md-claim-cuda-three-seed-production", "Collagen-mimetic MD: three H100 CUDA seeds of 100 ps after a CPU-CUDA parity check; no tissue stiffness follows",
                  (f"On {jr['GPU'].split(',')[0]} (CUDA required), after a CPU-CUDA parity check on the same prepared system (energy difference {par['energy_abs_difference_kJ_mol_per_atom']:.2g} kJ/mol/atom against a limit of {par['frozen_limits']['energy_per_atom_max']}; force relative L2 {par['force_relative_L2_difference']:.2g} against {par['frozen_limits']['force_relative_L2_max']}), "
                   f"seeds {', '.join(str(r['seed']) for r in runs)} each ran {runs[0]['production_ps']:g} ps after {runs[0]['equilibration_ps']:g} ps equilibration; final C-alpha RMSD from the production start is {', '.join(f'{r['final_CA_RMSD_nm']:.3f}' for r in runs)} nm and the sampled temperature over the last 20% is "
                   f"{', '.join(f'{x['last_20_percent_sampled_temperature_mean_K']:.1f}' for x in an['runs'])} K."),
                  "A computed ensemble of three seeds of a short trajectory. The cross-scale gate refuses any conversion to tissue modulus or fin function.", asm + [f"Job {ret['job_id']}; {ret['all_returned_job_file_hashes_verified']} returned file hashes were verified by the producer."], lim,
                  f"{cuda_dir}/production/receipt.json", c.blob(f"{cuda_dir}/production/receipt.json"), "Production receipt: three CUDA runs.")
    a3 = _action(c, SRC, "run-md-action-cuda-v2", cl_c, f"Provider-executed job {ret['job_id']} (CUDA required; {jr['GPU'].split(',')[0]}; {jr['wall_seconds']:.1f} s wall); the producer reports {ret['all_returned_job_file_hashes_verified']} returned file hashes verified; the prior failed job {ret['prior_failed_job_retained']} is retained",
                 [ACCEPT_REPLAY, ACCEPT_REVIEW], ["OpenMM 8.4 with CUDA on an H100"], dict(input=f"prepared system sha256 {par['same_prepared_system_sha256']}; positions sha256 {par['same_prepared_positions_sha256'][:16]}", code=f"git:{em.REPO_LABEL}@{commit}; remote code sha256 {jr['remote_code_sha256'][:16]}; source commit {ret['source_code_commit'][:12]}",
                 model="OpenMM 8.4 classical MD, CUDA mixed precision (no language model)", environment=f"python {pr['python'].split('(')[0].strip()}; {pr['platform']}; GPU {jr['GPU']}", parameters=f"seeds 1731-1733; {runs[0]['production_steps']} production steps; DeterministicForces {runs[0]['platform_properties']['DeterministicForces']}", scope="short atomistic ensemble"), [])
    ev_c = _evidence(c, SRC, "run-md-evidence-cuda-v2", cl_c, kind="simulated", relation="unspecified", produced_by=a3, source=em._source(c, f"{cuda_dir}/production/receipt.json", c.blob(f"{cuda_dir}/production/receipt.json"), "Production receipt."),
                     method="CPU-CUDA parity then three CUDA production runs; every locally present file hash in the job and production receipts was recomputed" + (f"; {len(not_here)} job-receipt files are inside the prepared-inputs archive and not separately checked here." if not_here else "."), context="Applicability: this prepared system. " + em.IMPORT_NOTE, assumptions=asm,
                     provenance=_prov(c, job_id=ret["job_id"], parity=par, gpu=jr["GPU"], wall_seconds=jr["wall_seconds"], runs=[{k: r[k] for k in ("seed", "wall_seconds", "final_CA_RMSD_nm")} for r in runs], files_recomputed=len(present) + len(prod), files_stated_not_checked=not_here),
                     limitations=lim, uncertainty="Three seeds; no convergence or block-averaging claim; RMSD is from the production start.",
                     artifacts=[c.artifact("output", f"{cuda_dir}/production/trajectory-{x}.npz", prod[f"trajectory-{x}.npz"], f"seed {x}: saved trajectory") for x in (1731, 1732, 1733)] + [c.artifact("output", f"{cuda_dir}/production/metrics-{x}.json", prod[f"metrics-{x}.json"], f"seed {x}: metrics") for x in (1731, 1732, 1733)]
                     + [c.artifact("certificate", f"{cuda_dir}/cpu-cuda-parity.json", c.blob(f"{cuda_dir}/cpu-cuda-parity.json"), "CPU-CUDA parity"), c.artifact("log", f"{cuda_dir}/job-receipt.json", c.blob(f"{cuda_dir}/job-receipt.json"), "job receipt"),
                        c.artifact("log", f"{cuda_dir}/production/receipt.json", c.blob(f"{cuda_dir}/production/receipt.json"), "production receipt"), c.artifact("environment", f"{cuda_dir}/environment.txt", c.blob(f"{cuda_dir}/environment.txt"), "CUDA environment"),
                        c.artifact("input", f"{cuda_dir}/prepared-inputs.tar.gz", c.blob(f"{cuda_dir}/prepared-inputs.tar.gz"), "exact prepared System and State")])
    ra = _action(c, SRC, "run-md-action-cuda-render", cl_c, "Imported record of a producer-reported render (not re-run by Frontier): video and poster of seed 1731 from the actual saved states, rigidly aligned, no deformation invented",
                 ["Re-rendering the trajectory reproduces the frames; mp4 bytes can differ across ffmpeg builds.", "Pictures are views of computed states, not evidence."], ["python3 with matplotlib; ffmpeg"],
                 dict(input=f"simulation evidence version {ev_c['version']}; trajectory sha256 {rn['trajectory_sha256'][:16]}", code=f"git:{em.REPO_LABEL}@{commit}; render code sha256 {rn['render_code_sha256'][:16]}", model="none: rendering", environment="NOT RECORDED", parameters=f"{rn['frames']} frames at {rn['display_fps']} fps; transform: {rn['coordinate_transform'][:90]}", scope="visualisation of one seed"), [ev_c])
    _evidence(c, SRC, "run-md-evidence-cuda-render", cl_c, kind="simulated", relation="context_only", produced_by=ra, source=em._source(c, f"{MD}/cuda-render/render.json", c.blob(f"{MD}/cuda-render/render.json"), "Render receipt."),
              method="Producer renders the saved seed-1731 trajectory; output hashes were recomputed.", context=RENDER_NOTE + " " + em.IMPORT_NOTE, assumptions=asm, provenance=_prov(c, seed=rn["seed"], frames=rn["frames"], outputs_recomputed=sorted(rn_out)),
              limitations=[em.IMPORT_NOTE, RENDER_NOTE, NOT_CALIBRATED], artifacts=[c.artifact("output", f"{MD}/cuda-render/{n}", b, d) for n, b, d in (("trajectory.mp4", rn_out.get("trajectory.mp4"), "video of seed 1731"), ("poster.png", rn_out.get("poster.png"), "poster")) if b is not None]
              + [c.artifact("log", f"{MD}/cuda-render/render.json", c.blob(f"{MD}/cuda-render/render.json"), "render receipt")])
    return c


def _has(c: AssetChain, path: str) -> bool:
    import subprocess as sp
    return sp.run(["git", "-C", c.repo, "cat-file", "-e", f"{c.commit}:{path}"], capture_output=True).returncode == 0


LATER["md"] = md_chain
ALL_CHAINS = {**CHAINS, **LATER}


def md_continuation_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    """Three conditional 900 ps continuations (global 100 -> 1000 ps) of the three CUDA parents: ONE system, three branches, not six independent samples.

    Kept apart: the provider run, the predeclared window diagnostic (False, False, True), and the render of one branch (context only).
    """
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "md_continuation")
    v3, an_dir, rd = f"{MD}/cuda-v3", f"{MD}/continuation-analysis", f"{MD}/continuation-render"
    pr = c.jblob(f"{v3}/production/receipt.json")
    jr = c.jblob(f"{v3}/job-receipt.json")
    rv = c.jblob(f"{v3}/return-verification.json")
    proto = c.jblob(f"{MD}/continuation-protocol.json")
    an = c.jblob(f"{an_dir}/summary.json")
    anp = c.jblob(f"{an_dir}/provenance.json")
    rn = c.jblob(f"{rd}/render.json")
    runs = pr["runs"]
    c.check("runs", sorted(r["seed"] for r in runs) == [11731, 11732, 11733] and all(r["backend"] == "CUDA" and r["production_ps"] == 900.0 for r in runs), f"runs {[(r['seed'], r['backend'], r['production_ps']) for r in runs]}")
    c.check("not_independent", an["n_parent_branches"] == 3 and an["n_new_independent_biological_samples"] == 0 and "not6independent" in pr["scope"].replace(" ", ""), f"scope {pr['scope']!r}")
    flags = [b["predeclared_diagnostic"]["small_window_drift"] for b in sorted(an["branches"], key=lambda b: b["parent_seed"])]
    c.check("drift_flags", flags == [False, False, True] and an["small_window_drift_diagnostic_count"] == 1, f"flags {flags}")
    c.check("analysis.receipts", an["extension_receipt_sha256"] == hashlib.sha256(c.blob(f"{v3}/production/receipt.json")).hexdigest() and an["protocol_sha256"] == pr["protocol_sha256"], "analysis names this production receipt and protocol")
    c.check("render.receipt", rn["simulation_receipt_sha256"] == hashlib.sha256(c.blob(f"{v3}/production/receipt.json")).hexdigest() and rn["seed"] == 11731, "render names this production receipt (seed 11731 only)")
    prod = {n: c.same_hash(f"prod.{n}", f"{v3}/production/{n}", h) for n, h in pr["files"].items()}
    present = {n: c.same_hash(f"job.{n}", f"{v3}/{n}", h) for n, h in jr["files"].items() if _has(c, f"{v3}/{n}")}
    not_here = sorted(n for n in jr["files"] if n not in present)
    c.same_hash("analysis.summary", f"{an_dir}/summary.json", anp["outputs"]["summary.json"])
    c.same_hash("analysis.png", f"{an_dir}/conditional-branches.png", anp["outputs"]["conditional-branches.png"])
    rn_out = {n: c.same_hash(f"render.{n}", f"{rd}/{n}", h) for n, h in rn["outputs"].items()}
    ids = (jr["source_job_id"], rv["source_job_id"])
    lim = [em.IMPORT_NOTE, "Classical atomistic MD of a collagen-mimetic peptide; empirical accuracy UNKNOWN; cross-scale transfer UNKNOWN. " + NOT_CALIBRATED,
           "Three conditional continuations of three parents under one Hamiltonian: NOT six independent samples, and no equilibrium, folding-stability, material-modulus or biological-success probability follows.",
           "Each branch restarts from exact recorded positions and velocities with a new thermostat seed; the State XML does not preserve integrator RNG state, so this is not a bitwise replay of the parent's stochastic stream."]
    asm = [f"OpenMM {pr['openmm_version']}; continuation protocol sha256 {pr['protocol_sha256'][:16]}...; warm start sha256 {pr['warmstart_sha256'][:16]}...; no reset velocities, no minimisation, no extra thermalisation."]
    br = "; ".join(f"parent {b['parent_seed']} -> {b['new_thermostat_seed']}: final RMSD from the parent production start {b['final_original_reference_CA_RMSD_nm']:.3f} nm" for b in sorted(an["branches"], key=lambda b: b["parent_seed"]))
    cl_r = _claim(c, "run-mdc-claim-three-branches-1000ps", "Collagen-mimetic MD: three conditional continuations reached 1000 ps from the three CUDA parents",
                  f"Starting from the exact saved final states of the three 100 ps parents (seeds 1731-1733), three H100 CUDA continuations (new thermostat seeds 11731-11733) each ran {runs[0]['production_ps']:g} further ps, to a global production time of 1000 ps. {br}.",
                  "Three branches of one system, conditional on their parents. " + pr["scope"], asm, lim, f"{v3}/production/receipt.json", c.blob(f"{v3}/production/receipt.json"), "Production receipt: three CUDA continuations.")
    a1 = _action(c, SRC, "run-mdc-action-cuda-v3", cl_r, f"Provider-executed job (CUDA; {jr['GPU'].split(',')[0]}); the producer reports {rv['all_returned_job_file_hashes_independently_checked']} returned file hashes independently checked. The two receipts name different job ids ({ids[0]} in job-receipt.json, which the production receipt calls the PARENT job; {ids[1]} in return-verification.json); both are retained as found and not reconciled here",
                 [ACCEPT_REPLAY, ACCEPT_REVIEW], ["OpenMM 8.4 with CUDA on an H100"], dict(input=f"warm start sha256 {pr['warmstart_sha256']}; parent final states sha256 " + ", ".join(b["state_sha256"][:12] for b in proto["branches"]),
                 code=f"git:{em.REPO_LABEL}@{commit}; run code sha256 {pr['code_sha256'][:16]}", model="OpenMM 8.4 classical MD, CUDA mixed precision (no language model)", environment=f"python {pr['python'].split('(')[0].strip()}; numpy {pr['numpy_version']}; GPU {jr['GPU']}",
                 parameters=f"{proto['additional_production_steps']} steps at {proto['timestep_ps']} ps; {proto['temperature_K']} K; friction {proto['friction_per_ps']}/ps; new thermostat seeds 11731-11733", scope="three conditional continuations"), [])
    ev_r = _evidence(c, SRC, "run-mdc-evidence-cuda-v3", cl_r, kind="simulated", relation="unspecified", produced_by=a1, source=em._source(c, f"{v3}/production/receipt.json", c.blob(f"{v3}/production/receipt.json"), "Production receipt."),
                     method=f"Three CUDA continuations; every file hash in the production receipt was recomputed ({len(prod)} files) and so was every job-receipt hash whose file is in the checkout ({len(present)})" + (f"; {len(not_here)} job-receipt files are not in the checkout and are stated, not checked." if not_here else "."),
                     context="Applicability: this prepared system. " + em.IMPORT_NOTE, assumptions=asm, provenance=_prov(c, runs=[{k: r[k] for k in ("seed", "parent_seed", "wall_seconds", "final_CA_RMSD_nm")} for r in runs], job_ids_as_found=list(ids), files_recomputed=len(prod) + len(present), files_stated_not_checked=not_here),
                     limitations=lim, uncertainty="Three branches of one parent set; no convergence or block-averaging claim.",
                     artifacts=[c.artifact("output", f"{v3}/production/{n}", prod[n], n) for n in sorted(prod) if n.startswith(("trajectory-", "metrics-"))] + [c.artifact("log", f"{v3}/production/receipt.json", c.blob(f"{v3}/production/receipt.json"), "production receipt"),
                        c.artifact("log", f"{v3}/job-receipt.json", c.blob(f"{v3}/job-receipt.json"), "job receipt"), c.artifact("log", f"{v3}/return-verification.json", c.blob(f"{v3}/return-verification.json"), "return verification"),
                        c.artifact("protocol", f"{MD}/continuation-protocol.json", c.blob(f"{MD}/continuation-protocol.json"), "continuation protocol")])
    dg = [b["predeclared_diagnostic"] for b in sorted(an["branches"], key=lambda b: b["parent_seed"])]
    cl_d = _claim(c, "run-mdc-claim-window-diagnostic-false-false-true", "Collagen-mimetic MD: the predeclared small-window drift diagnostic read False, False, True across the three branches",
                  "Comparing the 600-800 ps and 800-1000 ps windows, the producer's predeclared small_window_drift flag is " + ", ".join(f"{b['parent_seed']}: {d['small_window_drift']} (RMSD window-mean change {d['RMSD_window_mean_change_nm']:.4f} nm, C-alpha Rg change {d['CA_Rg_window_mean_change_nm']:.4f} nm)" for b, d in zip(sorted(an["branches"], key=lambda b: b["parent_seed"]), dg))
                  + f"; {an['small_window_drift_diagnostic_count']} of {an['diagnostic_denominator']} true. Two of three are false, and they are retained.",
                  "A descriptive finite-window diagnostic. " + an["scope"], asm, lim + ["The flag is not a stability probability; even true does not establish equilibrium."], f"{an_dir}/summary.json", c.blob(f"{an_dir}/summary.json"), "Analysis summary.")
    a2 = _action(c, SRC, "run-mdc-action-window-analysis", cl_d, "Imported record of a producer-reported analysis (not re-run by Frontier); the analysis names the production receipt and protocol it read and both hashes were matched here",
                 [ACCEPT_REPLAY, ACCEPT_REVIEW], ["python3 with numpy"], dict(input=f"production receipt sha256 {an['extension_receipt_sha256']}; parent receipt sha256 {an['parent_receipt_sha256']}", code=f"git:{em.REPO_LABEL}@{commit}; analysis code sha256 {an['analysis_code_sha256'][:16]}",
                 model="none: descriptive analysis", environment="NOT RECORDED in the files read", parameters="windows 600-800 and 800-1000 ps, predeclared", scope="finite-window diagnostic"), [ev_r])
    _evidence(c, SRC, "run-mdc-evidence-window-analysis", cl_d, kind="simulated", relation="unspecified", produced_by=a2, source=em._source(c, f"{an_dir}/summary.json", c.blob(f"{an_dir}/summary.json"), "Analysis summary."),
              method="Predeclared two-window comparison per branch; output hashes were recomputed.", context="Applicability: these three branches. " + em.IMPORT_NOTE, assumptions=asm,
              provenance=_prov(c, flags=flags, n_parent_branches=an["n_parent_branches"], n_new_independent_biological_samples=an["n_new_independent_biological_samples"], biological_success_probability=an["biological_success_probability"]),
              limitations=lim, uncertainty="Windows of 22-23 samples each; no uncertainty model.", artifacts=[c.artifact("output", f"{an_dir}/summary.json", c.blob(f"{an_dir}/summary.json"), "analysis summary"), c.artifact("output", f"{an_dir}/conditional-branches.png", c.blob(f"{an_dir}/conditional-branches.png"), "branch figure")])
    ra = _action(c, SRC, "run-mdc-action-render", cl_r, "Imported record of a producer-reported render (not re-run by Frontier): video and poster of ONE branch (seed 11731) from its saved states, rigidly aligned, no deformation invented",
                 ["Re-rendering reproduces the frames; mp4 bytes can differ across ffmpeg builds.", "Pictures are views of computed states, not evidence."], ["python3 with matplotlib; ffmpeg"],
                 dict(input=f"continuation evidence version {ev_r['version']}; trajectory sha256 {rn['trajectory_sha256'][:16]}", code=f"git:{em.REPO_LABEL}@{commit}; render code sha256 {rn['render_code_sha256'][:16]}", model="none: rendering", environment="NOT RECORDED",
                 parameters=f"{rn['frames']} frames at {rn['display_fps']} fps; global time {rn['global_production_time_ps'][0]:g}-{rn['global_production_time_ps'][1]:g} ps", scope="visualisation of one branch"), [ev_r])
    _evidence(c, SRC, "run-mdc-evidence-render", cl_r, kind="simulated", relation="context_only", produced_by=ra, source=em._source(c, f"{rd}/render.json", c.blob(f"{rd}/render.json"), "Render receipt."),
              method="Producer renders the saved seed-11731 trajectory; output hashes were recomputed.", context=RENDER_NOTE + " " + em.IMPORT_NOTE, assumptions=asm, provenance=_prov(c, seed=rn["seed"], frames=rn["frames"], outputs_recomputed=sorted(rn_out)),
              limitations=[em.IMPORT_NOTE, RENDER_NOTE, NOT_CALIBRATED, "One of three branches is shown."], artifacts=[c.artifact("output", f"{rd}/{n}", rn_out[n], d) for n, d in (("trajectory.mp4", "video of branch 11731"), ("poster.png", "poster"))]
              + [c.artifact("log", f"{rd}/render.json", c.blob(f"{rd}/render.json"), "render receipt")])
    return c


LATER["md_continuation"] = md_continuation_chain
ALL_CHAINS = {**CHAINS, **LATER}


# ---------------------------------------------------------------------------------------------------------------- manufacturer material cards
MAT = "data/materials"
MAT_PROPS = ("solid_density_kg_m3", "liquid_density_kg_m3_not_for_part_mass", "tensile_modulus_Pa", "flexural_modulus_Pa", "ultimate_tensile_strength_Pa", "elongation_at_break_fraction")


def materials_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    """Manufacturer-reported photopolymer properties as CONDITIONAL source claims. Source assessments, no Action: Frontier measured nothing.

    The three Alpha cards carry a recorded sha256 of the manufacturer HTML the producer downloaded; those bytes are not in the repository, so the hashes are
    carried, not recomputed. The Tough 1500 V2 card has NO source hash and is Form 4 data of unestablished applicability to Form Studio 1.
    """
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "materials")
    cards = c.jblob(f"{MAT}/formlabs-studio-2026-10-31.json")
    chk = c.jblob(f"{MAT}/source-cell-check.json")
    c.check("cards.schema", cards["schema"] == "frontier.manufacturing.material-cards/1" and cards["evidence_kind"] == "manufacturer_reported_material_tests", f"schema {cards['schema']!r}")
    c.check("check.binds_cards", chk["material_cards_sha256"] == hashlib.sha256(c.blob(f"{MAT}/formlabs-studio-2026-10-31.json")).hexdigest(), "source-cell-check names these exact cards bytes")
    by = {m["id"]: m for m in cards["materials"]}
    alpha = [m for m in cards["materials"] if m["source_sha256"]]
    c.check("hashed_sources", len(alpha) == 3 and all(m["id"].startswith("alpha-") for m in alpha) and by["tough1500-v2-form4-reference-only"]["source_sha256"] is None, f"hashed {[m['id'] for m in alpha]}")
    c.check("cells", len(chk["checks"]) == 18 and {x["material"] for x in chk["checks"]} == {m["id"] for m in alpha}, f"{len(chk['checks'])} cells over {sorted({x['material'] for x in chk['checks']})}")
    for x in chk["checks"]:
        c.check(f"cell.{x['material']}.{x['property']}", x["property"] in MAT_PROPS and by[x["material"]][x["property"]] == x["converted_value"], f"card {by[x['material']].get(x['property'])!r} vs converted {x['converted_value']!r}")
    c.check("no_measurements", all(m["measured_print_mass_kg"] is None and m["thin_fin_coupon_result"] is None for m in cards["materials"]), "no measured print mass or fin coupon recorded in any card")
    lim_all = [em.IMPORT_NOTE, cards["scope"]] + cards["limitations"]
    art = lambda: [c.artifact("input", f"{MAT}/formlabs-studio-2026-10-31.json", c.blob(f"{MAT}/formlabs-studio-2026-10-31.json"), "material cards"),  # noqa: E731
                   c.artifact("log", f"{MAT}/source-cell-check.json", c.blob(f"{MAT}/source-cell-check.json"), "18 source cells and their unit conversions")]
    def mpa(v):
        return f"{v/1e6:g} MPa"
    for m in cards["materials"]:
        tough = m["source_sha256"] is None
        short = m["id"].split("-v")[0]
        stmt = (f"{m['name']} ({m['material_code']}, source revision {m['source_revision']}): the manufacturer reports solid density {m['solid_density_kg_m3']} kg/m3, tensile modulus {mpa(m['tensile_modulus_Pa'])}, flexural modulus {mpa(m['flexural_modulus_Pa'])}, "
                f"ultimate tensile strength {mpa(m['ultimate_tensile_strength_Pa'])} and elongation at break {m['elongation_at_break_fraction']*100:g}% under: {m['test_conditions']}")
        cond = ("Conditional on the manufacturer's test conditions (" + m["printer"] + "). " + ("Studio applicability is NOT established: " + m["studio_applicability"]["reason"] if tough else "Form Studio 1 data sheet default post-cure column."))
        asm = [f"Methods: density {m['methods']['density']}, tensile {m['methods']['tensile']}, flexural {m['methods']['flexural']}.", f"Liquid resin density {m['liquid_density_kg_m3_not_for_part_mass']} kg/m3 is recorded and excluded from part mass."]
        cl = _claim(c, f"run-materials-claim-{short}", f"{m['name']}: manufacturer-reported properties under stated cure conditions" + (" (Form 4 reference only)" if tough else ""), stmt, cond, asm, lim_all + ["No Frontier measurement of a coupon, fin, print mass or flight exists for this material."],
                    f"{MAT}/formlabs-studio-2026-10-31.json", c.blob(f"{MAT}/formlabs-studio-2026-10-31.json"), "Material card.")
        src_hash = ("NO source sha256 recorded: the PDF text was read through a web tool and no local byte hash was collected" if tough else f"source sha256 {m['source_sha256']} recorded by the producer; the manufacturer HTML bytes are retained outside the repository, so this adapter did not recompute it")
        _evidence(c, SRC, f"run-materials-evidence-{short}", cl, kind="source_assessment", relation=("qualifies" if tough else "supports"), produced_by=None,
                  source=em._source(c, f"{MAT}/formlabs-studio-2026-10-31.json", c.blob(f"{MAT}/formlabs-studio-2026-10-31.json"), "Material card."),
                  method=(f"The producer read the manufacturer data sheet ({m['source_url']}) at {m['source_locator']}. " + ("" if tough else "Six named cells were checked against the card and their unit conversions recomputed by this adapter. ") + src_hash + ". No simulator or test ran."),
                  context="A manufacturer-reported source assessment, not a Frontier measurement and not a specimen-level distribution. " + em.IMPORT_NOTE, assumptions=asm,
                  provenance=_prov(c, material=m["id"], source_url=m["source_url"], source_sha256=m["source_sha256"], source_bytes_in_repository=False, cells_checked=0 if tough else 6, studio_applicability=m.get("studio_applicability"), read_date=cards["read_date"]),
                  limitations=lim_all, artifacts=art(), uncertainty="No interval is given by the source for these cells; specimen variability is not available.")
    return c


LATER["materials"] = materials_chain
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
