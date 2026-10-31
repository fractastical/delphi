"""Machine-readable source / claim / action / evidence / artifact mapping for the BIOMD0000001047 replay.

Connector-local: it emits Frontier record drafts in the existing `frontier.models` shapes and adds
no root schema. Everything is a *proposed* draft; nothing is submitted, reviewed or accepted.

Three things are kept apart on purpose:
  * source assertions  -- what the paper/curators state (read at abstract level only);
  * simulations        -- what this connector computed from the pinned file;
  * unknown            -- applicability to flying fish, recorded as a `Problem`, not as a Claim.
No `observed` Evidence exists in this mapping, and the mapping says so.

`core_records()` is deterministic (fixed timestamp). `build()` adds the simulated Evidence only when
an orx capture is present; otherwise that slot says `absent`, never a placeholder.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

NAMESPACE, ISSUER = "node-a", "biomodels-worker"
PACKAGE = Path(__file__).resolve().parent
ACCESSION = "BIOMD0000001047"
RECEIPT_DIR = PACKAGE / "receipts" / ACCESSION
CREATED_AT = "2026-10-31T00:00:00+00:00"   # fixed so record versions are reproducible; not a claim about when work happened
MODEL_SHA256 = "da21ab52edba14b61e41ee87df7a8bb2f367a1206e6e822602f1e75271fae8e2"
# sha256 of the BioModels `publication.synopsis` string as retrieved 2026-10-31 (1,674 chars); abstract-level only.
SYNOPSIS_SHA256 = "39bae4093cc625b1c7ff7ae35792ca53aff45a2fb61b0538149220238e5c1b97"
PINS = {"libroadrunner": "2.10.0", "numpy": "2.4.4", "scipy": "1.17.1", "python": "3.13.12", "pytest": "9.0.2"}


def _frontier():
    sys.path.insert(0, str(PACKAGE.parents[1]))
    from frontier import models  # the root package in this repository, read-only
    return models


def _src(uri, locator, version, sha, access):
    return {"uri": uri, "locator": locator, "source_version": version, "content_sha256": sha,
            "content_available": False, "access": access, "license": None}


PAPER = _src(
    "https://pubmed.ncbi.nlm.nih.gov/9015458/",
    "BioModels metadata publication.synopsis (abstract-level; paper full text paywalled and not read)",
    "J Theor Biol 1996 183(4):429-446; BioModels revision 3", SYNOPSIS_SHA256,
    "Abstract only, via BioModels metadata. The article is not open access (Europe PMC, PMC, OpenAlex all report closed); "
    "the Oxford eprints accepted manuscript listed by OpenAlex timed out and was not read. No licence stated for the text.")
MODEL = _src(
    f"https://www.biomodels.org/{ACCESSION}", "main file delta_notch.xml (SBML L2V4)", "BioModels revision 3", MODEL_SHA256,
    "Public download without login. BioModels' FAQ states CC0 for all models, but its terms page redirected to a login form "
    "and was not read, so no licence is recorded here and the bytes are not redistributed.")


def _draft(kind, id_, payload):
    return {"namespace": NAMESPACE, "kind": kind, "id": id_, "issuer": ISSUER,
            "source_uri": f"urn:frontier:connector:biomodels:{ACCESSION}", "visibility": "public", "predecessor": None, "payload": payload}


def core_records() -> list[dict]:
    """Validated Claim/Problem/Action/Evidence records that do not depend on an orx run."""
    m = _frontier()
    drafts = [
        _draft("Claim", "biomodels-1047-source-model-claim", {
            "title": "Source assertion: Collier 1996 propose that Delta-Notch lateral inhibition with feedback can generate fine-grained cell-state patterns",
            "statement": "Collier, Monk, Maini and Lewis (1996) construct a two-state contact-mediated lateral-inhibition model in which receipt of Notch "
                         "activation reduces Delta production, and report that this feedback can amplify differences between adjacent cells into a pattern.",
            "context": "Paraphrase of the abstract as carried by BioModels. This is the paper's own theoretical claim about its model; it is not an observation "
                       "and was not re-derived from the paper.",
            "assumptions": ["Abstract-level reading only; the paper's conditions for patterning (parameter ranges) were not read."],
            "limitations": ["Source assertion only; no evidence in this mapping tests it against any organism.", "Full text not read."],
            "source": PAPER}),
        _draft("Claim", "biomodels-1047-source-biology-assertion", {
            "title": "Source assertion (unevaluated): the paper states Delta-Notch lateral inhibition is documented in flies, worms and vertebrates",
            "statement": "The abstract states that lateral inhibition is well documented in flies, worms and vertebrates and that Notch and Delta (or homologues) mediate it.",
            "context": "Background statement by the paper's authors. It is a pointer to literature the authors cite, not evidence gathered or checked here, and it does "
                       "not mention any fish, flying or otherwise.",
            "assumptions": [], "limitations": ["Not evaluated; the cited experiments were not read.", "Says nothing about any fin or flying-fish tissue."],
            "source": PAPER}),
        _draft("Claim", "biomodels-1047-model-behaviour", {
            "title": "Model behaviour: as encoded in BIOMD0000001047 the symmetric state is unstable and the file's perturbation resolves to opposite cell states",
            "statement": "Integrating the ODEs in BioModels file BIOMD0000001047 (sha256 da21ab52...) as written, with its stored non-dimensional parameters "
                         "(a=0.01, b=100, h=2, k=2, mu=1, rho=1), the symmetric steady state has a positive Jacobian eigenvalue, and from the file's initial conditions "
                         "(cell 2 starts 1% below cell 1) the two cells end in opposite Delta/Notch states.",
            "context": "A statement about this file's mathematics only. It is neither an observation of any organism nor a check that the file matches the paper. "
                       "Variables are non-dimensional; the file declares no units that are actually used.",
            "assumptions": ["The file is taken as published by BioModels (curated, revision 3).", "Integration horizon 0..60 in the model's own time, chosen for this replay."],
            "limitations": ["Applies to the two-cell system only.", "Fidelity to the paper was not checked.", "No biological parameter provenance is available from the file."],
            "source": MODEL}),
        _draft("Problem", "biomodels-1047-flying-fish-applicability", {
            "title": "UNKNOWN: whether Delta-Notch lateral inhibition acts in any flying-fish tissue relevant to flight morphology",
            "known_state": "A two-cell non-dimensional model of Drosophila-annotated (NCBI taxonomy id 7215, name unresolved) Delta-Notch lateral inhibition has been replayed. "
                           "Nothing links it to flying fish. The paper's abstract mentions flies, worms and vertebrates only.",
            "question": "Is there evidence that Notch-Delta lateral inhibition patterns a flying-fish structure of interest, and if so which quantities map onto this model?",
            "problem_kind": "project_gap",
            "novelty_status": "Not assessed; no literature search for fish or flying-fish Notch/Delta was performed.",
            "data_access": "Unknown. No flying-fish expression, genome or perturbation data was located or read.",
            "completeness": "recorded",
            "required_capabilities": ["literature and genome search for Exocoetidae Notch/Delta orthologs", "tissue-level expression or perturbation data", "units and time-scale mapping for the model"],
            "downstream_uses": ["A cross-species analogy would stay proposed until each item in `original.needed` is satisfied."],
            "dependencies": [], "source": MODEL,
            "original": {"needed": [
                "a named flying-fish trait and tissue where lateral inhibition is claimed, with evidence",
                "Notch/Delta orthologs identified and expressed in that tissue",
                "a mapping from dimensionless variables and time to measurable quantities",
                "a cell-neighbourhood geometry (this model has exactly two cells)",
                "parameter values or ranges for the target, with source and uncertainty",
                "an independent check that the pattern appears in a proxy or target tissue"],
                "status": "unknown"}}),
    ]
    records = {d["id"]: m.make_record(m.Draft.model_validate(d), created_at=CREATED_AT) for d in drafts}
    claim_a, claim_b = (m.ref(records[i]) for i in ("biomodels-1047-source-model-claim", "biomodels-1047-model-behaviour"))
    receipt = json.loads((RECEIPT_DIR / "receipt.json").read_text())
    action = _draft("Action", "biomodels-1047-replay", {
        "target": claim_b, "title": "Replay BIOMD0000001047 with libroadrunner, with independent-integrator and mutation controls",
        "acceptance_criteria": [
            "Re-execution from the pinned file reproduces the recorded trajectory CSV and inventory hashes byte-for-byte.",
            "All receipt controls pass, and the mutated-evaluator control is rejected.",
            "A changed law (h=0.5) does not reproduce the pattern and is not accepted under the original pin."],
        "required_capabilities": ["python 3.13", "libroadrunner 2.10.0 (needs libpython preload)", "numpy 2.4.4", "scipy 1.17.1", "network to www.biomodels.org"],
        "cost_stop_bounds": f"Actual: {receipt['run']['elapsed_s']} s on one CPU thread, no GPU, no paid model. Stop bound: scope TasksMax=128 MemoryMax=4G MemorySwapMax=0 RuntimeMaxSec=600.",
        "cache_key": {"target": claim_b["version"], "input": f"BIOMD0000001047 delta_notch.xml sha256:{MODEL_SHA256}",
                      "code": f"connectors/biomodels code_sha256:{receipt['run']['code_sha256']}",
                      "model": "none: deterministic ODE integration, no language model",
                      "environment": "; ".join(f"{k} {v}" for k, v in PINS.items() if k != "pytest") + "; 1 thread",
                      "parameters": "file values; T=0..60, 601 points; cvode rtol 1e-10 atol 1e-14",
                      "scope": "two-cell Delta-Notch system as encoded; no biological applicability claimed",
                      "acceptance_policy": m.POLICY}})
    records[action["id"]] = m.make_record(m.Draft.model_validate(action), created_at=CREATED_AT)
    ev = _draft("Evidence", "biomodels-1047-source-assessment", {
        "target": claim_a, "evidence_kind": "source_assessment", "source": PAPER,
        "created_time": {"value": None, "basis": "unknown"}, "retrieved_time": {"value": "2026-10-31T18:30:00+00:00", "basis": "declared"},
        "method": "Read BioModels' metadata for the entry (curation status CURATED, publication synopsis). The paper's full text was not accessed.",
        "context": "Establishes only that BioModels carries this entry with this synopsis; it does not assess whether the paper is right.",
        "assumptions": [], "provenance": {"read_level": "abstract (via BioModels synopsis)", "paper_full_text": "could-not-access (paywalled; Oxford eprint timed out)",
                                          "metadata_sha256_of_synopsis": SYNOPSIS_SHA256},
        "source_dependence": {"declared": False}, "uncertainty": "Not quantified.",
        "limitations": ["Abstract-level only.", "A curated database entry is not an independent check of the paper."]})
    records[ev["id"]] = m.make_record(m.Draft.model_validate(ev), created_at=CREATED_AT)
    return list(records.values())


def artifacts() -> list[dict]:
    receipt = json.loads((RECEIPT_DIR / "receipt.json").read_text())
    rel = f"connectors/biomodels/receipts/{ACCESSION}"
    out = [{"role": "input-model", "kind": "SBML L2V4", "uri": MODEL["uri"], "sha256": MODEL_SHA256, "bytes": 43277,
            "in_repo": False, "reason": "licence terms unread; connector re-fetches and verifies the digest"}]
    for name, sha in sorted(receipt["output_sha256"].items()):
        out.append({"role": "simulation-output", "path": f"{rel}/{name}", "sha256": sha, "in_repo": True, "evidence_kind": "simulated"})
    out.append({"role": "run-receipt", "path": f"{rel}/receipt.json", "sha256": hashlib.sha256((RECEIPT_DIR / "receipt.json").read_bytes()).hexdigest(), "in_repo": True})
    return out


def build(orx_dir: Path | None = None) -> dict:
    m = _frontier()
    records = core_records()
    by_id = {r["id"]: r for r in records}
    sim_evidence = None
    orx_dir = orx_dir or PACKAGE / "orx"
    draft_path = orx_dir / "evidence_draft.json"
    if draft_path.exists():
        draft = json.loads(draft_path.read_text())
        rec = m.make_record(m.Draft.model_validate(draft), created_at=json.loads((orx_dir / "orx_facts.json").read_text())["evidence_created_at"])
        sim_evidence = rec
        by_id[rec["id"]] = rec
    edges = [{"type": "targets", "from": r["id"], "to": r["payload"]["target"]["id"]} for r in by_id.values() if "target" in r["payload"]]
    if sim_evidence:
        edges.append({"type": "produced_by_action", "from": sim_evidence["id"], "to": "biomodels-1047-replay", "note": "mapping-level edge; the root schema has no such typed field"})
    return {
        "mapping_schema": "biomodels-frontier-mapping-0.1 (connector-local; no root schema changed)",
        "status": "proposed drafts only; nothing submitted, reviewed or accepted",
        "separation": {
            "observed_evidence": [],
            "observed_note": "No observation of any biological system is recorded here. Every number was computed from a published model.",
            "source_assertions": ["biomodels-1047-source-model-claim", "biomodels-1047-source-biology-assertion", "biomodels-1047-source-assessment"],
            "simulation": ["biomodels-1047-model-behaviour", "biomodels-1047-replay"] + (["orx-run-simulated-evidence"] if sim_evidence else []),
            "simulated_evidence_slot": "present" if sim_evidence else "absent: no orx capture committed",
            "unknown": ["biomodels-1047-flying-fish-applicability"],
        },
        "unknowns": ["applicability to any flying-fish tissue", "parameter provenance (measured/fitted/assumed)", "fidelity of the file to the paper", "units and time scale",
                     "whether the paper's patterning conditions hold at these parameters (paper not read)"],
        "pins": PINS, "records": list(by_id.values()), "edges": edges, "artifacts": artifacts(),
    }


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else PACKAGE / "mapping" / f"{ACCESSION}.mapping.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = build()
    out.write_text(json.dumps(doc, indent=1, sort_keys=True))
    print(f"wrote {out.name}: {len(doc['records'])} records, {len(doc['edges'])} edges, simulated evidence {doc['separation']['simulated_evidence_slot']}")
