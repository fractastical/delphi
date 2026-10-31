"""propose(request) -> response: the pure library entry point behind POST /api/formalize/propose.

Pipeline: validate (grammar) -> refusal gates -> dimension report -> satisfiability + independent witness
check -> named negative/mutation controls -> response.  The solving step runs in an offline capped worker
(`python -m frontier.formalize.worker`, same interpreter, stripped env, wall-clock cap, at most 2 concurrent).
Model-supplied content is parsed as JSON data only; nothing is executed or evaluated.
"""
from __future__ import annotations

import copy
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import dims as D
from . import leangen, refusals
from .grammar import (LIMITS, SCHEMA_ERROR, SCHEMA_RESPONSE, GrammarError, canonical, is_literal, parse_literal,
                      sha256_obj, term_to_text, validate_request)
from .solve import Model, check, holds
from ..worker_limits import Slots

SLOTS = Slots(2)                 # also draws on the process-wide worker budget in worker_limits
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_ARGV = [sys.executable, "-s", "-m", "frontier.formalize.worker"]  # tests may point this at a labelled stub
ASSUMED_SCOPE = ("Only the constraints exactly as written, under the declared symbols, units and domains. Not a claim that the "
                 "constraints encode the source text, not a claim about biological function, and nothing outside the "
                 "declared symbols and domains.")
NOT_ESTABLISHED = ["translation fidelity to the source", "biological function",
                   "anything outside the declared symbols/domains"]
HTTP_STATUS = {"request_too_large": 413, "unknown_field": 400, "unsupported_expression": 422, "solver_busy": 429,
               "solver_unavailable": 503}


def error_body(code: str, detail: str = "") -> dict:
    assert code in HTTP_STATUS, code
    b = {"schema": SCHEMA_ERROR, "code": code, "calibrated": False}
    if detail:
        b["detail"] = detail[:300]
    return b


def http_status(body: dict) -> int:
    return HTTP_STATUS.get(body.get("code"), 500) if body.get("schema") == SCHEMA_ERROR else 200


# ---------------------------------------------------------------- the pure computation (runs inside the worker)
def _dim_report(ctx: dict):
    rep, sdim, problems = [], {}, []
    for n, s in ctx["symbols"].items():
        try:
            sdim[n] = D.parse_unit(s["unit"])
        except D.UnitError as e:
            problems.append(f"symbol {n}: {e}")
    if problems:
        return None, None, problems
    for c in ctx["constraints"]:
        if c.get("dimension_check", True) is False:
            rep.append({"constraint": c["id"], "ok": None, "skipped": True, "dims": None})
            continue
        try:
            d = D.constraint_dim(c["expr"], sdim, is_literal, parse_literal)
            rep.append({"constraint": c["id"], "ok": True, "dims": D.fmt(d)})
        except D.DimError as e:
            rep.append({"constraint": c["id"], "ok": False, "dims": None, "error": str(e)})
    return rep, sdim, problems


def _flip(op: str) -> str:
    return {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "=="}[op]


def _strict_negation(op: str) -> str:
    return {"<": ">=", "<=": ">", ">": "<=", ">=": "<", "==": "<"}[op]  # "==" negated is a disjunction; use "<" branch


def _pows(term, path=()):
    """Yield (path-to-pow-node) for each pow node in a term."""
    if isinstance(term, dict):
        if term["op"] == "pow":
            yield path
        else:
            for i, a in enumerate(term["args"]):
                yield from _pows(a, path + (i,))


def _get(term, path):
    for i in path:
        term = term["args"][i]
    return term


def _mutated_ctx(req: dict, edit) -> dict | None:
    r = copy.deepcopy(req)
    ok = edit(r)
    if not ok:
        return None
    try:
        return validate_request(r)
    except GrammarError:
        return None


def controls(req: dict, ctx: dict, base_checks: dict, dim_rep: list) -> list:
    """Named controls.  Each has a pre-declared `expected`; `observed` is measured; they never change the verdict."""
    out = []
    cons = ctx["constraints"]
    sdim = {n: D.parse_unit(s["unit"]) for n, s in ctx["symbols"].items()}

    def dim_ok(c2ctx) -> bool:
        sd = {n: D.parse_unit(s["unit"]) for n, s in c2ctx["symbols"].items()}
        for c in c2ctx["constraints"]:
            if c.get("dimension_check", True) is False:
                continue
            try:
                D.constraint_dim(c["expr"], sd, is_literal, parse_literal)
            except D.DimError:
                return False
        return True

    # 1. exponent mutants on equality/inequality laws: expected to be rejected by the dimension check
    n_exp = 0
    for ci, c in enumerate(req["proposal"]["constraints"]):
        if c.get("dimension_check", True) is False:
            continue
        for side in ("lhs", "rhs"):
            for path in _pows(c["expr"][side]):
                if n_exp >= 6:
                    break

                def edit(r, ci=ci, side=side, path=path):
                    node = _get(r["proposal"]["constraints"][ci]["expr"][side], path)
                    node["exp"] = node["exp"] + 1 if node["exp"] < 4 else node["exp"] - 1
                    return True
                m = _mutated_ctx(req, edit)
                if m is None:
                    continue
                n_exp += 1
                node = _get(c["expr"][side], path)
                out.append({"name": f"exponent_mutant:{c['id']}.{side}:{node['base']}^{node['exp']}->{node['exp'] + 1 if node['exp'] < 4 else node['exp'] - 1}",
                            "kind": "dimension", "expected": "rejected", "observed": "rejected" if not dim_ok(m) else "accepted",
                            "note": "a dimensionless base symbol would not be detected by units"})
    # 2. wrong-unit mutant: change the unit of each symbol used by the first dimension-checked constraint
    first = next((c for c in req["proposal"]["constraints"] if c.get("dimension_check", True) is not False), None)
    if first:
        used = sorted({n for n in ctx["names"] if n in canonical(first).decode()})[:3]
        for n in used:
            def edit(r, n=n):
                for s in r["proposal"]["symbols"]:
                    if s["name"] == n:
                        s["unit"] = "s" if s.get("unit", "1") in ("1", "") else "1"
                        return True
                return False
            m = _mutated_ctx(req, edit)
            if m is not None:
                out.append({"name": f"wrong_unit:{n}", "kind": "dimension", "expected": "rejected",
                            "observed": "rejected" if not dim_ok(m) else "accepted"})
    # 3. witness-based controls (only if base was sat with an exact witness)
    model = Model(ctx)
    wit = base_checks.get("witness")
    if base_checks.get("result") == "sat" and wit:
        from fractions import Fraction
        pt = [Fraction(wit[n]) for n in ctx["names"]]
        out.append({"name": "witness_independent_recheck", "kind": "positive", "expected": "accepted",
                    "observed": "accepted" if not model.violations(pt) else "rejected"})
        if any(op == "==" for _, op, _ in model.cons):
            pt2 = list(pt)
            for i, n in enumerate(ctx["names"]):
                if any(p.degree_in(i) for _, op, p in model.cons if op == "=="):
                    pt2[i] = pt2[i] + (1 if not ctx["symbols"][n]["integer"] else 1)
                    break
            out.append({"name": "perturbed_witness_rejected", "kind": "witness", "expected": "rejected",
                        "observed": "rejected" if model.violations(pt2) else "accepted",
                        "note": "one symbol of the witness increased by 1 unit of its own declared unit"})
        # flip each inequality / guard: original witness must fail strictly
        for c in req["proposal"]["constraints"]:
            op = c["expr"]["op"]
            if op == "==":
                continue

            def edit(r, cid=c["id"]):
                for k in r["proposal"]["constraints"]:
                    if k["id"] == cid:
                        k["expr"]["op"] = _strict_negation(k["expr"]["op"])
                        return True
                return False
            m = _mutated_ctx(req, edit)
            if m is None:
                continue
            mm = Model(m)
            strict_before = any(abs(p.eval(pt)) == 0 for cid2, _, p in model.cons if cid2 == c["id"])
            out.append({"name": f"negate_constraint:{c['id']}", "kind": "mutation", "expected": "witness_rejected",
                        "observed": "witness_rejected" if mm.violations(pt) else "witness_still_accepted",
                        "note": "strict negation of this constraint: a witness on its boundary violates it too" if strict_before else "strict negation of this constraint"})
        # drop each non-equality constraint: is it binding? search for a point that satisfies the rest but violates it
        for c in req["proposal"]["constraints"]:
            op = c["expr"]["op"]
            if op == "==":
                continue

            def edit(r, cid=c["id"]):
                for k in r["proposal"]["constraints"]:
                    if k["id"] == cid:
                        k["expr"]["op"] = _strict_negation(k["expr"]["op"])
                        return True
                return False
            m = _mutated_ctx(req, edit)
            if m is None:
                continue
            res = check(Model(m), timeout_s=1.5)
            out.append({"name": f"drop_guard_binding:{c['id']}", "kind": "probe", "expected": None,
                        "observed": {"sat": "binding", "unsat": "redundant_given_the_others"}.get(res["result"], "undetermined"),
                        "detail": ("a point exists that satisfies every other constraint and violates this one: dropping it would admit it"
                                   if res["result"] == "sat" else "no such point found: this constraint is redundant given the others"
                                   if res["result"] == "unsat" else "undetermined"),
                        **({"witness_violating_it": res["witness"]} if res.get("witness") else {})})
    elif base_checks.get("result") == "unsat" and len(cons) <= 8:
        # unsat core by deletion: which dropped constraints make it satisfiable
        flips = []
        for c in req["proposal"]["constraints"]:
            def edit(r, cid=c["id"]):
                r["proposal"]["constraints"] = [k for k in r["proposal"]["constraints"] if k["id"] != cid]
                return True
            m = _mutated_ctx(req, edit)
            if m is None:
                continue
            res = check(Model(m), timeout_s=1.0)
            flips.append((c["id"], res["result"]))
        for cid, r in flips:
            out.append({"name": f"drop_constraint:{cid}", "kind": "probe", "expected": None,
                        "observed": "in_a_conflict_core" if r == "sat" else ("not_needed_for_the_conflict" if r == "unsat" else "undetermined"),
                        "note": "a probe, not a control: removing a member of a minimal conflict turns unsat into sat; a redundant constraint does not"})
    return out


def compute(req: dict) -> dict:
    """Pure function: request -> response (no subprocess).  Called by the worker; also usable in tests."""
    ctx = validate_request(req)
    resp = {
        "schema": SCHEMA_RESPONSE, "status": "unknown",
        "proposal_sha256": sha256_obj(req["proposal"]), "request_sha256": sha256_obj(req),
        "calibrated": False, "evidence_kind": "none", "assumed_scope": ASSUMED_SCOPE,
        "dimension_report": [], "checks": [], "negative_controls": [], "refusals": [],
        "unresolved_translation": [dict(u) for u in req["proposal"].get("unresolved", [])],
        "lean": "not_run", "next_questions": [], "not_established": list(NOT_ESTABLISHED), "limits": dict(LIMITS),
        "source_mapping_declared": [m.get("element") for m in req["proposal"].get("source_mapping", [])],
    }
    refs = refusals.gate(ctx)
    resp["refusals"] = refs
    dim_rep, sdim, problems = _dim_report(ctx)
    if problems:
        resp["status"] = "invalid"
        resp["invalid_reasons"] = problems
        return resp
    resp["dimension_report"] = dim_rep
    # constraints that nothing maps to the source: say so, do not hide
    mapped = {m.get("element") for m in req["proposal"].get("source_mapping", [])}
    unmapped = [c["id"] for c in ctx["constraints"] if c["id"] not in mapped]
    if unmapped:
        resp["unresolved_translation"].append({"id": "UNMAPPED", "question": f"constraints without a source_mapping quote: {unmapped}"})
    model = Model(ctx)
    chk = check(model, timeout_s=5.0) if ctx["constraints"] else {"constraint": "ALL", "result": "unknown", "method": "none", "independent_check": "none", "note": "no constraints"}
    resp["checks"] = [chk]
    dim_bad = [r["constraint"] for r in dim_rep if r["ok"] is False]
    for u in [s for s in ctx["symbols"].values() if s["status"] == "unknown"]:
        resp["unresolved_translation"].append({"id": f"UNKNOWN_{u['name']}", "question": f"symbol {u['name']} has status 'unknown': its value/range is not given by the source"})
    if refs:
        resp["status"] = "refused"
        resp["separated_checkable_facts"] = {"note": "constraints in the proposal checked as plain arithmetic/sequence facts; they are NOT the refused causal claim",
                                              "checks": [chk], "dimension_report": dim_rep}
        resp["checks"] = []
        resp["dimension_report"] = []
        resp["causal_claim_formalized"] = False
    elif dim_bad:
        resp["status"] = "invalid"
        resp["invalid_reasons"] = [f"dimension check failed for {dim_bad}: " + "; ".join(r["error"] for r in dim_rep if r["ok"] is False)]
    elif chk["result"] in ("sat", "unsat"):
        resp["status"] = "checked"
        resp["evidence_kind"] = "formal"
    else:
        resp["status"] = "unknown"
    if req.get("options", {}).get("controls", True) and resp["status"] in ("checked", "invalid", "unknown") and ctx["constraints"]:
        try:
            # Mutation controls only mean something when the base is dimensionally valid: against an already-invalid law they would
            # compare mutants to a faulty base and report "expected rejected" outcomes whose premise does not hold.
            resp["negative_controls"] = controls(req, ctx, chk, dim_rep) if not dim_bad else []
            if dim_bad:
                resp["controls_skipped_reason"] = "the proposal as written already fails the dimension check; mutation controls would compare against a faulty base"
        except Exception as e:  # noqa: BLE001 - controls must never break the verdict
            resp["negative_controls"] = [{"name": "controls_failed", "expected": "n/a", "observed": f"error:{type(e).__name__}"}]
    # a control that fails to discriminate is reported, never hidden
    ctl = [c for c in resp["negative_controls"] if c.get("expected") is not None]
    resp["controls_summary"] = {"n": len(ctl), "as_expected": sum(1 for c in ctl if c.get("expected") == c.get("observed")),
                                "probes": len(resp["negative_controls"]) - len(ctl),
                                "meaning": "controls have a pre-declared expectation; probes (kind 'probe') are measurements with none, e.g. which constraints bind"}
    if resp["refusals"] == [] and dim_bad:
        resp["rejected_by_dimension_check"] = dim_bad
    if req.get("options", {}).get("lean_statement") and resp["status"] == "checked":
        okc = [c["id"] for c, r in zip(ctx["constraints"], dim_rep) if r["ok"]]
        if okc:
            g = leangen.generate(ctx, only=okc)
            resp["lean_statement"] = {"text": g["text"], "sha256": g["sha256"], "theorems": g["theorems"],
                                      "status": "generated_not_compiled",
                                      "meaning": "unit-rescaling invariance of each constraint as written; compile separately (engineering/formalize/lean_run.py)"}
    resp["next_questions"] = _next_questions(ctx, resp)
    return resp


def _next_questions(ctx, resp) -> list:
    q = []
    for u in resp["unresolved_translation"]:
        q.append(u.get("question", ""))
    if resp["status"] == "refused":
        q.append("What mechanistic mapping (with declared quantities) connects the lesion to the trait, and what evidence class supports each link?")
    if resp["status"] in ("checked", "unknown"):
        q.append("Does each symbol's unit and domain match the source's definition? (this tool cannot check translation fidelity)")
        q.append("Is the witness (if any) inside the empirically relevant range, or only inside the declared box?")
    if resp["status"] == "invalid":
        q.append("Which exponent or unit in the proposed law disagrees with the source equation?")
    return [x for x in q if x][:8]


# ---------------------------------------------------------------- the capped worker driver
def _worker_env() -> dict:
    return {"PATH": "/usr/bin:/bin", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(REPO_ROOT), "LANG": "C.UTF-8"}


def propose(request, *, timeout_s: float | None = None) -> dict:
    """Validate and check a proposal.  Always returns a dict: a response/1 or an error/1 body.  Never raises on input."""
    try:
        raw_len = len(canonical(request))
    except (TypeError, ValueError, RecursionError):                       # non-finite numbers, non-JSON values, or a nesting bomb
        return error_body("unsupported_expression", "request is not finite JSON data of bounded depth")
    if raw_len > LIMITS["max_bytes"]:
        return error_body("request_too_large", f"{raw_len} > {LIMITS['max_bytes']} bytes")
    try:
        validate_request(request)
    except GrammarError as e:
        return error_body(e.code, e.detail)
    except Exception as e:  # noqa: BLE001 - propose() never raises on input, whatever shape it has
        return error_body("unsupported_expression", f"request could not be validated ({type(e).__name__})")
    if not SLOTS.acquire(blocking=False):
        return error_body("solver_busy", "2 of 2 worker slots in use")
    t = float(LIMITS["timeout_s"] if timeout_s is None else timeout_s)
    t0 = time.monotonic()
    try:
        p = subprocess.Popen(WORKER_ARGV, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=_worker_env(), cwd=str(REPO_ROOT), start_new_session=True)
        try:
            out, err = p.communicate(json.dumps(request).encode("utf-8"), timeout=t)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.communicate()
            return _timeout_response(request, t)
    except OSError as e:
        return error_body("solver_unavailable", f"worker could not start: {type(e).__name__}")
    finally:
        SLOTS.release()
    try:
        body = json.loads(out.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return error_body("solver_unavailable", "worker returned no parseable response")
    if p.returncode != 0 and body.get("schema") != SCHEMA_ERROR:
        return error_body("solver_unavailable", f"worker exit {p.returncode}")
    if body.get("schema") == SCHEMA_RESPONSE:
        body["worker_wall_s"] = round(time.monotonic() - t0, 3)
    return body


def _timeout_response(request: dict, t: float) -> dict:
    return {"schema": SCHEMA_RESPONSE, "status": "unknown", "proposal_sha256": sha256_obj(request["proposal"]),
            "request_sha256": sha256_obj(request), "calibrated": False, "evidence_kind": "none", "assumed_scope": ASSUMED_SCOPE,
            "dimension_report": [], "checks": [{"constraint": "ALL", "result": "unknown", "method": "none", "independent_check": "none",
                                                "note": f"solver wall-clock limit {t:g}s reached; worker killed; no verdict"}],
            "negative_controls": [], "refusals": [], "unresolved_translation": [], "lean": "not_run",
            "next_questions": ["Simplify the constraint set or tighten the symbol domains."],
            "not_established": list(NOT_ESTABLISHED), "limits": dict(LIMITS), "timed_out": True}
