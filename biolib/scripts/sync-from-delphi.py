#!/usr/bin/env python3
"""Build the Biolib tree from the Lean modules in the delphi working tree.

Biolib is organized by biology (Allometry, Biomechanics, Morphogenesis, PopulationGenetics,
Physiology, Ecology), the way Physlib is organized by physics. The modules themselves are
developed in the delphi working tree (fractastical/delphi_private), where each sits beside the
claim source or pipeline that produced it. This script copies them here, rewrites their `import`
lines to the Biolib module names, prepends a provenance docstring, and writes PROVENANCE.json so
every file here can be traced to an origin path, commit and registry law.

    python3 scripts/sync-from-delphi.py [--src ../../delphisci]

Core vs Alpha follows the registry: a module whose laws are `accepted`, or whose theorems are
Lean-checked claims in the claim graph, goes in `Biolib/`; candidate, proposed and contested
material, pipeline certificates and audits go in `BiolibAlpha/`. The split is recorded per module
below and is a decision, not a computation; change it here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# origin path (relative to the delphi working tree) -> Biolib module name
MODULES: dict[str, str] = {
    # --- Biolib (core) ---
    # Allometry: size, shape and the scaling of parts
    "lean/Delphi/Thompson.lean": "Biolib.Allometry.CubeLaw",
    "lean/Delphi/Scaling.lean": "Biolib.Allometry.Scaling",
    "lean/Delphi/Empirical.lean": "Biolib.Allometry.EmpiricalBands",
    "claim-sources/thompson-growth-form/lean/ThompsonLaws/Magnitude.lean": "Biolib.Allometry.Magnitude",
    "claim-sources/thompson-growth-form/lean/ThompsonLaws/LimbBoneSimilarity.lean": "Biolib.Allometry.LimbBoneSimilarity",
    # Biomechanics: structures, materials, flight
    "claim-sources/thompson-growth-form/lean/ThompsonLaws/Mechanics.lean": "Biolib.Biomechanics.Mechanics",
    "claim-sources/thompson-growth-form/lean/ThompsonLaws/HollowTube.lean": "Biolib.Biomechanics.HollowTube",
    "claim-sources/thompson-growth-form/lean/ThompsonLaws/Hygromorphs.lean": "Biolib.Biomechanics.Hygromorphs",
    "lean/Delphi/Flight.lean": "Biolib.Biomechanics.Flight",
    "lean/Delphi/Altitude.lean": "Biolib.Biomechanics.Altitude",
    # Morphogenesis: cells, packing, spirals, shells, horns
    "claim-sources/thompson-growth-form/lean/ThompsonLaws/Cells.lean": "Biolib.Morphogenesis.Cells",
    "claim-sources/thompson-growth-form/lean/ThompsonLaws/Spirals.lean": "Biolib.Morphogenesis.Spirals",
    "claim-sources/thompson-growth-form/lean/ThompsonLaws/HornsLeavesEggs.lean": "Biolib.Morphogenesis.HornsLeavesEggs",
    "claim-sources/thompson-growth-form/lean/ThompsonLaws/TwelvePentagons.lean": "Biolib.Morphogenesis.TwelvePentagons",
    # Population genetics and evolution
    "lean/Delphi/Fisher.lean": "Biolib.PopulationGenetics.Fisher",
    "lean/Delphi/Kimura.lean": "Biolib.PopulationGenetics.Kimura",
    "lean/Delphi/MaynardSmith.lean": "Biolib.PopulationGenetics.MaynardSmith",
    "lean/Delphi/Favored.lean": "Biolib.PopulationGenetics.FavoredFixation",
    "lean/Delphi/Genotype.lean": "Biolib.PopulationGenetics.Genotype",
    # Physiology
    "lean/Delphi/Physiology.lean": "Biolib.Physiology.Basic",
    "lean/Delphi/Perturb.lean": "Biolib.Physiology.Perturbations",
    "claim-sources/thompson-growth-form/lean/ThompsonLaws/MurrayCubic.lean": "Biolib.Physiology.MurrayCubic",
    # Ecology and evolution at the population level (Darwin)
    "claim-sources/darwin-origin/lean/DarwinLaws/Struggle.lean": "Biolib.Ecology.Struggle",
    "claim-sources/darwin-origin/lean/DarwinLaws/Succession.lean": "Biolib.Ecology.Succession",
    "claim-sources/darwin-origin/lean/DarwinLaws/Islands.lean": "Biolib.Ecology.Islands",
    "claim-sources/darwin-origin/lean/DarwinLaws/Tree.lean": "Biolib.Ecology.Tree",
    # Meta: anatomy graphs and the constraint forms the laws take
    "lean/Delphi/Blueprint.lean": "Biolib.Meta.Blueprint",
    "lean/Delphi/Constraints.lean": "Biolib.Meta.Constraints",
    # --- BiolibAlpha (lighter review: candidate, contested, pipeline) ---
    "lean/Delphi/CellGeometry.lean": "BiolibAlpha.Morphogenesis.CellGeometry",
    "lean/Delphi/Turing.lean": "BiolibAlpha.Morphogenesis.Turing",
    "lean/Delphi/Hydrostatics.lean": "BiolibAlpha.Physiology.Hydrostatics",
    "claim-sources/thompson-growth-form/lean/ThompsonLaws/HamiltonScope.lean": "BiolibAlpha.PopulationGenetics.HamiltonScope",
    "lean/registry/proposals/maynardsmith-hitchhiking/law.lean": "BiolibAlpha.PopulationGenetics.Hitchhiking",
    "lean/registry/proposals/disc-flying-fish-fin-ratio-gap/law.lean": "BiolibAlpha.Allometry.FlyingFishFinRatioGap",
    "lean/registry/proposals/disc-heterurus-mass-exponent/law.lean": "BiolibAlpha.Allometry.HeterurusMassExponent",
    "lean/registry/proposals/disc-measured-wing-loading-band/law.lean": "BiolibAlpha.Allometry.MeasuredWingLoadingBand",
    "lean/registry/proposals/disc-pectoral-length-allometry/law.lean": "BiolibAlpha.Allometry.PectoralLengthAllometry",
    "lean/registry/lean/P3bContested.lean": "BiolibAlpha.Physiology.DepthCapContested",
    "lean/registry/lean/Witnesses.lean": "BiolibAlpha.Meta.Witnesses",
    "lean/Delphi/Audit.lean": "BiolibAlpha.Meta.Audit",
    "lean/Delphi/Certificates/AFlyingFish.lean": "BiolibAlpha.Certificates.AFlyingFish",
    "lean/Delphi/Certificates/FinDevelopment.lean": "BiolibAlpha.Certificates.FinDevelopment",
    "lean/Delphi/Certificates/Eliminations.lean": "BiolibAlpha.Certificates.Eliminations",
    "lean/Delphi/Certificates/EliminationsEmpirical.lean": "BiolibAlpha.Certificates.EliminationsEmpirical",
    "lean/Delphi/Certificates/EliminationsGenotype.lean": "BiolibAlpha.Certificates.EliminationsGenotype",
    "lean/Delphi/Certificates/EliminationsOpenProblems.lean": "BiolibAlpha.Certificates.EliminationsOpenProblems",
}

# Origin modules that do not compile on the pinned toolchain, so they are not in Biolib. Found by
# building this package; the reason is checked against the source each sync, not assumed.
EXCLUDED: dict[str, str] = {
    "lean/Delphi/Certificates/EliminationsFlier.lean": "references Delphi.Constraints.vmin_rules_out, which no longer exists; not in the Delphi root import",
    "lean/Delphi/Certificates/EliminationsTff.lean": "references Delphi.Constraints.vmin_rules_out, which no longer exists; not in the Delphi root import",
    "lean/Delphi/Certificates/EliminationsPhysiology.lean": "references Delphi.Constraints.aerobic_flight_rules_out, which no longer exists; not in the Delphi root import",
    "claim-sources/wolfram-nks/lean/WolframLaws/Additive.lean": "does not compile (type mismatches, unsolved goals); its reports/ directory is empty, so no claim is counted as proved by it",
    "claim-sources/wolfram-nks/lean/WolframLaws/Digits.lean": "does not compile; reports/ empty",
    "claim-sources/wolfram-nks/lean/WolframLaws/Logic.lean": "does not compile and depends on sorryAx; reports/ empty",
}

# origin Lean module name -> origin path, for rewriting `import` lines
def origin_module_name(path: str) -> str:
    p = Path(path)
    if path.startswith("lean/Delphi/"):
        return ".".join(["Delphi", *p.relative_to("lean/Delphi").with_suffix("").parts])
    for lib in ("ThompsonLaws", "DarwinLaws", "WolframLaws"):
        if f"/{lib}/" in path:
            return ".".join([lib, *p.parts[p.parts.index(lib) + 1 :]]).removesuffix(".lean")
    return ""  # registry files are not imported by anything


IMPORT_MAP = {origin_module_name(o): m for o, m in MODULES.items() if origin_module_name(o)}
SUBJECT_DOC = {
    "Allometry": "size, shape and the scaling of parts with body size",
    "Biomechanics": "structures, materials and locomotion under physical law",
    "Morphogenesis": "how cells, tissues and shells take their form",
    "PopulationGenetics": "allele frequencies, fixation, selection and inheritance",
    "Physiology": "metabolism, transport and the perturbations an organism survives",
    "Ecology": "populations, competition, succession and biogeography",
    "Meta": "anatomy graphs, constraint forms and informal results awaiting formalization",
    "Certificates": "kernel-checked eliminations of specific designs against the laws",
    "Computation": "discrete systems from A New Kind of Science, formalized while the claims were assessed",
}


def sh(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def law_index(src: Path) -> dict[str, list[dict]]:
    """origin module path -> [{law_id, status, version, theorem}]"""
    out: dict[str, list[dict]] = {}
    for f in sorted((src / "lean/registry/laws").glob("*.json")):
        d = json.loads(f.read_text())
        ref = d.get("lean_ref") or {}
        if ref.get("module"):
            out.setdefault(ref["module"], []).append(
                {"law_id": d["law_id"], "status": d["status"], "version": d.get("version"), "theorem": ref.get("theorem")}
            )
    return out


def lean_checked_claims(src: Path) -> dict[str, list[str]]:
    """origin module path -> claim ids whose Lean report marks them formalized there."""
    out: dict[str, list[str]] = {}
    for rep in src.glob("claim-sources/*/lean/reports/*.json"):
        try:
            d = json.loads(rep.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(d, list):
            continue
        proj = str(rep.parents[2].relative_to(src))  # claim-sources/<project>
        cand = [p for p in MODULES if p.startswith(proj) and Path(p).stem == rep.stem]
        for e in d:
            if not isinstance(e, dict) or e.get("status") != "formalized" or not e.get("claim_id"):
                continue
            for p in cand:
                out.setdefault(p, [])
                if e["claim_id"] not in out[p]:
                    out[p].append(e["claim_id"])
    return out


def rewrite(text: str, module: str, origin: str, commit: str, laws: list[dict], claims: list[str]) -> str:
    lines = text.split("\n")
    # Lean allows a module comment before the imports; rewrite every import line in the header
    # and put the provenance block right after the last one.
    i = 0
    for k, line in enumerate(lines):
        if line.startswith("import "):
            name = line[len("import "):].strip()
            if name in IMPORT_MAP:
                lines[k] = f"import {IMPORT_MAP[name]}"
            elif name.startswith(("Delphi.", "ThompsonLaws.", "DarwinLaws.", "WolframLaws.")):
                raise SystemExit(f"{origin}: import {name} has no Biolib target")
            i = k + 1
    if i == 0:
        raise SystemExit(f"{origin}: no import line")
    laws_s = ", ".join(f"`{l['law_id']}` ({l['status']}{', v' + l['version'] if l.get('version') else ''})" for l in laws) or "none"
    claims_s = ", ".join(f"`{c}`" for c in claims) or "none"
    subject = module.split(".")[1]
    prov = [
        "/-!",
        f"## Biolib · {subject}: {SUBJECT_DOC.get(subject, '')}",
        "",
        f"Origin: `{origin}` in fractastical/delphi_private at `{commit[:12]}`, copied by",
        "`biolib/scripts/sync-from-delphi.py`. Edit it there; this copy is regenerated.",
        f"Registry laws: {laws_s}.",
        f"Lean-checked claims: {claims_s}.",
        "-/",
        "",
    ]
    return "\n".join(lines[:i] + prov + lines[i:])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT.parent.parent / "delphisci"))
    args = ap.parse_args()
    src = Path(args.src).resolve()
    if not (src / "lean/Delphi.lean").exists():
        sys.exit(f"not a delphi working tree: {src}")
    commit = sh(["git", "rev-parse", "HEAD"], src)
    dirty = bool(sh(["git", "status", "--porcelain", "--", "lean", "claim-sources/*/lean"], src))
    laws = law_index(src)
    claims = lean_checked_claims(src)

    for old in list((ROOT / "Biolib").rglob("*.lean")) + list((ROOT / "BiolibAlpha").rglob("*.lean")):
        if old.name != "Informal.lean":
            old.unlink()

    prov = {"source_repo": "https://github.com/fractastical/delphi_private", "source_commit": commit,
            "source_dirty": dirty, "toolchain": (src / "lean/lean-toolchain").read_text().strip(), "modules": [],
            "excluded": [{"origin": k, "reason": v, "exists": (src / k).exists()} for k, v in EXCLUDED.items()]}
    roots: dict[str, list[str]] = {"Biolib": [], "BiolibAlpha": []}
    for origin, module in MODULES.items():
        text = (src / origin).read_text()
        dest = ROOT / Path(*module.split(".")).with_suffix(".lean")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rewrite(text, module, origin, commit, laws.get(origin, []), claims.get(origin, [])))
        roots[module.split(".")[0]].append(module)
        prov["modules"].append({
            "module": module, "origin": origin, "origin_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "laws": laws.get(origin, []), "lean_checked_claims": claims.get(origin, []),
            "lines": text.count("\n"),
            "theorems": len(re.findall(r"^(?:theorem|lemma)\s", text, re.M)),
            "defs": len(re.findall(r"^(?:noncomputable )?(?:def|structure|inductive|abbrev)\s", text, re.M)),
        })
    roots["Biolib"].append("Biolib.Meta.Informal")
    for lib, mods in roots.items():
        (ROOT / f"{lib}.lean").write_text("\n".join(f"import {m}" for m in sorted(mods)) + "\n")
    (ROOT / "PROVENANCE.json").write_text(json.dumps(prov, indent=1) + "\n")

    # laws with no module at all: the informal-results list, and the proposed laws without Lean
    unformalized = []
    for f in sorted((src / "lean/registry/laws").glob("*.json")):
        d = json.loads(f.read_text())
        if not (d.get("lean_ref") or {}).get("module"):
            unformalized.append({"law_id": d["law_id"], "status": d["status"], "label": d.get("label"),
                                 "statement_en": d.get("statement_en"), "level": d.get("level")})
    cj = json.loads((src / "docs/claims.json").read_text())
    cl = cj["claims"] if isinstance(cj, dict) else cj
    with_lean = {c for v in claims.values() for c in v} | {l["law_id"] for v in laws.values() for l in v}
    lit = [{"id": c["id"], "label": c.get("label"), "statement": c.get("statement"), "notation": c.get("notation"),
            "thinker": c.get("thinker"), "year": c.get("year"), "work": c.get("work"),
            "formalization": (c.get("formalization") or {}).get("tags")}
           for c in cl if c.get("theorem") and c.get("proof") == "literature" and c["id"] not in with_lean]
    write_informal(unformalized, lit)
    write_status(prov, roots, unformalized, lit)
    n_core = len(roots["Biolib"]) - 1
    print(f"Biolib: {n_core} modules, BiolibAlpha: {len(roots['BiolibAlpha'])} modules, "
          f"{sum(m['theorems'] for m in prov['modules'])} theorems/lemmas, "
          f"{len(lit) + len(unformalized)} informal results; source {commit[:12]}{' (dirty)' if dirty else ''}")


def write_status(prov: dict, roots: dict[str, list[str]], unformalized: list[dict], lit: list[dict]) -> None:
    """STATUS.md: every number about Biolib, computed here so the README never carries one by hand."""
    import collections
    mods = prov["modules"]
    core = [m for m in mods if m["module"].startswith("Biolib.")]
    alpha = [m for m in mods if m["module"].startswith("BiolibAlpha.")]
    laws = [l for m in mods for l in m["laws"]]
    st = collections.Counter(l["status"] for l in laws)
    claims = sorted({c for m in mods for c in m["lean_checked_claims"]})
    subj = collections.Counter(m["module"].split(".")[1] for m in core)
    rows = ["| module | origin | theorems | laws | Lean-checked claims |", "|---|---|---:|---|---:|"]
    for m in sorted(mods, key=lambda m: m["module"]):
        rows.append(f"| `{m['module']}` | `{m['origin']}` | {m['theorems']} | "
                    f"{', '.join(l['law_id'] for l in m['laws']) or ''} | {len(m['lean_checked_claims'])} |")
    excl = "\n".join(f"- `{e['origin']}`: {e['reason']}" for e in prov["excluded"])
    text = f"""# Biolib status

Generated by `scripts/sync-from-delphi.py` from fractastical/delphi_private at `{prov['source_commit'][:12]}`
{'(working tree dirty)' if prov['source_dirty'] else ''}; toolchain `{prov['toolchain']}`.

| | Biolib | BiolibAlpha |
|---|---:|---:|
| modules | {len(core) + 1} (incl. `Meta.Informal`) | {len(alpha)} |
| theorem/lemma declarations | {sum(m['theorems'] for m in core)} | {sum(m['theorems'] for m in alpha)} |
| definitions | {sum(m['defs'] for m in core)} | {sum(m['defs'] for m in alpha)} |

Lines of Lean: {sum(m['lines'] for m in mods)}. Subjects in Biolib: {', '.join(f'{k} ({v})' for k, v in sorted(subj.items()))}.

Registry laws carried: {len(laws)} ({', '.join(f'{v} {k}' for k, v in sorted(st.items()))}); laws without a Lean module,
listed as informal results: {len(unformalized)}. Claims the claim graph records as proved in the literature but not
in Lean here, listed as informal results: {len(lit)}. Claims with a Lean proof in a carried module: {len(claims)}.

Axioms: run `lake env lean scripts/axioms.lean` after `lake build`; it fails if any theorem depends on more than
`propext`, `Classical.choice` and `Quot.sound`.

## Not carried

Origin modules that do not compile on the pinned toolchain, so they are not in Biolib:

{excl}

## Modules

{chr(10).join(rows)}
"""
    (ROOT / "STATUS.md").write_text(text)


def lean_str(s: str | None) -> str:
    return json.dumps(s or "")


def ident(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def write_informal(laws: list[dict], claims: list[dict]) -> None:
    out = [
        "import Mathlib",
        "",
        "/-!",
        "## Biolib · Meta: informal results",
        "",
        "An informal result is a statement that belongs in Biolib and has not been formalized yet: an",
        "English statement, a name, its source, and the reading it should be formalized under. It is a",
        "placeholder someone who knows Lean can turn into a theorem without knowing the biology first, the",
        "way Physlib's `informal_lemma` works. This file is generated by `scripts/sync-from-delphi.py` from",
        "the registry laws that have no Lean module and the claims the claim graph records as proved in the",
        "literature without a Lean proof here. `proof: literature` is a recorded status, not a Biolib theorem.",
        "-/",
        "",
        "namespace Biolib.Informal",
        "",
        "/-- An informal result: formalize it, then replace the entry with an `import` of the module. -/",
        "structure Informal where",
        "  /-- stable id: a registry law id or a claim id -/",
        "  id : String",
        "  label : String",
        "  statement : String",
        "  /-- where the result comes from -/",
        "  source : String",
        "  /-- `law-proposed`, `literature-proved` -/",
        "  status : String",
        "  /-- formalization tags from the claim graph: one | several | identity | contingent -/",
        "  tags : List String := []",
        "  deriving Repr",
        "",
    ]
    names = []
    for l in laws:
        n = ident(l["law_id"])
        names.append(n)
        out += [f"def {n} : Informal where",
                f"  id := {lean_str(l['law_id'])}",
                f"  label := {lean_str(l['label'])}",
                f"  statement := {lean_str(l['statement_en'])}",
                f"  source := {lean_str('lean/registry/laws/' + l['law_id'] + '.json (' + str(l.get('level')) + ')')}",
                f"  status := {lean_str('law-' + l['status'])}", ""]
    for c in claims:
        n = ident(c["id"])
        names.append(n)
        stmt = c["statement"] or ""
        if c.get("notation"):
            stmt += "  [" + c["notation"] + "]"
        source = f"{c.get('thinker')} ({c.get('year')}), {c.get('work')}"
        out += [f"def {n} : Informal where",
                f"  id := {lean_str(c['id'])}",
                f"  label := {lean_str(c['label'])}",
                f"  statement := {lean_str(stmt)}",
                f"  source := {lean_str(source)}",
                f"  status := \"literature-proved\"",
                f"  tags := [{', '.join(lean_str(t) for t in (c.get('tags') or c.get('formalization') or []))}]", ""]
    out += ["/-- Every informal result, for `#eval (all.map (·.id))`. -/",
            "def all : List Informal := [", *[f"  {n}," for n in names[:-1]], f"  {names[-1]}", "]", "",
            "theorem all_length : all.length = " + str(len(names)) + " := by rfl", "",
            "end Biolib.Informal", ""]
    dest = ROOT / "Biolib/Meta/Informal.lean"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out))


if __name__ == "__main__":
    main()
