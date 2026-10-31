"""Bioelectric (Hodgkin-Huxley chain) and mechanobiology (motor-clutch) simulation bundles -> PROPOSED Claim / Action / Evidence drafts.

Uses only kinds the deployed store has (Claim, Action, Evidence). Same rules as `visual_assets`: compute and render are separate Actions;
render Evidence is always `context_only` and a picture is never support; every stated hash is recomputed from an immutable git blob and a
mismatch refuses the chain; pointers are `urn:sha256`/`referenced` with no URL; nothing here is executed by Frontier (these Actions record
what the producer reports; both producers state their own exit codes); source context, conditions, limitations and open questions are kept.

The claims are descriptions of what a DECLARED model did under DECLARED conditions. Neither model is calibrated to any fish, fin or tissue.
"""
from __future__ import annotations

import json

from . import engineering_manifest as em
from .common import sha_bytes
from .visual_assets import AssetChain, RENDER_NOTE, _action, _evidence, _prov

ADAPTER_ID = "frontier_adapters.sim_bundles"
ADAPTER_VERSION = "0.1.0"
BIO = "artifacts/bioelectric"
BIO_CODE = "engineering/bioelectric"
MECH = "artifacts/mechanobio"
MECH_BRANCH_COMMIT = "76a93e7"          # artifacts live on work/mechanobio; root's tip has the code but not these files


def _fmt(xs, n=1):
    return ", ".join("null" if x is None else f"{x:.{n}f}" for x in xs)


# ------------------------------------------------------------------------------------------------------------- bioelectric
def bioelectric_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "bioelectric")
    man = c.jblob(f"{BIO}/manifest.json")
    c.check("manifest.schema", man.get("schema") == "frontier.bioelectric.bundle/1" and man.get("status") == "completed" and man.get("exit_status") == 0,
            f"schema {man.get('schema')!r} status {man.get('status')!r} exit {man.get('exit_status')!r}")
    blobs = {rel: c.same_hash(f"file.{rel}", f"{BIO}/{rel}", meta["sha256"]) for rel, meta in man["files"].items()}      # all 63 listed files
    for rel, meta in man["files"].items():
        c.check(f"size.{rel}", len(blobs[rel]) == meta["bytes"], f"{rel}: manifest {meta['bytes']} bytes, blob {len(blobs[rel])}")
    code = {n: c.same_hash(f"code.{n}", f"{BIO_CODE}/{n}", h) for n, h in man["code_sha256"].items()}
    manifest_b = c.blob(f"{BIO}/manifest.json")
    integ = c.jblob(f"{BIO}/integrity_receipt.json")
    c.check("integrity.passed", integ.get("status") == "passed" and integ.get("code_sha256_match") is True, f"integrity receipt {integ.get('status')!r}")
    ctl_b = c.blob(f"{BIO}/controls_baseline.json")
    mut = c.jblob(f"{BIO}/mutation_receipt.json")
    arms = {r["arm"]: r for r in mut["receipts"]}
    c.check("mutation.arms", arms["baseline"]["exit_status"] == 0 and arms["gap_sign_mutant"]["exit_status"] == 1 and arms["restored"]["exit_status"] == 0,
            f"baseline exit {arms['baseline']['exit_status']}, mutant {arms['gap_sign_mutant']['exit_status']}, restored {arms['restored']['exit_status']}")
    rr = c.jblob(f"{BIO}/render_receipt.json")
    c.check("render.exit", rr["exit_status"] == 0 and rr["kind"] == "render", f"render exit {rr['exit_status']}")
    for k, h in rr["input_artifacts"].items():
        c.check(f"render.input.{k}", sha_bytes(blobs[k]) == h, f"render receipt input {k}")
    c.check("render.code", rr["code_sha256"] == man["code_sha256"], "render receipt code hashes equal the manifest's")
    src = c.jblob(f"{BIO}/sources.json")
    hh = src["scientific_source"]
    asm = [f"Scientific source: {hh['authors']}, {hh['title']}, DOI {hh['doi']} ({hh['accession']}). {hh['context']}. {hh['data_status']}.",
           f"Source sections read: {'; '.join(hh['read_sections'])}. PDF sha256 {hh['retrieved_pdf_sha256'][:16]}... (full text not redistributed).",
           hh["voltage_conversion"], "Implementation cross-check only (no NEURON/BETSE run): " + src["implementation_crosscheck"]["url"]]
    src_uri = "urn:frontier:adapter:sim-bundles:bioelectric"
    src_ptr = em._source(c, f"{BIO}/sources.json", blobs["sources.json"] if "sources.json" in blobs else c.blob(f"{BIO}/sources.json"), "Source envelope of the model.")
    base = c.jblob(f"{BIO}/baseline.json")
    lim_model = list(base["limitations"])
    opens = [f"OPEN ({q['id']}, scales {','.join(q['scales'])}): {q['question']} Next evidence: {q['next_evidence']}" for q in base["open_questions"]]
    arms_txt = (f"Implementation controls: baseline exit {arms['baseline']['exit_status']}; with the gap-junction endpoint current sign flipped (law mutant) exit {arms['gap_sign_mutant']['exit_status']} (control detects it); "
                f"restored exit {arms['restored']['exit_status']}. Numerical scope: {man['numerical_scope']}. Biological validation: {man['biological_validation']}.")
    common_lim = [em.IMPORT_NOTE, "SIMULATED with published squid-axon membrane kinetics; NOT measured fin voltages and not calibrated to any fish.", arms_txt] + lim_model[1:] + opens
    scen = {"baseline": "all gap-coupled cells", "sodium_reduced": "sodium conductance scaled to 0.35", "disconnected": "gap conductance 0", "no_stimulus": "stimulus current 0"}
    sim_ev: dict[str, dict] = {}
    claims: dict[str, dict] = {}
    for name in ("baseline", "sodium_reduced", "disconnected", "no_stimulus"):
        d = c.jblob(f"{BIO}/{name}.json")
        rq, mt = d["request"], d["metrics"]
        cross = [t for t in mt["first_crossing_0mV_ms_by_cell"] if t is not None]
        stmt = (f"In the producer's 12-cell Hodgkin-Huxley chain with ohmic gap junctions (scenario '{name}': sodium_scale {rq['sodium_scale']}, potassium_scale {rq['potassium_scale']}, gap {rq['gap_mS_cm2']} mS/cm^2, "
                f"stimulus {rq['stimulus_uA_cm2']} uA/cm^2 into cell 0 during 5 <= t < 6 ms, {rq['temperature_c']} C, {rq['duration_ms']} ms, dt {rq['dt_ms']} ms), {mt['cells_crossing_0mV']} of {d['n_cells']} cells cross 0 mV"
                + (f"; first crossings {min(cross):.1f}-{max(cross):.1f} ms" if cross else "") + f"; peak voltage by cell (mV): {_fmt(mt['peak_mV_by_cell'], 1)}.")
        claim = c.add(c.draft("Claim", f"sim-bioelectric-claim-{name}", {
            "title": f"Bioelectric chain, scenario {name}: {scen[name]}",
            "statement": stmt,
            "context": "A deterministic model outcome for declared network, pulse and perturbation values; the membrane law is published squid giant axon, the 12-cell chain and gap conductance are assumed design scenarios. " + asm[0],
            "assumptions": asm + [f"Request: {json.dumps(rq, sort_keys=True)}."], "limitations": common_lim,
            "source": em._source(c, f"{BIO}/{name}.json", blobs[f"{name}.json"], "Scenario result file (actual voltage, time, gates and ionic currents)."),
            "source_record_version": None, "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "derived"}, src_uri))
        claims[name] = claim
        sa = d["simulationAction"]
        act = _action(c, src_uri, f"sim-bioelectric-action-sim-{name}", claim,
                      f"Imported record of a producer-reported run (NOT executed by Frontier): {sa['engine']}, scenario {name}",
                      ["A clean re-execution from the pinned code and request reproduces the voltage and time digests.", "An independent reviewer checks the model against the source before the numbers are used."],
                      ["python3 with numpy"],
                      dict(input=f"request sha256 {sa['input_sha256']}; scenario {name}", code=f"git:{em.REPO_LABEL}@{commit}; " + ", ".join(f"{k}:{v[:12]}" for k, v in sorted(man['code_sha256'].items())),
                           model=f"{base['model_id']} ({sa['method']}; no language model)", environment=f"python {man['environment']['python']}, numpy {man['environment']['numpy']}, threads {man['environment']['threads']}",
                           parameters=json.dumps(rq, sort_keys=True), scope="simulated; published squid-axon parameters, assumed network"), [])
        arts = [c.artifact("output", f"{BIO}/{name}.json", blobs[f"{name}.json"], "scenario result with actual sampled states"), c.artifact("log", f"{BIO}/manifest.json", manifest_b, "bundle manifest: command, exit status, environment, hashes of all 63 files"),
                c.artifact("environment", f"{BIO}/integrity_receipt.json", c.blob(f"{BIO}/integrity_receipt.json"), "integrity receipt: every manifest hash and 53 voltage/time digests recomputed by the producer"),
                c.artifact("input", f"{BIO}/sources.json", c.blob(f"{BIO}/sources.json"), "source envelope")] + [c.artifact("code", f"{BIO_CODE}/{n}", code[n]) for n in ("model.py", "run.py")]
        if name == "baseline":
            arts += [c.artifact("certificate", f"{BIO}/controls_baseline.json", ctl_b, "controls: closed-form passive error, clamp gate error, convergence"),
                     c.artifact("log", f"{BIO}/mutation_receipt.json", c.blob(f"{BIO}/mutation_receipt.json"), "law-mutant receipt: baseline 0, sign-flipped 1, restored 0")]
        sim_ev[name] = _evidence(c, src_uri, f"sim-bioelectric-evidence-sim-{name}", claim, kind="simulated", relation="unspecified", produced_by=act, source=src_ptr,
                                 method=f"{sa['method']}. {arms_txt}", context="Applicability: this model with these assumed network values. " + em.IMPORT_NOTE, assumptions=asm,
                                 provenance=_prov(c, model_id=base["model_id"], manifest_command="python -m engineering.bioelectric.run --output artifacts/bioelectric", elapsed_s=man["elapsed_s"],
                                                  state_sha256=sa.get("state_sha256"), voltage_sha256=sa.get("voltage_sha256"), worktree_parent_commit=man["worktree_parent_commit"], source_identity=man["source_identity"], timestamp_seattle=man["timestamp_seattle"]),
                                 limitations=common_lim, artifacts=arts,
                                 uncertainty="No uncertainty quantification: deterministic runs; numerical convergence screened for the default scenario and a smooth passive cable only.")
    # atlas
    at = c.jblob(f"{BIO}/atlas.json")
    mat = at["color_matrix"]
    aclaim = c.add(c.draft("Claim", "sim-bioelectric-claim-atlas", {
        "title": "Bioelectric chain response atlas: cells crossing 0 mV over sodium scale x gap conductance",
        "statement": (f"Over the producer's {at['count']} integrations (sodium_scale {at['x']['values']} by gap_mS_cm2 {at['y']['values']}, other values fixed at {json.dumps(at['fixed'], sort_keys=True)}), the number of cells whose saved voltage crosses 0 mV within 30 ms is, "
                      f"by gap row: " + "; ".join(f"gap {g}: {row}" for g, row in zip(at['y']['values'], mat)) + "."),
        "context": at["scope"] + ". " + at["interpretation"] + ". " + asm[0],
        "assumptions": asm + [f"Axis status: {at['x']['name']} {at['x']['status']}; {at['y']['name']} {at['y']['status']}."], "limitations": common_lim,
        "source": em._source(c, f"{BIO}/atlas.json", blobs["atlas.json"], "Atlas file; each cell points to a hashed per-run artifact."),
        "source_record_version": None, "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "derived"}, src_uri))
    aact = _action(c, src_uri, "sim-bioelectric-action-sim-atlas", aclaim, "Imported record of a producer-reported run (NOT executed by Frontier): 49 integrations over the sodium-by-gap grid",
                   ["A clean re-execution reproduces each per-run voltage/time digest listed in atlas.json.", "An independent reviewer checks the grid choices."], ["python3 with numpy"],
                   dict(input=f"atlas.json sha256 {man['files']['atlas.json']['sha256']}", code=f"git:{em.REPO_LABEL}@{commit}; model.py {man['code_sha256']['model.py'][:12]}", model=f"{base['model_id']} (no language model)",
                        environment=f"python {man['environment']['python']}, numpy {man['environment']['numpy']}", parameters=json.dumps(at["fixed"], sort_keys=True), scope="simulated response map; not an optimisation objective"), [])
    aev = _evidence(c, src_uri, "sim-bioelectric-evidence-sim-atlas", aclaim, kind="simulated", relation="unspecified", produced_by=aact, source=src_ptr,
                    method="49 integrations of the same model; the matrix counts cells crossing 0 mV.", context="Applicability: this model grid only. " + em.IMPORT_NOTE, assumptions=asm,
                    provenance=_prov(c, per_run_artifacts=at["count"], per_run_digests_recomputed_by_producer=integ["voltage_time_artifacts_checked"]), limitations=common_lim,
                    artifacts=[c.artifact("output", f"{BIO}/atlas.json", blobs["atlas.json"], "atlas matrix and the list of 49 hashed per-run artifacts"), c.artifact("log", f"{BIO}/manifest.json", manifest_b, "bundle manifest listing all 63 file hashes")]
                    + [c.artifact("code", f"{BIO_CODE}/run.py", code["run.py"])])
    # renders: video + poster (three scenarios) and atlas.png
    vm = [a for a in man["files"] if a in ("bioelectric.mp4", "poster.png")]
    for name in ("baseline", "sodium_reduced", "disconnected"):
        ract = _action(c, src_uri, f"sim-bioelectric-action-render-{name}", claims[name],
                       "Imported record of a producer-reported render (NOT executed by Frontier): ffmpeg encode of actual selected state frames of three scenarios (one video shows all three)",
                       ["Re-rendering from the pinned code and scenario files reproduces the frames; mp4 bytes can differ across ffmpeg builds.", "The video is a picture of computed states, not evidence."],
                       ["python3 with numpy and matplotlib; ffmpeg"],
                       dict(input=f"simulation evidence version {sim_ev[name]['version']}; render inputs " + ", ".join(f"{k}:{v[:12]}" for k, v in rr["input_artifacts"].items()),
                            code=f"git:{em.REPO_LABEL}@{commit}; render.py {man['code_sha256']['render.py'][:12]}", model="none: deterministic rendering", environment="matplotlib/ffmpeg builds NOT recorded in the receipt",
                            parameters=f"{rr['n_frames']} frames, {rr['fps']} fps, model horizon {rr['model_horizon_ms']} ms, temporal interpolation {rr['temporal_interpolation']}; " + " ".join(rr["command"])[:200], scope="visualisation of a simulated model"), [sim_ev[name]])
        _evidence(c, src_uri, f"sim-bioelectric-evidence-render-{name}", claims[name], kind="simulated", relation="context_only", produced_by=ract,
                  source=em._source(c, f"{BIO}/render_receipt.json", c.blob(f"{BIO}/render_receipt.json"), "Render receipt."),
                  method=f"Producer draws {rr['n_frames']} actual selected state frames (no temporal interpolation: {rr['temporal_interpolation']}) and encodes with ffmpeg (exit {rr['exit_status']}).",
                  context=RENDER_NOTE + " The same video shows baseline, sodium_reduced and disconnected; which part belongs to this scenario is not recorded in the receipt. " + em.IMPORT_NOTE, assumptions=asm,
                  provenance=_prov(c, source_frame_indices_count=len(rr["source_frame_indices"]), wall_playback_seconds=rr["wall_playback_seconds"], ffprobe=integ["ffprobe"]), limitations=[em.IMPORT_NOTE, RENDER_NOTE],
                  artifacts=[c.artifact("output", f"{BIO}/bioelectric.mp4", blobs["bioelectric.mp4"], "video of computed states (1280x720 H.264, 180 frames, 7.5 s)"), c.artifact("output", f"{BIO}/poster.png", blobs["poster.png"], "poster image"),
                             c.artifact("log", f"{BIO}/render_receipt.json", c.blob(f"{BIO}/render_receipt.json"), "render receipt with input hashes, frame indices and ffmpeg command"), c.artifact("code", f"{BIO_CODE}/render.py", code["render.py"])])
    ract = _action(c, src_uri, "sim-bioelectric-action-render-atlas", aclaim, "Imported record of a producer-reported render (NOT executed by Frontier): atlas image from atlas.json (no separate render receipt: produced inside the same run)",
                   ["Re-running run.py reproduces atlas.png from atlas.json."], ["python3 with numpy and matplotlib"],
                   dict(input=f"simulation evidence version {aev['version']}", code=f"git:{em.REPO_LABEL}@{commit}; run.py {man['code_sha256']['run.py'][:12]}", model="none", environment="NOT RECORDED separately", parameters="as run.py", scope="visualisation of a simulated grid"), [aev])
    _evidence(c, src_uri, "sim-bioelectric-evidence-render-atlas", aclaim, kind="simulated", relation="context_only", produced_by=ract, source=em._source(c, f"{BIO}/manifest.json", manifest_b, "Bundle manifest."),
              method="Atlas image drawn from the atlas matrix.", context=RENDER_NOTE + " The producer recorded no separate render receipt for atlas.png. " + em.IMPORT_NOTE, assumptions=asm, provenance=_prov(c),
              limitations=[em.IMPORT_NOTE, RENDER_NOTE], artifacts=[c.artifact("output", f"{BIO}/atlas.png", blobs["atlas.png"], "atlas image"), c.artifact("log", f"{BIO}/manifest.json", manifest_b, "bundle manifest")])
    return c


# ------------------------------------------------------------------------------------------------------------- mechanobiology
def mechanobio_chain(repo: str, commit: str, *, namespace="node-a", issuer="importer", created_at=None) -> AssetChain:
    created_at = created_at or em._commit_utc(repo, commit)
    c = AssetChain(repo, commit, namespace, issuer, created_at, "mechanobio")
    sm = c.jblob(f"{MECH}/simulation-manifest.json")
    fm = c.jblob(f"{MECH}/feedback-simulation-manifest.json")
    rm = c.jblob(f"{MECH}/render-manifest.json")
    for nm, m in (("sim", sm), ("feedback", fm), ("render", rm)):
        c.check(f"{nm}.schema", m.get("schema", "").startswith("frontier.mechanobio."), f"{nm} schema {m.get('schema')!r}")
    blobs = {}
    for m in (sm, fm, rm):
        for a in m["artifacts"]:
            blobs[a["title"]] = c.same_hash(f"artifact.{a['title']}", f"{MECH}/{a['title']}", a["sha256"])
            c.check(f"size.{a['title']}", len(blobs[a["title"]]) == a["byte_size"], f"{a['title']}: manifest {a['byte_size']} bytes")
    code_files = sm["code_files"]
    # Simulation files are checked strictly. render.py is listed in the simulation manifest too, but it takes no part in the simulation and the
    # producer edited it afterwards (the render manifest states the pinned hash): record the stale listing as a finding, do not hide it.
    code = {p: c.same_hash(f"code.{p}", p, h) for p, h in code_files.items() if not p.endswith("/render.py")}
    render_b = c.same_hash("render.code", "engineering/mechanobio/render.py", rm["render_code_sha256"])
    stale = code_files.get("engineering/mechanobio/render.py")
    c.check("render.listing_in_simulation_manifest", stale == rm["render_code_sha256"],
            f"simulation manifest lists render.py {str(stale)[:12]}..., the pinned file and the render manifest say {rm['render_code_sha256'][:12]}...: stale listing, render.py is not used by the simulation", refuse=False)
    STALE = [] if stale == rm["render_code_sha256"] else [f"Producer inconsistency kept visible: the simulation manifest lists render.py as {stale[:16]}..., but the pinned render.py hashes to {rm['render_code_sha256'][:16]}... (the render manifest agrees). render.py takes no part in the simulation; the listing predates a render edit."]
    sweep = json.loads(blobs["sweep.json"]); ctl = json.loads(blobs["controls.json"]); proto = json.loads(blobs["protocol.json"]); req_b = blobs["request.json"]
    c.check("sweep.count", sweep["n_simulations"] == 600 and len(sweep["rows"]) == 25 and sweep["protocol_sha256"] == sm["input_sha256"], f"{sweep['n_simulations']} simulations, {len(sweep['rows'])} cells; protocol hash equals the manifest input")
    c.check("controls.passed", ctl["passed"] is True, "producer's controls report passed")
    srcj = json.loads(c.blob("engineering/mechanobio/sources.json"))
    paper = json.dumps(srcj)[:1400]
    ssrc = srcj.get("scientific_source") or srcj
    pap = f"Scientific source: Gong et al., PNAS 2018, DOI 10.1073/pnas.1716620115, Model Description Eqs 1-6 and Fig 1C/D (motor-clutch model with a standard-linear-solid contact). Supplementary Table S1 was NOT retrieved; parameters other than the main-text example are assumed (per the producer)."
    src_uri = "urn:frontier:adapter:sim-bundles:mechanobio"
    rows = sweep["rows"]
    tr = [r["mean_traction_pN"] for r in rows]; dd = [r["paired_intervention_mean_change_pN"] for r in rows]
    lim = [em.IMPORT_NOTE, "SIMULATED motor-clutch mechanics with a seeded first-order Bernoulli binding/rupture split; no reinforcement, no catch bonds, no ligand recruitment, no membrane resistance.",
           "Intervals are Monte Carlo (normal approximation) only; they are not biological or parameter uncertainty."] + [f"Producer states it does not establish: {x}" for x in sweep["not_established"]] + \
          ["A separate cloud sweep (7x7 cells x 32 seeds x 2 arms, 3136 simulations) was specified by the producer but is NOT claimed executed."] + STALE
    asm = [pap, f"Protocol: stiffness {proto['stiffness_pN_nm']} pN/nm x viscosity {proto['viscosity_pN_s_nm']} pN s/nm, seeds {proto['seed_list']}, {proto['duration_s']} s at dt {proto['dt_s']} s; defaults {json.dumps(proto['defaults'], sort_keys=True)}.",
           f"Intervention: {proto['intervention']}. {proto['interval_scope']}."]
    claim1 = c.add(c.draft("Claim", "sim-mechanobio-claim-sweep", {
        "title": "Motor-clutch model: mean traction over a 5x5 stiffness-by-viscosity grid with Bell versus constant rupture (600 simulations)",
        "statement": (f"In the producer's motor-clutch model (25 stiffness-by-viscosity cells x {len(proto['seed_list'])} seeds x 2 rupture arms = {sweep['n_simulations']} simulations), mean traction across cells ranges "
                      f"{min(tr):.3f} to {max(tr):.3f} pN; the paired mean change from constant-rupture to Bell-force rupture ranges {min(dd):.5f} to {max(dd):.5f} pN across cells. These are Monte Carlo summaries of a declared model."),
        "context": "A descriptive summary of the producer's sweep.json computed by this adapter from its rows (min and max of two columns). " + pap, "assumptions": asm, "limitations": lim,
        "source": em._source(c, f"{MECH}/sweep.json", blobs["sweep.json"], "Sweep file with all replicate summaries."), "source_record_version": None, "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "derived"}, src_uri))
    bell = ctl["bell_law_mutant"]
    claim2 = c.add(c.draft("Claim", "sim-mechanobio-claim-bell-sensitivity", {
        "title": "Motor-clutch model: Bell-law rupture matters in the declared 5-clutch setting",
        "statement": (f"In the producer's declared 5-clutch setting (stiffness 1 pN/nm, rupture force 1 pN, seed {bell['same_seed']}), mean traction is {bell['baseline_mean_pN']:.3f} pN with Bell force-dependent rupture and "
                      f"{bell['mutant_mean_pN']:.3f} pN when exp(force/Fb) is replaced by 1 (absolute change {bell['absolute_change_pN']:.3f} pN; detection threshold {bell['detection_threshold_pN']} pN, detected {bell['detected']})."),
        "context": "An implementation-sensitivity control of the model, not a biological finding. " + pap, "assumptions": asm, "limitations": lim,
        "source": em._source(c, f"{MECH}/controls.json", blobs["controls.json"], "Controls file."), "source_record_version": None, "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "derived"}, src_uri))
    cdesc = f"analytic elastic max error {ctl['analytic_elastic_no_rupture']['max_error_pN']:.3g} pN; independent solve_ivp max error {ctl['independent_viscoelastic_integration']['max_error_pN']:.3g} pN; zero binding {ctl['zero_binding']['max_force_pN']} pN; zero motor velocity {ctl['zero_motor_velocity']['max_force_pN']} pN; force-balance residual {ctl['force_balance']['max_residual_pN']:.3g} pN"
    env = json.loads(blobs["environment.json"])
    cache_code = f"git:{em.REPO_LABEL}@{commit}; " + ", ".join(f"{k.split('/')[-1]}:{v[:12]}" for k, v in sorted(code_files.items()))
    evs = {}
    for cid, claim, outs, ids in ((1, claim1, ["sweep.json", "trajectory.json", "request.json", "protocol.json", "controls.json", "environment.json"], "sweep"),
                                   (2, claim2, ["feedback-trajectory.json", "constant-rupture-trajectory.json", "controls.json", "request.json"], "bell")):
        act = _action(c, src_uri, f"sim-mechanobio-action-sim-{ids}", claim, "Imported record of a producer-reported run (NOT executed by Frontier): motor-clutch ensemble simulation",
                      ["A clean re-execution from the pinned code and protocol reproduces the sweep rows and trajectory hashes.", "An independent reviewer checks the model against the paper."],
                      ["python3 with numpy and scipy"],
                      dict(input=f"protocol sha256 {sm['input_sha256']}" if cid == 1 else f"request sha256 {fm['request_sha256']}; input {fm['provenance']['input_sha256'][:16]}", code=cache_code,
                           model="motor-clutch + standard-linear-solid contact (exact matrix exponentials; seeded Bernoulli binding; no language model)", environment=f"environment sha256 {sm['environment_sha256']}; python/numpy/scipy per environment.json",
                           parameters=json.dumps(proto["defaults"], sort_keys=True) if cid == 1 else "5 clutches, rupture force 1 pN, stiffness 1 pN/nm, seed 19 (explicitly assumed scenario)", scope="simulated; not calibrated to any cell"), [])
        evs[cid] = _evidence(c, src_uri, f"sim-mechanobio-evidence-sim-{ids}", claim, kind="simulated", relation="unspecified", produced_by=act, source=em._source(c, f"{MECH}/simulation-manifest.json", c.blob(f"{MECH}/simulation-manifest.json"), "Simulation manifest."),
                             method=f"Producer's ensemble simulation; controls: {cdesc}; timestep screen {json.dumps(ctl['timestep_screen'])[:200]}.", context="Applicability: this model with these assumed parameters. " + em.IMPORT_NOTE, assumptions=asm,
                             provenance=_prov(c, elapsed_s=sm["elapsed_s"] if cid == 1 else fm["provenance"]["elapsed_s"], environment=env if len(json.dumps(env)) < 900 else "see environment.json artifact", source_receipt_sha256=sm["source_receipt_sha256"]),
                             limitations=lim, artifacts=[c.artifact("output" if t in ("sweep.json", "trajectory.json", "feedback-trajectory.json", "constant-rupture-trajectory.json") else ("certificate" if t == "controls.json" else ("environment" if t == "environment.json" else ("protocol" if t == "protocol.json" else "input"))), f"{MECH}/{t}", blobs[t]) for t in outs]
                             + [c.artifact("code", "engineering/mechanobio/model.py", code["engineering/mechanobio/model.py"]), c.artifact("code", "engineering/mechanobio/sweep.py", code["engineering/mechanobio/sweep.py"])],
                             uncertainty="Monte Carlo normal-approximation intervals over seeds only; no parameter or biological uncertainty.")
    for cid, claim, ids in ((1, claim1, "sweep"), (2, claim2, "bell")):
        ract = _action(c, src_uri, f"sim-mechanobio-action-render-{ids}", claim, "Imported record of a producer-reported render (NOT executed by Frontier): video, poster and response-surface plot from computed states",
                       ["Re-rendering from the pinned code and the trajectory/sweep reproduces the frames; mp4 bytes can differ across ffmpeg builds.", "Pictures are read as views of computed states, not as evidence."], ["python3 with matplotlib; ffmpeg"],
                       dict(input=f"simulation evidence version {evs[cid]['version']}; trajectory {rm['input_trajectory']['sha256'][:16]}; sweep {rm['input_sweep']['sha256'][:16]}", code=f"git:{em.REPO_LABEL}@{commit}; render.py {rm['render_code_sha256'][:12]}",
                            model="none: deterministic rendering", environment=f"matplotlib {rm['matplotlib']}; {rm['ffmpeg'][:60]}", parameters=f"{rm['frames']} frames, {rm['fps']} fps, frame_indices_sha256 {rm['frame_indices_sha256'][:16]}", scope="visualisation of a simulated model"), [evs[cid]])
        _evidence(c, src_uri, f"sim-mechanobio-evidence-render-{ids}", claim, kind="simulated", relation="context_only", produced_by=ract, source=em._source(c, f"{MECH}/render-manifest.json", c.blob(f"{MECH}/render-manifest.json"), "Render manifest."),
                  method=f"Producer draws {rm['frames']} frames from the feedback trajectory and sweep and encodes them (ffmpeg).", context=RENDER_NOTE + " The video follows the 5-clutch paired scenario and the plot the sweep; both outputs are attached to each Claim. " + em.IMPORT_NOTE,
                  assumptions=asm, provenance=_prov(c, frame_indices_sha256=rm["frame_indices_sha256"], ffmpeg=rm["ffmpeg"], matplotlib=rm["matplotlib"]), limitations=[em.IMPORT_NOTE, RENDER_NOTE],
                  artifacts=[c.artifact("output", f"{MECH}/{t}", blobs[t], d) for t, d in (("mechanobio.mp4", "video of computed states"), ("poster.png", "poster"), ("response-surface.png", "response-surface plot"))]
                  + [c.artifact("log", f"{MECH}/render-manifest.json", c.blob(f"{MECH}/render-manifest.json"), "render manifest"), c.artifact("code", "engineering/mechanobio/render.py", render_b)])
    return c


def build(repo: str, root_commit: str, mech_commit: str, *, namespace="node-a", issuer="importer") -> list[dict]:
    return bioelectric_chain(repo, root_commit, namespace=namespace, issuer=issuer).records + mechanobio_chain(repo, mech_commit, namespace=namespace, issuer=issuer).records


def main(argv=None) -> int:
    import argparse
    import os
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", required=True); ap.add_argument("--bio-commit", required=True); ap.add_argument("--mech-commit", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--namespace", default="node-a"); ap.add_argument("--issuer", default="importer")
    a = ap.parse_args(argv)
    bio, mech = em.resolve_commit(a.repo, a.bio_commit), em.resolve_commit(a.repo, a.mech_commit)
    recs = build(a.repo, bio, mech, namespace=a.namespace, issuer=a.issuer)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "records.json"), "w") as fh:
        json.dump({"bio_commit": bio, "mech_commit": mech, "records": recs}, fh, indent=1, sort_keys=True)
    print(json.dumps({"records": len(recs), "by_kind": {k: sum(1 for r in recs if r["kind"] == k) for k in ("Claim", "Action", "Evidence")}, "bio_commit": bio, "mech_commit": mech}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
