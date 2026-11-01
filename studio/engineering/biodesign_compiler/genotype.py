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
import math
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
DIRECTIONS = {
    "forward": "sequence to function: a context-conditioned effect prediction. It needs a measured transfer for the stated genotype, species, cell state, stage and condition.",
    "inverse": "function to sequence: propose a CANDIDATE SET, then reuse the forward checks on every member. An edge that is not a calibrated transfer for the context is never inverted, and a set is never one guaranteed genome.",
}
INVERSE_RULES = [
    "proposing a candidate and endorsing it are different: a proposal needs provenance and a sequence artifact (or an explicit unresolved reference) and asserts nothing about function",
    "an interface that is not a calibrated transfer for the stated context is never inverted: no candidate is endorsed through it, but proposals are retained as unscreened hypotheses",
    "endorsement needs a calibrated path to the target, passing forward checks and a validation plan whose required checks all passed",
    "an ortholog or homolog is not interchangeable: function does not transfer across species or contexts without its own context-matched measurement",
    "the output is a candidate set with provenance and the unresolved bridges, never a single guaranteed genome, and the compiler adds no sequence of its own",
]
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
            "required_measurement": "a measured transfer (quantity, unit, bounds) for exactly the design's species, tissue, cell state, life stage, condition, allele and construct context",
            "proposed_experiments": [{"id": w, **wps[w]} for w in WORKPACKAGES.get(iid, []) if w in wps] or [{"note": "no experiment for this interface is recorded in the design-control map"}],
            "directions": {
                "forward": {"from": a, "to": b, "label": "context-conditioned effect prediction", "state": "unknown"},
                "inverse": {"from": b, "to": a, "label": "candidate proposal; endorsement only through the forward path", "proposable": True, "invertible": False, "why": "the forward edge is not a calibrated transfer for any context, so no candidate can be endorsed through it"},
            },
        }
    return {
        "schema": GRAPH_SCHEMA,
        "nodes": [{"id": n, "text": NODE_TEXT[n]} for n in NODES],
        "interfaces": ifs,
        "directions": DIRECTIONS,
        "inverse_rules": INVERSE_RULES,
        "states": list(STATES),
        "sources": pins,
        "scope": "an explicit dependency graph of what a genotype-to-fin design needs; every interface is unknown and nothing is calibrated",
        "must_not_say": MUST_NOT_SAY,
        "biological_success_probability": None,
    }


# --------------------------------------------------------------------------------------------------------------- checking
MAX_PIN_BYTES = 16 * 1024 * 1024
MAX_SEQ_NT = 5_000_000
IUPAC = frozenset("ACGTURYSWKMBDHVN")
MEASUREMENT_SCHEMA = "frontier.transfer-measurement/1"  # the source artifact class a calibrated transfer may rest on
INVALID_PREFIXES = ("measured bound", "transfer bound", "value used", "unsupported", "the pointer", "status", "unknown interface")


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _pointer(doc, ptr):
    for part in [p for p in ptr.split("/") if p]:
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


def _safe_file(root: Path, rel) -> tuple[Path | None, str | None]:
    """A repository-relative path only: absolute paths, traversal, NUL, drive letters and symlinks that leave the repository are refused, and so is a
    file over the size bound. This is an identity check on pinned artifacts, not a file-reading API."""
    if not isinstance(rel, str) or not rel or "\x00" in rel:
        return None, "path must be a non-empty repository-relative string"
    if rel.startswith(("/", "\\")) or Path(rel).is_absolute() or ".." in Path(rel).parts or (len(rel) > 1 and rel[1] == ":"):
        return None, f"path {rel!r} must stay inside the repository"
    base = Path(root).resolve()
    try:
        resolved = (base / rel).resolve()
    except (OSError, RuntimeError):
        return None, f"path {rel!r} cannot be resolved"
    if resolved != base and base not in resolved.parents:
        return None, f"path {rel!r} resolves outside the repository"
    if not resolved.is_file():
        return None, f"pinned file {rel} is missing"
    if resolved.stat().st_size > MAX_PIN_BYTES:
        return None, f"pinned file {rel} is larger than {MAX_PIN_BYTES} bytes"
    return resolved, None


def _pinned(root: Path, ref) -> tuple[bytes | None, str | None]:
    sha = ref.get("sha256") if isinstance(ref, dict) else None
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha) or not isinstance(ref.get("path"), str):
        return None, "no pinned path and sha256"
    f, err = _safe_file(root, ref["path"])
    if err:
        return None, err
    with f.open("rb") as h:
        b = h.read(MAX_PIN_BYTES + 1)
    if len(b) > MAX_PIN_BYTES:
        return None, f"pinned file {ref['path']} is larger than {MAX_PIN_BYTES} bytes"
    if bc.sha(b) != sha:
        return None, f"{ref['path']} changed: pinned {sha[:12]}, found {bc.sha(b)[:12]}"
    return b, None


def _context_mismatch(design_ctx: dict, ev_ctx: dict) -> list[str]:
    return [f for f in CONTEXT_FIELDS if not ev_ctx.get(f) or ev_ctx.get(f) != design_ctx.get(f)]


def _parse_json_rows(text: str, select_sha: str | None) -> tuple[dict | None, str | None]:
    """A JSON list of rows that each carry a `sequence` string (the reused model outputs). Exactly one row is selected, by the pinned normalised digest."""
    try:
        rows = json.loads(text)
    except ValueError:
        return None, "the sequence artifact looks like JSON but does not parse"
    if not isinstance(rows, list) or not all(isinstance(r, dict) and isinstance(r.get("sequence"), str) for r in rows):
        return None, "unsupported JSON sequence format: a list of objects with a string `sequence` is expected"
    if not select_sha:
        return None, "a JSON list of sequences needs the pinned sequence_sha256 to select exactly one row"
    keyed = []
    for n, r in enumerate(rows):
        seq = "".join(r["sequence"].split()).upper()
        if seq and not (set(seq) - IUPAC) and len(seq) <= MAX_SEQ_NT and bc.sha(seq.encode()) == select_sha:
            keyed.append((n, seq, r))
    if len(keyed) != 1:
        return None, f"the pinned digest matches {len(keyed)} rows of the JSON list: exactly one is required"
    n, seq, r = keyed[0]
    if r.get("length") is not None and (isinstance(r["length"], bool) or r["length"] != len(seq)):
        return None, "the row's own length field does not match its sequence"
    return {"format": "json_rows", "record_id": f"row {n}", "records_in_file": len(rows), "sequence_sha256": select_sha, "length_nt": len(seq), "ambiguity_codes": sorted(set(seq) - set("ACGT")), "sequence": seq}, None


def parse_sequence(b: bytes, record_id: str | None = None, select_sha: str | None = None) -> tuple[dict | None, str | None]:
    """Supported formats: one FASTA record; a multi-record FASTA when record_id names exactly one record; or raw sequence letters. The normalised
    nucleotide digest (upper case, no whitespace, no header) is reported separately from the digest of the file's bytes."""
    try:
        text = b.decode("ascii")
    except UnicodeDecodeError:
        return None, "the sequence artifact is not ASCII text"
    if text.lstrip().startswith("["):
        return _parse_json_rows(text, select_sha)
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if not lines:
        return None, "the sequence artifact is empty"
    if lines[0].startswith(">"):
        records, fmt = [], "fasta"
        for x in lines:
            if x.startswith(">"):
                head = x[1:].split()
                records.append([head[0] if head else "", []])
            else:
                records[-1][1].append(x)
        records = [(i, "".join(parts)) for i, parts in records]
    else:
        records, fmt = [("", "".join(lines))], "raw"
    if record_id is not None:
        pick = [r for r in records if r[0] == record_id]
        if len(pick) != 1:
            return None, f"record_id {record_id!r} matches {len(pick)} records in the artifact"
        rid, seq = pick[0]
    elif len(records) > 1:
        return None, f"the artifact holds {len(records)} records: name one with record_id (a multi-record file is ambiguous)"
    else:
        rid, seq = records[0]
    seq = seq.upper()
    if not seq:
        return None, "the sequence is empty"
    if len(seq) > MAX_SEQ_NT:
        return None, f"the sequence is longer than {MAX_SEQ_NT} nucleotides"
    bad = sorted(set(seq) - IUPAC)
    if bad:
        return None, "the sequence has non-nucleotide characters: " + "".join(bad)
    return {"format": fmt, "record_id": rid, "records_in_file": len(records), "sequence_sha256": bc.sha(seq.encode()), "length_nt": len(seq), "ambiguity_codes": sorted(set(seq) - set("ACGT")), "sequence": seq}, None


def _bind_sequence(declared_len, declared_hash, literal, info: dict) -> list[str]:
    out = []
    if declared_len is not None and (isinstance(declared_len, bool) or not isinstance(declared_len, int) or declared_len != info["length_nt"]):
        out.append(f"declared length {declared_len!r} is not the length of the sequence in the artifact ({info['length_nt']} nt)")
    if declared_hash is not None and declared_hash != info["sequence_sha256"]:
        out.append("declared sequence_sha256 is not the normalised nucleotide digest of the artifact's sequence (the file digest is a separate pin)")
    if literal is not None and "".join(str(literal).split()).upper() != info["sequence"]:
        out.append("the sequence literal differs from the sequence in the pinned artifact")
    return out


def check_sequence(root: Path, c: dict) -> dict:
    """A candidate sequence is acceptable only as a pinned artifact that parses, whose declared length, digest and literal equal the sequence actually
    in it. A bare literal is refused."""
    problems, info = [], None
    if c.get("sequence") and not c.get("source_ref"):
        problems.append("a sequence literal without a pinned source artifact is refused (no unpinned DNA)")
    if c.get("source_ref"):
        b, err = _pinned(root, c.get("source_ref"))
        if err:
            problems.append(("stale sequence reference: " if "changed" in err else "") + err)
        else:
            info, perr = parse_sequence(b, c.get("record_id"), c.get("sequence_sha256"))
            if perr:
                problems.append(perr)
            else:
                problems += _bind_sequence(c.get("length", c.get("length_nt")), c.get("sequence_sha256"), c.get("sequence"), info)
    elif not problems:
        problems.append("no pinned source artifact")
    kind = c.get("evidence_kind")
    return {
        "id": c.get("id"),
        "source_ref": c.get("source_ref"),
        "file_sha256": (c.get("source_ref") or {}).get("sha256"),
        "sequence_sha256": info["sequence_sha256"] if info else None,
        "length_nt": info["length_nt"] if info else None,
        "record_id": info["record_id"] if info else None,
        "format": info["format"] if info else None,
        "ambiguity_codes": info["ambiguity_codes"] if info else None,
        "evidence_kind": kind,
        "observed_context": c.get("observed_context"),
        "problems": problems,
        "valid": not problems,
        "note": "homology or marker similarity is not function: this candidate leaves the dna->expression interface unknown" if kind in ("homology", "none", None) else "measured expression in the stated context is still not a calibrated transfer",
    }


def _check_inputs(root: Path, iid: str, ev: dict, inputs: dict, cand_digests: set | None) -> list[str]:
    """Exact input dependency. DNA to expression: the evidence must name the nucleotide digest of a candidate in THIS design, so different DNA cannot
    inherit a measurement through identical allele or construct labels. Downstream interfaces: declared upstream input pins and a transfer version,
    not a blanket requirement to sequence-bind every numerical model. Pinned inputs must still match their bytes."""
    out = []
    if iid == "I1":
        d = inputs.get("sequence_sha256")
        if not (isinstance(d, str) and len(d) == 64 and all(c in "0123456789abcdef" for c in d)):
            out.append("measured bound not verifiable: DNA to expression evidence must carry inputs.sequence_sha256, the normalised nucleotide digest of the candidate")
        elif cand_digests is not None and d not in cand_digests:
            out.append("measured bound not verifiable: the evidence is for a sequence digest that is not a candidate in this design (identical allele or construct labels do not transfer a measurement to different DNA)")
    else:
        if not (isinstance(ev.get("transfer_version"), str) and ev["transfer_version"]):
            out.append("measured bound not verifiable: a downstream interface measurement must name its transfer version")
    for name, v in inputs.items():
        if isinstance(v, dict):
            _, err = _pinned(root, v)
            if err:
                out.append(f"measured bound not verifiable: input {name!r}: " + err)
        elif not (isinstance(v, str) and v):
            out.append(f"measured bound not verifiable: input {name!r} must be a digest string or a pinned artifact")
    return out


def check_evidence(root: Path, ev: dict, design_ctx: dict, cand_digests: set | None = None) -> dict:
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
        lo, hi, used = t.get("lo"), t.get("hi"), t.get("value_used")
        if not (isinstance(t.get("quantity"), str) and t["quantity"].strip() and isinstance(t.get("unit"), str) and t["unit"].strip()):
            reasons.append("measured bound not verifiable: a transfer needs a non-empty quantity and unit")
        if not (_finite(lo) and _finite(hi) and lo <= hi):
            reasons.append("transfer bound must be finite numbers with lo <= hi")
        elif used is not None and (not _finite(used) or not (lo <= used <= hi)):
            reasons.append(f"value used {used!r} is not a finite number inside the stated bound [{lo}, {hi}]")
        inputs = ev.get("inputs")
        if not isinstance(inputs, dict) or not inputs:
            reasons.append("measured bound not verifiable: an interface measurement must name its exact inputs (for DNA to expression the candidate's nucleotide digest; downstream, the upstream input pins)")
        else:
            reasons += _check_inputs(root, iid, ev, inputs, cand_digests)
        b, err = _pinned(root, ref)
        if err:
            reasons.append("measured bound not verifiable: " + err)
        else:
            try:
                doc = json.loads(b)
                if doc.get("schema") != MEASUREMENT_SCHEMA:
                    reasons.append(f"unsupported source artifact class: a transfer rests on a {MEASUREMENT_SCHEMA} artifact, this one is {doc.get('schema')!r}")
                else:
                    m = _pointer(doc, ref["pointer"])
                    if m.get("evidence_class") != "measured_experiment":
                        reasons.append(f"unsupported source: evidence_class {m.get('evidence_class')!r} is not a measured experiment (a model output or simulation is not a measurement)")
                    elif not (_finite(m.get("lo")) and _finite(m.get("hi")) and m["lo"] <= m["hi"]):
                        reasons.append("the pointer does not lead to finite ordered lo/hi bounds in the pinned measurement")
                    else:
                        if (m["lo"], m["hi"]) != (lo, hi):
                            reasons.append(f"transfer bound [{lo}, {hi}] differs from the pinned measurement [{m['lo']}, {m['hi']}]")
                        if (m.get("quantity"), m.get("unit")) != (t.get("quantity"), t.get("unit")):
                            reasons.append(f"transfer bound quantity/unit {t.get('quantity')!r}/{t.get('unit')!r} differ from the measurement's {m.get('quantity')!r}/{m.get('unit')!r}")
                        if doc.get("inputs") != inputs or doc.get("transfer_version") != ev.get("transfer_version"):
                            reasons.append("the pinned measurement was made on different inputs or a different transfer version than the evidence states")
                        mc = m.get("context") or {}
                        if any(mc.get(f) != (ev.get("context") or {}).get(f) for f in CONTEXT_FIELDS):
                            reasons.append("the pinned measurement was made in a different context than the evidence states: " + ", ".join(f for f in CONTEXT_FIELDS if mc.get(f) != (ev.get("context") or {}).get(f)))
            except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                reasons.append("the pointer does not lead to a measurement object in the pinned artifact")
    valid = not any(r.startswith(INVALID_PREFIXES) or "the pinned measurement" in r for r in reasons)
    effective = status if (valid and applicable) else ("proposed" if status == "proposed" and applicable else "unknown")
    return {"interface": iid, "status": status, "effective": effective, "applicable": applicable, "valid": valid, "context": ev.get("context"), "transfer": ev.get("transfer"), "reasons": reasons}


# ------------------------------------------------------------------------------------- versioned validation plans and results
CHECK_STATUSES = ("pass", "fail", "blocked", "not_run", "not_applicable", "missing", "stale")
# explicit mapping of the compiler's existing axis statuses; anything unlisted, stale, errored or skipped is never a pass
AXIS_STATUS_MAP = {"pass": "pass", "fail": "fail", "fail (retained)": "fail", "unresolved": "blocked", "unassessed": "blocked", "mixed": "blocked"}


def map_axis_status(status: str) -> str:
    if status in AXIS_STATUS_MAP:
        return AXIS_STATUS_MAP[status]
    return "fail" if status.startswith("fail") else "not_run" if status.startswith("measured, no frozen threshold") else "blocked"


PLAN_SCHEMA = "frontier.validation-plan/1"
RESULT_SCHEMA = "frontier.validation-result/1"


def _count(x):
    """A case count is a non-negative int: a bool, float, NaN or negative number is not a count."""
    return x if isinstance(x, int) and not isinstance(x, bool) and x >= 0 else None


def _bound_plan(root: Path, plan: dict) -> str | None:
    """The plan in the design must equal the plan artifact it pins: id, version, candidate and the set of required checks."""
    b, err = _pinned(root, plan.get("ref"))
    if err:
        return ("stale plan: " if "changed" in err else "plan: ") + err
    try:
        doc = json.loads(b)
    except ValueError:
        return "unverified plan: the pinned file is not JSON"
    if not isinstance(doc, dict) or doc.get("schema") != PLAN_SCHEMA:
        return f"unverified plan: the pinned file is not a {PLAN_SCHEMA} artifact, so its metadata is the caller's word only"
    sig = lambda p: (p.get("id"), p.get("version"), p.get("candidate_id"), p.get("candidate_sequence_sha256"), sorted((c.get("id"), bool(c.get("endpoint")), bool(c.get("executable"))) for c in p.get("required_checks", [])))  # noqa: E731
    if sig(doc) != sig(plan):
        return "unverified plan: the plan's id, version, candidate or required checks differ from the pinned plan artifact"
    return None


def _bound_result(root: Path, res: dict) -> tuple[dict | None, str | None]:
    b, err = _pinned(root, res.get("ref"))
    if err:
        return None, ("stale result: " if "changed" in err else "result: ") + err
    try:
        doc = json.loads(b)
    except ValueError:
        return None, "unverified result: the pinned file is not JSON"
    if not isinstance(doc, dict) or doc.get("schema") != RESULT_SCHEMA:
        return None, f"unverified result: the pinned file is not a {RESULT_SCHEMA} artifact, so its status and case counts are the caller's word only"
    for k in ("plan_id", "plan_version", "check_id", "status", "cases", "candidate_sequence_sha256"):
        if doc.get(k) != res.get(k):
            return None, f"unverified result: {k} differs from the pinned result artifact"
    v = doc.get("validator") or {}
    if not (isinstance(v.get("role"), str) and v["role"] and isinstance(v.get("identity"), str) and v["identity"] and isinstance(v.get("dependence_identity"), str) and v["dependence_identity"]):
        return None, "unverified result: the pinned artifact names no validator role, identity and evidence-dependence identity"
    return doc, None


def _check_result(plan_ok: str | None, check: dict, res: dict | None, root: Path, plan: dict) -> dict:
    """One required check: missing (no result), not_run (stated), stale (a pin or the plan version changed), blocked (unverified or vacuous), fail or pass.
    The plan and the result are bound to their pinned artifacts' bytes. A pass needs at least one evaluable positive and one meaningful negative case, and
    for an executable gate the negative must have been rejected."""
    out = {"id": check["id"], "interface": check.get("interface"), "endpoint": bool(check.get("endpoint")), "executable": bool(check.get("executable"))}
    if plan_ok:
        return {**out, "status": "stale" if plan_ok.startswith("stale") else "blocked", "reason": plan_ok}
    if res is None:
        return {**out, "status": "missing", "reason": "no result is recorded for this required check (a missing check is not a pass and is not a failure)"}
    if res.get("plan_version") != plan.get("version"):
        return {**out, "status": "stale", "reason": f"the result is for plan version {res.get('plan_version')}, the plan is version {plan.get('version')}"}
    if plan.get("candidate_sequence_sha256") and res.get("candidate_sequence_sha256") != plan.get("candidate_sequence_sha256"):
        return {**out, "status": "blocked", "reason": "the result is for a different candidate sequence than the plan: it cannot validate this candidate"}
    st = res.get("status")
    if st not in CHECK_STATUSES or st in ("missing", "stale"):
        return {**out, "status": "blocked", "reason": f"result status {st!r} is not one of pass, fail, blocked, not_run, not_applicable"}
    if st in ("not_run", "blocked") and not res.get("ref"):
        return {**out, "status": st, "reason": res.get("reason"), "scope": res.get("scope")}
    doc, err = _bound_result(root, res) if res.get("ref") else (None, "a result needs a pinned execution record")
    if err:
        return {**out, "status": "stale" if err.startswith("stale") else "blocked", "reason": err}
    if st == "not_applicable":
        if not res.get("reason"):
            return {**out, "status": "blocked", "reason": "not_applicable needs a stated reason"}
        if check.get("endpoint"):
            return {**out, "status": "blocked", "reason": "not_applicable cannot remove a required endpoint"}
    if st == "pass":
        cases = res.get("cases") or {}
        why = []
        if not (_count(cases.get("positive")) or 0) >= 1:
            why.append("no evaluable positive case")
        if not (_count(cases.get("negative")) or 0) >= 1:
            why.append("no meaningful negative case")
        if check.get("executable") and cases.get("negative_rejected") is not True:
            why.append("the negative case was not shown to be rejected for the intended reason")
        if why:
            return {**out, "status": "blocked", "reason": "vacuous pass refused: " + "; ".join(why)}
    return {**out, "status": st, "reason": res.get("reason"), "scope": res.get("scope"), "licenses": res.get("licenses") if st == "pass" else None, "ref": res.get("ref"), "validator": (doc or {}).get("validator")}


def evaluate_validation(root: Path, design: dict) -> dict:
    """Versioned validation plans and results attached to a design. Each plan pins its artifact and names required checks; each result is a separate
    record bound to its own pinned artifact. Reports every check as pass, fail, blocked, not_run, not_applicable, missing or stale: missing, stale,
    errored or skipped never pass, and a plan whose required checks are all not_applicable cannot pass: it needs an executed required endpoint."""
    root = Path(root)
    plans, results = design.get("validation_plans", []), design.get("validation_results", [])
    out = []
    for plan in plans:
        plan_err = _bound_plan(root, plan)
        checks = []
        for check in plan.get("required_checks", []):
            mine = [r for r in results if r.get("plan_id") == plan.get("id") and r.get("check_id") == check["id"]]
            checks.append(_check_result(plan_err, check, mine[-1] if mine else None, root, plan))
        ok = any(c["status"] == "pass" and c["endpoint"] for c in checks) and all(c["status"] == "pass" or (c["status"] == "not_applicable" and not c["endpoint"]) for c in checks)
        counts = {k: sum(1 for c in checks if c["status"] == k) for k in CHECK_STATUSES}
        out.append(
            {
                "plan_id": plan.get("id"),
                "version": plan.get("version"),
                "candidate_sequence_sha256": plan.get("candidate_sequence_sha256"),
                "candidate_id": plan.get("candidate_id"),
                "endpoint": plan.get("endpoint"),
                "decision": plan.get("decision"),
                "ref": plan.get("ref"),
                "checks": checks,
                "counts": counts,
                "all_required_pass": ok,
                "licenses": [c["licenses"] for c in checks if c.get("licenses")],
            }
        )
    return {"plans": out, "attached": bool(plans), "all_required_pass": bool(out) and all(p["all_required_pass"] for p in out)}


def compile_design(root: Path, graph: dict, design: dict, _cand_digests=None) -> dict:
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
    cand_digests = {x["sequence_sha256"] for x in seqs + [y for y in led["sequences"] if y.get("sequence_available")] if x.get("valid") and x.get("sequence_sha256")} if _cand_digests is None else set(_cand_digests)
    evs = [check_evidence(root, e, ctx, cand_digests) for e in direct + led["interface_evidence"]]  # ledger-derived items carry "ledger_bridge"
    for ev, src in zip(evs[len(direct) :], led["interface_evidence"]):
        ev["ledger_bridge"], ev["ledger_status"], ev["from_entry"], ev["source_context"] = src["ledger_bridge"], src["ledger_status"], src["from_entry"], src["source_context"]
    best = {}
    for iid in INTERFACES:
        cand = [e["effective"] for e in evs if e["interface"] == iid]
        best[iid] = max(cand, key=STATES.index) if cand else "unknown"
    tests = [{k: t.get(k) for k in ("id", "interface", "kind", "description")} | {"status": "proposed"} for t in design.get("validation_tests", [])]
    unresolved = [{"interface": i, "text": INTERFACE_TEXT[i], "state": s, "needs": "calibrated transfer for " + ", ".join(f"{f}={ctx.get(f)}" for f in CONTEXT_FIELDS) if ctx else "a stated context"} for i, s in best.items() if s != "calibrated_transfer"]
    validation = evaluate_validation(root, design)
    claimed = design.get("claim") == "working_assembly"
    reasons = list(problems) + led["problems"]
    reasons += [f"{s['id']}: {p}" for s in seqs for p in s["problems"]] + [f"plan {p['id']}: {q}" for p in plans for q in p["problems"]]
    reasons += [f"{e['interface']}: {r}" for e in evs for r in e["reasons"] if not e["valid"]]
    if claimed:
        if unresolved:
            reasons.append("required interfaces are not calibrated for this context: " + ", ".join(u["interface"] for u in unresolved))
        reasons += [f"validation plan {p['plan_id']} is for a candidate digest that is not a candidate in this design" for p in validation["plans"] if p.get("candidate_sequence_sha256") and p["candidate_sequence_sha256"] not in cand_digests]
        if not validation["attached"]:
            reasons.append("no validation plan is attached: every proposed design carries a falsifiable validation plan")
        elif not validation["all_required_pass"]:
            reasons.append("required validation checks have not passed: " + ", ".join(f"{p['plan_id']}:{c['id']}={c['status']}" for p in validation["plans"] for c in p["checks"] if c["status"] != "pass"))
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
        "validation": validation,
        # proposing a candidate and assuring its function are separate questions: eligibility never implies assurance
        "proposal_eligibility": {"eligible": not problems and not any(not x["valid"] for x in seqs + led["sequences"]), "reasons": problems + [f"{x['id']}: {q}" for x in seqs + led["sequences"] for q in x["problems"]]},
        "function_assurance": {"interfaces_calibrated": not unresolved, "validation_all_required_pass": validation["all_required_pass"], "level": "none" if unresolved or not validation["all_required_pass"] else "checks_pass_for_the_stated_context"},
        "assembly_unresolved_interfaces": unresolved,
        "scope": "evidence bookkeeping only; no DNA was generated, nothing was ordered or run, and no biological claim follows from this verdict",
        "must_not_say": MUST_NOT_SAY,
    }


def propagate(graph: dict, design: dict, change: dict, root: Path | None = None) -> dict:
    """What a change invalidates. change = {"node": n} or {"interface": I}. An interface is invalidated when the node it reads FROM (or an
    earlier one) changed; a node when it is the changed node or later. Claims, calibrations and checked layers name what they depend on. A checked
    layer is retained only with dependency pins that still verify against `root`, and only as a result for the ORIGINAL pinned model or geometry:
    a layer with no pins, or pins not checked, is reported as unverified and never silently retained. No transfer function is invented."""
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

    own = change.get("node")
    invalidated, retained, unverified = [], [], []
    for x in layers:
        if x.get("node") == own:
            invalidated.append(x["id"])
            continue
        pins = x.get("pins") or []
        if not pins:
            unverified.append({"id": x["id"], "why": "no dependency pins are declared: an unknown dependency is not silently retained"})
        elif root is None:
            unverified.append({"id": x["id"], "why": "dependency pins were not checked (no repository root given)"})
        else:
            bad = [p.get("path") if isinstance(p, dict) else str(p) for p in pins if _pinned(root, p)[1]]
            (unverified.append({"id": x["id"], "why": "dependency pins no longer verify: " + ", ".join(bad)}) if bad else retained.append(x["id"]))
    return {
        "change": change,
        "invalidated_nodes": down_nodes,
        "invalidated_interfaces": down_ifs,
        "invalidated_claims": [c["id"] for c in claims if dep(c)],
        "retained_claims": [c["id"] for c in claims if not dep(c)],
        "invalidated_calibrations": [e["interface"] for e in calib if e["interface"] in down_ifs],
        "retained_calibrations": [e["interface"] for e in calib if e["interface"] not in down_ifs],
        "invalidated_checked_layers": invalidated,
        "retained_checked_layers": retained,
        "unverified_checked_layers": unverified,
        "retained_scope": "a retained layer check is a result for its original pinned model or geometry only; it is not a result for the changed design",
    }


# ------------------------------------------------------------------------------------------------- validation slices and cutsets
VALIDATION_SCHEMA = "frontier.biodesign.validation-slices/1"
INSTRUMENT_FILE = "artifacts/crossscale-doe/protocol.json"  # the experimental-design owner's instrument contracts (claude-14); read, never written
INSTRUMENT_MANIFEST = "artifacts/crossscale-doe/manifest.json"
# which of those contracts belong to which boundary or layer; a boundary with none keeps an explicit gap rather than an invented contract
INSTRUMENT_MAP = {"I1": ["P1-reporter-expression"], "I2": [], "I3": ["P2-growth-to-EI", "R1-ray-bending"], "I4": ["R2-inflow-tip", "R3-load"], "I5": []}
NODE_INSTRUMENTS = {"shape_mechanics": ["V1-saved-deflection-section", "V2-saved-tip-and-slope", "R1-ray-bending", "R4-length"]}


def instrument_contracts(root: Path) -> dict:
    """Real instrument contracts, pinned: the file must match the sha256 its own manifest declares. Missing or stale means no contracts (explicit gaps)."""
    root = Path(root)
    f, err = _safe_file(root, INSTRUMENT_FILE)
    m, merr = _safe_file(root, INSTRUMENT_MANIFEST)
    if err or merr:
        return {"contracts": {}, "why": err or merr, "ref": None}
    b = f.read_bytes()
    try:
        declared = json.loads(m.read_bytes())["files"]["protocol.json"]["sha256"]
        doc = json.loads(b)
    except (ValueError, KeyError, TypeError):
        return {"contracts": {}, "why": "the instrument manifest or protocol is not readable", "ref": None}
    if bc.sha(b) != declared:
        return {"contracts": {}, "why": f"{INSTRUMENT_FILE} changed: its manifest declares {declared[:12]}, found {bc.sha(b)[:12]}", "ref": None}
    ref = {"path": INSTRUMENT_FILE, "sha256": declared}
    return {"contracts": {i["id"]: {**ref, "instrument_id": i["id"], "status": i.get("status"), "observable": i.get("observable"), "unit": i.get("unit"), "kind": "virtual" if str(i.get("kind", "")).startswith("virtual") else "physical"} for i in doc.get("instruments", [])}, "why": None, "ref": ref}


def instrument_slots(contracts: dict, ids: list[str]) -> list[dict]:
    """Contract refs for the given ids, always with a physical and a virtual slot: a missing contract is an explicit gap, not a hidden null."""
    got = [contracts["contracts"][i] for i in ids if i in contracts["contracts"]]
    slots = [{"kind": c["kind"], "contract_ref": {k: c[k] for k in ("path", "sha256", "instrument_id", "status", "observable", "unit")}} for c in got]
    for kind in ("physical", "virtual"):
        if not any(x["kind"] == kind for x in slots):
            slots.append({"kind": kind, "contract_ref": None, "gap": contracts["why"] or "no contract exists for this boundary and kind"})
    return sorted(slots, key=lambda x: (x["kind"], (x["contract_ref"] or {}).get("instrument_id", "~")))


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


def validation_slices(graph: dict, design: dict | None = None, report: dict | None = None, root: Path | None = None) -> dict:
    """For each causal boundary: the exact input and observation class that would check it, controls, the decision rule, what stays unknown, the
    instrument slots (physical or virtual) another worker's contracts must fill, and what a proposed DNA change invalidates. Nothing here is a
    result or a calibrated transfer; every slice closes only with a calibrated_transfer pinned to the design's own context."""
    design = design or {}
    ctx = design.get("context") or {}
    contracts = instrument_contracts(root) if root is not None else {"contracts": {}, "why": "no repository root was given, so no instrument contract was read", "ref": None}
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
            "instrument_slots": instrument_slots(contracts, INSTRUMENT_MAP[iid]),
            "directions": g["directions"],
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
        layer[n["id"]] = {
            "independent_check": text,
            "compiler_axes": found,
            "retained_when_dna_changes": n["id"] != "dna",
            "note": "a layer's own check is untouched by an upstream change, for its original pinned model or geometry only; the claims that link layers are what invalidates",
            "instrument_slots": instrument_slots(contracts, NODE_INSTRUMENTS.get(n["id"], [])),
        }
    return {
        "schema": VALIDATION_SCHEMA,
        "interfaces": ifs,
        "layers": layer,
        "cutsets": [{"claim": c, **cutset(graph, a, b, design)} for c, a, b in STANDARD_CLAIMS],
        "after_proposed_dna_change": {k: dna[k] for k in ("invalidated_nodes", "invalidated_interfaces", "retained_calibrations", "invalidated_calibrations")} | {"meaning": "every interface evidence entry was for the previous sequence and must be repeated; independent numerical checks of other layers are retained"},
        "instrument_contracts_ref": contracts["ref"],
        "scope": "requirements for validation, not protocols, not results; no calibrated genotype-to-phenotype transfer exists or is implied",
        "must_not_say": MUST_NOT_SAY,
    }


# ------------------------------------------------------------------------------------------------------------ inverse direction
INVERSE_SCHEMA = "frontier.biodesign.inverse-request/1"
INVERSE_REPORT_SCHEMA = "frontier.biodesign.inverse-report/1"


def inverse_cutset(graph: dict, target_node: str) -> list[str]:
    """The interfaces between the DNA and the target function: each must be a calibrated transfer for the context before any inversion."""
    return cutset(graph, "dna", target_node)["interfaces"]


def compile_inverse(root: Path, graph: dict, request: dict, forward: dict) -> dict:
    """Function to sequence, with PROPOSAL and ENDORSEMENT kept apart. A candidate may be proposed whenever it has provenance and a sequence artifact
    (or an explicit unresolved sequence reference); proposing it asserts nothing about function. A candidate is ENDORSED only when every interface
    from the DNA to the target is a calibrated transfer for the stated context, the forward checks pass for it, and a validation plan attached to it has
    passed all required checks. Unendorsed proposals are retained, never dropped. The compiler adds no sequence, never inverts an uncalibrated edge,
    never treats a homolog as interchangeable, and never returns one guaranteed genome."""
    root = Path(root)
    problems = []
    if request.get("schema") != INVERSE_SCHEMA:
        problems.append(f"schema must be {INVERSE_SCHEMA}")
    target = request.get("target_node")
    if target not in NODES:
        problems.append(f"target_node must be one of {', '.join(NODES)}")
        target = None
    ctx = forward.get("context") or {}
    request_digests = {x["sequence_sha256"] for x in (check_sequence(root, c) for c in request.get("candidates", [])) if x["valid"] and x["sequence_sha256"]}
    base = compile_design(root, graph, {**forward, "claim": "proposal", "sequence_candidates": [], "build_plan_proposals": []}, request_digests)
    base_invalid = base["verdict"] == "invalid_document" or bool(base["reasons"])
    state = base["interface_state"]
    needed = inverse_cutset(graph, target) if target else []
    blocked = [{"interface": i, "state": state.get(i, "unknown"), "why": "not a calibrated transfer for this context: the forward edge cannot be inverted, so no candidate can be endorsed", "needs": graph["interfaces"][i]["proposed_experiments"]} for i in needed if state.get(i) != "calibrated_transfer"]
    plans = {p["plan_id"]: p for p in evaluate_validation(root, forward)["plans"]}
    cands = []
    for c in request.get("candidates", []):
        prov = c.get("provenance") or {}
        miss = [k for k in ("proposer", "method") if not prov.get(k)] + ([] if prov.get("source_refs") else ["source_refs"])
        ineligible = [f"provenance is missing: {', '.join(miss)}"] if miss else []
        unresolved = bool(c.get("sequence_unresolved")) and isinstance(c.get("unresolved_ref"), str) and bool(c["unresolved_ref"]) and not c.get("source_ref")
        seq = check_sequence(root, c)
        if not unresolved:
            ineligible += seq["problems"]
        flags = []
        obs = c.get("observed_context") or {}
        if c.get("ortholog_of") or c.get("evidence_kind") == "homology" or (obs.get("species") and obs.get("species") != ctx.get("species")):
            flags.append("ortholog or homolog: function is not interchangeable across species or contexts; it needs its own context-matched measurement")
        if unresolved:
            flags.append(f"sequence unresolved ({c['unresolved_ref']}): the candidate is a hypothesis without sequence evidence and cannot be endorsed")
        why_not = list(flags)
        if base_invalid:
            why_not.append("the forward design is invalid or carries problems: " + "; ".join(base["reasons"][:3]))
        if blocked:
            why_not.append("an interface on the path is not a calibrated transfer for this context")
        fcheck = {}
        if not ineligible and not unresolved and not base_invalid and not blocked and not flags:
            mine_ev = [e for e in forward.get("interface_evidence", []) if e.get("interface") != "I1" or not isinstance(e.get("inputs"), dict) or e["inputs"].get("sequence_sha256") in (None, seq["sequence_sha256"])]  # another candidate's I1 measurement is for other DNA
            fwd = compile_design(root, graph, {**forward, "claim": "proposal", "sequence_candidates": [c], "interface_evidence": mine_ev})
            fcheck = {"interface_state": {i: fwd["interface_state"][i] for i in needed}, "reasons": fwd["reasons"]}
            if fwd["reasons"] or any(fwd["interface_state"][i] != "calibrated_transfer" for i in needed):
                why_not.append("did not pass the forward checks for this target")
            mine = [p for p in plans.values() if p["candidate_id"] == c.get("id") and p.get("candidate_sequence_sha256") == seq["sequence_sha256"]]
            if not mine:
                why_not.append("no validation plan is attached to this candidate")
            elif not all(p["all_required_pass"] for p in mine):
                why_not.append("required validation checks have not passed: " + ", ".join(f"{p['plan_id']}:{k['id']}={k['status']}" for p in mine for k in p["checks"] if k["status"] != "pass"))
        cands.append(
            {
                "id": c.get("id"),
                "provenance": prov,
                "sequence": seq,
                "sequence_unresolved": c.get("unresolved_ref") if unresolved else None,
                "ortholog_of": c.get("ortholog_of"),
                "forward_check": fcheck,
                "eligible_as_proposal": not ineligible,
                "ineligible": ineligible,
                "flags": flags,
                "endorsed": not ineligible and not why_not,
                "not_endorsed_because": why_not,
            }
        )
    proposals = [c for c in cands if c["eligible_as_proposal"]]
    endorsed = [c for c in proposals if c["endorsed"]]
    if problems:
        verdict = "invalid_request"
    elif base_invalid and not proposals:
        verdict = "invalid_forward_design"
    elif endorsed:
        verdict = "endorsed_candidate_set"
    elif proposals:
        verdict = "proposals_only"
    else:
        verdict = "no_eligible_proposal"
    return {
        "schema": INVERSE_REPORT_SCHEMA,
        "request_id": request.get("id"),
        "target_node": target,
        "context": ctx,
        "verdict": verdict,
        "problems": problems,
        "forward_design_problems": base["reasons"],
        "interfaces_crossed": needed,
        "blocked_interfaces": blocked,
        "proposals": [{"id": c["id"], "provenance": c["provenance"], "sequence": c["sequence"]["source_ref"], "sequence_unresolved": c["sequence_unresolved"], "flags": c["flags"], "endorsed": c["endorsed"], "not_endorsed_because": c["not_endorsed_because"]} for c in proposals],
        "endorsed_candidate_set": [{"id": c["id"], "provenance": c["provenance"], "sequence": c["sequence"]["source_ref"], "forward_check": c["forward_check"]} for c in endorsed],
        "ineligible_candidates": [{"id": c["id"], "provenance": c["provenance"], "issues": c["ineligible"]} for c in cands if not c["eligible_as_proposal"]],
        "unresolved_bridges": [{"interface": i, "bridges": [b["bridge"] for b in graph["interfaces"][i]["bridges"]]} for i in needed if state.get(i) != "calibrated_transfer"],
        "single_genome_guaranteed": False,
        "rules": INVERSE_RULES,
        "added_sequences": 0,
        "scope": "proposals are hypotheses with provenance; an endorsed member passed the forward checks and its validation plan for the stated context, which is not a guarantee of function; no sequence was generated here",
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
    """Normalised fields for exact matching, filled only where the source's own context states the meaning (nested `context`, else flat fields).
    A field the source does not state stays None and therefore never matches a design: nothing is inferred (not an adult stage from a tissue string,
    not a cell program). The source-native context is carried unchanged beside it (see `source_context`)."""
    c = e.get("context") if isinstance(e.get("context"), dict) else {}
    pick = lambda *names: next((c.get(n) for n in names if isinstance(c.get(n), str) and c.get(n)), None) or next((e.get(n) for n in names if isinstance(e.get(n), str) and e.get(n)), None)  # noqa: E731
    return {
        "species": e.get("species"),
        "tissue": pick("tissue"),
        "cell_state": pick("cell_state", "cell"),
        "life_stage": pick("life_stage"),
        "condition": pick("condition", "state", "injury_or_condition"),
        "allele": pick("allele"),
        "construct_context": pick("construct_context", "construct", "promoter_context"),
    }


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
            b, err = _pinned(root, art)
            if err:
                prob.append(("stale sequence reference: " if "changed" in err else "") + err)
            else:
                info, perr = parse_sequence(b, s.get("record_id"), s.get("sequence_sha256"))
                prob += [perr] if perr else _bind_sequence(s.get("length_nt"), s.get("sequence_sha256"), None, info)
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
                "direction": e.get("direction"),
                "functional_validation": e.get("functional_validation", "unknown"),
                "source_context": e.get("context"),
                "unmapped_context_fields": [f for f, v in _entry_context(e).items() if not v],
                "desired_readout": e.get("desired_readout"),
                "candidate_refs": e.get("candidate_refs"),
                "source_refs": e.get("source_refs"),
                "model_ready_reason": e.get("model_ready_reason"),
                "context": _entry_context(e),
                "demonstrated_readout": e.get("demonstrated_readout"),
                "demonstrated_effect": e.get("demonstrated_effect"),
                "missing_causal_bridge": e.get("missing_causal_bridge"),
                "falsifiable_validation_readout": e.get("falsifiable_validation_readout"),
                "model_ready": e.get("model_ready"),
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
                {
                    "interface": item["interface"],
                    "status": BRIDGE_STATE.get(b.get("status"), "unknown"),
                    "context": _entry_context(e),
                    "from_entry": b.get("from_entry"),
                    "source_context": e.get("context"),
                    "ledger_bridge": b["id"],
                    "ledger_status": b.get("status"),
                    "conditions": b.get("conditions"),
                    "missing_parameters": b.get("missing_parameters"),
                    "transfer": item.get("transfer"),
                }
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
    inverse_example = {"schema": INVERSE_SCHEMA, "id": "baseline-inverse-no-candidates", "target_node": "shape_mechanics", "candidates": []}
    inv = compile_inverse(root, g, inverse_example, baseline_design)
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
        "inverse_example": {"request": inverse_example, "verdict": inv["verdict"], "blocked": [b["interface"] for b in inv["blocked_interfaces"]], "single_genome_guaranteed": inv["single_genome_guaranteed"]},
        "directions": DIRECTIONS,
        "baseline_example": {"design": baseline_design, "verdict": rep["verdict"], "unresolved": [u["interface"] for u in rep["assembly_unresolved_interfaces"]]},
    }
    vs = validation_slices(g, {"context": baseline_design["context"]}, {**rep, "compiled": json.loads((root / SOURCES["compiler_report"]).read_text())["compiled"]}, root)
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
