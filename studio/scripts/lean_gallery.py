"""Lean evidence gallery: the real Lean source, the exact receipts of the runs that compiled it, and the mutants Lean rejected.

build(ins, out) returns the snapshot object and writes the published files into `out` under the site's "@artifacts/lean-gallery/..." convention.
Nothing here runs Lean. Each family is a RECORDED run: its receipt pins every input by sha256, and the helper recomputes the assembled sources that
were compiled and compares them with the receipt. A family whose files have changed since its receipt is reported as stale or refused, never as
compiled, and its source is not published. What Lean checked is only the stated mathematics; it says nothing about organism viability,
a genotype-to-fin causal link or any empirical fact."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = "@artifacts/lean-gallery"
PUBLIC = "artifacts/lean-gallery"
STANDARD_AXIOMS = {"Classical.choice", "Quot.sound", "propext"}

SCOPE = [
    "Lean checks the mathematics of the statements shown, for all values that satisfy their hypotheses. It does not check that a statement models a fish.",
    "Nothing here shows an organism is viable, that a genotype causes a fin shape, or anything empirical.",
    "Each result is a recorded run: this site did not run Lean. A receipt counts only while the files it pinned are unchanged.",
    "The proposal checker writes Lean text but does not compile it. These theorems are hand-authored, not extracted from a language-model answer.",
    "The oxygen family is a conditional steady-transport model rule. It does not establish oxygen adequacy, cell viability, repair, actuation or organism function in either linked project.",
]

# What each family is, in plain words, and the equations its theorems state (the Lean statements are shown verbatim beside them).
FAMILIES = [
    {"id": "geometric-similarity", "title": "Geometric similarity: wing loading and speed scaling",
     "dir": "engineering/formal", "receipt": "RECEIPT.json", "theory": "GeometricSimilarity.lean", "positive_extra": "MutantRefutations.lean", "negative": "NegativeControls.lean",
     "summary": "Under similarity with length ratio k (area k squared, mass k cubed, same air density, lift coefficient and gravity), wing loading scales as k and the level-flight proxy speed as the square root of k. A solver-emitted conflict certificate is also checked.",
     "equations": [
         {"label": "Wing loading", "tex": "WL=\\frac{m\\,g}{S}"},
         {"label": "Level-flight proxy speed", "tex": "V=\\sqrt{\\frac{2\\,m\\,g}{\\rho\\,S\\,C}}"},
         {"label": "Wing loading under similarity (area k^2, mass k^3)", "tex": "WL(k^{3}m,\\,k^{2}S)=k\\,WL(m,S)"},
         {"label": "Speed under similarity", "tex": "V(k^{3}m,\\,k^{2}S)=\\sqrt{k}\\,V(m,S)"},
         {"label": "Wing-loading ceiling at speed V", "tex": "2\\,m\\,g\\le V^{2}\\rho S C\\ \\Rightarrow\\ 2\\,WL\\le \\rho V^{2}C"}],
     "assumptions": ["Every symbol is a positive real number.", "Air density, lift coefficient and gravity are unchanged between the two sizes.", "Mass ratio k^3 and area ratio k^2 are assumptions of the model (hypotheses of the theorem), not derived.",
                     "The lift condition is a level-flight proxy (L = W), not a glide analysis."]},
    {"id": "unit-algebra", "title": "Unit algebra: conversion, interval mapping and dimensions",
     "dir": "engineering/formal", "receipt": "UNIT_ALGEBRA_RECEIPT.json", "theory": "UnitAlgebra.lean", "positive_extra": "UnitAlgebraControls.lean", "negative": "UnitAlgebraNegative.lean",
     "summary": "The arithmetic the coupling checker relies on when it validates a unit conversion: converting twice equals converting by the product, a positive factor keeps order and sign, a nonzero factor is undone by its inverse, and dimension exponents add.",
     "equations": [
         {"label": "Conversion composes", "tex": "(x f)\\,g=x\\,(f g)"},
         {"label": "Interval mapped by a positive factor", "tex": "lo\\le x\\le hi,\\ f>0\\ \\Rightarrow\\ lo\\,f\\le x f\\le hi\\,f"},
         {"label": "Dimension exponents add", "tex": "\\dim(dst)=\\dim(src)+\\dim(f)"}],
     "assumptions": ["Values are exact rationals (conversion) and integer exponents (dimensions).", "A positive factor is required for the interval rule; the control shows it is necessary.", "Units themselves (what a kilogram is) are conventions checked in Python, not here."]},
    {"id": "cantilever-guard", "title": "Cantilever guard: a small-deflection bound with satisfiable hypotheses",
     "dir": "engineering/formalize/lean", "receipt": "RECEIPT.json", "theory": "CantileverGuard.lean", "negative_file": "CantileverGuard_negative_corrupt_law.lean",
     "summary": "For every positive P, L, E and I, if the end-load law 3EId = PL^3 holds and the bending stiffness satisfies 10 P L^2 <= 3 E I, then the deflection satisfies d <= L/10. The hypotheses are shown to be satisfiable, and the stiffness hypothesis is shown to be necessary.",
     "equations": [
         {"label": "End-load law (stated)", "tex": "3\\,E\\,I\\,d=P\\,L^{3}"},
         {"label": "Stiffness hypothesis", "tex": "10\\,P\\,L^{2}\\le 3\\,E\\,I"},
         {"label": "Guard conclusion", "tex": "d\\le \\frac{L}{10}"}],
     "assumptions": ["P, L, E and I are positive reals.", "The Euler-Bernoulli end-load law is a stated hypothesis, not shown to model a fin ray.", "No real stiffness is shown to satisfy the stiffness hypothesis."]},
    {"id": "steady-oxygen-bound", "title": "Oxygen transport: center-content bounds for sphere and slab",
     "dir": "engineering/formalize/lean", "receipt": "lean-receipt.json",
     "receipt_path": "artifacts/oxygen-diffusion-rule/lean-receipt.json",
     "receipt_sha256": "2275021b43ba35a0fa5bba874e0cc5b355365b58347ef40b221991e292215f71",
     "theory": "OxygenDiffusionBound.lean", "negative_file": "OxygenDiffusionBound_negative_corrupt_law.lean",
     "source_paths": {
         "OxygenDiffusionBound.lean": "engineering/formalize/lean/OxygenDiffusionBound.lean",
         "OxygenDiffusionBound_negative_corrupt_law.lean": "engineering/formalize/lean/OxygenDiffusionBound_negative_corrupt_law.lean",
     },
     "display_artifacts": [
         {"name": "rule-contract.json", "path": "artifacts/oxygen-diffusion-rule/rule-contract.json", "sha256": "ca5fb2992e9e8a54ef17a9637cc4dcce9c77b2c8b100e4f9fd6f0e627066e3a3", "role": "rule contract"},
         {"name": "geometry-control.png", "path": "artifacts/oxygen-diffusion-rule/geometry-control.png", "sha256": "09c8e5d266b537dc07fc4916b2c4f25102a60659dc934ba5ee762f1c75997fea", "role": "geometry and model-response figure"},
         {"name": "live-project-reuse.json", "path": "artifacts/oxygen-diffusion-rule/live-project-reuse.json", "sha256": "8f59a1fc2dafd7aff891fd747f54beff589e8e9293b2241f0a99a716aa15143c", "role": "separate live-project context attachment"},
     ],
     "context_project_source": {"path": "projects/reuse-studies/live-projects.json", "sha256": "bb2e730a6703afe842c0d663a6a81c1b1aa804523b9c4653220062231b857d28"},
     "context_expected_ids": ["project-epithelial-repair", "project-tissue-microcarrier"],
     "positive_check_names": [
         "sphere_center_oxygen_bound", "slab_center_oxygen_bound",
         "sphere_zero_radius_boundary", "slab_zero_thickness_boundary",
         "sphere_at_diffusion_limit", "slab_at_diffusion_limit",
     ],
     "summary": "Lean checks the equivalence between nonnegative center oxygen and each ideal geometry's size bound. The sphere coefficient 6 follows Grimes et al. Eq. 2.6 after converting boundary partial pressure to the paper's oxygen-content variable; the one-sided slab coefficient 2 is a separately derived analogue. Both project contexts are model-reuse links with unknown parameters, not viability predictions.",
     "equations": [
         {"label": "Spherical center-content bound", "tex": "C_{center}=C_0-\\frac{aR^2}{6D},\\quad aR^2\\le 6DC_0"},
         {"label": "One-sided slab center-content bound", "tex": "C_{center}=C_0-\\frac{aL^2}{2D},\\quad aL^2\\le 2DC_0"},
     ],
     "assumptions": [
         "Steady diffusion with constant, isotropic D > 0 and spatially constant consumption a > 0.",
         "Boundary oxygen content C0 ≥ 0; sphere has supplied outer boundary C(R)=C0 and center symmetry.",
         "Slab L is distance from a no-flux mid-plane to one supplied face C(L)=C0; total symmetric slab thickness is 2L.",
         "C0 is oxygen-gas volume per tissue mass and a is that volume consumed per tissue mass per second in the source equation context; per-volume inputs require a consistent conversion not performed here.",
     ],
     "proves": "For the stated algebraic profiles and positive diffusion coefficient, center oxygen is nonnegative exactly when aR² ≤ 6DC0 (sphere) or aL² ≤ 2DC0 (one-sided slab). The six recorded Lean statements include these two parametric equivalences, zero-size boundary values and equality at the diffusion limits.",
     "does_not_prove": [
         "A negative continuation beyond the limit is an out-of-domain model diagnostic, not physical negative oxygen.",
         "No cell-specific D, consumption a, boundary C0, oxygen measurement, viability threshold or tissue calibration is supplied for either project.",
         "The spherical limit is from a colorectal tumor-spheroid source context; its fitted values are not transferred to either project.",
         "The slab is a derived 1-D analogue, not a Grimes equation; neither geometry proves repair, barrier recovery, actuation, motion or organism function.",
     ],
     "statement_origin": "Hand-authored Lean algebra after the source-to-equation interpretation; the solver does not verify that translation or any empirical premise."},
]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _cert_corrupt(good: str) -> str:
    """The same corruption the checking harness applies to the solver certificate (engineering/formal/lean_checks.py)."""
    return good.replace("(10 : ℝ)", "(20 : ℝ)").replace("conflict_instance", "neg_corrupted")


def theorems(text: str) -> list[dict]:
    """Theorems and definitions with their docstring and statement, taken verbatim from the source (to ':=')."""
    lines = text.splitlines(); found = []; i = 0; doc = None
    while i < len(lines):
        ln = lines[i]
        if ln.lstrip().startswith("/--"):
            j = i; buf = [ln]
            while "-/" not in lines[j]:
                j += 1; buf.append(lines[j])
            doc = re.sub(r"\s+", " ", " ".join(buf).replace("/--", "").replace("-/", "")).strip(); i = j + 1; continue
        m = re.match(r"\s*(?:@\[[^\]]*\]\s*)?(?:noncomputable\s+)?(theorem|def|structure)\s+([A-Za-z_][\w.']*)", ln)
        if m:
            sig = [ln]; j = i
            while ":=" not in lines[j] and j + 1 < len(lines) and not lines[j + 1].strip() == "":
                j += 1; sig.append(lines[j])
            stmt = "\n".join(sig); stmt = stmt.split(":=")[0].rstrip() if ":=" in stmt else stmt
            found.append({"kind": m.group(1), "name": m.group(2), "line": i + 1, "doc": doc, "statement": stmt})
            doc = None; i = j + 1; continue
        if ln.strip() and not ln.lstrip().startswith("--"):
            doc = None
        i += 1
    return found


def neg_blocks(text: str) -> list[dict]:
    blocks, cur = [], None
    for n, ln in enumerate(text.splitlines(), 1):
        m = re.match(r"-- NEG:(\w+) (BEGIN|END)", ln)
        if m and m.group(2) == "BEGIN":
            cur = {"id": m.group(1), "line": n, "code": []}
        elif m and cur:
            blocks.append({**cur, "code": "\n".join(cur["code"])}); cur = None
        elif cur is not None:
            cur["code"].append(ln)
    return blocks


def _read(root: Path, rel: str, ins) -> bytes | None:
    f = root / rel
    return ins.read(rel) if f.is_file() else None


def _family(spec: dict, ins, out: dict, root: Path) -> dict:
    d = spec["dir"]; rel = lambda n: f"{d}/{n}"
    def source_path(name):
        if name in spec.get("source_paths", {}):
            return spec["source_paths"][name]
        return f"{Path(d).parent.as_posix()}/{name[3:]}" if name.startswith("..") else rel(name)
    receipt_path = spec.get("receipt_path", rel(spec["receipt"]))
    fam = {k: spec[k] for k in ("id", "title", "summary", "equations", "assumptions")}
    for optional in ("proves", "does_not_prove", "statement_origin"):
        if optional in spec:
            fam[optional] = spec[optional]
    reasons: list[str] = []; files: dict[str, bytes] = {}
    receipt_b = _read(root, receipt_path, ins)
    if receipt_b is None:
        return {**fam, "status": "missing", "reasons": [f"{receipt_path} is not in the tree"], "files": [], "theorems": [], "negative_blocks": []}
    R = json.loads(receipt_b); fam["receipt"] = {"path": receipt_path, "sha256": _sha(receipt_b), "bytes": len(receipt_b)}
    if spec.get("receipt_sha256") and _sha(receipt_b) != spec["receipt_sha256"]:
        reasons.append("the pinned Lean receipt changed")
    # which hashes the receipt pinned, and what the run claimed
    if spec["id"] == "geometric-similarity":
        L = R["lean_checks"]; prov = L["provenance"]; pins = dict(prov["files"]); pos, neg = L["positive"], L["negative"]; flags = {"positive": pos.get("exit") == 0 and pos.get("only_standard_axioms"), "negative": L["negative"].get("exit") == 1 and all(L["negative"]["each_block_rejected"].values()) and not L["negative"]["errors_outside_blocks"]}
        assembled = prov["assembled_sources_sha256"]; versions = {"lean_version": L["lean_version"], "mathlib_rev": prov.get("mathlib_rev"), "toolchain": prov.get("lean_toolchain_file")}
        run = {"positive": {"exit": pos["exit"], "seconds": pos.get("seconds"), "axioms": pos.get("axioms_used"), "only_standard_axioms": pos.get("only_standard_axioms"), "axiom_prints": pos.get("n_axiom_prints")},
               "negative": {"exit": neg["exit"], "seconds": neg.get("seconds"), "each_block_rejected": neg["each_block_rejected"], "first_error": neg.get("first_error_message", {}), "errors_outside_blocks": neg["errors_outside_blocks"]}}
        cert = R["lean_certificate_text"]; solver = R["solver_result"]
        fam["certificate"] = {"lean": cert, "corrupted_lean": _cert_corrupt(cert), "solver": {k: solver.get(k) for k in ("status", "conflict", "core_minimal", "reason", "scope", "used_constraints")}, "compiled": "inside the positive run (assembled after the theory and the mutant refutations)"}
        fam["receipt"]["all_ok"] = L["all_ok"]
    elif spec["id"] == "unit-algebra":
        prov = R["provenance"]; pins = dict(prov["unit_algebra_files"]); flags = {"positive": R["positive"].get("exit") == 0 and R["positive"].get("only_standard_axioms"), "negative": R["negative"].get("exit") == 1 and all(R["negative"]["each_block_rejected"].values()) and not R["negative"]["errors_outside_blocks"]}
        assembled = prov["assembled_sources_sha256"]; versions = {"lean_version": R["lean_version"], "mathlib_rev": prov.get("mathlib_rev"), "toolchain": prov.get("lean_toolchain_file")}
        run = {"positive": {"exit": R["positive"]["exit"], "axioms": R["positive"].get("axioms_used"), "only_standard_axioms": R["positive"].get("only_standard_axioms"), "axiom_prints": R["positive"].get("axiom_prints")},
               "negative": {"exit": R["negative"]["exit"], "each_block_rejected": R["negative"]["each_block_rejected"], "first_error": {}, "errors_outside_blocks": R["negative"]["errors_outside_blocks"]}}
        fam["receipt"]["all_ok"] = R["all_ok"]
    elif spec["id"] == "steady-oxygen-bound":
        assembled = {}
        pins = {
            spec["theory"]: R["source"]["sha256"],
            spec["negative_file"]: R["mutant_source"]["sha256"],
        }
        pos = R["positive"]
        axiom_matches = re.findall(r"'OxygenDiffusion\.([A-Za-z0-9_]+)' depends on axioms: \[([^\]]*)\]", pos["stdout"])
        axiom_map = {name: sorted(x.strip() for x in axioms.split(",") if x.strip()) for name, axioms in axiom_matches}
        reported_names = [name for name, _ in axiom_matches]
        expected_names = spec["positive_check_names"]
        mutant_raw = _read(root, source_path(spec["negative_file"]), ins)
        mutant_lines = mutant_raw.decode("utf-8").splitlines() if mutant_raw else []
        expected_lines = [
            number for number, line in enumerate(mutant_lines, start=1)
            if line.strip() in {
                "nlinarith [hD, ha, hC0, hR, hmul]",
                "nlinarith [hD, ha, hC0, hL, hmul]",
                "example : 0 ≤ mutatedSphereCenterOxygen 1 1 (6 / 5) (5 / 2) := by",
                "example : 0 ≤ mutatedSlabCenterOxygen 1 1 3 2 := by",
            }
        ]
        negative = R["corrupted_coefficients"]
        error_lines = [int(line) for line in re.findall(
            re.escape(Path(spec["negative_file"]).name) + r":(\d+):\d+: error:", negative["stdout"])]
        expected_axioms = set(STANDARD_AXIOMS)
        flags = {
            "positive": pos["exit"] == 0 and not pos["sorryAx"] and pos["only_standard_axioms"]
                         and reported_names == expected_names and len(axiom_map) == 6
                         and all(set(row) == expected_axioms for row in axiom_map.values()),
            "negative": negative["exit"] == 1 and negative["expected_failures"] == 4
                         and negative["actual_failure_diagnostics"] == 4 and negative["correct_law_twins_compiled"]
                         and negative["assertion_scope"] == ["sphere coefficient 6→5", "slab coefficient 2→1"]
                         and error_lines == expected_lines == negative["diagnostic_lines"]
                         and negative["stdout"].count("linarith failed to find a contradiction") == 2
                         and negative["stdout"].count("error: unsolved goals") == 2
                         and negative["stdout"].count("⊢ False") == 4 and not negative["stderr"],
        }
        if not flags["positive"]:
            reasons.append("the oxygen receipt lacks six compiled statements with only the recorded standard axioms")
        if not flags["negative"]:
            reasons.append("the oxygen mutant receipt does not match its four expected compiler failures")
        if R["status"] != "pass":
            reasons.append("the oxygen receipt does not record a passing validation run")
        if R["source"].get("path") != source_path(spec["theory"]):
            reasons.append("the oxygen receipt points to a different positive source")
        if R["mutant_source"].get("path") != source_path(spec["negative_file"]):
            reasons.append("the oxygen receipt points to a different negative-control source")
        versions = {"lean_version": R["lean_version"], "mathlib_rev": R["mathlib"]["revision"],
                    "toolchain": R["mathlib"]["input_revision"]}
        run = {
            "positive": {"exit": pos["exit"], "seconds": pos["seconds"],
                         "axioms": sorted({a for row in axiom_map.values() for a in row}),
                         "axioms_per_theorem": axiom_map, "only_standard_axioms": flags["positive"],
                         "theorem_count": len(axiom_map), "theorem_names": reported_names},
            "negative": {"exit": negative["exit"], "seconds": None, "rejected": flags["negative"],
                         "failure_count": negative["actual_failure_diagnostics"], "diagnostic_lines": error_lines,
                         "each_block_rejected": {"sphere_parametric": flags["negative"], "slab_parametric": flags["negative"],
                                                  "sphere_witness": flags["negative"], "slab_witness": flags["negative"]},
                         "first_error": "Two parametric mutant steps and two exact counterexample witnesses were rejected; see the pinned receipt."},
        }
        fam["check_results"] = [{"name": name, "status": "recorded compile passed", "axioms": axiom_map[name]}
                                for name in expected_names if name in axiom_map]
        fam["receipt"]["all_ok"] = all(flags.values()) and not reasons
    else:
        pins = dict(R["files_sha256"]); prov = R["provenance"]; assembled = {}; versions = {"lean_version": R["lean_version"], "mathlib_rev": prov.get("mathlib_rev"), "toolchain": prov.get("lean_toolchain_file")}
        flags = {"positive": R["positive"].get("exit") == 0 and R["positive"].get("only_standard_axioms"), "negative": R["negative_corrupt_law"].get("rejected") is True}
        run = {"positive": {"exit": R["positive"]["exit"], "seconds": R["positive"].get("seconds"), "axioms": sorted({a for v in R["positive"]["axioms_per_theorem"].values() for a in v}), "only_standard_axioms": R["positive"].get("only_standard_axioms"), "theorems": R["positive"]["theorems"], "axioms_per_theorem": R["positive"]["axioms_per_theorem"], "note": R["positive"].get("warnings_note")},
               "negative": {"exit": R["negative_corrupt_law"]["exit"], "rejected": R["negative_corrupt_law"]["rejected"], "first_error": R["negative_corrupt_law"].get("first_error"), "seconds": R["negative_corrupt_law"].get("seconds")}}
        fam["does_not_prove"] = R["does_not_prove"]; fam["proves"] = R["proves"]; fam["statement_origin"] = R["statement_origin"]
        fam["receipt"]["all_ok"] = flags["positive"] and flags["negative"]
    fam["versions"] = versions; fam["run"] = run
    # 1. every pinned file must still have the pinned bytes
    for name, sha in pins.items():
        b = _read(root, source_path(name), ins)
        if b is None:
            reasons.append(f"pinned file {name} is missing")
        elif _sha(b) != sha:
            reasons.append(f"{name} changed since the receipt: pinned {sha[:12]}, found {_sha(b)[:12]}")
        elif name.endswith(".lean"):
            files[name] = b
    # 2. the sources that were compiled must be reproducible from the current files
    theory = files.get(spec["theory"]); assembled_ok = None
    if spec["id"] == "geometric-similarity" and theory is not None and all(k in files for k in ("MutantRefutations.lean", "NegativeControls.lean")):
        cert = R["lean_certificate_text"]; t = theory.decode()
        pos = t + files["MutantRefutations.lean"].decode() + "\nopen FlyingFish\n" + cert + "\n#print axioms conflict_instance\n"
        neg = t + files["NegativeControls.lean"].decode().replace("@@CORRUPTED_CERTIFICATE@@", _cert_corrupt(cert))
        got = {"positive": _sha(pos.encode()), "negative": _sha(neg.encode()), "certificate_text": _sha(cert.encode()), "corrupted_certificate_text": _sha(_cert_corrupt(cert).encode())}
        assembled_ok = all(assembled.get(k) == v for k, v in got.items())
        if not assembled_ok:
            reasons += [f"the compiled {k} source is not what the current files assemble to" for k, v in got.items() if assembled.get(k) != v]
    elif spec["id"] == "unit-algebra" and theory is not None and all(k in files for k in ("UnitAlgebraControls.lean", "UnitAlgebraNegative.lean")):
        got = {"positive": _sha((theory.decode() + files["UnitAlgebraControls.lean"].decode()).encode()), "negative": _sha((theory.decode() + files["UnitAlgebraNegative.lean"].decode()).encode())}
        assembled_ok = all(assembled.get(k) == v for k, v in got.items())
        if not assembled_ok:
            reasons += [f"the compiled {k} source is not what the current files assemble to" for k, v in got.items() if assembled.get(k) != v]
    elif spec["id"] == "steady-oxygen-bound" and theory is not None and spec["negative_file"] in files:
        assembled_ok = (_sha(theory) == R["source"]["sha256"]
                        and _sha(files[spec["negative_file"]]) == R["mutant_source"]["sha256"])
        if not assembled_ok:
            reasons.append("the positive or mutant source differs from the bytes in the recorded Lean receipt")
    fam["assembled_sources_match"] = assembled_ok
    # A summary boolean cannot substitute for the actual nonempty control/axiom record.
    axioms = set(run["positive"].get("axioms") or [])
    flags["positive"] = flags["positive"] and bool(axioms) and axioms <= STANDARD_AXIOMS
    if spec.get("negative") and spec["negative"] in files:
        expected = {b["id"] for b in neg_blocks(files[spec["negative"]].decode())}
        reported = run["negative"]["each_block_rejected"]
        flags["negative"] = (flags["negative"] and bool(expected) and set(reported) == expected
                             and all(value is True for value in reported.values()))
    elif spec.get("negative_file"):
        flags["negative"] = (flags["negative"] and run["negative"]["exit"] == 1
                             and bool(run["negative"].get("first_error")))
    fam["receipt"]["all_ok"] = bool(fam["receipt"]["all_ok"] and all(flags.values()))
    # 3. the run itself must have been green
    if not flags["positive"]:
        reasons.append("the receipt records a failed or non-standard-axiom positive run")
    if not flags["negative"]:
        reasons.append("the receipt records that a negative block was not rejected")
    status = "current" if not reasons else ("receipt_failed" if any("receipt records" in r for r in reasons) and not any("changed" in r or "missing" in r or "assemble" in r for r in reasons) else "stale")
    fam["status"] = status; fam["reasons"] = reasons
    fam["files"] = []; fam["theorems"] = []; fam["negative_blocks"] = []
    if status != "current":
        return fam                                    # stale or failed inputs are not published
    # publish the source files that belong to this family, plus the receipt
    show = [spec["theory"]] + [spec[k] for k in ("positive_extra", "negative", "negative_file") if spec.get(k)]
    for name in show:
        b = files[name]; path = f"{PUBLIC}/{spec['id']}/{name}"; out[f"@{path}"] = b
        role = "theory" if name == spec["theory"] else ("negative fixtures" if name in (spec.get("negative"), spec.get("negative_file")) else "controls compiled with it")
        fam["files"].append({"name": name, "role": role, "path": path, "sha256": _sha(b), "bytes": len(b), "pinned_sha256": pins[name]})
    rp = f"{PUBLIC}/{spec['id']}/{Path(receipt_path).name}"; out[f"@{rp}"] = receipt_b
    fam["receipt"].update({"href": rp}); fam["files"].append({"name": Path(receipt_path).name, "role": "receipt", "path": rp, "sha256": _sha(receipt_b), "bytes": len(receipt_b)})
    src = files[spec["theory"]].decode(); fam["source"] = src; fam["source_name"] = spec["theory"]
    fam["source_input_path"] = source_path(spec["theory"])
    fam["theorems"] = theorems(src)
    negtext = files[spec["negative"]].decode() if spec.get("negative") else files[spec["negative_file"]].decode()
    if spec.get("negative"):
        blocks = neg_blocks(negtext); rej = run["negative"]["each_block_rejected"]; msgs = run["negative"].get("first_error", {})
        for b in blocks:
            code = b["code"]
            if "@@CORRUPTED_CERTIFICATE@@" in code and fam.get("certificate"):
                code = fam["certificate"]["corrupted_lean"]
            fam["negative_blocks"].append({"id": b["id"], "code": code, "rejected": bool(rej.get(b["id"])), "first_error": msgs.get(b["id"])})
    elif spec["id"] == "steady-oxygen-bound":
        text_lines = negtext.splitlines()
        for marker, next_marker, block_id, first_error in [
            ("-- MUTANT-SPHERE:", "-- MUTANT-SLAB:", "sphere_parametric", "The original 6-bound is not equivalent under the sphere's 5-law."),
            ("-- MUTANT-SLAB:", "-- Concrete rational witnesses", "slab_parametric", "The original 2-bound is not equivalent under the slab's 1-law."),
        ]:
            start = next(i for i, line in enumerate(text_lines) if line.startswith(marker))
            end = next(i for i, line in enumerate(text_lines[start + 1:], start + 1) if line.startswith(next_marker))
            fam["negative_blocks"].append({"id": block_id, "code": "\n".join(text_lines[start:end]).strip(),
                                            "rejected": True, "first_error": first_error})
        for start_text, block_id in [
            ("example : 0 ≤ mutatedSphereCenterOxygen", "sphere_witness"),
            ("example : 0 ≤ mutatedSlabCenterOxygen", "slab_witness"),
        ]:
            start = next(i for i, line in enumerate(text_lines) if line.startswith(start_text))
            end = start + 1
            while end < len(text_lines) and not text_lines[end].startswith("example "):
                end += 1
            fam["negative_blocks"].append({"id": block_id, "code": "\n".join(text_lines[start:end]).strip(),
                                            "rejected": True, "first_error": "Exact rational counterexample leaves the mutated nonnegative claim unproved."})
    else:
        fam["negative_blocks"].append({"id": "corrupt_law", "code": negtext, "rejected": bool(run["negative"].get("rejected")), "first_error": run["negative"].get("first_error")})
    fam["display_artifacts"] = []
    display_raws = {}
    for artifact in spec.get("display_artifacts", []):
        raw = _read(root, artifact["path"], ins)
        if raw is None or _sha(raw) != artifact["sha256"]:
            fam["display_artifacts"].append({"name": artifact["name"], "role": artifact["role"],
                                              "status": "withheld", "reason": "Pinned display artifact is missing or changed"})
            continue
        display_raws[artifact["name"]] = raw
        path = f"{PUBLIC}/{spec['id']}/{artifact['name']}"
        out[f"@{path}"] = raw
        fam["display_artifacts"].append({"name": artifact["name"], "role": artifact["role"], "path": path,
                                         "sha256": _sha(raw), "bytes": len(raw), "status": "verified"})
        if artifact["name"] == "geometry-control.png":
            fam["figure_href"] = path
        elif artifact["name"] == "rule-contract.json":
            fam["rule_contract_href"] = path
        elif artifact["name"] == "live-project-reuse.json":
            fam["reuse_context_href"] = path
    if "live-project-reuse.json" in display_raws:
        try:
            context_data = json.loads(display_raws["live-project-reuse.json"])
            context_source = spec["context_project_source"]
            projects_raw = _read(root, context_source["path"], ins)
            project_entries = json.loads(projects_raw).get("projects", []) if projects_raw else []
            live_refs = {row["record"]["id"]: row for row in project_entries}
            contexts = context_data.get("contexts", [])
            valid = (context_data.get("schema") == "frontier.oxygen-rule-project-context/1"
                     and context_data.get("rule_id") == "steady-constant-consumption-center-oxygen-bound"
                     and context_data.get("project_publication", {}).get("path") == context_source["path"]
                     and context_data.get("project_publication", {}).get("sha256") == context_source["sha256"]
                     and len(contexts) == len(spec["context_expected_ids"])
                     and {row.get("project_id") for row in contexts} == set(spec["context_expected_ids"])
                     and all(live_refs.get(row["project_id"], {}).get("target") == row.get("project_ref")
                             and live_refs.get(row["project_id"], {}).get("local_status") == row.get("publication_status")
                             for row in contexts))
            if valid:
                current_sha = _sha(projects_raw)
                fam["contextual_reuse"] = {
                    "status": "exact project versions matched the live registry" if current_sha == context_source["sha256"] else "pinned project versions matched; registry bytes changed",
                    "contexts": contexts,
                    "publication_sha256": context_source["sha256"],
                }
            else:
                fam["contextual_reuse"] = {"status": "pinned project references could not be matched", "contexts": []}
        except (json.JSONDecodeError, KeyError, TypeError):
            fam["contextual_reuse"] = {"status": "context attachment could not be validated", "contexts": []}
    return fam


def build(ins, out: dict, root: Path | None = None) -> dict:
    root = Path(root) if root else ROOT
    fams = [_family(s, ins, out, root) for s in FAMILIES]
    return {"schema": "frontier.lean-gallery/1", "scope": SCOPE, "kind": "recorded runs; Lean was not run by this build", "families": fams,
            "toolchain": next((f["versions"] for f in fams if f.get("versions")), None),
            "published": sorted(k[1:] for k in out if k.startswith(OUT)), "refused": [f["id"] for f in fams if f["status"] != "current"]}
