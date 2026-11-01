"""Genotype-to-design surface: what the compiler, the sequence-evidence ledger and the cross-scale design screen actually contain, as a snapshot object.

build(ins, out, root=None) returns the object and writes a finite allowlist of source files into `out` under the site's "@artifacts/genotype/..." convention.
Nothing here is computed about biology. Every count is taken from the current ledger or compiler bytes, every input is bound to the sha256 its own
manifest declares (a changed input is WITHHELD and says why, never shown as current), and no aggregate confidence is produced. The compiler checks and
proposes; it does not synthesise DNA and no interface is a calibrated transfer, so nothing is endorsed."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIO = "artifacts/biodesign-compiler"
SEQ = "artifacts/sequence-evidence"
DOE = "artifacts/crossscale-doe"
PUBLIC = "artifacts/genotype"
LEDGER_SCHEMA = "frontier.sequence-function-ledger/1"
CONTRACT_SCHEMA = "frontier.crossscale-doe.instrument-contracts/1"
GENOTYPE_FILES = ("genotype-graph.json", "genotype-contract.json", "genotype-validation.json")
# Only these are ever copied into the site: the compiler's own outputs, the ledger, the four natural-reference sequences and the DOE files shown.
SEQUENCE_ALLOW_SUFFIX = (".fasta", ".fa")
DOE_ALLOW = ("instrument-contracts.json", "result.json", "candidates.json")

SCOPE = [
    "The compiler checks and proposes. It does not create DNA, and nothing here is a working organism, construct or genome.",
    "No interface from sequence to function is a calibrated transfer, so no candidate is endorsed. Forward and inverse are both proposals checked against stated context.",
    "A formal implication (what a claim depends on) is kept apart from the biological premises it would need; no aggregate biological confidence is shown.",
]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _json(b: bytes | None):
    try:
        return json.loads(b) if b is not None else None
    except ValueError:
        return None


class _Bound:
    """Reads files through the builder's input recorder and checks each against a declared sha256. Anything missing, unreadable or changed is
    recorded in `withheld` with its reason and returns None, so callers cannot show it as current."""

    def __init__(self, ins, root: Path):
        self.ins, self.root, self.withheld, self.cache = ins, root, [], {}

    def raw(self, rel: str) -> bytes | None:
        f = self.root / rel
        if not f.is_file():
            return None
        if rel not in self.cache:
            self.cache[rel] = self.ins.read(rel)
        return self.cache[rel]

    def get(self, rel: str, want: str | None, label: str) -> bytes | None:
        b = self.raw(rel)
        if b is None:
            self.withheld.append({"path": rel, "label": label, "reason": "missing from the repository"})
        elif not want:
            self.withheld.append({"path": rel, "label": label, "reason": "its manifest does not declare a hash for it"})
        elif _sha(b) != want:
            self.withheld.append({"path": rel, "label": label, "reason": f"changed since its manifest was written: declared {want[:12]}, found {_sha(b)[:12]}"})
        else:
            return b
        return None


def _manifest(bound: _Bound, rel: str, label: str) -> dict:
    b = bound.raw(rel)
    d = _json(b)
    if not isinstance(d, dict) or not isinstance(d.get("files"), (list, dict)):
        bound.withheld.append({"path": rel, "label": label, "reason": "manifest missing or unreadable, so nothing it pins can be shown as current"})
        return {}
    files = d["files"]
    return {f["path"]: f["sha256"] for f in files if isinstance(f, dict) and "path" in f} if isinstance(files, list) else {f"{rel.rsplit('/', 1)[0]}/{k}": v.get("sha256") for k, v in files.items() if isinstance(v, dict)}


def _put(bound: _Bound, out: dict, rel: str, b: bytes, role: str, want: str) -> dict:
    name = rel.split("/")[-1]
    path = f"{PUBLIC}/{role}/{name}"
    out[f"@{path}"] = b
    return {"name": name, "role": role, "source": rel, "path": path, "sha256": want, "bytes": len(b)}


def _ledger(bound: _Bound, out: dict, files: list) -> dict | None:
    man = _manifest(bound, f"{SEQ}/manifest.json", "sequence-evidence manifest")
    want = man.get(f"{SEQ}/ledger.json")
    b = bound.get(f"{SEQ}/ledger.json", want, "sequence-function ledger")
    led = _json(b)
    if led is None:
        return None
    if led.get("schema") != LEDGER_SCHEMA:
        bound.withheld.append({"path": f"{SEQ}/ledger.json", "label": "sequence-function ledger", "reason": f"unsupported schema {led.get('schema')!r}"})
        return None
    files.append(_put(bound, out, f"{SEQ}/ledger.json", b, "ledger", want))
    seqs = []
    for s in led.get("sequences", []):
        ref = s.get("artifact_ref") or {}
        rel, h = ref.get("path"), ref.get("sha256")
        pub = None
        if isinstance(rel, str) and rel.startswith(f"{SEQ}/sequences/") and rel.endswith(SEQUENCE_ALLOW_SUFFIX):  # natural-reference FASTA only; model-output JSON stays a pinned source
            sb = bound.get(rel, h, f"sequence {s.get('id')}")
            if sb is not None:
                pub = _put(bound, out, rel, sb, "sequences", h)
                files.append(pub)
        seqs.append(
            {
                "id": s.get("id"),
                "kind": s.get("sequence_kind"),
                "length_nt": s.get("length_nt"),
                "sequence_sha256": s.get("sequence_sha256"),
                "identity": s.get("experimental_construct_identity"),
                "reference": s.get("reference"),
                "source_refs": s.get("source_refs", []),
                "artifact": {"path": rel, "sha256": h},
                "download": pub["path"] if pub else None,
            }
        )
    ents = [
        {
            "id": e.get("id"),
            "evidence_class": e.get("evidence_class"),
            "direction": e.get("direction"),
            "functional_validation": e.get("functional_validation"),
            "downstream_layer": e.get("downstream_layer"),
            "species": e.get("species"),
            "context": e.get("context") or {},
            "demonstrated_effect": e.get("demonstrated_effect"),
            "missing_causal_bridge": e.get("missing_causal_bridge"),
            "readout": e.get("falsifiable_validation_readout"),
            "model_ready": e.get("model_ready"),
            "sequence_refs": e.get("sequence_refs", []),
            "source_refs": e.get("source_refs", []),
        }
        for e in led.get("entries", [])
    ]
    sources = [
        {"id": x.get("id"), "doi": x.get("doi"), "evidence_status": x.get("evidence_status"), "license": x.get("redistribution_license"), "full_text_in_public_tree": x.get("full_text_in_public_tree"), "response_sha256": x.get("response_sha256"), "selectors": x.get("selectors", [])} for x in led.get("sources", [])
    ]
    return {"sha256": want, "schema": led["schema"], "sequences": seqs, "entries": ents, "bridges": led.get("bridges", []), "sources": sources, "scope": led.get("scope"), "unresolved_LEN_coordinates": led.get("unresolved_LEN_GRCz11_coordinates")}


def _counts(led: dict) -> dict:
    """Every number is computed from the ledger as it is now."""
    seq, ent = led["sequences"], led["entries"]
    proposals = [e for e in ent if e["direction"] == "inverse_proposal"]
    return {
        "sequence_artifacts": len(seq),
        "sequence_kinds": dict(Counter(s["kind"] for s in seq)),
        "sequence_identity": dict(Counter(str(s["identity"]) for s in seq)),
        "entries": len(ent),
        "entries_by_class": dict(Counter(e["evidence_class"] for e in ent)),
        "entries_by_direction": dict(Counter(e["direction"] for e in ent)),
        "entries_by_functional_validation": dict(Counter(str(e["functional_validation"]) for e in ent)),
        "retained_unscreened_proposals": len(proposals),
        "bridges_by_status": dict(Counter(b.get("status") for b in led["bridges"])),
    }


def _contracts(bound: _Bound, out: dict, files: list, man: dict) -> dict | None:
    rel = f"{DOE}/instrument-contracts.json"
    b = bound.get(rel, man.get(rel), "instrument contracts")
    doc = _json(b)
    if doc is None:
        return None
    if doc.get("schema") != CONTRACT_SCHEMA:
        bound.withheld.append({"path": rel, "label": "instrument contracts", "reason": f"unsupported schema {doc.get('schema')!r}"})
        return None
    files.append(_put(bound, out, rel, b, "doe", man[rel]))
    rows = []
    for i, c in enumerate(doc.get("contracts", [])):
        slot = c.get("proposed_compiler_slot") or {}
        rows.append(
            {
                "id": c.get("instrument id and version"),
                "kind": c.get("kind"),
                "evidence_type": c.get("evidence_type"),
                "interface": slot.get("interface"),
                "slot_kind": slot.get("kind"),
                "blocked_on": c.get("blocked_on"),
                "observation": c.get("observation schema with units"),
                "calibration_context": c.get("calibration_context"),
                "pointer": f"/contracts/{i}",
                "calibrated": False,
            }
        )
    return {"sha256": man[rel], "rows": rows, "rule": doc.get("rule"), "protocol_sha256": doc.get("protocol_sha256")}


def _screen(bound: _Bound, out: dict, files: list, man: dict) -> dict | None:
    rel = f"{DOE}/result.json"
    b = bound.get(rel, man.get(rel), "design screen result")
    r = _json(b)
    if not isinstance(r, dict) or not isinstance(r.get("funnel"), dict):
        return None
    files.append(_put(bound, out, rel, b, "doe", man[rel]))
    f = r["funnel"]
    stages = sorted({k[: -len(suf)] for k in f if k[:1] == "S" for suf in ("_flags_any", "_rejects_first_listed") if k.endswith(suf)})
    return {
        "sha256": man[rel],
        "candidates": f.get("candidates"),
        "survivors": f.get("survivors"),
        "evidence_kind": r.get("evidence_kind"),
        "stages": [{"id": s, "flags_any": f.get(f"{s}_flags_any"), "rejects_first_listed": f.get(f"{s}_rejects_first_listed")} for s in stages],
        "biological_success_probability": r.get("biological_success_probability"),
        "empirical_validation": r.get("empirical_validation"),
        "protocol_sha256": r.get("protocol_sha256"),
    }


def _compiler(bound: _Bound, out: dict, files: list, root: Path) -> dict:
    man = _manifest(bound, f"{BIO}/genotype-manifest.json", "genotype manifest")
    got = {}
    for name in GENOTYPE_FILES:
        rel = f"{BIO}/{name}"
        b = bound.get(rel, man.get(rel), name)
        d = _json(b)
        if d is not None:
            got[name] = d
            files.append(_put(bound, out, rel, b, "compiler", man[rel]))
    graph = got.get("genotype-graph.json")
    if graph:  # the graph names the repository files it was built from; a changed source means the graph no longer describes the repository
        for k, s in (graph.get("sources") or {}).items():
            if bound.get(s.get("path", ""), s.get("sha256"), f"graph source {k}") is None:
                graph = None
                break
    return {"graph": graph, "contract": got.get("genotype-contract.json"), "validation": got.get("genotype-validation.json"), "manifest": man}


def _interfaces(graph: dict, val: dict | None, contracts_sha: str | None) -> list[dict]:
    rows = []
    for iid, g in graph["interfaces"].items():
        v = ((val or {}).get("interfaces") or {}).get(iid, {})
        slots = []
        for s in v.get("instrument_slots", []):
            ref = s.get("contract_ref") or {}
            slots.append({"kind": s.get("kind"), "id": ref.get("instrument_id"), "status": ref.get("status"), "gap": s.get("gap")})
        rows.append(
            {
                "id": iid,
                "from": g.get("from"),
                "to": g.get("to"),
                "text": g.get("text"),
                "state": g.get("state"),
                "required_measurement": g.get("required_measurement"),
                "required_context": g.get("required_context", []),
                "bridges": [{"id": b.get("bridge") or b.get("id"), "status": b.get("status"), "text": b.get("text")} for b in g.get("bridges", [])],
                "directions": g.get("directions"),
                "proposed_experiments": [{"id": e.get("id"), "note": e.get("note")} for e in g.get("proposed_experiments", [])],
                "validation": {
                    "input": v.get("input"),
                    "observation": v.get("observation"),
                    "controls": v.get("controls", []),
                    "decision_rule": v.get("decision_rule"),
                    "ledger_readouts": v.get("ledger_readouts", []),
                    "recorded_bridges": v.get("recorded_bridges", []),
                    "invalidated_by_dna_change": v.get("invalidated_by_dna_change"),
                    "invalidated_by_context_change": v.get("invalidated_by_context_change"),
                    "instrument_slots": slots,
                }
                if v
                else None,
            }
        )
    return rows


def build(ins, out: dict, root: Path | None = None) -> dict | None:
    root = Path(root) if root else ROOT
    bound = _Bound(ins, root)
    if not (root / BIO / "genotype-manifest.json").exists():
        return None
    files: list = []
    comp = _compiler(bound, out, files, root)
    led = _ledger(bound, out, files)
    doe_man = _manifest(bound, f"{DOE}/manifest.json", "DOE manifest")
    contracts = _contracts(bound, out, files, doe_man)
    screen = _screen(bound, out, files, doe_man)
    graph, val = comp["graph"], comp["validation"]
    ref = ((val or {}).get("instrument_contracts_ref") or {}).get("sha256")
    notes = []
    if val and contracts and ref != contracts["sha256"]:  # the validation was generated against other instrument bytes than the DOE now declares
        notes.append({"path": f"{BIO}/genotype-validation.json", "label": "validation slices", "reason": f"built against instrument contracts {str(ref)[:12]}, the DOE now declares {contracts['sha256'][:12]}"})
        val = None
    uncal = [i for i, g in (graph or {}).get("interfaces", {}).items() if g.get("state") != "calibrated_transfer"]
    return {
        "schema": "frontier.site.genotype/1",
        "status": "current" if graph and led and not bound.withheld and not notes else "partial",
        "withheld": bound.withheld + notes,
        "scope": SCOPE,
        "must_not_say": (graph or {}).get("must_not_say", []),
        "nodes": [{"id": n["id"], "text": n["text"]} for n in (graph or {}).get("nodes", [])],
        "interfaces": _interfaces(graph, val, contracts["sha256"] if contracts else None) if graph else [],
        "interface_states": {i: g.get("state") for i, g in (graph or {}).get("interfaces", {}).items()},
        "uncalibrated_interfaces": uncal,
        "endorsed_candidates": 0 if graph and len(uncal) == len(graph["interfaces"]) else None,  # no interface is calibrated, so the compiler endorses none; unknown if the graph is withheld
        "single_genome_guaranteed": False,
        "cutsets": (val or {}).get("cutsets", []),
        "after_dna_change": (val or {}).get("after_proposed_dna_change"),
        "inverse_rules": (graph or {}).get("inverse_rules", []),
        "ledger": ({**led, "counts": _counts(led)} if led else None),
        "formal": {"cutsets": (val or {}).get("cutsets", []), "text": "A claim depends on every interface it crosses; each must be a calibrated transfer for the stated context before the claim can follow. This is bookkeeping about dependence, not a biological result."},
        "premises": [{"id": b.get("id"), "status": b.get("status"), "from_entry": b.get("from_entry"), "to_layer": b.get("to_layer"), "conditions": b.get("conditions")} for b in (led or {}).get("bridges", [])],
        "instrument_contracts": contracts,
        "design_screen": screen,
        "files": files,
        "manifests": {"genotype": f"{BIO}/genotype-manifest.json", "sequence_evidence": f"{SEQ}/manifest.json", "doe": f"{DOE}/manifest.json"},
    }
