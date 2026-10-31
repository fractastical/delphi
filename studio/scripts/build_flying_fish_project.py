#!/usr/bin/env python3
"""Build the flying-fish mission as a validated Project draft from the COMMITTED site catalog and snapshot.

Deterministic (no timestamps, no network). Every member ref is copied verbatim from site/data/catalog.json and the script
fails closed if a wanted record is absent: it never invents a version. Those refs live in the catalog's `snapshot` namespace;
to submit to a live node run `repin(draft, store, token)` (below), which replaces each ref by the node's current head for the
same kind+id or raises. The mission is one featured Project on a generic schema, not a hardcoded organism.

    python3 scripts/build_flying_fish_project.py [projects/flying-fish.draft.json]
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from frontier.models import Draft  # noqa: E402

CATALOG, SNAPSHOT = ROOT / "site/data/catalog.json", ROOT / "site/data/snapshot.json"
OUT = ROOT / "projects/flying-fish.draft.json"
DRAFT_ID = "project-flying-fish-mission"

# (catalog id, role, subsystem, scale, relationship, applicability, rationale)
MEMBERS = [
    ("doc-SPEC-005", "mission", "mission specification", None, "context_for",
     "Declared: the governing specification of the demo mission and its honesty rules; it makes no biological claim.",
     "Pinned so the project states its own governing document."),
    ("src-fish1990", "evidence", "wing loading and aspect-ratio allometry", "organism", "supports",
     "Declared: preserved Exocoetidae specimens (n = 199, 0.003-0.53 kg); mass, wing-loading and pectoral-fin aspect-ratio ranges. "
     "A source envelope, not a flight-feasibility result and not a universal limit.",
     "The only primary dataset behind the numeric design envelope."),
    ("src-parkchoi2010", "evidence", "lift and drag polar", "organ", "informs",
     "Declared: the intended source of lift/drag coefficients for a flying-fish model. The PDF has not been read in this "
     "repository, so no coefficient from it is applied anywhere.",
     "Marks exactly which calibration is missing for the glide model."),
    ("src-davenport1992", "evidence", "stability and wing-loading morphometrics", "organism", "constrains",
     "Declared: known only through a publisher extract; its stability argument is not turned into a numeric limit here.",
     "Records a stated stability constraint without inventing a threshold."),
    ("src-davenport2003", "gap", "maximum size argument", "organism", "context_for",
     "Declared: UNREAD (publisher challenge). No size limit is derived from it.",
     "The paper a size limit would need; its absence is a gap, not a result."),
    ("src-daane2021", "context", "molecule-to-fin association", "molecular", "informs",
     "Declared: an association in zebrafish with genome signatures across species; transfer to exocoetids is an unestablished "
     "hypothesis and no parameter maps it to wing area.",
     "The one molecule-to-fin source indexed; kept without a causal bridge."),
    ("src-darwin1859", "context", "historical framing", "ecological", "context_for",
     "Declared: Chapter VI conceivability argument; context only, not evidence for a transition.",
     "Primary source of the design problem's framing."),
    ("src-lovejoy2004", "context", "phylogeny of the family", "ecological", "context_for",
     "Declared: phylogenetic context; no trait-scale parameter is drawn from it.",
     "Context for what 'evolutionarily possible' would have to mean."),
    ("doc-model-coupling", "design", "model coupling layer", None, "implements",
     "Declared: describes typed ports and the composable / scenario / refused rule for coupling models; it validates no coupling itself.",
     "States how models may be composed and why bridges are refused."),
    ("doc-2026-10-31-kcne1-binding-ddg-STOPPED", "measurement", "macromolecular binding test", "macromolecular", "constrains",
     "Declared: a preregistered test that STOPPED at its coverage floor (a structure covering about a fifth of the assay). "
     "Not a flying-fish result.",
     "Shows what a stopped, honest test at this scale looks like."),
    ("F002", "gap", "molecular-to-tissue evidence", "tissue", "depends_on",
     "Declared: the open question of what measured and modelled quantities could connect molecular predictions to tissue transport; unanswered.",
     "The recorded gap between the molecular and tissue scales."),
    ("F003", "subsystem", "linear versus nonlinear pattern", "tissue", "informs",
     "Declared: how linear instability analysis relates to the nonlinear pattern a simulation produces; open.",
     "Applies to any reaction-diffusion model considered for fin patterning."),
    ("turing-wavelength", "subsystem", "pattern wavelength at onset", "tissue", "context_for",
     "Declared: a generic Turing onset-wavelength statement from the Delphi register; no fin-tissue parameter maps to it.",
     "Context only: the coupling layer refuses reaction-diffusion mode number -> wing span."),
]

# scale -> (status, note). 'implemented_model' = a runnable model exists FOR THIS MISSION at that scale.
COVERAGE = [
    ("molecular", "source_only", "One molecule-to-fin source (Daane 2021, association in zebrafish); no executable model, no parameter link to wing area."),
    ("macromolecular", "unimplemented", "No structure or affinity input for a fin-patterning protein; the one binding test was stopped at its coverage floor."),
    ("subcellular", "unimplemented", "Nothing indexed."),
    ("cellular", "source_only", "A two-cell Delta-Notch model is replayed in this project but it is non-dimensional and not tied to a fish; no cell-to-fin coupling exists."),
    ("tissue", "unimplemented", "A reaction-diffusion field sweep exists only for abstract kinetics; no fin-tissue model, no SI length or time scale."),
    ("organ", "implemented_model", "An elastic fin-ray beam with an ASSUMED stiffness range runs; no calibrated fin stiffness exists."),
    ("neural", "unimplemented", "Nothing indexed."),
    ("organism", "implemented_model", "Exact-rational constraint solver, point-mass glide simulation and a fin load bridge run; all rest on declared assumptions."),
    ("developmental", "source_only", "Fish 1990 allometry only (a measured scaling of wing loading with mass); no developmental model."),
    ("collective", "unimplemented", "Nothing indexed."),
    ("ecological", "source_only", "Darwin 1859, a phylogeny and a fossil source as context; no ecological model."),
    ("evolutionary", "unknown", "No source or model is indexed for this scale in the snapshot."),
]

REQUIREMENTS = [
    # numeric envelope constraints are Fish 1990's observed ranges; they bound the design space, they do not certify it.
    dict(id="req-mass-min", kind="constraint", text="Stay at or above the lightest specimen mass in the source envelope.",
         quantity=dict(name="body mass", unit="kg", comparator=">=", value="0.003"), source_member=1, stage="proposed"),
    dict(id="req-mass-max", kind="constraint", text="Stay at or below the heaviest specimen mass in the source envelope.",
         quantity=dict(name="body mass", unit="kg", comparator="<=", value="0.53"), source_member=1, stage="proposed"),
    dict(id="req-wl-min", kind="constraint", text="Stay at or above the lowest reported wing loading.",
         quantity=dict(name="wing loading", unit="N/m^2", comparator=">=", value="11.7"), source_member=1, stage="proposed"),
    dict(id="req-wl-max", kind="constraint", text="Stay at or below the highest reported wing loading.",
         quantity=dict(name="wing loading", unit="N/m^2", comparator="<=", value="208.9"), source_member=1, stage="proposed"),
    dict(id="req-coupling-labels", kind="validation",
         text="Every coupling between models is reported as composable, assumption-level scenario, or refused; scenario results keep that label.",
         source_member=8, stage="declared"),
    dict(id="req-no-feasibility-claim", kind="non_goal",
         text="Do not claim that an organism is feasible, that a source envelope is a universal feasibility region, or that a model coupling is a biological correspondence.",
         stage="declared"),
]
OPEN_QUESTIONS = [
    dict(text="What measured and modelled quantities could connect a molecular prediction to tissue transport in one specified fish system?",
         problem="F002", blocks=[5, 9]),
    dict(text="How does a linear instability result relate to the nonlinear pattern a reaction-diffusion simulation produces for a fin-like domain?",
         problem="F003", blocks=[12]),
    dict(text="Which measured lift and drag coefficients apply to a flying-fish-like body? The Park & Choi tables have not been read, so CL_max, CD0 and e are declared priors.",
         blocks=[2]),
    dict(text="What is the effective flexural rigidity of an excised fin ray under the clamping that matches its in-fin boundary condition? The beam model sweeps an assumed range.",
         blocks=[]),
    dict(text="Is there a sourced upper size limit for a gliding fish? Davenport 2003, the paper that argues one, is unread.", blocks=[4]),
]


def load() -> tuple[dict, dict, dict]:
    cat = json.loads(CATALOG.read_text())
    return cat, json.loads(SNAPSHOT.read_text()), {r["ref"]["id"]: r["ref"] for r in cat["records"]}


def build() -> dict:
    cat, snap, refs = load()
    members = []
    for cid, role, sub, scale, rel, appl, why in MEMBERS:
        if cid not in refs:
            raise SystemExit(f"catalog has no record {cid!r}; refusing to invent a ref")
        m = dict(ref=refs[cid], role=role, subsystem=sub, relationship=rel, applicability=appl,
                 causal_bridge="none_declared", rationale=why)
        if scale:
            m["scale"] = scale
        members.append(m)
    questions = []
    for q in OPEN_QUESTIONS:
        d = dict(text=q["text"], blocks=q["blocks"])
        if q.get("problem"):
            d["problem"] = refs[q["problem"]]
        questions.append(d)
    payload = {
        "title": "Engineer toward a flying fish",
        "mission": snap["mission"]["title"] + ": explore, with typed models and refusals, what a flying-fish-like glider would require. "
                   "This is a design-studio project on a generic schema; it does not assert that any design is feasible.",
        "source": {"uri": "https://github.com/kganjam/delphi-frontier", "locator": "site/data/snapshot.json#mission",
                   "source_version": snap["input_fingerprint"][:12], "content_sha256": hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
                   "content_available": False, "access": "public repository file; member refs are snapshot-catalog refs", "license": None},
        "limitations": ["Every member ref is a snapshot-catalog ref (namespace 'snapshot'), not a live-store version: re-pin before submitting.",
                        "Membership is a declared pin and states where a record applies; it infers no causal link between members.",
                        "No calibration bridges any pair of scales; every coupling above the organ scale is refused or assumption-level.",
                        "The numeric requirements are Fish 1990 observed ranges proposed as a design envelope, not a feasibility certificate."],
        "scale_coverage": [dict(scale=s, status=st, note=n) for s, st, n in COVERAGE],
        "members": members, "requirements": REQUIREMENTS, "open_questions": questions,
    }
    draft = {"namespace": "snapshot", "kind": "Project", "id": DRAFT_ID, "issuer": "dx-guilds",
             "source_uri": "urn:frontier:project-draft:flying-fish", "visibility": "public", "payload": payload}
    Draft.model_validate(draft)          # the real contract; raises on any violation
    return {
        "draft": draft,
        "grounding": {
            "refs_source": "site/data/catalog.json (snapshot namespace), copied verbatim",
            "catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
            "snapshot_sha256": hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
            "members_grounded": len(members), "members_in_catalog": sum(m["ref"]["id"] in refs for m in members),
            "artifact_pins": "none: the catalog does not list per-record artifact digests, so none is pinned",
            "unimplemented_or_unknown_scales": [s for s, st, _ in COVERAGE if st in ("unimplemented", "unknown")],
            "issuer_note": "issuer is a placeholder; the importing operator re-issues under their authenticated actor",
            "not_established": ["any design is feasible", "any coupling is a biological correspondence",
                                "that these refs exist as versions in a live node"]},
    }


def repin(draft: dict, store, token: str | None = None) -> dict:
    """Rewrite a draft's namespace and every member / calibration / open-question ref to the node's CURRENT head for the same
    kind+id. Raises Missing if any record is absent: nothing is guessed, dropped or kept at a stale snapshot version."""
    out = copy.deepcopy(draft)
    out["namespace"] = store.namespace
    pl = out["payload"]

    def fix(r):
        return store.head_ref(r["kind"], r["id"], token)["ref"]
    for m in pl["members"]:
        m["ref"] = fix(m["ref"])
        if m.get("calibration"):
            m["calibration"] = fix(m["calibration"])
    for q in pl["open_questions"]:
        if q.get("problem"):
            q["problem"] = fix(q["problem"])
    pl["limitations"] = [x for x in pl["limitations"] if "snapshot-catalog ref" not in x]
    Draft.model_validate(out)
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build(), indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"wrote {target}")
