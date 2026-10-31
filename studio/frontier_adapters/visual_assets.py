"""Visual-asset manifests (glide video, reaction-diffusion video, printable form studies) -> PROPOSED Claim / Action / Evidence drafts.

The point: every picture, video and mesh is tied to the Claim it depicts through an Evidence record, and the computation that made the
numbers is a DIFFERENT Action from the one that drew them.

  Claim  <-  Evidence (simulated|formal, relation unspecified)  <- Action "compute"   : the numbers
  Claim  <-  Evidence (simulated, relation context_only)         <- Action "render"    : the picture / mesh, inputs = the compute Evidence

Rules this module enforces (each has a must-fail control in tests/test_visual_assets.py):
  * Rendering is never support. Every render / build Evidence has relation `context_only`. Nothing here sets `supports`, `reproduces`
    or any relation for a picture. A video of a simulation adds no evidence for the Claim.
  * Every hash the producer states is RECOMPUTED from an immutable git blob; a mismatch refuses the chain. Hashes the producer states
    but whose bytes are not in the commit (e.g. the glide PNG frames) are recorded as "stated, not verifiable here".
  * Pointers are `urn:sha256:` with availability `referenced`. No hosted URL is emitted: a URL needs the byte mapping (served bytes
    hash to the stated sha256) and a stated licence, and root's media resolver is not in this module's inputs.
  * Imported Actions record what the producer reports. They are not executed by Frontier. The one exception is the optional glide
    REPLAY, which this adapter really runs (bounded, numpy only) and records with its command, exit code and numbers.
  * Printer, resin and slicing are UNKNOWN in the producer's material and stay unknown. Forms are engineered illustrations.

Reads git blobs only (`git cat-file`); never the working tree; never writes to a store. Importing is `import_cli`'s job.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

from . import engineering_manifest as em
from .artifacts import find_abs_paths
from .common import sha_bytes, sha_obj, validate_draft

ADAPTER_ID = "frontier_adapters.visual_assets"
ADAPTER_VERSION = "0.1.0"
REPO_LABEL = em.REPO_LABEL
Refused = em.Refused
SIM = "engineering/simulation"
PRINT = "artifacts/print"
MEDIA_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".mp4", ".webm", ".mov", ".glb", ".gltf", ".stl", ".3mf", ".obj")
RENDER_NOTE = ("A picture, video or mesh of what was computed. It adds no support for the Claim and is not an independent check of it; "
               "rendering it successfully says nothing about whether the model is right.")


class AssetChain(em.Chain):
    """market's Chain with a larger record cap (several forms per bundle). Checks, blobs and artifact pointers are inherited."""
    max_records = 100

    def add(self, draft: dict) -> dict:
        if len(self.records) >= self.max_records:
            raise Refused(f"[{self.name}] more than {self.max_records} records")
        bad = find_abs_paths(draft)
        if bad:
            raise Refused(f"[{self.name}] absolute local path in a draft at {bad}")
        v = validate_draft(draft, self.created_at)
        if v["licence_gate_offenders"]:
            raise Refused(f"[{self.name}] store licence gate would refuse: {v['licence_gate_offenders']}")
        self.records.append(v["record"])
        return {k: v["record"][k] for k in ("namespace", "kind", "id", "version")}


def _prov(c: AssetChain, **kw) -> dict:
    return {"adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION}, "source_commit": c.commit,
            "execution": "reported by the producer; not executed or replayed by this adapter unless a replay Evidence says so", **kw}


def _action(c, src, id_, target, title, criteria, caps, ck, inputs):
    return c.add(c.draft("Action", id_, {
        "target": target, "title": title, "acceptance_criteria": criteria, "required_capabilities": caps,
        "cost_stop_bounds": "Wall time and resources of the producer's run are NOT recorded. No budget or stop bound was declared.",
        "cache_key": em._cache_key(target["version"], **ck), "inputs": inputs}, src))


def _evidence(c, src, id_, target, *, kind, relation, produced_by, source, method, context, assumptions, provenance, limitations, artifacts,
              uncertainty="Not quantified by the producer beyond what its record states."):
    created, retrieved = em._time(c)
    return c.add(c.draft("Evidence", id_, {
        "target": target, "evidence_kind": kind, "source": source, "created_time": created, "retrieved_time": retrieved,
        "method": method, "context": context, "assumptions": assumptions, "provenance": provenance,
        "source_dependence": {"declared": True, "group": "same producer made the claim, the numbers and the picture", "independent_of_claim": False},
        "uncertainty": uncertainty, "limitations": limitations, "local_id": None, "provider_assessment": None,
        "relation": relation, "produced_by": produced_by, "artifacts": artifacts}, src))


# ------------------------------------------------------------------------------------------------------------------ glide
GLIDE_CODE = ("animate_glide.py", "glide.py", "controlled.py", "evaluate.py", "schema.py", "__init__.py")


def replay_glide(repo: str, commit: str, *, timeout: int = 180) -> dict:
    """REALLY run the producer's numeric build() from the pinned blobs in a throwaway directory (numpy only, one thread, bounded).

    Returns {command, exit, numpy, seconds, candidates, ...}. Frames and video are NOT rendered. The caller compares `candidates` to the manifest.
    """
    import time
    with tempfile.TemporaryDirectory() as d:
        for rel in [f"{SIM}/{n}" for n in GLIDE_CODE] + ["engineering/__init__.py"]:
            dst = os.path.join(d, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as fh:
                fh.write(em.git_blob(repo, commit, rel))
        code = ("import json,sys\nsys.path.insert(0,'.')\nimport numpy as np\n"
                "from engineering.simulation import animate_glide as a\n"
                "cs=a.build()\n"
                "keys=('name','fS','fAR','m','S','b','AR','CL','range_nominal','time_nominal','V_stall')\n"
                "out=[{k:(float(c[k]) if k!='name' else c[k]) for k in keys}|{'mc_range_q10_q50_q90':[float(x) for x in np.quantile(c['mc_range'],[.1,.5,.9])]} for c in cs]\n"
                "print(json.dumps({'numpy':np.__version__,'candidates':out}))\n")
        cmd = [sys.executable, "-I", "-c", code]
        env = {"PATH": os.environ.get("PATH", ""), "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MPLBACKEND": "Agg", "PYTHONDONTWRITEBYTECODE": "1",
               "MPLCONFIGDIR": d}
        t0 = time.time()
        p = subprocess.run(cmd, cwd=d, env=env, capture_output=True, text=True, timeout=timeout)
        secs = time.time() - t0
        rep = {"command": "python -I -c 'from engineering.simulation import animate_glide as a; a.build()' (pinned blobs extracted to a throwaway directory; nothing rendered)",
               "exit": p.returncode, "seconds": round(secs, 2), "python": sys.version.split()[0], "threads": 1}
        if p.returncode != 0:
            rep["stderr_tail"] = p.stderr[-300:]
            return rep
        rep.update(json.loads(p.stdout.strip().splitlines()[-1]))
        return rep


def compare_glide(manifest_candidates: list[dict], replayed: list[dict]) -> dict:
    """Numeric comparison of the replay with the manifest. Reports the largest relative difference and whether every value is identical."""
    if len(manifest_candidates) != len(replayed):
        return {"compared": 0, "identical": False, "reason": "candidate counts differ"}
    worst, ident, n = 0.0, True, 0
    for m, r in zip(manifest_candidates, replayed):
        if m["name"] != r["name"]:
            return {"compared": n, "identical": False, "reason": f"candidate names differ: {m['name']!r} vs {r['name']!r}"}
        for k, v in m.items():
            if k == "name":
                continue
            a, b = (v if isinstance(v, list) else [v]), (r[k] if isinstance(r[k], list) else [r[k]])
            for x, y in zip(a, b):
                n += 1
                ident &= (x == y)
                worst = max(worst, abs(x - y) / max(abs(x), 1e-300))
    return {"compared": n, "identical": ident, "max_relative_difference": worst}


def glide_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None, replay: dict | None = None) -> AssetChain:
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "glide_video")
    vdir = f"{SIM}/video"
    man = c.jblob(f"{vdir}/manifest.json")
    c.check("manifest.kind", man.get("kind") == "glide trajectory animation" and man.get("evidence_kind") == "simulated", f"kind {man.get('kind')!r} evidence_kind {man.get('evidence_kind')!r}")
    mp4 = c.same_hash("video.mp4", f"{vdir}/{man['video']}", man["video_sha256"])
    poster = c.same_hash("video.poster", f"{vdir}/{man['poster']}", man["poster_sha256"])
    c.check("video.bytes", len(mp4) == man["video_bytes"], f"manifest {man['video_bytes']} bytes, blob {len(mp4)}")
    c.check("video.frames", man["frames"] == man["fps"] * round(man["duration_video_s"]) and man["ffmpeg_exit"] == 0, f"{man['frames']} frames, {man['fps']} fps, {man['duration_video_s']} s, ffmpeg exit {man['ffmpeg_exit']}")
    code = {n: c.blob(f"{SIM}/{n}") for n in GLIDE_CODE}
    c.same_hash("code.animate_glide", f"{SIM}/animate_glide.py", man["code"]["sha256"])
    manifest_bytes = c.blob(f"{vdir}/manifest.json")
    cands = man["candidates"]
    cand_bytes = json.dumps(cands, sort_keys=True, separators=(",", ":")).encode()
    c.check("polar.is_assumption", man["polar_status"].startswith("design assumption"), man["polar_status"])
    c.check("candidates.count", len(cands) == 3, f"{len(cands)} candidates")
    src = "urn:frontier:adapter:visual-assets:glide-video"
    pol, rel, mc = man["polar"], man["release"], man["mc"]
    rng = "; ".join(f"{k['name']}: nominal range {k['range_nominal']:.2f} m, MC q10/q50/q90 {k['mc_range_q10_q50_q90'][0]:.1f}/{k['mc_range_q10_q50_q90'][1]:.1f}/{k['mc_range_q10_q50_q90'][2]:.1f} m" for k in cands)
    not_est = list(man["not_established"])
    lim = [em.IMPORT_NOTE, "The lift/drag polar is a DESIGN ASSUMPTION, not a measured fish polar.", f"Monte Carlo bands are over declared prior ranges (n={mc['n']}, seed {mc['seed']}), not over data."] + [f"Producer states it does not establish: {x}" for x in not_est]
    assumptions = [f"Point-mass glide, release {rel['V0_ms']} m/s at {rel['h0_m']} m, level, same for every candidate.", f"Polar CL_max {pol['CL_max']}, CD0 {pol['CD0']}, e {pol['e']} (design assumption).",
                   "Glide seconds are physical trajectory time and are unrelated to reaction-diffusion model time."]
    claim = c.add(c.draft("Claim", "viz-glide-claim-fixed-launch-ranges", {
        "title": "Fixed-launch glide ranges of three wing geometries in a point-mass model with an assumed polar",
        "statement": f"In the producer's point-mass glide model with the assumed polar above, released at {rel['V0_ms']} m/s from {rel['h0_m']} m, the computed nominal ranges are: {rng}.",
        "context": "Producer-derived numbers from a deterministic integration on DECLARED coefficients. The ranking among geometries is not robust: the producer states it flips with release speed.",
        "assumptions": assumptions, "limitations": lim,
        "source": em._source(c, f"{vdir}/manifest.json", manifest_bytes, "Claim numbers are the manifest's candidates block."),
        "source_record_version": None, "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "derived"}, src))
    act_sim = _action(c, src, "viz-glide-action-sim", claim,
                      "Imported record of a producer-reported run (NOT executed by Frontier): point-mass glide integration with Monte Carlo over declared polar priors",
                      ["A clean re-execution of build() from the pinned code reproduces the candidates block of the manifest.", "An independent reviewer checks the model and the assumed polar before the numbers are used for anything."],
                      ["python3 with numpy"],
                      dict(input=f"release {rel}; polar {pol}; priors {mc['priors']}", code=f"git:{REPO_LABEL}@{commit}; animate_glide.py {man['code']['sha256'][:16]} ; glide.py {sha_bytes(code['glide.py'])[:16]}",
                           model="glide-pointmass (deterministic point-mass integrator; no language model)", environment="NOT RECORDED by the producer (numpy version, interpreter)",
                           parameters=f"MC n={mc['n']} seed={mc['seed']}", scope="simulated surrogate on declared coefficients; not a measurement"), [])
    ev_sim = _evidence(c, src, "viz-glide-evidence-sim", claim, kind="simulated", relation="unspecified", produced_by=act_sim,
                       source=em._source(c, f"{vdir}/manifest.json", manifest_bytes, "Numeric results live in the candidates block of the video manifest."),
                       method="Producer's point-mass glide integration with a Monte Carlo band over declared polar priors; numbers read from the manifest's candidates block.",
                       context="Applicability: this surrogate with these assumed coefficients. " + em.IMPORT_NOTE, assumptions=assumptions,
                       provenance=_prov(c, polar=pol, mc=mc, code_hashes={k: sha_bytes(v) for k, v in code.items()}),
                       limitations=lim + ["The numeric output has no file of its own: it is embedded in the video manifest. The output artifact below is the canonical JSON of that block, derived by this adapter."],
                       artifacts=[c.artifact("output", f"{vdir}/manifest.json", cand_bytes, "canonical JSON of the manifest's candidates block (derived bytes; recompute from manifest.json)"),
                                  c.artifact("code", f"{SIM}/glide.py", code["glide.py"]), c.artifact("code", f"{SIM}/animate_glide.py", code["animate_glide.py"])])
    if replay is not None:
        # A replay that did not run is NOT evidence of anything: refuse rather than record an Action/Evidence for an execution that never happened.
        c.check("replay.ran", replay.get("exit") == 0 and bool(replay.get("candidates")), f"replay exit {replay.get('exit')!r}; {str(replay.get('stderr_tail', ''))[-160:]!r}")
        cmp_ = compare_glide(cands, replay["candidates"])
        report = json.dumps({"replay": {k: v for k, v in replay.items() if k != "candidates"}, "comparison": cmp_}, sort_keys=True, indent=1).encode()
        act_rep = _action(c, src, "viz-glide-action-replay", claim,
                          "Local replay executed by the corpus adapter (bounded, numpy only, one thread): build() from the pinned blobs; no frames, no video",
                          ["The replayed candidates equal the manifest's candidates block."], ["python3 with numpy"],
                          dict(input=f"pinned blobs at {commit}", code=f"git:{REPO_LABEL}@{commit}; animate_glide.py {man['code']['sha256'][:16]}", model="none",
                               environment=f"python {replay.get('python')}, numpy {replay.get('numpy')}, {replay.get('threads')} thread", parameters="as pinned; nothing overridden",
                               scope="numeric reproduction only"), [ev_sim])
        _evidence(c, src, "viz-glide-evidence-replay", claim, kind="simulated", relation="reproduces" if cmp_.get("identical") else "unspecified", produced_by=act_rep,
                  source=em._source(c, f"{vdir}/manifest.json", manifest_bytes, "Compared with the manifest's candidates block."),
                  method="Re-ran the producer's numeric build() and compared every candidate number with the manifest.",
                  context=f"Compared {cmp_.get('compared')} numbers; identical: {cmp_.get('identical')}; largest relative difference {cmp_.get('max_relative_difference')}. A reproduction of the producer's own computation, not an independent check of the model.",
                  assumptions=assumptions, provenance=_prov(c, execution="executed by this adapter", replay={k: v for k, v in replay.items() if k != "candidates"}, comparison=cmp_),
                  limitations=lim + ["Same code and same assumptions: reproducibility, not validity."],
                  artifacts=[c.artifact("log", f"{vdir}/manifest.json", report, "replay report: command, exit code, versions, comparison (derived bytes)")])
    act_rend = _action(c, src, "viz-glide-action-render", claim,
                       "Imported record of a producer-reported render (NOT executed by Frontier): matplotlib frames and an ffmpeg encode of the computed trajectories",
                       ["Re-rendering from the pinned code reproduces the frames; mp4 bytes can differ across ffmpeg builds.", "The video is read as a picture of computed trajectories, not as evidence."],
                       ["python3 with numpy and matplotlib; ffmpeg"],
                       dict(input=f"simulation evidence version {ev_sim['version']}", code=f"git:{REPO_LABEL}@{commit}; animate_glide.py {man['code']['sha256'][:16]}", model="none: deterministic rendering",
                            environment="NOT RECORDED by the producer (ffmpeg build, matplotlib, fonts)", parameters=f"{man['frames']} frames, {man['fps']} fps, {man['resolution'][0]}x{man['resolution'][1]}; {man['ffmpeg_cmd'][:200]}",
                            scope="visualisation of a simulated surrogate"), [ev_sim])
    _evidence(c, src, "viz-glide-evidence-render", claim, kind="simulated", relation="context_only", produced_by=act_rend,
              source=em._source(c, f"{vdir}/manifest.json", manifest_bytes, "Render manifest."),
              method=f"Producer draws {man['frames']} frames from the integrated trajectories and encodes them with ffmpeg (exit {man['ffmpeg_exit']}).",
              context=RENDER_NOTE + " " + em.IMPORT_NOTE, assumptions=assumptions,
              provenance=_prov(c, frames_sha256_of_first_middle_last=man["frames_sha256_of_first_middle_last"], frames_note="the PNG frames are not in the commit; these three hashes are stated by the producer and cannot be checked here",
                               time_units=man["time_units"]),
              limitations=[em.IMPORT_NOTE, RENDER_NOTE, "Creation time and order relative to the simulation are not recorded; the Actions are separate because the code paths and outputs are."],
              artifacts=[c.artifact("output", f"{vdir}/{man['video']}", mp4, "video of the computed trajectories; bytes can vary with the ffmpeg build"),
                         c.artifact("output", f"{vdir}/{man['poster']}", poster, "poster image (last frame)"),
                         c.artifact("log", f"{vdir}/manifest.json", manifest_bytes, "producer manifest with output hashes, ffmpeg command and exit code"),
                         c.artifact("code", f"{SIM}/animate_glide.py", code["animate_glide.py"])])
    return c


# ------------------------------------------------------------------------------------------------------------------ RD
def rd_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "rd_video")
    vdir, rdir = f"{SIM}/video", f"{SIM}/rd"
    man = c.jblob(f"{vdir}/manifest_rd.json")
    rec = c.jblob(f"{rdir}/receipt.json")
    c.check("manifest.kind", man.get("kind") == "RD field time-series animation" and man.get("evidence_kind") == "simulated", f"kind {man.get('kind')!r}")
    mp4 = c.same_hash("video.mp4", f"{vdir}/{man['video']}", man["video_sha256"])
    poster = c.same_hash("video.poster", f"{vdir}/{man['poster']}", man["poster_sha256"])
    receipt_b = c.same_hash("receipt", f"{rdir}/receipt.json", man["receipt_sha256"])
    cells_b = c.same_hash("cells.json", f"{rdir}/cells.json", rec["cells_json_sha256"])
    rd_code = c.same_hash("code.rd_frames", f"{SIM}/rd_frames.py", rec["code_sha256"])
    anim_b = c.same_hash("code.animate_rd", man["code"]["module"], man["code"]["sha256"])
    c.check("source.agree", man["source"] == rec["source"], "video manifest and rerun receipt cite the same sweep source")
    cells_by = {x["cell_id"]: x for x in rec["cells"]}
    src = "urn:frontier:adapter:visual-assets:rd-video"
    manifest_b = c.blob(f"{vdir}/manifest_rd.json")
    s = rec["source"]
    for mc in man["cells"]:
        cid = mc["cell_id"]
        rc = cells_by[cid]
        c.check(f"cell{cid}.agree", mc["frames_sha256"] == rc["frames_sha256"] and mc["reproduces_frozen_row"] == rc["reproduces_frozen_row"], "manifest and receipt agree on frames hash and reproduction flag")
        frames = c.same_hash(f"cell{cid}.frames", f"{rdir}/{rc['frames_file']}", rc["frames_sha256"])
        fz = rc["frozen_sweep_row_A"]
        lim = [em.IMPORT_NOTE, "A model-internal outcome of a declared reaction-diffusion model; no biological or fin-tissue mechanism is established.",
               "The frozen sweep rows live in another repository; rows_sha256 below is stated by the producer and not recomputed here."] + [f"Producer states it does not establish: {x}" for x in man["not_established"]]
        assumptions = [f"Zero-flux 1-D, solver A; protocol {s['protocol']}.", f"T_tau {rc['T_tau']}, dt_tau {rc['dt_tau']}, N {rc['N']}, saved every {rc['save_every_tau']} tau.", "tau is dimensionless model time, unrelated to glide seconds."]
        claim = c.add(c.draft("Claim", f"viz-rd-claim-cell-{cid}", {
            "title": f"Reaction-diffusion sweep cell {cid}: {rc['label'][:120]}",
            "statement": (f"In the producer's declared 1-D zero-flux reaction-diffusion sweep (cell {cid}), the rerun gives dominant mode {rc['rerun_final']['mode']} with amplitude {rc['rerun_final']['amp_std_u']:.6g}; "
                          f"the frozen sweep row A states mode {fz['mode']}, amplitude {fz['amp']:.6g}, pattern {fz['pattern']}, settled {fz['settled']}. Cell label: {rc['label']}."),
            "context": "Producer-derived model outcome on declared parameters; says what the declared model does, not what any tissue does.",
            "assumptions": assumptions, "limitations": lim,
            "source": em._source(c, f"{rdir}/receipt.json", receipt_b, f"Cell {cid} entry of the rerun receipt."),
            "source_record_version": None, "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "derived"}, src))
        act_sim = _action(c, src, f"viz-rd-action-sim-{cid}", claim,
                          f"Imported record of a producer-reported run (NOT executed by Frontier): rerun of sweep cell {cid} saving field frames",
                          ["A clean re-execution from the pinned code and cells.json reproduces the frames file hash and the frozen row.", "An independent reviewer checks the model before the outcome is used for anything."],
                          ["python3 with numpy; the pde solver vendored in the producer repository"],
                          dict(input=f"cells.json sha256 {rec['cells_json_sha256']}; cell {cid}", code=f"git:{REPO_LABEL}@{commit}; rd_frames.py {rec['code_sha256'][:16]}", model="reaction-diffusion solver A (deterministic; no language model)",
                               environment="NOT RECORDED by the producer", parameters=f"T_tau {rc['T_tau']}, dt_tau {rc['dt_tau']}, N {rc['N']}", scope=f"model outcome; rerun {rc['seconds']:.2f} s reported by the producer"), [])
        ev_sim = _evidence(c, src, f"viz-rd-evidence-sim-{cid}", claim, kind="simulated", relation="unspecified", produced_by=act_sim,
                           source=em._source(c, f"{rdir}/receipt.json", receipt_b, "Rerun receipt."),
                           method=f"Producer reran cell {cid} with solver A and compared with the frozen sweep row: reproduces_frozen_row {rc['reproduces_frozen_row']}, relative amplitude difference {rc['relative_amp_difference']:.3g}.",
                           context="Applicability: the declared model only. " + em.IMPORT_NOTE, assumptions=assumptions,
                           provenance=_prov(c, sweep_source=s, rows_sha256_note="stated by the producer; the rows are in another repository and were not recomputed here"),
                           limitations=lim, artifacts=[c.artifact("output", f"{rdir}/{rc['frames_file']}", frames, f"saved field frames of cell {cid} (npz)"),
                                                       c.artifact("input", f"{rdir}/cells.json", cells_b, "cell definitions"), c.artifact("log", f"{rdir}/receipt.json", receipt_b, "rerun receipt"),
                                                       c.artifact("code", f"{SIM}/rd_frames.py", rd_code)])
        act_rend = _action(c, src, f"viz-rd-action-render-{cid}", claim,
                           f"Imported record of a producer-reported render (NOT executed by Frontier): field animation drawn from the saved frames (one video shows both cells)",
                           ["Re-rendering from the pinned code and the frames file reproduces the frames; mp4 bytes can differ across ffmpeg builds.", "The video is read as a picture of computed fields, not as evidence."],
                           ["python3 with numpy and matplotlib; ffmpeg"],
                           dict(input=f"simulation evidence version {ev_sim['version']}; frames {rc['frames_sha256']}", code=f"git:{REPO_LABEL}@{commit}; animate_rd.py {man['code']['sha256'][:16]}", model="none: deterministic rendering",
                                environment="NOT RECORDED by the producer", parameters=f"{man['frames']} frames, {man['fps']} fps; {man['ffmpeg_cmd'][:200]}", scope="visualisation of a simulated model"), [ev_sim])
        _evidence(c, src, f"viz-rd-evidence-render-{cid}", claim, kind="simulated", relation="context_only", produced_by=act_rend,
                  source=em._source(c, f"{vdir}/manifest_rd.json", manifest_b, "Render manifest."),
                  method=f"Producer draws {man['frames']} frames ({rc['n_frames']} saved states per cell, no interpolation) and encodes with ffmpeg (exit {man['ffmpeg_exit']}).",
                  context=RENDER_NOTE + " The same video shows both cells; which part belongs to this cell is not recorded in the manifest. " + em.IMPORT_NOTE, assumptions=assumptions,
                  provenance=_prov(c, time_units=man["time_units"]), limitations=[em.IMPORT_NOTE, RENDER_NOTE],
                  artifacts=[c.artifact("output", f"{vdir}/{man['video']}", mp4, "video of both cells' computed fields; bytes can vary with the ffmpeg build"),
                             c.artifact("output", f"{vdir}/{man['poster']}", poster, "poster image"),
                             c.artifact("log", f"{vdir}/manifest_rd.json", manifest_b, "producer manifest with output hashes and ffmpeg command"),
                             c.artifact("code", man["code"]["module"], anim_b)])
    return c


# ------------------------------------------------------------------------------------------------------------------ print forms
def print_forms_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None, forms: list[str] | None = None) -> AssetChain:
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "print_forms")
    man = c.jblob(f"{PRINT}/manifest.json")
    c.check("manifest.schema", man.get("schema") == "frontier.print.manifest/2", f"schema {man.get('schema')!r}")
    pr = man["printer_resin"]
    c.check("printer.unknown", pr.get("printer") == "unknown" and pr.get("resin") == "unknown", f"printer {pr.get('printer')!r}, resin {pr.get('resin')!r}: kept as unknown")
    blobs = {}
    for rel, stated in man["files"].items():                                   # EVERY file the manifest lists
        blobs[rel] = c.same_hash(f"file.{rel}", f"{PRINT}/{rel}", stated)
    manifest_b = c.blob(f"{PRINT}/manifest.json")
    src = "urn:frontier:adapter:visual-assets:print-forms"
    run = man["run"]
    chosen = forms or sorted(man["forms"])
    for fid in chosen:
        f = man["forms"][fid]
        design = json.loads(blobs[f["design"]])
        solver_rel = f"solver/{fid}.solver.json"
        sol = json.loads(blobs[solver_rel])["default"]
        c.check(f"{fid}.stl", sha_bytes(blobs[f"stl/{fid}.stl"]) == f["stl_sha256"], "form stl_sha256 equals the listed STL file")
        c.check(f"{fid}.solver_status", sol["status"] == f["solver"], f"solver file {sol['status']!r}, manifest {f['solver']!r}")
        c.check(f"{fid}.valid", f["valid"] is True and f["stand_valid"] is True, f"mesh valid {f['valid']}, stand valid {f['stand_valid']}")
        if sol["status"] == "feasible":
            outcome = "feasible; witness " + ", ".join(f"{k}={v}" for k, v in sorted(sol["witness"].items()))
        else:
            outcome = "unsat; minimal conflicting constraints " + ", ".join(sol["conflict"])
        not_checked = [str(x) for x in (design.get("not_checked") or [])]
        lim = [em.IMPORT_NOTE, man["label"], "Printer, resin and slicing are UNKNOWN; nothing was sliced, loaded into PreForm or printed.", "z3 verdict re-checked by z3 only; no independent proof object (producer's wording)." if sol["status"] == "unsat" else "The z3 witness was re-checked exactly by the producer's own code, not independently.",
               "Constraint satisfaction on a declared constraint set says nothing about whether the form flies or is biologically viable."] + [f"Producer lists as not checked: {x}" for x in not_checked]
        assumptions = [f"Declared constraints used: {', '.join(sol['used_constraints'])}.", "Level-flight lift proxy with a caller-set CL; not a statement that flight or gliding is feasible."]
        claim = c.add(c.draft("Claim", f"viz-form-claim-{fid}", {
            "title": f"Declared-constraint check for printable form {fid}: {design.get('title', fid)}",
            "statement": f"For the declared constraint set of design {fid} ({design.get('role', '')}), the producer's z3 solver reports {outcome}. The mesh built from this design is reported valid ({f['bounds_mm']} mm bounds, volume {f['volume_mm3']:.1f} mm^3).",
            "context": "An engineered illustrative form, not an ancestor, a viable organism or a flight-tested design. This Claim concerns the producer's own constraint set only.",
            "assumptions": assumptions, "limitations": lim,
            "source": em._source(c, f"{PRINT}/{solver_rel}", blobs[solver_rel], "Solver result file for this form."),
            "source_record_version": None, "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "derived"}, src))
        act_solve = _action(c, src, f"viz-form-action-solve-{fid}", claim,
                            "Imported record of a producer-reported solve (NOT executed by Frontier): z3 constraint check of the declared design",
                            ["A clean re-execution from the pinned solver and the design file reproduces the solver result file.", "An independent reviewer checks the constraint set against the claim."],
                            ["python3 with z3-solver " + str(run["libraries"].get("z3-solver"))],
                            dict(input=f"design {f['design']} sha256 {man['files'][f['design']][:16]}", code=f"solver blob {run['solver']['blob_sha256'][:16]} ({run['solver']['path']} at {run['solver']['commit'][:12]} on {run['solver']['branch']}); staged outside the repo: {run['solver']['staged_outside_repo']}",
                                 model="z3-nlsat-tracked v1 (SMT solver; no language model)", environment="z3 " + str(sol["z3_version"]) + "; other versions " + json.dumps(run["libraries"], sort_keys=True),
                                 parameters=f"launch speed query {run['launch_speed_query_m_s']} m/s; box {run['box_mm']} mm", scope="declared constraint set only"), [])
        ev_solve = _evidence(c, src, f"viz-form-evidence-solve-{fid}", claim, kind="formal", relation="unspecified", produced_by=act_solve,
                             source=em._source(c, f"{PRINT}/{solver_rel}", blobs[solver_rel], "Solver result."),
                             method=f"z3 constraint check ({sol['solver']}, z3 {sol['z3_version']}): status {sol['status']}; reason: {sol['reason'] or 'none given'}",
                             context="Applicability: the declared constraint set. " + em.IMPORT_NOTE, assumptions=assumptions,
                             provenance=_prov(c, solver_result={k: sol[k] for k in ("status", "solver", "z3_version", "used_constraints", "conflict", "core_minimal", "lean", "checks")}),
                             limitations=lim, artifacts=[c.artifact("output", f"{PRINT}/{solver_rel}", blobs[solver_rel], "solver result"),
                                                         c.artifact("input", f"{PRINT}/{f['design']}", blobs[f["design"]], "design file with the declared parameters and constraints")])
        act_build = _action(c, src, f"viz-form-action-build-{fid}", claim,
                            "Imported record of a producer-reported geometry build (NOT executed by Frontier): mesh, stand, GLB and PNG renders from the design",
                            ["Rebuilding with the pinned library versions reproduces the files byte for byte (the producer states two consecutive builds were identical).", "Meshes and images are read as views of a design, not as evidence."],
                            ["python3 with manifold3d, trimesh, numpy, matplotlib (versions in the manifest)"],
                            dict(input=f"solver evidence version {ev_solve['version']}; design {f['design']}", code=f"engineering/geometry build; run code_sha256 {run['code_sha256']}", model="none: deterministic geometry build",
                                 environment=json.dumps(run["libraries"], sort_keys=True), parameters=f"display scale {f['display_scale']}; set {f['set']}", scope="geometry of an illustrative design"), [ev_solve])
        names = [f"stl/{fid}.stl", f"stl/{fid}-stand.stl", f"web/{fid}.glb", f"img/{fid}.png", f"img/{fid}-on-stand.png"]
        arts = [c.artifact("geometry", f"{PRINT}/{names[0]}", blobs[names[0]], "printable solid (STL)"), c.artifact("geometry", f"{PRINT}/{names[1]}", blobs[names[1]], "display stand (STL)"),
                c.artifact("geometry", f"{PRINT}/{names[2]}", blobs[names[2]], "web mesh (GLB)"),
                c.artifact("output", f"{PRINT}/{names[3]}", blobs[names[3]], "render image"), c.artifact("output", f"{PRINT}/{names[4]}", blobs[names[4]], "render image on stand"),
                c.artifact("log", f"{PRINT}/manifest.json", manifest_b, "print manifest listing all file hashes, library versions and the printer-unknown statement")]
        _evidence(c, src, f"viz-form-evidence-build-{fid}", claim, kind="simulated", relation="context_only", produced_by=act_build,
                  source=em._source(c, f"{PRINT}/manifest.json", manifest_b, "Print manifest."),
                  method="Producer builds the solid with manifold3d from the design, validates the mesh and renders images.",
                  context=RENDER_NOTE + f" Mesh validity: valid {f['valid']}, converged {f['converged']}, stand valid {f['stand_valid']}; mesh_sha256 {f['mesh_sha256'][:16]}... is stated by the producer as a geometry hash, not a file hash.",
                  assumptions=assumptions, provenance=_prov(c, run=run, glide=f["glide"], simulation_comparison=f["simulation_comparison"]),
                  limitations=lim + [f"Glide status for this form: {f['glide']!r}; no simulation of this form is linked unless a separate Evidence says so."], artifacts=arts)
    return c


# ------------------------------------------------------------------------------------------------------------------ coverage
def media_in_commit(repo: str, commit: str, roots=("artifacts", "engineering", "connectors", "site/artifacts")) -> list[dict]:
    """Every media file under `roots` at the commit: path, sha256 (from the blob), bytes."""
    out = subprocess.run(["git", "-C", repo, "ls-tree", "-r", "--name-only", commit, "--", *roots], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise Refused(f"cannot list {commit[:12]}: {out.stderr.strip()[:100]}")
    rows = []
    for p in out.stdout.splitlines():
        if p.lower().endswith(MEDIA_EXT):
            b = em.git_blob(repo, commit, p)
            rows.append({"path": p, "sha256": sha_bytes(b), "bytes": len(b)})
    return rows


def coverage(media: list[dict], records: list[dict]) -> dict:
    """Which media files are tied to Evidence (their sha256 is an ArtifactRef inside an Evidence that targets a Claim).

    Tied means: the sha256 appears in an Evidence's artifacts. It does NOT mean the Evidence supports anything; `relations` shows how it is tied."""
    tie: dict[str, list[dict]] = {}
    for r in records:
        if r["kind"] != "Evidence":
            continue
        for a in r["payload"].get("artifacts", []):
            tie.setdefault(a["sha256"], []).append({"evidence": r["id"], "relation": r["payload"].get("relation", "unspecified"), "target": r["payload"]["target"]["id"], "role": a["role"]})
    tied, untied = [], []
    for m in media:
        (tied if m["sha256"] in tie else untied).append({**m, "tied_to": tie.get(m["sha256"], [])})
    dup = {}
    for m in media:
        dup.setdefault(m["sha256"], []).append(m["path"])
    return {"media_files": len(media), "tied": len(tied), "untied": len(untied), "untied_paths": sorted(u["path"] for u in untied),
            "supports_by_media": sum(1 for t in tied for x in t["tied_to"] if x["relation"] == "supports"),
            "same_bytes_at_several_paths": {k[:16]: v for k, v in dup.items() if len(v) > 1}, "tied_detail": tied}


def build_all(repo: str, commit: str, *, namespace="node-a", issuer="importer", replay=None, created_at=None) -> list[dict]:
    recs = []
    for ch in (glide_chain(repo, commit, namespace=namespace, issuer=issuer, replay=replay, created_at=created_at),
               rd_chain(repo, commit, namespace=namespace, issuer=issuer, created_at=created_at),
               print_forms_chain(repo, commit, namespace=namespace, issuer=issuer, created_at=created_at)):
        recs += ch.records
    return recs


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", required=True); ap.add_argument("--source-commit", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--namespace", default="node-a"); ap.add_argument("--issuer", default="importer")
    ap.add_argument("--also-records", action="append", default=[], help="JSON file(s) of already-built/imported Records, counted when checking which media are tied")
    ap.add_argument("--replay-glide", action="store_true", help="really run the producer's numeric glide build() (bounded) and record the comparison")
    a = ap.parse_args(argv)
    commit = em.resolve_commit(a.repo, a.source_commit)
    replay = replay_glide(a.repo, commit) if a.replay_glide else None
    recs = build_all(a.repo, commit, namespace=a.namespace, issuer=a.issuer, replay=replay)
    os.makedirs(a.out, exist_ok=True)
    media = media_in_commit(a.repo, commit)
    known = list(recs)
    for f in a.also_records:
        with open(f) as fh:
            d = json.load(fh)
        known += d["records"] if isinstance(d, dict) else d
    cov = coverage(media, known)
    with open(os.path.join(a.out, "records.json"), "w") as fh:
        json.dump({"records": recs}, fh, indent=1, sort_keys=True)
    with open(os.path.join(a.out, "coverage.json"), "w") as fh:
        json.dump({"source_commit": commit, **cov}, fh, indent=1, sort_keys=True)
    if replay:
        with open(os.path.join(a.out, "glide-replay.json"), "w") as fh:
            json.dump(replay, fh, indent=1, sort_keys=True)
    print(json.dumps({"records": len(recs), "by_kind": {k: sum(1 for r in recs if r["kind"] == k) for k in ("Claim", "Action", "Evidence")}, "media_files": cov["media_files"], "tied": cov["tied"],
                      "untied": cov["untied"], "supports_by_media": cov["supports_by_media"], "source_commit": commit}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
