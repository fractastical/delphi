"""Design-control map: regions, controllable parameters, bound status, sensitivity, identifiability,
missing bridges and work packages, every number a pointer into a pinned git blob of an existing result.

    python -m engineering.design_control.build --write   # regenerate artifacts/design-control/map.json
    python -m engineering.design_control.build --check   # rebuild from pinned blobs, compare, integrity-check

Nothing here is measured or simulated by this module. A value is either copied from a source blob by
pointer (`ref`) or derived from such blobs by a named function; `check` re-reads the blobs and refuses
any drift. No confidence, probability or aggregate score is produced anywhere.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

SCHEMA = "frontier.design-control/1"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "artifacts", "design-control", "map.json")
BOUND_STATUS = ("measured", "sourced", "assumed", "unknown")

# id -> (branch, commit, path). Commits are the final pushed tips named in each owner's handoff
# (messages/*-to-codex03.md); every blob is read with `git show <commit>:<path>`, never from a worktree.
SOURCES = {
    "assurance": ("work/design-assurance", "0722fc7992a72ea4b425cd2636a30eceff3d714d", "artifacts/assurance/map.json"),
    "fin-summary": ("work/fin-assurance-experiment", "1adc724bcdbd7f19e954b25a18d94c67426e87ca", "artifacts/assurance-experiments/summary.json"),
    "fin-controls": ("work/fin-assurance-experiment", "1adc724bcdbd7f19e954b25a18d94c67426e87ca", "artifacts/assurance-experiments/controls.json"),
    "fin-protocol": ("work/fin-assurance-experiment", "1adc724bcdbd7f19e954b25a18d94c67426e87ca", "engineering/assurance_experiments/protocol.json"),
    "ecology": ("work/ecology", "d3d64c68131ecf5795d820e543c3c0309d9d901a", "artifacts/ecology/uncertainty-aggregate/summary.json"),
    "knobs": ("work/fish-control-data", "73d3a83df599d84b2e225d12a95d68bf262fc670", "data/fish-controls/knobs.json"),
    "regulatory": ("work/fish-regulatory-map", "bff38281e28cf65961626a342612ba2c993861d2", "artifacts/fish-regulatory-map/map.json"),
    "reg-metadata": ("work/regulatory-metadata", "1b77f81", "artifacts/regulatory-metadata/run/coverage-reviewed.json"),
    "behavior": ("work/fish-behavior-control", "30db26bdd8fb5f153bfaa2fc19eafca4789c5f10", "artifacts/behavior/interface.json"),
    "bioelectric": ("work/bioelectric", "d0143976fc1621b350dce9e2a33ade3253657ccb", "artifacts/bioelectric/sodium_reduced.json"),
    "planner": ("work/experimental-design", "cc12164addd85c124a7e596b1059c005cf5650e9", "artifacts/experimental-design/result.json"),
}


def repo_root():
    return subprocess.check_output(["git", "rev-parse", "--git-common-dir"], cwd=HERE, text=True).strip()


def blob(src):
    _, commit, path = SOURCES[src]
    git_dir = os.path.abspath(os.path.join(HERE, repo_root())) if not os.path.isabs(repo_root()) else repo_root()
    return subprocess.check_output(["git", "--git-dir", git_dir, "show", f"{commit}:{path}"])


_cache = {}


def doc(src):
    if src not in _cache:
        _cache[src] = json.loads(blob(src))
    return _cache[src]


def resolve(obj, ptr):
    """JSON pointer; a segment `k=v` selects the list item whose key k equals v."""
    for seg in [s for s in ptr.split("/") if s]:
        if "=" in seg and isinstance(obj, list):
            k, v = seg.split("=", 1)
            hits = [x for x in obj if str(x.get(k)) == v]
            if len(hits) != 1:
                raise KeyError(f"{ptr}: {seg} matched {len(hits)} items")
            obj = hits[0]
        elif isinstance(obj, list):
            obj = obj[int(seg)]
        else:
            obj = obj[seg]
    return obj


def ref(src, ptr):
    """A value copied from a source blob, with its address so it can be re-read."""
    return {"value": resolve(doc(src), ptr), "src": src, "ptr": ptr}


def bound(status, basis, **kw):
    assert status in BOUND_STATUS
    return {"status": status, "basis": basis, **kw}


def eco_delay_table():
    """Per setting, neighbors versus no-neighbor ablation, at the fixed 0.6 s saved endpoint only.
    (triggered_count at run end is not used: every fish eventually responds, so it hides the delay.)"""
    rows = {}
    for r in doc("ecology")["results"]:
        t, ep = r["task"], r["endpoint"]
        assert ep["available"], r["id"]
        rows.setdefault((t["setting"], "neighbors" if t["neighbors"] else "ablation"), []).append(
            (t["seed"], ep["response_count"], len(r["main_summary"]["delays_s"]), t["overrides"]))
    return [{"setting": s, "mode": m, "responses_at_0_6s": sum(x[1] for x in v), "fish": sum(x[2] for x in v),
             "seeds": [x[0] for x in v], "overrides": v[0][3]} for (s, m), v in sorted(rows.items())]


def eco_override(key):
    """The distinct values a parameter takes across the saved arms, read from the arms' own overrides."""
    vals = [r["overrides"][key] for r in eco_delay_table() if key in r["overrides"]]
    return sorted({json.dumps(v) for v in vals})


def build():
    def eco_vals(k):
        return {"value": [json.loads(x) for x in eco_override(k)], "src": "ecology", "ptr": "derived:eco_delay_table"}
    srcs = []
    for sid, (branch, commit, path) in SOURCES.items():
        b = blob(sid)
        srcs.append({"id": sid, "branch": branch, "commit": commit, "path": path,
                     "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)})
    knobs = "knobs"
    lay = []

    lay.append({
        "id": "molecular-regulatory", "scale": "molecular/regulatory", "region_ids": [],
        "label": "Gene regulation to fin program",
        "what_exists": "Measured zebrafish fin multiome and methylation datasets mapped for applicability; no flying-fish measurement and no regulatory model run.",
        "parameters": [],
        "controls_note": "No controllable parameter is identified at this scale: the sources report observed expression/accessibility, not an intervention-response relation.",
        "results": [
            {"id": "reg-rows", "text": "Cell-state rows with explicit species/tissue/assay/accession and a stated missing bridge",
             "count": len(doc("regulatory")["rows"]), "ref": {"src": "regulatory", "ptr": "/rows"}},
            {"id": "reg-sample-identity", "text": "Confirmed independent biological sample count in the GEO metadata audit stays null; do not count 20 libraries as 20 replicates",
             "ref": ref("reg-metadata", "/targets/target=GSE261907/sample_count"), "independent_count": None},
        ],
        "bridges": [{"id": "regulatory-" + p["from"].replace(" ", "-") + "-to-" + p["to"].replace(" ", "-").replace("/", "-"),
                     "from": p["from"], "to": p["to"], "status": p["status"], "value": p["value"],
                     "ref": {"src": "regulatory", "ptr": f"/coupling_ports/{i}"}}
                    for i, p in enumerate(doc("regulatory")["coupling_ports"])],
    })

    lay.append({
        "id": "cell-bioelectric", "scale": "cellular", "region_ids": [],
        "label": "Membrane voltage and gap-junction coupling (Hodgkin-Huxley chain, 12 cells)",
        "what_exists": "A published-squid-parameter simulator with closed-form and convergence controls; no fin-cell calibration and no voltage-to-tissue map.",
        "parameters": [
            {"id": "sodium_scale", "label": "Sodium conductance scale", "unit": "1", "controllable": True,
             "value": ref("bioelectric", "/request/sodium_scale"),
             "bound": bound("assumed", "scenario value (x0.35 arm of a perturbation set); published squid g_Na is the baseline, not a fin measurement",
                            scale_arm=ref("bioelectric", "/request/sodium_scale")),
             "sensitivity": {"kind": "simulated scenario contrast", "result": "x0.35 arm: no cell crosses 0 mV in the 30 ms window (assurance handoff, bioelectric branch)",
                             "ref": ref("bioelectric", "/metrics")},
             "identifiability": "not assessed: no voltage data from target tissue exists in these sources"},
            {"id": "gap_mS_cm2", "label": "Gap-junction conductance", "unit": "mS/cm2", "controllable": True,
             "value": ref("bioelectric", "/request/gap_mS_cm2"),
             "bound": bound("assumed", "network and coupling assumed; model source gives membrane parameters only"),
             "sensitivity": {"kind": "simulated scenario contrast", "result": "disconnected arm: only the stimulated cell fires (bioelectric handoff)", "ref": ref("bioelectric", "/limitations")},
             "identifiability": "not assessed"},
        ],
        "results": [{"id": "bio-limits", "text": "Scope limits stated by the producing model", "ref": ref("bioelectric", "/limitations")}],
        "bridges": [{"id": "voltage-to-gene-tissue-fin", "from": "membrane voltage", "to": "tissue/fin geometry or stiffness",
                     "status": "unsupported", "value": None, "ref": {"src": "bioelectric", "ptr": "/open_questions"}}],
    })

    lay.append({
        "id": "tissue-fin-ray", "scale": "tissue/organ", "region_ids": ["pectoral-left", "pectoral-right"],
        "label": "Fin ray mechanics (single Euler-Bernoulli beam, two load shapes)",
        "what_exists": "A frozen-protocol paired ensemble over three predeclared candidates with analytic, grid, speed-law-mutant and local-sensitivity controls.",
        "parameters": [
            {"id": "ray_length_m", "label": "Ray length", "unit": "m", "controllable": True,
             "value": ref("fin-protocol", "/candidates/id=baseline/ray_length_m"),
             "alternative": ref("fin-protocol", "/candidates/id=shorter-ray/ray_length_m"),
             "bound": bound("assumed", "two declared design candidates; multiplier range is an assumed latent, not measured geometry",
                            multiplier=ref("fin-protocol", "/latents/geometry/maps/length_multiplier")),
             "sensitivity": {"kind": "local paired elasticity, other inputs held fixed (not causal, not variance importance)",
                             "elasticity": ref("fin-controls", "/paired_sensitivity/length_multiplier/elasticity"),
                             "expected_from_dimensions": ref("fin-controls", "/paired_sensitivity/length_multiplier/expected_from_dimensions")},
             "identifiability": "geometry is a design choice here; no matched per-ray measurement exists"},
            {"id": "EI_multiplier", "label": "Flexural rigidity multiplier (EI)", "unit": "1", "controllable": True,
             "value": ref("fin-protocol", "/candidates/id=baseline/EI_multiplier"),
             "alternative": ref("fin-protocol", "/candidates/id=stiffer-ray/EI_multiplier"),
             "bound": bound("assumed", "design draw 0.0003*10^u N m2 is assumed; the bluegill composite-modulus envelope is a separate source context and is never transferred to candidate EI",
                            design_draw=ref("fin-protocol", "/latents/design_material/maps/EI_Nm2"),
                            source_context=ref("fin-protocol", "/context_only/source_values"),
                            source_status=ref("fin-protocol", "/context_only/source_status")),
             "sensitivity": {"kind": "local paired elasticity, other inputs held fixed",
                             "elasticity": ref("fin-controls", "/paired_sensitivity/EI_Nm2/elasticity"),
                             "expected_from_dimensions": ref("fin-controls", "/paired_sensitivity/EI_Nm2/expected_from_dimensions")},
             "identifiability": "stiffness and load scale are not separable from deflection reads alone: the planner's deflection-only design has rank 1 against 2 for deflection plus an independent load read (abstract linear-Gaussian cantilever, assumed prior, not this fin)",
             "identifiability_ref": {"deflection_only_rank": ref("planner", "/designs/id=deflection_only/identifiability/rank"),
                                     "mixed_rank": ref("planner", "/designs/id=mixed_load_deflection/identifiability/rank"),
                                     "status": ref("planner", "/status")}},
            {"id": "speed_m_s", "label": "Air speed (scenario)", "unit": "m/s", "controllable": False,
             "value": ref("fin-protocol", "/latents/weather/maps/speed_m_s"),
             "bound": bound("assumed", "weather latent is a declared stress scenario with perfect negative density/speed rank correlation, not fitted weather data"),
             "sensitivity": {"kind": "local paired elasticity; V^1-load mutant gives 1 and is detected",
                             "elasticity": ref("fin-controls", "/paired_sensitivity/speed_m_s/elasticity"),
                             "expected_from_dimensions": ref("fin-controls", "/paired_sensitivity/speed_m_s/expected_from_dimensions")},
             "identifiability": "uncontrolled context"},
        ],
        "results": [
            {"id": "ensemble-" + c["candidate"]["id"], "text": f"both-load predicate passes, {c['candidate']['id']}",
             "numerator": ref("fin-summary", f"/candidates/{i}/numerator"), "denominator": ref("fin-summary", f"/candidates/{i}/denominator"),
             "fraction": ref("fin-summary", f"/candidates/{i}/fraction"),
             "interval_kind": "conditional Wilson 95%, sampling variation under the assumed scenario law only",
             "interval": ref("fin-summary", f"/candidates/{i}/conditional_wilson95_interval"),
             "meaning": "fraction of assumed-scenario draws inside the linear envelope; not a probability of biological success; draws are shared across candidates"}
            for i, c in enumerate(doc("fin-summary")["candidates"])],
        "bridges": [{"id": b["id"], "from": b["id"], "to": "target-fin behaviour", "status": b["status"], "value": None,
                     "need": b["need"], "ref": {"src": "assurance", "ptr": f"/project/unsupported_essential_bridges/id={b['id']}"}}
                    for b in doc("assurance")["project"]["unsupported_essential_bridges"]],
    })

    pect = doc(knobs)["knobs"]
    lay.append({
        "id": "organ-fin-proportions", "scale": "organ", "region_ids": ["pectoral-left", "pectoral-right", "pelvic-left", "pelvic-right"],
        "label": "Measured fin proportions (flying fish and relatives)",
        "what_exists": "The only measured per-specimen data in this map: Daane 2021 Data S1A fin length against standard length, fitted here, plus published Fish 1990 fits without raw data.",
        "parameters": [
            {"id": "pectoral_vs_SL_flying_fish", "label": "Pectoral fin length against standard length (flying fish)", "unit": "cm vs cm", "controllable": False,
             "value": ref(knobs, "/knobs/id=s1a-pectoral-length-vs-sl-flying-fish/fit/b"),
             "bound": bound("measured", "log10-log10 OLS on specimens; bootstrap 95% CI on the exponent, in-sample fit over the stated SL range only",
                            ci95=ref(knobs, "/knobs/id=s1a-pectoral-length-vs-sl-flying-fish/fit/bootstrap/b_ci95"),
                            n=ref(knobs, "/knobs/id=s1a-pectoral-length-vs-sl-flying-fish/fit/n"),
                            r2=ref(knobs, "/knobs/id=s1a-pectoral-length-vs-sl-flying-fish/fit/r2")),
             "sensitivity": {"kind": "measured allometry exponent, not a design sensitivity"},
             "identifiability": "fin length is identified against SL in sample; leave-one-out RMSE is reported",
             "identifiability_ref": {"loocv_rmse_log10": ref(knobs, "/knobs/id=s1a-pectoral-length-vs-sl-flying-fish/fit/loocv_rmse_log10"),
                                     "quality": ref(knobs, "/knobs/id=s1a-pectoral-length-vs-sl-flying-fish/fit_quality")}},
            {"id": "pelvic_vs_SL_flying_halfbeak", "label": "Pelvic fin length against standard length (flying halfbeak)", "unit": "cm vs cm", "controllable": False,
             "value": ref(knobs, "/knobs/id=s1a-pelvic-length-vs-sl-flying-halfbeak/fit/b"),
             "bound": bound("measured", "same method; fit judged unusable",
                            r2=ref(knobs, "/knobs/id=s1a-pelvic-length-vs-sl-flying-halfbeak/fit/r2"),
                            n=ref(knobs, "/knobs/id=s1a-pelvic-length-vs-sl-flying-halfbeak/fit/n")),
             "sensitivity": {"kind": "none: no relation recovered"},
             "identifiability": "not identifiable from these data",
             "identifiability_ref": {"quality": ref(knobs, "/knobs/id=s1a-pelvic-length-vs-sl-flying-halfbeak/fit_quality")}},
        ],
        "results": [{"id": "knob-count", "text": "Control-knob records by kind; per-specimen raw data exist only for the observed_and_fitted_here kind",
                     "count": len(pect), "kinds": sorted({k["kind"] for k in pect})}],
        "bridges": [{"id": "fin-length-to-ray-EI", "from": "fin length proportion", "to": "ray EI(x) and load field",
                     "status": "unknown", "value": None,
                     "need": "S1A has fin length against SL only; ray geometry, EI and load are not in it",
                     "ref": {"src": "fin-summary", "ptr": "/next_measurements"}}],
    })

    lay.append({
        "id": "body-glide-escape", "scale": "organism/collective", "region_ids": ["body", "pectoral-left", "pectoral-right", "pelvic-left", "pelvic-right"],
        "label": "Rigid-body glide and eight-fish escape (MuJoCo + quasi-steady VLM, not CFD)",
        "what_exists": "28 scenarios and 56 simulations with timestep and actuator gates passed; the assumed-delay arms are the only parameter contrast with saved outcomes.",
        "parameters": [
            {"id": "mass_kg", "label": "Body mass", "unit": "kg", "controllable": True,
             "value": eco_vals("mass_kg"),
             "bound": bound("assumed", "engineering assumption; not resin mass or a measured specimen"),
             "sensitivity": {"kind": "paired arms (the baseline 0.05 kg is the unlisted default)", "result": "responses at 0.6 s are the same as baseline in both mass arms; two seeds, no interaction estimate"},
             "identifiability": "no interaction estimate was made"},
            {"id": "reaction_delay_s_range", "label": "Escape reaction-delay range", "unit": "s", "controllable": True,
             "value": eco_vals("reaction_delay_s_range"),
             "bound": bound("assumed", "assumed delay envelope; no measured neural parameter"),
             "sensitivity": {"kind": "saved paired outcomes at the fixed 0.6 s endpoint (response flags, neighbors vs no-neighbor ablation); no variance partition", "table": eco_delay_table()},
             "identifiability": "two seeds per arm; no variance partition and no interaction estimate"},
            {"id": "fin_stiffness_Nm_rad", "label": "Hinge stiffness", "unit": "N m/rad", "controllable": True,
             "value": eco_vals("fin_stiffness_Nm_rad"),
             "bound": bound("assumed", "engineering hinge assumption"),
             "sensitivity": {"kind": "saved paired arms", "result": "responses at 0.6 s equal baseline in both hinge arms; two seeds"},
             "identifiability": "not assessed"},
        ],
        "results": [
            {"id": "eco-scope", "text": "Aggregate scope", "scenarios": ref("ecology", "/scenario_count"), "computed": ref("ecology", "/computed_count"),
             "status": ref("ecology", "/status"), "scope": ref("ecology", "/scope")},
        ],
        "bridges": [{"id": "glide-to-flight-prediction", "from": "simulated glide/escape", "to": "organism behaviour",
                     "status": "unsupported", "value": None, "need": "no calibrated or measured trajectory comparison",
                     "ref": {"src": "assurance", "ptr": "/project/unsupported_essential_bridges/id=fin-deformation-aerodynamic-polar"}}],
    })

    lay.append({
        "id": "behavior-control", "scale": "neural/behavior", "region_ids": ["body", "caudal"],
        "label": "Phase-oscillator controller with PD actuator",
        "what_exists": "An engineering controller with passing numerical controls; no neurons, no genotype-to-behavior map, no hydrodynamic transfer.",
        "parameters": [
            {"id": "frequency_Hz", "label": "Oscillator frequency", "unit": "Hz", "controllable": True,
             "value": ref("behavior", "/parameter_registry/name=frequency_Hz/value"),
             "bound": bound("assumed", "assumed scenario; literature range discussed but not fitted",
                            basis_text=ref("behavior", "/parameter_registry/name=frequency_Hz/basis")),
             "sensitivity": {"kind": "scenario contrast (35 Hz baseline vs 25 Hz), controller metrics only"},
             "identifiability": "not assessed"},
        ],
        "results": [{"id": "behavior-transfer", "text": "Proposed angle-to-fluid coupling is explicitly unsupported",
                     "ref": ref("behavior", "/proposed_coupling/status")}],
        "bridges": [{"id": "phase-to-fluid-force", "from": "oscillator phase/frequency", "to": "fluid force",
                     "status": "unsupported", "value": None, "need": ref("behavior", "/proposed_coupling/need")["value"],
                     "ref": {"src": "behavior", "ptr": "/proposed_coupling"}}],
    })

    # work packages: independence is claimed only where no declared input of one is an output of another
    wps = [
        {"id": "wp-fin-EI-load", "title": "Measure EI(x) under target clamping and the load field", "kind": "physical-measurement",
         "closes": ["tissue-to-EI"], "inputs": [], "status": "proposed-not-executed",
         "why": ref("fin-summary", "/next_measurements/0"), "gates": ["frozen protocol before data", "matched ray geometry + clamp + actuation tuple", "independent load-scale read (planner: deflection-only is rank 1)"]},
        {"id": "wp-load-shape", "title": "Measure spatial pressure/load shape", "kind": "physical-measurement",
         "closes": ["fin-load-bridge"], "inputs": [], "status": "proposed-not-executed",
         "why": ref("fin-summary", "/next_measurements/1"), "gates": ["frozen protocol before data"]},
        {"id": "wp-reg-sample-identity", "title": "Resolve GSE261907 barcode and replicate pairing from small metadata files", "kind": "computational-metadata",
         "closes": ["expression-to-conductance (first step only)"], "inputs": [], "status": "proposed-not-executed",
         "why": ref("regulatory", "/proposed_next_actions/id=fin-regulatory-coverage-audit/question"),
         "bound": ref("regulatory", "/proposed_next_actions/id=fin-regulatory-coverage-audit/bound"),
         "stop_rule": ref("regulatory", "/proposed_next_actions/id=fin-regulatory-coverage-audit/stop_rule")["value"]},
        {"id": "wp-moving-wall", "title": "Moving-wall fluid solver with calibration controls", "kind": "computational-model",
         "closes": ["phase-to-fluid-force"], "inputs": [], "status": "not-started",
         "why": ref("behavior", "/proposed_coupling/need")},
        {"id": "wp-cost-mass-area", "title": "Mass and lifting-area cost of shorter or stiffer rays", "kind": "physical-measurement",
         "closes": ["candidate choice (shorter vs stiffer)"], "inputs": [], "status": "proposed-not-executed",
         "why": ref("fin-summary", "/next_measurements/2")},
        {"id": "wp-deformed-polar", "title": "Deformed-fin aerodynamic polar", "kind": "computational-model",
         "closes": ["fin-deformation-aerodynamic-polar"], "inputs": ["wp-fin-EI-load", "wp-load-shape"], "status": "blocked-on-inputs",
         "why": ref("assurance", "/project/unsupported_essential_bridges/id=fin-deformation-aerodynamic-polar/need")},
    ]
    nxt = {
        "id": "wp-fin-EI-load",
        "why_this_one": [
            "It is the only item that both removes an explicit essential blocker (tissue-to-EI) and has a stated measurement in the owning handoff.",
            "The ensemble fractions differ across candidates only under assumed envelopes; the fin assay's own next step is EI(x), and mesh refinement alone does not address the larger uncertainties.",
            "Planner structure result: deflection-only reads leave stiffness and load scale confounded (rank 1), so the measurement must include an independent load read.",
        ],
        "not_claimed": "No expected-information-gain or utility number ranks the packages: the assurance map leaves both null because cost and outcome models are absent.",
        "assurance_priority_class": ref("assurance", "/project/next_actions/id=resolve-cell-tissue-fin/priority_class"),
        "expected_information_gain": ref("assurance", "/project/next_actions/id=resolve-cell-tissue-fin/expected_information_gain"),
    }
    return {
        "schema": SCHEMA,
        "concept": {"line": "Evidence-led science. Goal-driven engineering.",
                    "text": "Bottom-up: Delphi literature claims and equations. Top-down: design requirements. The gaps appear where they do not meet."},
        "separation": "Humans set the target goals. Solver or model validity (checked equations, convergence, controls) is a different thing from empirical biological realism, which is unknown for every layer here.",
        "biological_success_probability": None, "confidence_percent": None, "aggregate_score": None,
        "sources": srcs, "layers": lay, "workpackages": wps, "next_experiment": nxt,
        "execution_note": "Work packages are independent exactly when their inputs lists are disjoint; wp-deformed-polar depends on two others. Nothing here is executed or decentralized: all rows are proposals.",
        "non_claims": ["No new simulation, measurement or inference was run to make this map.",
                       "Fractions are conditional simulation-envelope fractions, not probabilities of biology.",
                       "Local elasticities hold other inputs fixed and are not causal biological effects."],
    }


def collect_refs(o, path=""):
    if isinstance(o, dict):
        if "src" in o and "ptr" in o:
            yield path, o
        for k, v in o.items():
            yield from collect_refs(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from collect_refs(v, f"{path}/{i}")


FORBIDDEN = ("probability", "confidence", "score", "plddt", "pae")


def check(m):
    """Return a list of problems; empty means every integrity check held."""
    bad = []
    for s in m["sources"]:
        b = blob(s["id"])
        if hashlib.sha256(b).hexdigest() != s["sha256"] or len(b) != s["bytes"]:
            bad.append(f"source {s['id']}: blob differs from pinned bytes")
    for p, r in collect_refs(m):
        if r["ptr"].startswith("derived:"):
            continue
        try:
            now = resolve(doc(r["src"]), r["ptr"])
        except Exception as e:
            bad.append(f"{p}: {r['src']}{r['ptr']} unresolved ({e})")
            continue
        if "value" in r and now != r["value"]:
            bad.append(f"{p}: value drift at {r['src']}{r['ptr']}")
    if m != build():
        bad.append("map.json differs from a fresh build of the pinned sources")
    ids = {w["id"] for w in m["workpackages"]}
    for w in m["workpackages"]:
        for i in w["inputs"]:
            if i not in ids:
                bad.append(f"{w['id']}: unknown input {i}")
    def reach(a, seen=()):
        w = next((x for x in m["workpackages"] if x["id"] == a), None)
        return w is not None and any(i == a or i in seen or reach(i, seen + (a,)) for i in w["inputs"])
    for w in m["workpackages"]:
        if reach(w["id"]):
            bad.append(f"dependency cycle through {w['id']}")
    for layer in m["layers"]:
        for q in layer["parameters"]:
            st = q["bound"]["status"]
            if st not in BOUND_STATUS:
                bad.append(f"{q['id']}: bound status {st}")
            if st == "measured" and not (q["bound"].get("n") or {}).get("value"):
                bad.append(f"{q['id']}: measured without an n")
            if st in ("assumed", "sourced") and not q["bound"].get("basis"):
                bad.append(f"{q['id']}: {st} bound without basis")
    def walk(o, p=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if any(f in k.lower() for f in FORBIDDEN) and v is not None and not isinstance(v, (dict, list)) and k not in ("interval_kind",):
                    bad.append(f"{p}/{k}: forbidden score-like field is non-null")
                walk(v, f"{p}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{p}/{i}")
    walk(m)
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.write:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as f:
            json.dump(build(), f, indent=1, sort_keys=True)
            f.write("\n")
        print("wrote", OUT)
    if a.check:
        bad = check(json.load(open(OUT)))
        for b in bad:
            print("PROBLEM", b)
        print("problems:", len(bad))
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
