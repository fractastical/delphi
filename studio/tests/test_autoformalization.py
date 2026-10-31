"""Autoformalization: bounded declarative proposals checked offline. Hand-worked expectations are explained beside each assertion.
Nothing here calls a model: the recorded LLM runs under engineering/formalize/runs are verified OFFLINE against their own receipts and re-checked."""
import ast
import copy
import hashlib
import json
import re
import sys
import threading
from fractions import Fraction
from pathlib import Path

import pytest

from engineering.formalize import cases, extract
from frontier import formalize as F
from frontier.formalize import dims, service
from frontier.formalize.grammar import GrammarError, parse_literal, validate_request
from frontier.formalize.solve import Model

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "engineering" / "formalize" / "runs"


def propose(req):
    return F.propose(req)


def is_error(body, code):
    return body.get("schema") == "frontier.formalize.error/1" and body["code"] == code and body["calibrated"] is False


# ------------------------------------------------------------------ the grammar: bounded, declarative, data only
def test_rational_literals_are_exact():
    assert parse_literal("-1/2") == Fraction(-1, 2) and parse_literal("0.25") == Fraction(1, 4) and parse_literal("1e-6") == Fraction(1, 10**6)
    for bad in ("0x10", "1/0", "inf", "nan", "2**8", "__import__('os')", "1e100", "", "--3", True, 1.5, 10**31):
        with pytest.raises(GrammarError):
            parse_literal(bad)


def test_a_zero_denominator_literal_is_a_grammar_error_and_propose_never_raises():
    r = cases.cantilever_request()
    r["proposal"]["constraints"][1]["expr"]["rhs"] = "1/0"
    body = propose(r)                                                                             # used to raise ZeroDivisionError out of propose()
    assert is_error(body, "unsupported_expression") and "zero denominator" in body["detail"]
    for weird in (None, 5, "text", [], {"schema": "frontier.formalize.request/1"}, {"schema": "x", "claim": 3}):
        assert propose(weird)["schema"] == "frontier.formalize.error/1"


def test_nesting_bombs_are_errors_not_exceptions():
    r = cases.cantilever_request()
    x = []
    for _ in range(100000):
        x = [x]
    r["proposal"]["assumptions"] = x                                                            # used to raise RecursionError out of propose()
    assert is_error(propose(r), "unsupported_expression")
    r = cases.cantilever_request()
    term = "L"
    for _ in range(3000):
        term = {"op": "+", "args": [term, "L"]}
    r["proposal"]["constraints"][1]["expr"]["rhs"] = term
    assert propose(r)["schema"] == "frontier.formalize.error/1"


def test_polynomial_semantics_of_the_cantilever_law_by_hand():
    ctx = validate_request(cases.cantilever_request())
    m = Model(ctx)
    pt = {"E": 2, "I": 3, "delta": 5, "P": 7, "L": 1, "w": 0}
    # C1: 3*E*I*delta == P*L^3  ->  lhs-rhs = 3*2*3*5 - 7*1 = 90 - 7 = 83 ; C2: delta <= L/10 -> 5 - 1/10 = 49/10
    point = [Fraction(pt.get(n, 0)) for n in m.names]
    vals = {cid: p.eval(point) for cid, _, p in m.cons}
    assert vals == {"C1": Fraction(83), "C2": Fraction(49, 10)}


@pytest.mark.parametrize("name,edit,code", [
    ("function call", lambda r: r["proposal"]["constraints"][1]["expr"].update(rhs={"op": "sqrt", "args": ["L"]}), "unsupported_expression"),
    ("division by a symbol", lambda r: r["proposal"]["constraints"][1]["expr"].update(rhs={"op": "/", "args": ["L", "P"]}), "unsupported_expression"),
    ("division by zero literal", lambda r: r["proposal"]["constraints"][1]["expr"].update(rhs={"op": "/", "args": ["L", "0"]}), "unsupported_expression"),
    ("undeclared symbol", lambda r: r["proposal"]["constraints"][1]["expr"].update(rhs="Q"), "unsupported_expression"),
    ("code in a term", lambda r: r["proposal"]["constraints"][1]["expr"].update(rhs="__import__('os').system('id')"), "unsupported_expression"),
    ("exponent above the cap", lambda r: r["proposal"]["constraints"][0]["expr"]["rhs"]["args"][1].update(exp=5), "unsupported_expression"),
    ("boolean as a number", lambda r: r["proposal"]["constraints"][1]["expr"].update(rhs=True), "unsupported_expression"),
    ("huge literal", lambda r: r["proposal"]["constraints"][1]["expr"].update(rhs="1e100"), "unsupported_expression"),
    ("unknown top-level field", lambda r: r.update(extra_field=1), "unknown_field"),
    ("unknown proposal field", lambda r: r["proposal"].update(code="print(1)"), "unknown_field"),
    ("symbol name with a dot", lambda r: r["proposal"]["symbols"][0].update(name="os.system"), "unsupported_expression"),
    ("symbol name starting with underscore", lambda r: r["proposal"]["symbols"][0].update(name="__x"), "unsupported_expression"),
    ("operator that is not in the grammar", lambda r: r["proposal"]["constraints"][1]["expr"].update(op="=~"), "unsupported_expression"),
])
def test_grammar_rejects_everything_outside_it(name, edit, code):
    r = cases.cantilever_request()
    edit(r)
    body = propose(r)
    assert is_error(body, code), (name, body)
    assert service.http_status(body) in (400, 422)


def test_node_cap_size_cap_and_non_finite_data():
    r = cases.cantilever_request()
    term = "L"
    for _ in range(40):                       # 40 nested sums -> well over 64 nodes
        term = {"op": "+", "args": [term, "L"]}
    r["proposal"]["constraints"][1]["expr"]["rhs"] = term
    assert is_error(propose(r), "unsupported_expression")
    big = cases.cantilever_request()
    big["proposal"]["assumptions"] = [{"id": f"A{i}", "text": "x" * 900, "kind": "scope"} for i in range(30)]
    body = propose(big)
    assert is_error(body, "request_too_large") and service.http_status(body) == 413
    nan = cases.cantilever_request()
    nan["proposal"]["constraints"][1]["expr"]["rhs"] = float("nan")
    assert is_error(propose(nan), "unsupported_expression")


def test_package_contains_no_eval_exec_network_or_shell():
    banned_names = {"eval", "exec", "compile", "__import__", "open"}            # builtins only; re.compile and a solver's model.eval are attribute calls
    banned_attrs = {"system", "popen", "urlopen", "exec_module", "load_module", "check_output", "check_call", "run"}
    banned_imports = {"socket", "urllib", "requests", "http", "ftplib", "smtplib", "ctypes", "pickle", "marshal", "shelve", "importlib"}
    for path in sorted((ROOT / "frontier" / "formalize").glob("*.py")):
        tree = ast.parse(path.read_text())
        names = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        attrs = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        imported = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | \
                   {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not (names & banned_names), (path.name, names & banned_names)
        assert not (attrs & banned_attrs), (path.name, attrs & banned_attrs)
        assert not (imported & banned_imports), (path.name, imported & banned_imports)
        if path.name != "service.py":
            assert "subprocess" not in imported, path.name        # only the service starts the capped worker


# ------------------------------------------------------------------ dimensions (exact integer exponents of the SI base)
def test_units_are_a_closed_table_with_exact_dimensions():
    assert dims.parse_unit("N m^-2") == dims.parse_unit("Pa") == (1, -1, -2, 0, 0, 0, 0)            # kg m^-1 s^-2
    assert dims.parse_unit("1") == dims.parse_unit("") == (0,) * 7
    for bad in ("cm", "MPa", "mm^2", "furlong", "m^100"):
        with pytest.raises(dims.UnitError):
            dims.parse_unit(bad)


def test_dimension_reports_match_hand_algebra():
    r = propose(cases.cantilever_request())
    got = {d["constraint"]: d["dims"] for d in r["dimension_report"]}
    # C1: E*I*delta = Pa * m^4 * m = kg m^-1 s^-2 * m^5 = kg m^4 s^-2 (also P*L^3 = N*m^3 = kg m s^-2 * m^3) ; C2: delta <= L/10 -> m
    assert got == {"C1": "kg m^4 s^-2", "C2": "m"}


def test_adding_unlike_dimensions_is_invalid():
    r = cases.cantilever_request()
    r["proposal"]["constraints"][1]["expr"] = {"op": "<=", "lhs": {"op": "+", "args": ["P", "L"]}, "rhs": "1"}      # N + m
    body = propose(r)
    assert body["status"] == "invalid" and body["dimension_report"][1]["ok"] is False and body["evidence_kind"] == "none"


# ------------------------------------------------------------------ satisfiability: what sat / unsat / unknown mean
def test_cantilever_sat_with_an_exact_witness_checked_by_independent_arithmetic():
    body = propose(cases.cantilever_request())
    c = body["checks"][0]
    assert body["status"] == "checked" and body["evidence_kind"] == "formal" and c["result"] == "sat" and c["independent_check"] == "ok"
    w = {k: Fraction(v) for k, v in c["witness"].items()}
    assert 3 * w["E"] * w["I"] * w["delta"] == w["P"] * w["L"] ** 3 and w["delta"] <= w["L"] / 10                  # recomputed here, not trusted
    assert 10**8 <= w["E"] <= 10**9 and 0 < w["L"] <= Fraction(1, 10) and 0 < w["P"] <= 1


def test_gc_window_is_a_counting_property_and_sat():
    c = propose(cases.gc_design_request())["checks"][0]
    n, g = Fraction(c["witness"]["n"]), Fraction(c["witness"]["g"])
    assert c["result"] == "sat" and n.denominator == g.denominator == 1 and 18 <= n <= 30 and 2 * n <= 5 * g <= 3 * n and g <= n


def test_overconstrained_gc_window_is_unsat_by_exhaustive_integer_enumeration():
    body = propose(cases.gc_infeasible_request())
    c = body["checks"][0]
    # needs g/n >= 7/10 and g/n <= 3/10 with n >= 18: no integer pair exists, and the box (13 x 31 points) is searched in full
    assert body["status"] == "checked" and c["result"] == "unsat" and "enumerat" in c["method"].lower() or "interval" in c["method"].lower()
    probes = {p["name"]: p["observed"] for p in body["negative_controls"] if p["kind"] == "probe"}
    assert probes == {"drop_constraint:C1": "in_a_conflict_core", "drop_constraint:C2": "in_a_conflict_core", "drop_constraint:C3": "not_needed_for_the_conflict"}


def test_interval_refutation_is_sound_for_a_single_impossible_constraint():
    r = cases.gc_design_request()
    r["proposal"]["symbols"] = [{"name": "x", "unit": "1", "domain": {"lo": "1", "hi": "2"}, "status": "declared", "source_ref": "t"}]
    r["proposal"]["constraints"] = [{"id": "C1", "kind": "inequality", "dimension_check": True, "expr": {"op": "<=", "lhs": "x", "rhs": "0"}}]
    r["proposal"]["source_mapping"] = []
    c = propose(r)["checks"][0]
    assert c["result"] == "unsat" and "interval" in c["method"].lower()


def test_interval_refutation_does_not_refute_a_boundary_point():
    def one(op, lo, hi, rhs):
        r = cases.gc_design_request()
        r["proposal"]["symbols"] = [{"name": "x", "unit": "1", "domain": {"lo": lo, "hi": hi}, "status": "declared", "source_ref": "t"}]
        r["proposal"]["constraints"] = [{"id": "C1", "kind": "inequality", "dimension_check": True, "expr": {"op": op, "lhs": "x", "rhs": rhs}}]
        r["proposal"]["source_mapping"] = []
        return propose(r)["checks"][0]
    assert one("<=", "0", "1", "0")["result"] == "sat"            # x = 0 satisfies x <= 0: range of x-0 is [0,1], lo = 0 is NOT > 0, so no refutation
    assert one(">=", "-1", "0", "0")["result"] == "sat"           # x = 0 satisfies x >= 0
    assert one("<", "0", "1", "0")["result"] == "unsat"           # strict: x < 0 over [0,1] has no solution (lo >= 0)
    assert one(">", "-1", "0", "0")["result"] == "unsat"          # strict: x > 0 over [-1,0] has no solution


def test_a_solved_variable_that_leaves_its_declared_domain_is_not_a_witness():
    r = cases.gc_design_request()
    r["proposal"]["symbols"] = [{"name": "x", "unit": "1", "domain": {"lo": "0", "hi": "1", "hi_open": True}, "status": "unknown", "source_ref": "t"},
                                {"name": "y", "unit": "1", "domain": {"lo": "1", "hi": "2"}, "status": "declared", "source_ref": "t"},
                                {"name": "z", "unit": "1", "domain": {"lo": "0", "hi": "1"}, "status": "declared", "source_ref": "t"}]
    # x == y + z forces x >= 1, but x < 1 is declared: a search that solves for x lands on x = 1 and must reject it. Interval arithmetic cannot refute it (the hull touches 0).
    r["proposal"]["constraints"] = [{"id": "C1", "kind": "equality", "dimension_check": True, "expr": {"op": "==", "lhs": "x", "rhs": {"op": "+", "args": ["y", "z"]}}}]
    r["proposal"]["source_mapping"] = []
    c = propose(r)["checks"][0]
    assert c["result"] != "sat" and "witness" not in c


def test_unknown_is_reported_not_guessed():
    r = cases.gc_design_request()
    r["proposal"]["symbols"] = [{"name": "x", "unit": "1", "domain": {"lo": "0", "hi": "2"}, "status": "declared", "source_ref": "t"},
                                {"name": "y", "unit": "1", "domain": {"lo": "0", "hi": "2"}, "status": "declared", "source_ref": "t"}]
    r["proposal"]["constraints"] = [{"id": "C1", "kind": "equality", "dimension_check": True,
                                     "expr": {"op": "==", "lhs": {"op": "+", "args": [{"op": "pow", "base": "x", "exp": 2}, {"op": "pow", "base": "y", "exp": 2}]}, "rhs": "3"}}]
    r["proposal"]["source_mapping"] = []
    body = propose(r)
    # x^2 + y^2 = 3 has no rational solution (3 is not a sum of two rational squares), so a witness can never be found, and interval arithmetic cannot refute it
    assert body["checks"][0]["result"] != "sat" and body["status"] in ("unknown", "checked")
    if body["checks"][0]["result"] == "unsat":
        assert body["checks"][0]["independent_check"] == "none"       # a solver verdict without a proof object is labelled as such
    else:
        assert body["status"] == "unknown" and body["evidence_kind"] == "none"


def test_witness_search_resolves_equalities_in_dependency_order():
    r = cases.gc_design_request()
    r["proposal"]["symbols"] = [{"name": n, "unit": "1", "domain": {"lo": "1", "hi": "4"}, "status": "declared", "source_ref": "t"} for n in ("a", "b", "c")]
    # a == b*c is listed FIRST but needs b, which the second equality (b == 2*c) determines: the earlier code failed on exactly this shape
    r["proposal"]["constraints"] = [
        {"id": "C1", "kind": "equality", "dimension_check": True, "expr": {"op": "==", "lhs": "a", "rhs": {"op": "*", "args": ["b", "c"]}}},
        {"id": "C2", "kind": "equality", "dimension_check": True, "expr": {"op": "==", "lhs": "b", "rhs": {"op": "*", "args": ["2", "c"]}}}]
    r["proposal"]["source_mapping"] = []
    c = propose(r)["checks"][0]
    w = {k: Fraction(v) for k, v in c["witness"].items()}
    assert c["result"] == "sat" and w["b"] == 2 * w["c"] and w["a"] == w["b"] * w["c"] and 1 <= w["a"] <= 4


def test_a_perturbed_witness_is_rejected_by_the_exact_checker():
    ctx = validate_request(cases.cantilever_request())
    m = Model(ctx)
    w = propose(cases.cantilever_request())["checks"][0]["witness"]
    pt = [Fraction(w[n]) for n in m.names]
    assert m.violations(pt) == []
    pt2 = list(pt); pt2[m.names.index("delta")] += 1
    assert m.violations(pt2) != []


# ------------------------------------------------------------------ refusals: causal genotype-phenotype is not formalized
def test_causal_genotype_phenotype_claim_is_refused_and_checkable_facts_are_kept_apart():
    body = propose(cases.oca2_request())
    assert body["status"] == "refused" and [x["code"] for x in body["refusals"]] == ["CAUSAL_GENOTYPE_PHENOTYPE_NO_MECHANISM"] and body["evidence_kind"] == "none"
    assert body["causal_claim_formalized"] is False and "separated_checkable_facts" in body and body["checks"] == []
    needed = " ".join(body["refusals"][0]["what_would_be_needed"])
    assert "mechanistic map" in needed and "say nothing about function" in needed


def test_refusal_gate_does_not_fire_on_mechanics_or_on_a_pure_counting_property():
    assert propose(cases.gc_design_request())["status"] == "checked"                     # says outright that it says nothing about function
    r = cases.cantilever_request()
    r["claim"]["text"] = "Load causes deflection of a cantilever beam: w = P L^3 / (3 E I)."   # causal wording without genotype or phenotype
    assert propose(r)["status"] == "checked"


def test_claims_of_biological_function_are_refused():
    r = cases.gc_design_request()
    r["claim"]["text"] = "This sequence guarantees the protein will express and function in the cell."
    body = propose(r)
    assert body["status"] == "refused" and "BIOLOGICAL_FUNCTION_NOT_FORMALIZABLE" in [x["code"] for x in body["refusals"]]


# ------------------------------------------------------------------ corrupt laws and named controls
def test_corrupt_laws_are_rejected_before_any_satisfiability_claim():
    for kind in ("L2", "wrong_unit"):
        body = propose(cases.corrupt_cantilever(kind))
        assert body["status"] == "invalid" and body["evidence_kind"] == "none" and body["rejected_by_dimension_check"] == ["C1"], kind
        assert body["negative_controls"] == [] and "faulty base" in body["controls_skipped_reason"]       # a control against a faulty base would mislead


def test_all_pre_declared_controls_hold_on_the_valid_fixtures():
    for name in ("cantilever", "gc_window", "gc_infeasible"):
        body = propose(cases.CASES[name]())
        cs = body["controls_summary"]
        assert cs["n"] > 0 and cs["as_expected"] == cs["n"], (name, [(c["name"], c["expected"], c["observed"]) for c in body["negative_controls"] if c["expected"] not in (None, c["observed"])])
    cant = {c["name"] for c in propose(cases.cantilever_request())["negative_controls"]}
    assert {"wrong_unit:E", "wrong_unit:I", "wrong_unit:L", "witness_independent_recheck", "perturbed_witness_rejected", "negate_constraint:C2"} <= cant
    assert any(n.startswith("exponent_mutant:C1") for n in cant)


def test_dropping_the_guard_is_not_detected_by_satisfiability_alone():
    body = propose(cases.corrupt_cantilever("drop_guard"))
    assert body["status"] == "checked"                       # still consistent: sat does not show the guard was encoded
    assert [c["constraint"] for c in body["dimension_report"]] == ["C1"] and body["source_mapping_declared"] == ["C1"]


def test_every_response_says_what_it_does_not_establish():
    for name in ("cantilever", "gc_window", "oca2_causal_refusal"):
        body = propose(cases.CASES[name]())
        assert body["lean"] == "not_run" and body["calibrated"] is False
        assert {"translation fidelity to the source", "biological function"} <= set(body["not_established"]) and "not a claim that the constraints encode the source text" in body["assumed_scope"].lower() \
            or "not a claim that the" in body["assumed_scope"]
    checked = propose(cases.cantilever_request())
    assert checked["lean_statement"]["status"] == "generated_not_compiled" and checked["unresolved_translation"]


def test_responses_are_deterministic_apart_from_wall_time():
    a, b = propose(cases.cantilever_request()), propose(cases.cantilever_request())
    for k in ("worker_wall_s",):
        a.pop(k, None); b.pop(k, None)
    assert a == b and a["request_sha256"] == F.sha256_obj(cases.cantilever_request())


# ------------------------------------------------------------------ the capped worker
def test_worker_environment_is_stripped(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-should-not-leak")
    monkeypatch.setenv("HOME", "/home/someone")
    env = service._worker_env()
    assert "GEMINI_API_KEY" not in env and "HOME" not in env and set(env) <= {"PATH", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH", "LANG"}
    assert "secret" not in json.dumps(env)


def test_slots_are_bounded_and_refuse_instead_of_queueing():
    held = [service.SLOTS.acquire(blocking=False) for _ in range(2)]
    try:
        assert all(held)
        body = propose(cases.cantilever_request())
        assert is_error(body, "solver_busy") and service.http_status(body) == 429
    finally:
        for h in held:
            if h:
                service.SLOTS.release()
    assert propose(cases.cantilever_request())["status"] == "checked"          # released slots work again


def test_timeout_and_crash_of_the_worker_are_reported_not_hidden(monkeypatch, tmp_path):
    hang = tmp_path / "hang.py"
    hang.write_text("import time\ntime.sleep(60)\n")
    monkeypatch.setattr(service, "WORKER_ARGV", [sys.executable, str(hang)])
    t = F.propose(cases.cantilever_request(), timeout_s=0.5)
    assert t["schema"] == "frontier.formalize.response/1" and t["status"] == "unknown" and t["evidence_kind"] == "none"
    crash = tmp_path / "crash.py"
    crash.write_text("import sys\nsys.exit(3)\n")
    monkeypatch.setattr(service, "WORKER_ARGV", [sys.executable, str(crash)])
    assert is_error(propose(cases.cantilever_request()), "solver_unavailable")


# ------------------------------------------------------------------ the recorded LLM runs, verified OFFLINE
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


RUN_DIRS = sorted(d for d in RUNS.iterdir() if d.is_dir() and (d / "receipt.json").exists()) if RUNS.exists() else []


@pytest.mark.skipif(not RUN_DIRS, reason="no recorded model runs in this checkout")
def test_recorded_runs_are_internally_consistent_and_carry_no_credentials():
    assert len(RUN_DIRS) >= 5
    for d in RUN_DIRS:
        r = json.loads((d / "receipt.json").read_text())
        assert r["provider"] == "google-generative-language" and r["model_requested"] == "gemini-3-flash-preview" and r["model_version_reported"] == "gemini-3-flash-preview", d.name
        assert _sha(d / "prompt.txt") == r["prompt_sha256"] and hashlib.sha256((d / "response.raw.txt").read_bytes()).hexdigest() == r["response_sha256"], d.name
        assert r["usage_reported_by_provider"]["totalTokenCount"] > 0 and "credential" not in json.dumps(r).lower().replace("credential\": \"read in process", "")
        for f in d.iterdir():
            text = f.read_text()
            assert not re.search(r"AIza[0-9A-Za-z_\-]{20,}|x-goog-api-key\s*[:=]\s*\S{10,}|GEMINI_API_KEY\s*=\s*\S+", text), (d.name, f.name)
        if (d / "proposal.json").exists():
            prop = json.loads((d / "proposal.json").read_text())
            assert r["proposal_sha256"] == hashlib.sha256(json.dumps(prop, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), d.name


@pytest.mark.skipif(not RUN_DIRS, reason="no recorded model runs in this checkout")
def test_recorded_run_outcomes_are_what_the_receipts_say():
    by = {d.name: json.loads((d / "receipt.json").read_text()) for d in RUN_DIRS}
    # attempts 1-2: the model's hidden thinking used the whole output budget and the JSON was cut off -> recorded as rejected, never repaired by hand
    for n in ("cantilever-gemini-1", "cantilever-gemini-2"):
        assert by[n]["finish_reason"] == "MAX_TOKENS" and by[n]["outcome"]["status"] == "model_output_rejected"
        assert by[n]["usage_reported_by_provider"]["thoughtsTokenCount"] > 0.9 * by[n]["generation"]["maxOutputTokens"] - 1000
    # attempt 3: a complete proposal; the checker found the model had dropped E*I from the law (dimension fault)
    a3 = by["cantilever-gemini-3"]
    assert a3["finish_reason"] == "STOP" and a3["generation"]["thinkingConfig"] == {"thinkingLevel": "low"} and a3["outcome"]["status"] == "invalid"
    resp3 = json.loads((RUNS / "cantilever-gemini-3" / "propose_response.json").read_text())
    c1 = next(d for d in resp3["dimension_report"] if d["constraint"] == "C1")
    assert c1["ok"] is False and c1["error"] == "lhs has dimension [m] but rhs has [kg m^4 s^-2]"
    # repair 1: division by a symbol is outside the grammar; repair 2: grammar-valid, solver then said unknown (kept as recorded)
    assert by["cantilever-gemini-3-repair"]["outcome"]["status"] == "unsupported_expression" and by["cantilever-gemini-3-repair"]["parent_checker_status"] == "invalid"
    assert by["cantilever-gemini-3-repair2"]["outcome"]["status"] == "unknown"
    assert by["oca2-gemini-1"]["outcome"]["status"] == "refused" and by["oca2-gemini-1"]["outcome"]["refusal_codes"] == ["CAUSAL_GENOTYPE_PHENOTYPE_NO_MECHANISM"]


@pytest.mark.skipif(not RUN_DIRS, reason="no recorded model runs in this checkout")
def test_recorded_requests_re_check_offline_and_the_repaired_law_now_checks():
    r3 = json.loads((RUNS / "cantilever-gemini-3" / "request.json").read_text())
    assert propose(r3)["status"] == "invalid"                                                         # the model's mistranslation is still caught
    r4 = json.loads((RUNS / "cantilever-gemini-3-repair2" / "request.json").read_text())
    body = propose(r4)
    c = body["checks"][0]
    w = {k: Fraction(v) for k, v in c["witness"].items()}
    # the model's repaired law C1: 3*E*I*w_C == P*L^3, C2: B == E*I. Hand check of the witness: 3*1e8*1e-14*(1/30) = 1e-7 = 100*(1/1000)^3
    assert body["status"] == "checked" and c["result"] == "sat" and 3 * w["E"] * w["I"] * w["w_C"] == w["P"] * w["L"] ** 3 and w["B"] == w["E"] * w["I"]
    rec = json.loads((RUNS / "cantilever-gemini-3-repair2" / "recheck_after_solver_change.json").read_text())
    assert rec["original_status"] == "unknown" and rec["recheck"]["status"] == "checked" and rec["request_sha256_unchanged"] is True


# ------------------------------------------------------------------ extraction harness: data in, no code, no credential leakage
def test_model_output_is_parsed_as_data_only():
    assert extract.parse_proposal('```json\n{"symbols": []}\n```') == {"symbols": []}
    for bad in ("not json", "[1,2]", '{"a": ', "__import__('os')", "{'a': 1}"):
        with pytest.raises(extract.ExtractError):
            extract.parse_proposal(bad)


def test_thinking_setting_and_prompt_limits():
    assert extract.thinking_config("level:low") == {"thinkingLevel": "low"} and extract.thinking_config("budget:0") == {"thinkingBudget": 0} and extract.thinking_config(None) is None
    for bad in ("level:extreme", "budget:-1", "yolo"):
        with pytest.raises(extract.ExtractError):
            extract.thinking_config(bad)
    with pytest.raises(extract.ExtractError):
        extract.build_prompt("claim", "x" * (extract.MAX_PASSAGE_CHARS + 1))
    prompt, sha = extract.build_prompt("claim text", "passage text")
    assert sha == hashlib.sha256(b"passage text").hexdigest() and "No functions" in prompt and "never" not in prompt.lower().split("passage")[0][:0]


def test_provider_errors_never_contain_the_credential(monkeypatch):
    import urllib.error
    monkeypatch.setattr(extract, "_key", lambda: "SECRET-KEY-VALUE")
    def boom(req, timeout=0):
        raise urllib.error.HTTPError("https://x", 403, "bad key SECRET-KEY-VALUE", {}, None)
    monkeypatch.setattr(extract.urllib.request, "urlopen", boom)
    monkeypatch.setattr(extract.time, "sleep", lambda s: None)
    with pytest.raises(extract.ExtractError) as e:
        extract.call("prompt")
    assert "SECRET" not in str(e.value)
    monkeypatch.setattr(extract, "_key", lambda: (_ for _ in ()).throw(extract.ExtractError("no model credential is configured for this process")))
    with pytest.raises(extract.ExtractError, match="no model credential"):
        extract.call("prompt")


def test_repair_prompt_passes_only_checker_measurements():
    resp = {"status": "invalid", "dimension_report": [{"constraint": "C1", "ok": False, "error": "lhs has dimension [m] but rhs has [kg]"}, {"constraint": "C2", "ok": True}], "refusals": []}
    p = extract.repair_prompt("BASE", {"symbols": []}, resp)
    assert "constraint C1: lhs has dimension [m] but rhs has [kg]" in p and "C2" not in p.split("THE OFFLINE CHECKER REPORTED")[1].split("Return")[0] and "do not weaken a constraint" in p
    err = {"schema": "frontier.formalize.error/1", "code": "unsupported_expression", "detail": "C1: '/' takes [term, nonzero rational literal]"}
    assert "Division is only allowed by a rational LITERAL" in extract.repair_prompt("BASE", {}, err)


# ------------------------------------------------------------------ the Lean theorem: a parameterized statement with its receipt (verified OFFLINE; recompile is opt-in)
LEAN = ROOT / "engineering" / "formalize" / "lean"


def test_lean_receipt_matches_the_sources_and_the_theorem_is_not_vacuous():
    rec = json.loads((LEAN / "RECEIPT.json").read_text())
    pos, neg = LEAN / "CantileverGuard.lean", LEAN / "CantileverGuard_negative_corrupt_law.lean"
    assert rec["lean"] == "ran" and rec["files_sha256"] == {pos.name: hashlib.sha256(pos.read_bytes()).hexdigest(), neg.name: hashlib.sha256(neg.read_bytes()).hexdigest()}
    assert rec["positive"]["exit"] == 0 and rec["positive"]["only_standard_axioms"] is True
    assert set(rec["positive"]["theorems"]) == {"cantilever_guard", "cantilever_guard_hypotheses_satisfiable", "cantilever_guard_needs_stiffness"}
    assert rec["negative_corrupt_law"]["exit"] != 0 and rec["negative_corrupt_law"]["rejected"] is True            # the corrupted law fails to compile with the same proof
    assert rec["lean_version"].startswith("Lean (version 4.35.0") and rec["provenance"]["mathlib_rev"]
    text = pos.read_text()
    assert not re.search(r"\bsorry\b|native_decide|^\s*axiom\b|by decide|:= by rfl\b", text, re.M)                  # no cheats, no constant decide proofs
    assert "theorem cantilever_guard {P L E I d : ℝ}" in text and "∃ P L E I d : ℝ" in text and "¬ (∀ P L E I d : ℝ" in text      # universal, satisfiable, and necessary
    assert "hand-authored" in rec["statement_origin"] and "not derived mechanically" in rec["statement_origin"] and "anything about biology" in rec["does_not_prove"]
    assert "/tmp" not in json.dumps(rec) and "/data" not in json.dumps(rec)


@pytest.mark.skipif(not __import__("os").environ.get("FRONTIER_RUN_LEAN"), reason="set FRONTIER_RUN_LEAN=1 to recompile (about 1-2 minutes, 12G cap)")
def test_lean_files_recompile():
    from engineering.formalize import lean_run
    out = lean_run.run()
    assert out["lean"] == "ran" and out["positive"]["exit"] == 0 and out["negative_corrupt_law"]["rejected"] is True
