"""Genotype-to-design interface layer for the biodesign compiler (SPEC-014 extension). It is bookkeeping and refusal logic, not a genome compiler.

It adds, next to compile.py (which only checks linked artifacts):
  * an explicit dependency graph  dna -> expression/cell program -> growth/material -> fin shape/mechanics -> performance/behavior,
    built from the repository's real bridges (design-control map, compiler report, genetic blueprints), every interface unknown today;
  * a design document a candidate genotype would arrive in, with pinned sequence artifacts, build-plan PROPOSALS and per-interface evidence
    that is valid for ONE stated genotype/species/cell state/stage/environment;
  * a verdict that REJECTS a claimed working assembly unless every interface carries a calibrated transfer for the design's own context,
    every sequence pin still matches its bytes and every measured bound equals the bound in its pinned measurement;
  * change propagation: what a change invalidates downstream, and which independently checked layers are retained.
It never emits DNA, never orders anything, runs no model and makes no biological claim. Homology or marker similarity never raises an
interface above "unknown"."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from engineering.biodesign_compiler import compile as bc

ROOT = Path(__file__).resolve().parents[2]
GRAPH_SCHEMA = "frontier.biodesign.genotype-graph/1"
DESIGN_SCHEMA = "frontier.biodesign.genotype-design/1"
REPORT_SCHEMA = "frontier.biodesign.genotype-report/1"
NODES = ("dna", "expression", "growth_material", "shape_mechanics", "performance", "behavior")
NODE_TEXT = {
    "dna": "candidate sequence and construct (pinned artifact, never generated here)",
    "expression": "expression and cell program in a stated cell state and stage",
    "growth_material": "growth and material: proliferation, matrix and mineral deposition",
    "shape_mechanics": "fin shape and mechanics: ray geometry, stiffness EI(x), load",
    "performance": "aerodynamic performance of the fin and body (forces, glide)",
    "behavior": "organism behaviour and control",
}
INTERFACES = {"I1": ("dna", "expression"), "I2": ("expression", "growth_material"), "I3": ("growth_material", "shape_mechanics"), "I4": ("shape_mechanics", "performance"), "I5": ("performance", "behavior")}
INTERFACE_TEXT = {
    "I1": "DNA to expression in the stated cell state",
    "I2": "expression to growth/material (conductance, proliferation, deposition)",
    "I3": "growth/material to ray geometry and stiffness EI",
    "I4": "fin shape and deformation to aerodynamic performance",
    "I5": "simulated performance to organism behaviour and control",
}
# design-control bridge ids and compiler bridge names that belong to each interface (all read from the pinned files below)
BRIDGES = {
    "I1": ["blueprint->cell_program"],
    "I2": ["regulatory-expression-to-channel-density-conductance", "regulatory-voltage-or-transport-to-proliferation-rate", "regulatory-osteoblast/fibroblast-state-to-mineral-ECM-deposition", "voltage-to-gene-tissue-fin", "expression->growth"],
    "I3": ["regulatory-deposition-to-ray-geometry-and-EI", "fin-length-to-ray-EI", "fin-stiffness-calibration", "growth->EI"],
    "I4": ["fin-deformation-aerodynamic-polar", "cell-tissue-fin"],
    "I5": ["glide-to-flight-prediction", "phase-to-fluid-force"],
}
WORKPACKAGES = {"I2": ["wp-reg-sample-identity"], "I3": ["wp-fin-EI-load"], "I4": ["wp-load-shape", "wp-deformed-polar"], "I5": ["wp-moving-wall"]}
STATES = ("unknown", "proposed", "measured_context", "calibrated_transfer")  # "contradicted" (from a ledger bridge) is a blocker, not a rung
CONTEXT_FIELDS = ("species", "tissue", "cell_state", "life_stage", "condition", "allele", "construct_context")  # the sequence-function ledger's vocabulary
LEDGER_SCHEMA = "frontier.sequence-function-ledger/1"
BRIDGE_STATE = {"context_supported": "measured_context", "proposed": "proposed", "unresolved": "unknown", "contradicted": "contradicted"}
SOURCES = {"design_control": "artifacts/design-control/map.json", "compiler_report": "artifacts/biodesign-compiler/report.json", "blueprints": "artifacts/genetic-blueprints/blueprints.json"}
MUST_NOT_SAY = ["a working genome or construct was designed", "homology or a marker shows a function transfers to this organism", "an unresolved interface is a violated constraint", "a calibration measured in one context holds in another"]


# ----------------------------------------------------------------------------------------------------------- baseline graph
def baseline_graph(root: Path = ROOT) -> dict:
    """The graph as the repository's own files state it today. Every interface is unknown; each lists the bridges that would close it,
    the experiments the design-control map proposes, and the context a measurement must name."""
    pins = {k: bc.pin(root, v) for k, v in SOURCES.items()}
    dc = json.loads((root / SOURCES["design_control"]).read_text())
    rep = json.loads((root / SOURCES["compiler_report"]).read_text())
    bridges = {b["id"]: {"from": b["from"], "to": b["to"], "source_status": b["status"], "layer": L["id"]} for L in dc["layers"] for b in L.get("bridges", [])}
    cbridges = {b["bridge"]: {"source_status": b["status"], "reason": b["reason"]} for c in rep["compiled"][:1] for b in c["unresolved_bridges"]}
    wps = {w["id"]: {"title": w["title"], "kind": w["kind"], "status": w["status"], "closes": w["closes"]} for w in dc["workpackages"]}
    ifs = {}
    for iid, (a, b) in INTERFACES.items():
        ev, missing = [], []
        for name in BRIDGES[iid]:
            src = bridges.get(name) or cbridges.get(name)
            (ev if src else missing).append({"bridge": name, **(src or {})} if src else name)
        ifs[iid] = {
            "from": a,
            "to": b,
            "text": INTERFACE_TEXT[iid],
            "state": "unknown",
            "bridges": ev,
            "bridges_not_in_sources": missing,
            "required_context": list(CONTEXT_FIELDS),
            "required_measurement": "a measured transfer (quantity, unit, bounds) for exactly the design's genotype, species, cell state, stage and environment",
            "proposed_experiments": [{"id": w, **wps[w]} for w in WORKPACKAGES.get(iid, []) if w in wps] or [{"note": "no experiment for this interface is recorded in the design-control map"}],
        }
    return {
        "schema": GRAPH_SCHEMA,
        "nodes": [{"id": n, "text": NODE_TEXT[n]} for n in NODES],
        "interfaces": ifs,
        "states": list(STATES),
        "sources": pins,
        "scope": "an explicit dependency graph of what a genotype-to-fin design needs; every interface is unknown and nothing is calibrated",
        "must_not_say": MUST_NOT_SAY,
        "biological_success_probability": None,
    }


# --------------------------------------------------------------------------------------------------------------- checking
def _pointer(doc, ptr):
    for part in [p for p in ptr.split("/") if p]:
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


def _pinned(root: Path, ref) -> tuple[bytes | None, str | None]:
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        return None, "no pinned path and sha256"
    f = Path(root) / ref["path"]
    if not f.is_file():
        return None, f"pinned file {ref['path']} is missing"
    b = f.read_bytes()
    if bc.sha(b) != ref["sha256"]:
        return None, f"{ref['path']} changed: pinned {ref['sha256'][:12]}, found {bc.sha(b)[:12]}"
    return b, None


def _context_mismatch(design_ctx: dict, ev_ctx: dict) -> list[str]:
    return [f for f in CONTEXT_FIELDS if not ev_ctx.get(f) or ev_ctx.get(f) != design_ctx.get(f)]


def check_sequence(root: Path, c: dict) -> dict:
    """A candidate sequence is acceptable only as a pinned artifact whose bytes still match; a bare literal is refused."""
    problems = []
    if c.get("sequence") and not c.get("source_ref"):
        problems.append("a sequence literal without a pinned source artifact is refused (no unpinned DNA)")
    b, err = _pinned(root, c.get("source_ref")) if c.get("source_ref") else (None, "no pinned source artifact")
    if err and c.get("source_ref"):
        problems.append(("stale sequence reference: " if "changed" in err else "") + err)
    if b is not None and c.get("sequence_sha256") and c.get("sequence") and bc.sha(c["sequence"].encode()) != c["sequence_sha256"]:
        problems.append("sequence_sha256 does not match the sequence text")
    if not c.get("source_ref") and not problems:
        problems.append("no pinned source artifact")
    kind = c.get("evidence_kind")
    return {
        "id": c.get("id"),
        "source_ref": c.get("source_ref"),
        "sequence_sha256": c.get("sequence_sha256"),
        "length": c.get("length"),
        "evidence_kind": kind,
        "observed_context": c.get("observed_context"),
        "problems": problems,
        "valid": not problems,
        "note": "homology or marker similarity is not function: this candidate leaves the dna->expression interface unknown" if kind in ("homology", "none", None) else "measured expression in the stated context is still not a calibrated transfer",
    }


def check_evidence(root: Path, ev: dict, design_ctx: dict) -> dict:
    iid = ev.get("interface")
    reasons = []
    if iid not in INTERFACES:
        return {"interface": iid, "status": "unknown", "applicable": False, "valid": False, "reasons": ["unknown interface id"]}
    status = ev.get("status", "unknown")
    if status == "contradicted":
        return {"interface": iid, "status": "contradicted", "effective": "unknown", "applicable": False, "valid": False, "context": ev.get("context"), "transfer": ev.get("transfer"), "reasons": ["the ledger records this bridge as contradicted: it blocks a working claim and is not a calibration"]}
    if status not in STATES:
        reasons.append(f"status {status!r} is not one of {', '.join(STATES)}")
        status = "unknown"
    mism = _context_mismatch(design_ctx, ev.get("context") or {})
    applicable = not mism
    if mism:
        reasons.append("context mismatch (" + ", ".join(f"{f}: evidence {((ev.get('context') or {}).get(f))!r} vs design {design_ctx.get(f)!r}" for f in mism) + "): the calibration does not apply and is not used")
    if status == "measured_context" and not ev.get("transfer") and not ev.get("ledger_bridge"):
        reasons.append("measured bound not verifiable: a measured context needs a pinned measurement or a pinned ledger bridge")
    if status == "calibrated_transfer" or (status == "measured_context" and ev.get("transfer")):
        t = ev.get("transfer") or {}
        ref = t.get("bound_ref") or {}
        b, err = _pinned(root, ref)
        if err:
            reasons.append("measured bound not verifiable: " + err)
        else:
            try:
                doc = json.loads(b)
                lo, hi = _pointer(doc, ref["pointer"] + "/lo"), _pointer(doc, ref["pointer"] + "/hi")
                if (lo, hi) != (t.get("lo"), t.get("hi")):
                    reasons.append(f"transfer bound [{t.get('lo')}, {t.get('hi')}] differs from the pinned measurement [{lo}, {hi}]")
                elif t.get("value_used") is not None and not (lo <= t["value_used"] <= hi):
                    reasons.append(f"value used {t['value_used']} lies outside the measured bound [{lo}, {hi}]")
            except (ValueError, KeyError, IndexError, TypeError):
                reasons.append("the pointer does not lead to a lo/hi pair in the pinned measurement")
    valid = not any(r.startswith(("measured bound", "transfer bound", "value used", "the pointer", "status", "unknown interface")) for r in reasons)
    effective = status if (valid and applicable) else ("proposed" if status == "proposed" and applicable else "unknown")
    return {"interface": iid, "status": status, "effective": effective, "applicable": applicable, "valid": valid, "context": ev.get("context"), "transfer": ev.get("transfer"), "reasons": reasons}


def compile_design(root: Path, graph: dict, design: dict) -> dict:
    """Assess one design document against the graph. Returns a report with a verdict; the default and the only positive outcomes are
    "proposal_only" and (when every interface is calibrated for the design's own context) "consistent_evidence_for_the_stated_context"."""
    root = Path(root)
    problems = []
    if design.get("schema") != DESIGN_SCHEMA:
        problems.append(f"schema must be {DESIGN_SCHEMA}")
    ctx = design.get("context") or {}
    for f in CONTEXT_FIELDS:
        if not ctx.get(f):
            problems.append(f"context.{f} is required: an interface is specific to genotype, species, cell state, stage and environment")
    seqs = [check_sequence(root, c) for c in design.get("sequence_candidates", [])]
    plans = []
    for p in design.get("build_plan_proposals", []):
        _, err = _pinned(root, p.get("ref"))
        pr = []
        if p.get("state", "proposed") != "proposed":
            pr.append(f"state {p.get('state')!r} is refused: a build plan is a proposal; nothing is ordered or built here")
        if err:
            pr.append(err)
        plans.append({"id": p.get("id"), "ref": p.get("ref"), "state": "proposed", "problems": pr, "valid": not pr})
    led = consume_ledger(root, design)
    direct = [e for e in design.get("interface_evidence", []) if "ledger_bridge" not in e]
    evs = [check_evidence(root, e, ctx) for e in direct + led["interface_evidence"]]  # ledger-derived items carry "ledger_bridge"
    for ev, src in zip(evs[len(direct) :], led["interface_evidence"]):
        ev["ledger_bridge"], ev["ledger_status"] = src["ledger_bridge"], src["ledger_status"]
    best = {}
    for iid in INTERFACES:
        cand = [e["effective"] for e in evs if e["interface"] == iid]
        best[iid] = max(cand, key=STATES.index) if cand else "unknown"
    tests = [{k: t.get(k) for k in ("id", "interface", "kind", "description")} | {"status": "proposed"} for t in design.get("validation_tests", [])]
    unresolved = [{"interface": i, "text": INTERFACE_TEXT[i], "state": s, "needs": "calibrated transfer for " + ", ".join(f"{f}={ctx.get(f)}" for f in CONTEXT_FIELDS) if ctx else "a stated context"} for i, s in best.items() if s != "calibrated_transfer"]
    claimed = design.get("claim") == "working_assembly"
    reasons = list(problems) + led["problems"]
    reasons += [f"{s['id']}: {p}" for s in seqs for p in s["problems"]] + [f"plan {p['id']}: {q}" for p in plans for q in p["problems"]]
    reasons += [f"{e['interface']}: {r}" for e in evs for r in e["reasons"] if not e["valid"]]
    if claimed:
        if unresolved:
            reasons.append("required interfaces are not calibrated for this context: " + ", ".join(u["interface"] for u in unresolved))
        verdict = "rejected" if reasons else "consistent_evidence_for_the_stated_context"
    else:
        verdict = "proposal_only" if not problems else "invalid_document"
    return {
        "schema": REPORT_SCHEMA,
        "design_id": design.get("id"),
        "context": ctx,
        "claim": design.get("claim", "none"),
        "verdict": verdict,
        "reasons": reasons,
        "interface_state": best,
        "interface_assessment": evs,
        "candidate_sequence_artifact_refs": [s for s in seqs if s["valid"]] + [x for x in led["sequences"] if x["valid"] and x["sequence_available"]],
        "sequences_without_artifact": [x for x in led["sequences"] if not x["sequence_available"]],
        "rejected_sequence_candidates": [s for s in seqs if not s["valid"]] + [x for x in led["sequences"] if not x["valid"]],
        "ledger": led["ledger"],
        "ledger_entries_consumed": led["entries"],
        "build_plan_proposal_refs": [p for p in plans if p["valid"]],
        "validation_tests": tests,
        "assembly_unresolved_interfaces": unresolved,
        "scope": "evidence bookkeeping only; no DNA was generated, nothing was ordered or run, and no biological claim follows from this verdict",
        "must_not_say": MUST_NOT_SAY,
    }


def propagate(graph: dict, design: dict, change: dict) -> dict:
    """What a change invalidates. change = {"node": n} or {"interface": I}. An interface is invalidated when the node it reads FROM (or an
    earlier one) changed; a node when it is the changed node or later. Claims, calibrations and checked layers name what they depend on, so
    everything upstream and every independent checked layer is retained. No transfer function is invented to bridge a changed layer."""
    order = [n["id"] for n in graph["nodes"]]
    ifs = graph["interfaces"]
    if "node" in change:
        k = order.index(change["node"])
        down_nodes = order[k:]
        down_ifs = [i for i, v in ifs.items() if order.index(v["from"]) >= k]
    else:
        iid = change["interface"]
        keys = list(ifs)
        down_ifs = keys[keys.index(iid) :]
        down_nodes = order[order.index(ifs[iid]["to"]) :]
    down = set(down_nodes) | set(down_ifs)
    claims = design.get("claims", [])
    calib = design.get("interface_evidence", [])
    layers = design.get("checked_layers", [])

    def dep(c):
        return bool(set(c.get("depends_on", [])) & down)

    return {
        "change": change,
        "invalidated_nodes": down_nodes,
        "invalidated_interfaces": down_ifs,
        "invalidated_claims": [c["id"] for c in claims if dep(c)],
        "retained_claims": [c["id"] for c in claims if not dep(c)],
        "invalidated_calibrations": [e["interface"] for e in calib if e["interface"] in down_ifs],
        "retained_calibrations": [e["interface"] for e in calib if e["interface"] not in down_ifs],
        # a checked layer is the node's OWN numerical check (e.g. the aerodynamic convergence of one geometry): only a change to that node touches it,
        # an upstream change (a sequence) invalidates the claims that link them, not the check itself
        "invalidated_checked_layers": [x["id"] for x in layers if x.get("node") == change.get("node")],
        "retained_checked_layers": [x["id"] for x in layers if x.get("node") != change.get("node")],
    }


# ------------------------------------------------------------------------------------------------- validation slices and cutsets
VALIDATION_SCHEMA = "frontier.biodesign.validation-slices/1"
INSTRUMENT_FIELDS = ["instrument id and version", "input schema with units", "observation schema with units", "noise or uncertainty model", "replicate unit", "cost and duration units"]
# What would check each causal boundary: the READOUT CLASS and the input it needs. These are requirements, not protocols and not results.
SLICES = {
    "I1": {
        "input": "the candidate construct, as a pinned sequence artifact, introduced into the stated cell state, stage and condition",
        "observation": "the expression readout of that construct (for example a reporter or transcript level) in the same context, with its unit and timing",
        "controls": ["empty-construct control", "the same element with the tested region deleted or mutated", "the same construct in a different context to show specificity"],
        "unknown": "whether the element drives expression outside the tested context; homology or marker similarity does not answer it",
    },
    "I2": {
        "input": "a controlled change in the expression level of the candidate in the stated cell state",
        "observation": "channel density or conductance, proliferation rate, and mineral/ECM deposition, measured in the same tissue and stage",
        "controls": ["no-change control", "a dose series so a transfer is bounded, not a single point", "an independent readout of the same quantity"],
        "unknown": "expression to growth/material has no sourced mapping; a voltage, transport or cell-state change is not shown to set proliferation or deposition",
    },
    "I3": {
        "input": "the growth/material state of the fin (deposition per ray) from the previous boundary",
        "observation": "ray geometry and EI(x) under the target clamping and actuation, with the load field",
        "controls": ["a calibration beam of known EI", "the same measurement on the unmodified fin", "repeat on independent fins (the replicate unit is the animal)"],
        "unknown": "growth to flexural rigidity has no registered mapping; the nearest registered coupling is refused",
    },
    "I4": {
        "input": "the measured fin shape, EI(x) and load field",
        "observation": "the aerodynamic polar of the deformed fin (CL, CD against angle) and its numerical convergence",
        "controls": ["rigid-fin polar", "a mesh/lattice refinement", "an independent solver or wind-tunnel point"],
        "unknown": "the fin-deformation polar and cell-tissue-fin bridges are unsupported; a coarse/fine agreement is not an empirical validation",
    },
    "I5": {
        "input": "the simulated or measured performance (forces, glide)",
        "observation": "organism behaviour and control: kinematics, glide or escape outcome, oscillator phase and frequency against fluid force",
        "controls": ["a passive-body control", "a measured trajectory for the same body", "a moving-wall fluid calibration"],
        "unknown": "simulated glide or escape is not an organism behaviour, and oscillator phase to fluid force is unsupported",
    },
}
NODE_CHECKS = {
    "dna": ("sequence identity: sha256 of the pinned artifact and its source accession", []),
    "expression": ("regulatory map and blueprint pins", ["implementation", "empirical"]),
    "growth_material": ("no independent check exists for growth or material at this layer", []),
    "shape_mechanics": ("geometry, panel and component pins; unit and context checks", ["structural_refs", "units_context"]),
    "performance": ("aerodynamic domain and numerical checks of one geometry", ["model_domain", "numerical"]),
    "behavior": ("no independent check exists for organism behaviour at this layer", []),
}
STANDARD_CLAIMS = [
    ("genotype to fin shape", "dna", "shape_mechanics"),
    ("genotype to aerodynamic performance", "dna", "performance"),
    ("expression to fin shape", "expression", "shape_mechanics"),
    ("fin shape to performance, genotype held fixed", "shape_mechanics", "performance"),
    ("genotype to organism behaviour", "dna", "behavior"),
]


def cutset(graph: dict, from_node: str, to_node: str, design: dict | None = None) -> dict:
    """The interfaces a claim from one node to another crosses: each must be checked, and the claim stands only if every one is."""
    order = [n["id"] for n in graph["nodes"]]
    a, b = order.index(from_node), order.index(to_node)
    ids = [i for i, v in graph["interfaces"].items() if order.index(v["from"]) >= a and order.index(v["to"]) <= b]
    states = (design or {}).get("interface_state") or {}
    return {"from": from_node, "to": to_node, "interfaces": ids, "not_calibrated": [i for i in ids if states.get(i, "unknown") != "calibrated_transfer"]}


def validation_slices(graph: dict, design: dict | None = None, report: dict | None = None) -> dict:
    """For each causal boundary: the exact input and observation class that would check it, controls, the decision rule, what stays unknown, the
    instrument slots (physical or virtual) another worker's contracts must fill, and what a proposed DNA change invalidates. Nothing here is a
    result or a calibrated transfer; every slice closes only with a calibrated_transfer pinned to the design's own context."""
    design = design or {}
    ctx = design.get("context") or {}
    ledger_readouts = []
    if report and report.get("ledger_entries_consumed"):
        ledger_readouts = [{"entry": e["id"], "falsifiable_validation_readout": e.get("falsifiable_validation_readout"), "missing_causal_bridge": e.get("missing_causal_bridge")} for e in report["ledger_entries_consumed"]]
    dna = propagate(graph, design, {"node": "dna"})
    ifs = {}
    for iid, spec in SLICES.items():
        g = graph["interfaces"][iid]
        ifs[iid] = {
            "boundary": g["text"],
            "from": g["from"],
            "to": g["to"],
            "state": (report or {}).get("interface_state", {}).get(iid, g["state"]),
            "input": spec["input"],
            "observation": spec["observation"],
            "controls": spec["controls"],
            "context_required": list(CONTEXT_FIELDS),
            "context_stated": ctx or None,
            "decision_rule": "closes only as calibrated_transfer: a measured bound pinned in a measurement artifact, equal to the bound the design states, in a context equal to the design's on every field; homology or similarity never closes it",
            "what_remains_unknown": spec["unknown"],
            "recorded_bridges": [b["bridge"] for b in g["bridges"]],
            "recorded_experiments": g["proposed_experiments"],
            "instrument_slots": [{"kind": k, "contract_ref": None, "owner": "experimental-design instrument contracts (claude14)", "required_fields": INSTRUMENT_FIELDS} for k in ("physical", "virtual")],
            "invalidated_by_dna_change": iid in dna["invalidated_interfaces"],
            "invalidated_by_context_change": True,
            "ledger_readouts": ledger_readouts if iid in ("I1", "I2") else [],
        }
    layer = {}
    for n in graph["nodes"]:
        text, axes = NODE_CHECKS[n["id"]]
        found = {}
        for c in (report or {}).get("compiled", [])[:1]:
            found = {a: c["axes"][a]["status"] for a in axes if a in c.get("axes", {})}
        layer[n["id"]] = {"independent_check": text, "compiler_axes": found, "retained_when_dna_changes": n["id"] != "dna", "note": "a layer's own check is untouched by an upstream change; the claims that link layers are what invalidates"}
    return {
        "schema": VALIDATION_SCHEMA,
        "interfaces": ifs,
        "layers": layer,
        "cutsets": [{"claim": c, **cutset(graph, a, b, design)} for c, a, b in STANDARD_CLAIMS],
        "after_proposed_dna_change": {k: dna[k] for k in ("invalidated_nodes", "invalidated_interfaces", "retained_calibrations", "invalidated_calibrations")} | {"meaning": "every interface evidence entry was for the previous sequence and must be repeated; independent numerical checks of other layers are retained"},
        "scope": "requirements for validation, not protocols, not results; no calibrated genotype-to-phenotype transfer exists or is implied",
        "must_not_say": MUST_NOT_SAY,
    }


# ------------------------------------------------------------------------------------------------ the sequence-function ledger
def read_ledger(root: Path, ref: dict) -> tuple[dict | None, list[str]]:
    """Pin the ledger (artifacts/sequence-evidence/ledger.json, native mechanobio): refuse missing, changed or wrong-schema bytes. Never mutates it."""
    b, err = _pinned(root, ref)
    if err:
        return None, [("stale ledger: " if "changed" in err else "ledger: ") + err]
    try:
        L = json.loads(b)
    except ValueError:
        return None, ["ledger is not valid JSON"]
    if L.get("schema") != LEDGER_SCHEMA:
        return None, [f"ledger schema must be {LEDGER_SCHEMA}"]
    return L, []


def _entry_context(e: dict) -> dict:
    return {"species": e.get("species"), "tissue": e.get("tissue"), "cell_state": e.get("cell_state"), "life_stage": e.get("life_stage"), "condition": e.get("injury_or_condition"), "allele": e.get("allele"), "construct_context": e.get("tested_construct_or_promoter_context")}


def consume_ledger(root: Path, design: dict) -> dict:
    """Carry each consumed sequence and entry with its context and evidence class; derive interface evidence from ledger bridges.
    A natural reference sequence is not equated with an experimental allele, and a model output has functional validation unknown."""
    use = design.get("ledger")
    if not use:
        return {"ledger": None, "problems": [], "sequences": [], "entries": [], "interface_evidence": []}
    L, problems = read_ledger(root, use.get("ref"))
    out = {"ledger": {"ref": use.get("ref"), "protocol": (L or {}).get("protocol")}, "problems": problems, "sequences": [], "entries": [], "interface_evidence": []}
    if L is None:
        return out
    seqs = {s["id"]: s for s in L.get("sequences", [])}
    ents = {e["id"]: e for e in L.get("entries", [])}
    brs = {b["id"]: b for b in L.get("bridges", [])}
    for sid in use.get("sequence_ids", []):
        s = seqs.get(sid)
        if s is None:
            out["problems"].append(f"sequence {sid} is not in the pinned ledger")
            continue
        art = s.get("artifact_ref")
        prob = []
        if art:
            _, err = _pinned(root, art)
            if err:
                prob.append(("stale sequence reference: " if "changed" in err else "") + err)
        out["sequences"].append(
            {
                "id": sid,
                "sequence_sha256": s.get("sequence_sha256"),
                "length_nt": s.get("length_nt"),
                "sequence_kind": s.get("sequence_kind"),
                "reference": s.get("reference"),
                "artifact_ref": art,
                "sequence_available": bool(art),
                "problems": prob,
                "valid": not prob,
                "note": ("model output: functional validation unknown, never a validated promoter" if s.get("sequence_kind") == "existing_model_output" else "a natural reference sequence is not the experimental allele") if s.get("sequence_kind") != "unknown" else "sequence kind unknown",
            }
        )
    for eid in use.get("entry_ids", []):
        e = ents.get(eid)
        if e is None:
            out["problems"].append(f"entry {eid} is not in the pinned ledger")
            continue
        out["entries"].append(
            {
                "id": eid,
                "evidence_class": e.get("evidence_class"),
                "context": _entry_context(e),
                "demonstrated_readout": e.get("demonstrated_readout"),
                "demonstrated_effect": e.get("demonstrated_effect"),
                "missing_causal_bridge": e.get("missing_causal_bridge"),
                "falsifiable_validation_readout": e.get("falsifiable_validation_readout"),
                "model_ready": e.get("model_ready"),
                "functional_validation": "unknown" if e.get("evidence_class") == "model_output" else e.get("evidence_class"),
            }
        )
    for item in design.get("interface_evidence", []):
        if "ledger_bridge" in item:
            b = brs.get(item["ledger_bridge"])
            if b is None:
                out["problems"].append(f"bridge {item['ledger_bridge']} is not in the pinned ledger")
                continue
            e = ents.get(b.get("from_entry")) or {}
            out["interface_evidence"].append(
                {"interface": item["interface"], "status": BRIDGE_STATE.get(b.get("status"), "unknown"), "context": _entry_context(e), "ledger_bridge": b["id"], "ledger_status": b.get("status"), "conditions": b.get("conditions"), "missing_parameters": b.get("missing_parameters"), "transfer": item.get("transfer")}
            )
    return out


# --------------------------------------------------------------------------------------------------------------------- CLI
def build_files(root: Path = ROOT) -> dict[str, str]:
    g = baseline_graph(root)
    baseline_design = {
        "schema": DESIGN_SCHEMA,
        "id": "baseline-proposal-no-sequence",
        "claim": "working_assembly",
        "context": {"species": "Danio rerio", "tissue": "caudal fin", "cell_state": "regenerating blastema", "life_stage": "adult", "condition": "amputation", "allele": "wild type, strain unspecified", "construct_context": "none: no construct"},
    }
    rep = compile_design(root, g, baseline_design)
    contract = {
        "schema": "frontier.biodesign.genotype-contract/1",
        "graph_file": "genotype-graph.json",
        "design_schema": DESIGN_SCHEMA,
        "report_schema": REPORT_SCHEMA,
        "states": list(STATES),
        "context_fields": list(CONTEXT_FIELDS),
        "rules": [
            "a sequence is accepted only as a pinned artifact whose bytes still match",
            "a calibration applies only when every context field equals the design's",
            "a measured bound must equal the bound in its pinned measurement",
            "homology or marker similarity leaves an interface unknown",
            "a claimed working assembly is rejected while any interface is not a calibrated transfer for its own context",
            "a build plan stays a proposal",
        ],
        "must_not_say": MUST_NOT_SAY,
        "baseline_example": {"design": baseline_design, "verdict": rep["verdict"], "unresolved": [u["interface"] for u in rep["assembly_unresolved_interfaces"]]},
    }
    vs = validation_slices(g, {"context": baseline_design["context"]}, {**rep, "compiled": json.loads((root / SOURCES["compiler_report"]).read_text())["compiled"]})
    files = {"genotype-graph.json": json.dumps(g, indent=1, sort_keys=True) + "\n", "genotype-contract.json": json.dumps(contract, indent=1, sort_keys=True) + "\n", "genotype-validation.json": json.dumps(vs, indent=1, sort_keys=True) + "\n"}
    man = {"schema": "frontier.artifact-manifest/1", "files": [{"path": f"artifacts/biodesign-compiler/{k}", "sha256": bc.sha(v.encode()), "bytes": len(v)} for k, v in sorted(files.items())]}
    files["genotype-manifest.json"] = json.dumps(man, indent=2) + "\n"
    return files


if __name__ == "__main__":
    out = ROOT / "artifacts" / "biodesign-compiler"
    files = build_files()
    if "--check" in sys.argv:
        bad = [k for k, v in files.items() if not (out / k).exists() or (out / k).read_text() != v]
        print("PASS" if not bad else f"STALE {bad}")
        sys.exit(1 if bad else 0)
    for k, v in files.items():
        (out / k).write_text(v)
    print("wrote", len(files), "files")
