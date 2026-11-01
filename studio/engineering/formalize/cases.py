"""Hand-authored (human) proposals used as fixtures.  These are NOT LLM outputs; the LLM-produced proposal
is recorded separately under runs/.  Source passages are public text under sources/ (see MANIFEST.json)."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
S = lambda n: (HERE / "sources" / n).read_text(encoding="utf-8")
sha = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()


def cantilever_request() -> dict:
    p = S("cantilever_passage.txt")
    return {
        "schema": "frontier.formalize.request/1",
        "claim": {"id": "cantilever-tip-deflection",
                  "text": "Tip deflection of a clamped-free beam under a point load P at the free end is w_C = P L^3 / (3 E I); "
                          "the fin-ray uses E ~ 1e8-1e9 N m^-2 and I ~ 1e-6 cm^4 (Alben et al. 2007).",
                  "source": {"ref": "https://en.wikipedia.org/wiki/Euler%E2%80%93Bernoulli_beam_theory ; https://pmc.ncbi.nlm.nih.gov/articles/PMC2359861/",
                             "locator": "sources/cantilever_passage.txt", "text_sha256": sha(p)}},
        "proposal": {
            "symbols": [
                {"name": "P", "unit": "N", "domain": {"lo": "0", "hi": "1", "lo_open": True}, "status": "declared",
                 "source_ref": "end load; value range DECLARED here, not from the source"},
                {"name": "L", "unit": "m", "domain": {"lo": "0", "hi": "1/10", "lo_open": True}, "status": "declared",
                 "source_ref": "Alben: typical ray L=4 cm = 0.04 m; range declared"},
                {"name": "E", "unit": "Pa", "domain": {"lo": "100000000", "hi": "1000000000"}, "status": "given",
                 "source_ref": "Alben: composite E ~ 1e8-1e9 N m^-2"},
                {"name": "I", "unit": "m^4", "domain": {"lo": "1/1000000000000000", "hi": "1/10000000000000"}, "status": "declared",
                 "source_ref": "Alben: I ~ 1e-6 cm^4 = 1e-14 m^4 (cm^4 -> m^4 is x1e-8); bracket 1e-15..1e-13 declared"},
                {"name": "delta", "unit": "m", "domain": {"lo": "0", "hi": "1", "lo_open": True}, "status": "unknown",
                 "source_ref": "tip deflection w_C (the unknown being constrained)"}],
            "assumptions": [
                {"id": "A1", "text": "Euler-Bernoulli small-deflection, linear-elastic, clamped-free beam, constant EI, point load at the free end.", "kind": "modelling"},
                {"id": "A2", "text": "Small-deformation guard delta <= L/10 is a DECLARED validity limit of this repository's fin_mechanics package (tip_over_L_max = 1/10), not from the sources.", "kind": "scope"},
                {"id": "A3", "text": "SI units; the source gives I in cm^4 and the factor 1e-8 to m^4 is applied by the proposer.", "kind": "numerical"}],
            "constraints": [
                {"id": "C1", "kind": "equality", "dimension_check": True, "source_ref": "w_C = PL^3/(3EI)",
                 "expr": {"op": "==", "lhs": {"op": "*", "args": ["3", "E", "I", "delta"]},
                          "rhs": {"op": "*", "args": ["P", {"op": "pow", "base": "L", "exp": 3}]}}},
                {"id": "C2", "kind": "inequality", "dimension_check": True, "source_ref": "A2",
                 "expr": {"op": "<=", "lhs": "delta", "rhs": {"op": "/", "args": ["L", "10"]}}}],
            "source_mapping": [
                {"element": "C1", "quote": "<math>w_C = \\tfrac{PL^3}{3EI}</math>", "locator": "cantilever end-load table, deflection maximum"},
                {"element": "C2", "quote": "limited to small deflections of a beam", "locator": "lead sentence; numeric limit 1/10 is a repository choice"}],
            "unresolved": [
                {"id": "U1", "question": "The passage does not define P, L, E, I; standard notation (end load, length, Young's modulus, second moment of area) is assumed."},
                {"id": "U2", "question": "Alben's fin ray is a bilaminar beam with intraray shear, not the single Euler-Bernoulli beam of C1; is the single-beam law an acceptable surrogate?"}]},
        "options": {"controls": True, "lean_statement": True}}


def corrupt_cantilever(kind: str) -> dict:
    r = copy.deepcopy(cantilever_request())
    r["claim"]["id"] = "cantilever-corrupt-" + kind
    c1 = r["proposal"]["constraints"][0]["expr"]
    if kind == "L2":      # L^3 -> L^2 (dimension fault)
        c1["rhs"]["args"][1]["exp"] = 2
    elif kind == "wrong_unit":  # I given in cm^4 numerically but declared m^4 -> use wrong dimension: I in m^2
        for s in r["proposal"]["symbols"]:
            if s["name"] == "I":
                s["unit"] = "m^2"
    elif kind == "drop_guard":
        r["proposal"]["constraints"] = r["proposal"]["constraints"][:1]
        r["proposal"]["source_mapping"] = r["proposal"]["source_mapping"][:1]
    elif kind == "flip_guard":
        r["proposal"]["constraints"][1]["expr"]["op"] = ">="
    else:
        raise ValueError(kind)
    return r


def gc_design_request() -> dict:
    return {
        "schema": "frontier.formalize.request/1",
        "claim": {"id": "primer-gc-window",
                  "text": "A design target: an oligonucleotide of length n between 18 and 30 nt whose G+C count g satisfies 40% <= g/n <= 60%. "
                          "This is a counting property of a sequence; it says nothing about whether the sequence works as a primer or has any biological function.",
                  "source": {"ref": "design target stated by the user/proposer (no external source)", "locator": "none"}},
        "proposal": {
            "symbols": [
                {"name": "n", "unit": "1", "integer": True, "domain": {"lo": "18", "hi": "30"}, "status": "declared", "source_ref": "design target"},
                {"name": "g", "unit": "1", "integer": True, "domain": {"lo": "0", "hi": "30"}, "status": "unknown", "source_ref": "count of G or C in the sequence"}],
            "assumptions": [
                {"id": "A1", "text": "n and g are counts of nucleotides in one DNA strand written over {A,C,G,T}.", "kind": "modelling"},
                {"id": "A2", "text": "The 40-60% window is a conventional design heuristic chosen by the proposer; no source is cited.", "kind": "scope"}],
            "constraints": [
                {"id": "C1", "kind": "inequality", "dimension_check": True, "expr": {"op": "<=", "lhs": "g", "rhs": "n"}},
                {"id": "C2", "kind": "inequality", "dimension_check": True,
                 "expr": {"op": ">=", "lhs": {"op": "*", "args": ["5", "g"]}, "rhs": {"op": "*", "args": ["2", "n"]}}},
                {"id": "C3", "kind": "inequality", "dimension_check": True,
                 "expr": {"op": "<=", "lhs": {"op": "*", "args": ["5", "g"]}, "rhs": {"op": "*", "args": ["3", "n"]}}}],
            "source_mapping": [], "unresolved": [
                {"id": "U1", "question": "Is a 40-60% GC window the right design criterion for the intended assay? (no source cited)"}]},
        "options": {"controls": True}}


def gc_infeasible_request() -> dict:
    """Over-constrained: needs GC fraction >= 70% AND <= 30% -> unsat; shows an unsat verdict with deletion controls."""
    r = gc_design_request()
    r["claim"]["id"] = "primer-gc-infeasible"
    r["proposal"]["constraints"] = [
        {"id": "C1", "kind": "inequality", "dimension_check": True, "expr": {"op": ">=", "lhs": {"op": "*", "args": ["10", "g"]}, "rhs": {"op": "*", "args": ["7", "n"]}}},
        {"id": "C2", "kind": "inequality", "dimension_check": True, "expr": {"op": "<=", "lhs": {"op": "*", "args": ["10", "g"]}, "rhs": {"op": "*", "args": ["3", "n"]}}},
        {"id": "C3", "kind": "inequality", "dimension_check": True, "expr": {"op": "<=", "lhs": "g", "rhs": "n"}}]
    return r


def oca2_request() -> dict:
    p = S("oca2_passage.txt")
    return {
        "schema": "frontier.formalize.request/1",
        "claim": {"id": "molino-oca2-albinism",
                  "text": "Loss of oca2 exon 21 in Molino cavefish explains their albinism.",
                  "source": {"ref": "Warren et al. 2021 Nat Commun, PMC7933363 (Europe PMC full text)", "locator": "Results; sources/oca2_passage.txt",
                             "text_sha256": sha(p)}},
        "proposal": {
            "symbols": [
                {"name": "n", "unit": "1", "integer": True, "domain": {"lo": "18", "hi": "30"}, "status": "declared",
                 "source_ref": "length of the published oca2 exon 21 forward primer (PMC4361574 Methods)"},
                {"name": "g", "unit": "1", "integer": True, "domain": {"lo": "0", "hi": "30"}, "status": "declared",
                 "source_ref": "its G+C count"}],
            "assumptions": [
                {"id": "A1", "text": "Only the sequence-level count property of a published primer is encoded; the claimed causal link from the exon 21 lesion to albinism is NOT encoded.", "kind": "scope"}],
            "constraints": [
                {"id": "C1", "kind": "inequality", "dimension_check": True, "expr": {"op": "<=", "lhs": "g", "rhs": "n"}},
                {"id": "C2", "kind": "inequality", "dimension_check": True,
                 "expr": {"op": ">=", "lhs": {"op": "*", "args": ["5", "g"]}, "rhs": {"op": "*", "args": ["2", "n"]}}}],
            "source_mapping": [{"element": "C1", "quote": "oca2 exon 21 forward primer 5'-GAGAGTTTACCCAAAGCAGAGTG-3'", "locator": "PMC4361574 Methods"}],
            "unresolved": [{"id": "U1", "question": "What mechanism maps exon 21 absence to loss of pigment in this background?"}]},
        "options": {"controls": True}}


CASES = {
    "cantilever": cantilever_request,
    "cantilever_corrupt_L2": lambda: corrupt_cantilever("L2"),
    "cantilever_corrupt_unit": lambda: corrupt_cantilever("wrong_unit"),
    "cantilever_mutant_drop_guard": lambda: corrupt_cantilever("drop_guard"),
    "cantilever_mutant_flip_guard": lambda: corrupt_cantilever("flip_guard"),
    "gc_window": gc_design_request,
    "gc_infeasible": gc_infeasible_request,
    "oca2_causal_refusal": oca2_request,
}
