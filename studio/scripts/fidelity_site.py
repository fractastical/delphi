"""Aeroelastic fidelity ladder as a simulation-gallery card: the actual returned plots, the finest-lattice state video, the audit and the handoff.

build(ins, out, root=None) returns a list with one card in the shape of build_site.aeroelastic_cards (plus `figures` and `reports`, each file with its sha256)
and writes the allowlisted files into `out` under the site's "@artifacts/simulations/aeroelastic-fidelity-v1/..." convention. Nothing is rerun. Every
output is checked against the sha256 that return-handoff.json declares, the audit must say it passed with 0 findings, and the returned statuses must agree
with the independently recomputed ones. Any mismatch withholds the whole card: no file is published and no result is asserted.

What the return says is kept exactly as returned: 45 native arms, 27 effect statuses all sign_resolved and none resolved, bending and feedback undetermined in
all three contexts. The 21 rigid unit solves are a POSTHOC diagnostic, not part of the frozen ladder and not a decision. This is a bending-only,
torsion-rigid, fixed-alpha scaffold: no Navier-Stokes solve, no fluid-structure interaction and no biological claim."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = "artifacts/aeroelastic/fidelity-v1"
VID = "aeroelastic-fidelity-v1"
OUT = f"@artifacts/simulations/{VID}"
PUBLIC = f"artifacts/simulations/{VID}"
RENDER = f"{D}/render-l64x16-chi0.8-u20"
HANDOFF = f"{D}/return-handoff.json"
# The only files that may ever be copied: exactly what the handoff names, inside the fidelity directory. Roles decide how the card shows each.
ROLES = {
    f"{D}/fidelity-ladder.png": ("figure", "Fidelity ladder: five lattices, both effect triples and the native statuses", False),
    f"{D}/ladder-diagnostic.png": ("figure", "Posthoc rigid-solve diagnostic (not frozen, changes no decision)", True),
    f"{RENDER}/poster.png": ("poster", "Finest-lattice state, poster frame", False),
    f"{RENDER}/coupled-states.mp4": ("video", "Finest-lattice coupled states (static iterations, not time)", False),
    f"{RENDER}/provenance.json": ("report", "Render provenance", False),
    f"{D}/RESULTS.md": ("report", "Returned state and independent audit (report)", False),
    f"{D}/return-audit-report.json": ("report", "Frozen audit report (data)", False),
    f"{D}/ladder-diagnostic.json": ("report", "Posthoc diagnostic data", True),
    f"{D}/fidelity-figures.provenance.json": ("report", "Figure provenance", False),
}
SCOPE = "Bending-only, torsion-rigid, fixed-alpha scaffold with assumed EI. Not tissue, not a trimmed glide, not continuous fluid-structure interaction, not a Navier-Stokes solve, and no biological claim; biological_success_probability is null."


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _withheld(reason: list[str]) -> list[dict]:
    """A card that says what was refused and shows no result and no file."""
    return [
        {
            "id": VID,
            "title": "Aeroelastic fidelity ladder (withheld: the returned files do not match their declared hashes)",
            "scales": ["organ", "organism"],
            "evidence_kind": "withheld",
            "model": {"name": "not shown", "context": SCOPE},
            "time": {"units": "static iterations, not physical seconds", "note": "withheld"},
            "video": None,
            "video_state": "declared_but_unverified",
            "video_href": None,
            "poster_href": None,
            "provenance_href": None,
            "numerical_checks": [],
            "parameter_unknowns": [],
            "open_questions": [],
            "equations": [],
            "sources": [],
            "limitations": ["Withheld: " + "; ".join(reason)],
            "couplings": [],
            "manifest": HANDOFF,
            "native": True,
            "withheld": reason,
        }
    ]


def _read(ins, root: Path, rel: str) -> bytes | None:
    f = root / rel
    return ins.read(rel) if f.is_file() else None


def build(ins, out: dict, root: Path | None = None) -> list[dict]:
    root = Path(root) if root else ROOT
    hb = _read(ins, root, HANDOFF)
    if hb is None:
        return []
    try:
        ho = json.loads(hb)
        declared = {o["path"]: o["sha256"] for o in ho["outputs"]}
    except (ValueError, KeyError, TypeError):
        return _withheld([f"{HANDOFF} is not a readable handoff"])
    problems = [f"{p} is outside {D}" for p in declared if not p.startswith(D + "/")]
    files = {}
    for rel in ROLES:
        want, b = declared.get(rel), _read(ins, root, rel)
        if want is None:
            problems.append(f"{rel} is not declared in the handoff")
        elif b is None:
            problems.append(f"{rel} is missing")
        elif _sha(b) != want:
            problems.append(f"{rel} changed: declared {want[:12]}, found {_sha(b)[:12]}")
        else:
            files[rel] = b
    audit = json.loads(files[f"{D}/return-audit-report.json"]) if f"{D}/return-audit-report.json" in files else {}
    # The returned claims must agree with the audit that recomputed them from the returned bytes.
    nat, au = ho.get("native") or {}, ho.get("audit") or {}
    m = re.fullmatch(r"(\d+) sign_resolved, (\d+) resolved", str(nat.get("effect_statuses", "")))
    arms = re.fullmatch(r"(\d+)/(\d+)", str(nat.get("valid_arms", "")))
    recomputed = audit.get("recomputed_effects_and_decisions") or {}
    decisions = [(c, k, (v.get("decision") or {}).get(k)) for c, v in recomputed.items() for k in ("bending", "feedback")]
    statuses = [x for v in recomputed.values() for k, x in v.items() if k.startswith(("dCL", "CL_")) and isinstance(x, str)]
    if audit and not (audit.get("audit_passed") is True and not audit.get("findings") and au.get("audit_passed") is True and au.get("findings") == 0):
        problems.append("the audit did not pass with 0 findings")
    if audit and (audit.get("audit_protocol_sha256") != au.get("protocol_sha256") or audit.get("audit_code_sha256") != au.get("code_sha256")):
        problems.append("the audit report names a different protocol or code than the handoff")
    # 27 = the 9 quantities the frozen protocol classifies, in each context; the audit independently recomputed the 3 effect statuses per context.
    if audit and not (m and arms and arms.group(1) == arms.group(2) == str(audit.get("declared_arms")) and m.group(2) == "0" and int(m.group(1)) == 9 * len(recomputed)):
        problems.append("the returned arm count or effect statuses disagree with the audit")
    if audit and (not statuses or any(s != "sign_resolved" for s in statuses) or not decisions or any(d != "undetermined" for _, _, d in decisions)):
        problems.append("the recomputed statuses or decisions disagree with the returned ones")
    if problems or not audit:
        return _withheld(problems or ["the audit report is missing"])
    for rel, (role, _, _) in ROLES.items():
        out[f"{OUT}/{rel.rsplit('/', 1)[1]}"] = files[rel]
    href = lambda rel: f"{PUBLIC}/{rel.rsplit('/', 1)[1]}"  # noqa: E731
    entry = lambda rel: {"label": ROLES[rel][1], "href": href(rel), "sha256": declared[rel], "bytes": len(files[rel]), "posthoc": ROLES[rel][2]}  # noqa: E731
    ctxs = sorted(recomputed)
    native_n = int(arms.group(1))
    found = re.search(r"(\d+) rigid fixed-.{1,3} unit VLM solves", files[f"{D}/RESULTS.md"].decode("utf-8", "replace"))  # stated by the verified report; not recounted here
    n_rigid = int(found.group(1)) if found else None
    video, poster = f"{RENDER}/coupled-states.mp4", f"{RENDER}/poster.png"
    return [
        {
            "id": VID,
            "title": f"Aeroelastic fidelity ladder: {native_n} native arms, no effect magnitude resolved",
            "scales": ["organ", "organism"],
            "evidence_kind": "computed engineering result (video and plots: renders of returned states)",
            "model": {"name": "equivalent constant-EI bending scaffold + steady thin-surface VLM, five lattices", "context": SCOPE},
            "time": {"units": "static iterations, not physical seconds", "note": "The video shows the returned finest-lattice (64 x 16) states at chi 0.8, 20 m/s; deflection is unscaled. Nothing was rerun for this page."},
            "video": {"file": "coupled-states.mp4", "sha256": declared[video], "note": f"{len(files[video])} bytes"},
            "video_state": "present_verified",
            "video_href": href(video),
            "poster_href": href(poster),
            "provenance_href": href(f"{RENDER}/provenance.json"),
            "numerical_checks": [
                {"name": "native ladder", "result": f"{native_n} of {arms.group(2)} arms valid over {len(ctxs)} contexts ({', '.join(ctxs)}), five lattices; scientific exit {nat.get('exit_code')}"},
                {"name": "effect statuses", "result": f"{m.group(1)} sign_resolved, {m.group(2)} resolved: the sign is the same on every lattice but no magnitude is resolved. The audit's recomputation of the contributing statuses agrees ({len(statuses)} of {len(statuses)} sign_resolved)"},
                {"name": "engineering decisions", "result": f"bending and feedback are undetermined in all {len(ctxs)} contexts, so no context is promoted. This is the frozen outcome, not a failure; the remedy is a finer or separated ladder, never a looser rule"},
                {"name": "frozen audit", "result": f"passed with 0 findings; {audit.get('comparisons', {}).get('count')} comparisons, all within roundoff ({audit.get('comparisons', {}).get('exact')} exact); protocol {au['protocol_sha256'][:12]}…. Same-model integrity and reproduction, not validation"},
                {"name": "posthoc diagnostic (not frozen)", "result": f"{n_rigid if n_rigid is not None else 'a set of'} rigid unit solves after the return: rigid CL is non-monotone under span refinement and the mechanism is not identified. Descriptive only; it changes no status or decision"},
            ],
            "parameter_unknowns": ["EI is assumed, not measured.", "Mass, drag and the fixed angle of attack in the glide proxy are assumed engineering values."],
            "open_questions": ["Does a finer or span/chord-separated ladder resolve any effect magnitude? The posthoc solves suggest the same lattice scheme may not."],
            "equations": [],
            "sources": [
                {"label": "Returned report (RESULTS.md)", "locator": f"{PUBLIC}/RESULTS.md sha256 {declared[f'{D}/RESULTS.md'][:12]}…"},
                {"label": "Frozen audit report", "locator": f"{PUBLIC}/return-audit-report.json sha256 {declared[f'{D}/return-audit-report.json'][:12]}…"},
                {"label": "Handoff", "locator": f"{HANDOFF} (declares the sha256 of every output); collection receipt {ho.get('collection_receipt_sha256', '')[:12]}…"},
            ],
            "limitations": [SCOPE, "The 45 native arms are the frozen ladder. The rigid unit solves are a separate posthoc diagnostic and are not native arms.", "No effect magnitude is resolved; nothing here is a validated improvement."],
            "couplings": [],
            "manifest": HANDOFF,
            "native": True,
            "figures": [entry(f"{D}/fidelity-ladder.png"), entry(f"{D}/ladder-diagnostic.png")],
            "reports": [entry(r) for r in (f"{D}/RESULTS.md", f"{D}/return-audit-report.json", f"{D}/ladder-diagnostic.json", f"{D}/fidelity-figures.provenance.json", f"{RENDER}/provenance.json")],
            "counts": {"native_arms": native_n, "effect_statuses": {"sign_resolved": int(m.group(1)), "resolved": int(m.group(2))}, "contexts": len(ctxs), "undetermined_decisions": len(decisions), "posthoc_rigid_solves": n_rigid},
        }
    ]
