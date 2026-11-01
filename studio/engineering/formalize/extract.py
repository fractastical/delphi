"""One bounded LLM extraction: a pinned PUBLIC passage -> a typed constraint PROPOSAL (JSON data) -> the same checked pipeline as any other proposal.

What this is: an actual model call (Google Generative Language `generateContent`) whose output is parsed as JSON DATA and handed to
`frontier.formalize.propose`. The model never produces code; whatever it writes is validated against the bounded declarative grammar and
rejected otherwise. A rejected or invalid proposal is a RESULT and is recorded as such.

What this is not: a proof that the English was translated faithfully. Fidelity stays an open question the pipeline lists; `checked` means only that the
constraints as written are dimensionally consistent and satisfiable/unsatisfiable under the declared symbols.

Credential handling (same pattern as `frontier.discovery.GeminiEmbedder`): the key is read IN PROCESS from GEMINI_API_KEY or an env file, goes only
into the `x-goog-api-key` header, and is never logged, printed or written; provider error text is scrubbed of it. Usage is whatever the provider
reports (`usageMetadata`); no dollar figure is invented.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADAPTER = "engineering.formalize.extract/1"
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-3-flash-preview"          # the model this repository's earlier Gemini runs used (findings/gemini_assess_problems.py)
MAX_OUTPUT_TOKENS = 12000                           # counts hidden thinking tokens too; 4000 was truncated by thinking in the first recorded attempt (runs/cantilever-gemini-1)
MAX_PASSAGE_CHARS = 3000
MAX_ATTEMPTS = 2                                   # transport failures only; a bad PROPOSAL is never retried silently

GRAMMAR_SPEC = """TERM GRAMMAR (the only expressions allowed; anything else is rejected, not interpreted):
  term := a rational literal as a STRING ("3", "-1/2", "0.25", "1e-6"), OR a declared symbol name as a STRING,
          OR {"op":"+"|"-"|"*","args":[term,...]}, OR {"op":"/","args":[term, rational literal STRING]},
          OR {"op":"pow","base":"<symbol name>","exp":<integer 0..4>}
  constraint expr := {"op":"<"|"<="|">"|">="|"==","lhs":term,"rhs":term}
  at most 64 nodes. No functions, no sqrt, no variables you did not declare, no code.
UNITS: closed table only: SI base kg m s A K mol cd, and N Pa J W Hz C V; products with spaces, powers with ^ ("kg m s^-2"), "1" for dimensionless.
  NO prefixed units (no cm, mm, MPa): convert numerically to SI yourself and say so in an assumption.
SYMBOL: {"name":str(<=16 chars),"unit":str,"domain":{"lo":str,"hi":str,"lo_open":bool,"hi_open":bool},"status":"given"|"declared"|"unknown","source_ref":str,"integer":bool?}
  status "given" = the value or range appears in the passage; "declared" = YOU chose a range (say so in source_ref); "unknown" = the quantity being constrained."""

EXAMPLE = {"symbols": [{"name": "F", "unit": "N", "domain": {"lo": "0", "hi": "10", "lo_open": True}, "status": "declared", "source_ref": "range chosen by the proposer"},
                       {"name": "k", "unit": "N m^-1", "domain": {"lo": "1", "hi": "100"}, "status": "declared", "source_ref": "range chosen by the proposer"},
                       {"name": "x", "unit": "m", "domain": {"lo": "0", "hi": "1", "lo_open": True}, "status": "unknown", "source_ref": "extension"}],
           "assumptions": [{"id": "A1", "text": "Linear spring, small extension.", "kind": "modelling"}],
           "constraints": [{"id": "C1", "kind": "equality", "dimension_check": True, "source_ref": "F = k x",
                            "expr": {"op": "==", "lhs": "F", "rhs": {"op": "*", "args": ["k", "x"]}}}],
           "source_mapping": [{"element": "C1", "quote": "F = kx", "locator": "example only"}],
           "unresolved": [{"id": "U1", "question": "Is the spring linear over the whole range?"}]}

PROMPT = """You turn a short PUBLIC source passage into a typed mathematical PROPOSAL, as JSON data only. You do not write code. A separate offline checker will
test your constraints for dimensional consistency and satisfiability; it cannot tell whether you translated the passage faithfully, so you must say what you
were unsure of.

Rules:
1. Encode ONLY relations that the passage actually states (formulas, ranges, limits). Quote the exact source text (<=200 chars) for each constraint in source_mapping.
2. Every symbol needs a unit from the closed table and a domain. If the passage does not give a range, choose a plausible range, mark status "declared", and say
   in source_ref that YOU chose it. Never present a chosen range as sourced.
3. Put every translation choice you had to make, every undefined symbol and every modelling doubt in "unresolved". If the passage claims a CAUSE (gene or
   mutation explains a trait), do not invent a mechanism: encode nothing causal and list the missing mechanism in "unresolved".
4. Output exactly one JSON object with keys: symbols, assumptions, constraints, source_mapping, unresolved. No prose outside it.

{grammar}

EXAMPLE of the shape (a different, trivial topic):
{example}

CLAIM: {claim}

PASSAGE (verbatim, public; sha256 {sha}):
\"\"\"
{passage}
\"\"\"
"""


class ExtractError(RuntimeError):
    pass


def _key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        path = Path(os.environ.get("FRONTIER_GEMINI_ENV_FILE") or Path.home() / ".config/morphoswarm/gemini.env")
        try:
            for line in path.read_text().splitlines():
                m = re.match(r"^GEMINI_API_KEY=(.*)$", line.strip())
                if m:
                    key = m.group(1).strip().strip("\"'")
        except OSError:
            pass
    if not key:
        raise ExtractError("no model credential is configured for this process")
    return key


def build_prompt(claim: str, passage: str) -> tuple[str, str]:
    if len(passage) > MAX_PASSAGE_CHARS:
        raise ExtractError(f"passage longer than {MAX_PASSAGE_CHARS} characters")
    sha = sha256(passage.encode()).hexdigest()
    return PROMPT.format(grammar=GRAMMAR_SPEC, example=json.dumps(EXAMPLE, indent=1), claim=claim, sha=sha, passage=passage), sha


def thinking_config(spec: str | None) -> dict | None:
    """"level:low" -> thinkingLevel (Gemini 3 family); "budget:0" -> thinkingBudget (token budget). None -> provider default. Recorded in the receipt."""
    if not spec:
        return None
    kind, _, val = spec.partition(":")
    if kind == "level" and val in ("low", "high", "minimal", "medium"):
        return {"thinkingLevel": val}
    if kind == "budget" and val.isdigit():
        return {"thinkingBudget": int(val)}
    raise ExtractError(f"unsupported thinking setting {spec!r}")


def call(prompt: str, model: str = DEFAULT_MODEL, timeout: float = 120.0, max_output_tokens: int = MAX_OUTPUT_TOKENS, thinking: str | None = None) -> dict:
    """One provider call. Returns {raw_response, text, finish_reason, usage, model_version, wall_s, attempts}. The key is never in the result or in error text."""
    key = _key()
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": max_output_tokens, "responseMimeType": "application/json"}}
    if thinking_config(thinking):
        body["generationConfig"]["thinkingConfig"] = thinking_config(thinking)
    data = json.dumps(body).encode()
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(URL.format(model=model), data=data, method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key, "User-Agent": "delphi-frontier-formalize/1"})
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.loads(r.read())
            cand = (resp.get("candidates") or [{}])[0]
            text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
            return {"raw_response": resp, "text": text, "finish_reason": cand.get("finishReason"), "usage": resp.get("usageMetadata"),
                    "model_version": resp.get("modelVersion"), "wall_s": round(time.monotonic() - t0, 2), "attempts": attempt}
        except urllib.error.HTTPError as e:
            last = f"provider answered HTTP {e.code}"
            if e.code < 500 and e.code != 429:
                break
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            last = f"provider call failed: {type(e).__name__}"
        time.sleep(3 * attempt)
    raise ExtractError(str(last).replace(key, "<key>"))


def parse_proposal(text: str) -> dict:
    """The model's text as JSON DATA. Anything that is not a single JSON object is an extraction failure, never evaluated."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        obj = json.loads(t)
    except json.JSONDecodeError as e:
        raise ExtractError(f"model output is not valid JSON: {e.msg}") from None
    if not isinstance(obj, dict):
        raise ExtractError("model output is not a JSON object")
    return obj


def run(case_id: str, claim_text: str, passage_path: Path, source_ref: str, locator: str, out_dir: Path, model: str = DEFAULT_MODEL, dry_run: bool = False,
        max_output_tokens: int = MAX_OUTPUT_TOKENS, thinking: str | None = None) -> dict:
    from frontier.formalize import propose
    passage = passage_path.read_text(encoding="utf-8")
    prompt, psha = build_prompt(claim_text, passage)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prompt.txt").write_text(prompt)
    receipt = {"schema": "engineering.formalize.extraction-receipt/1", "adapter": ADAPTER, "case": case_id, "provider": "google-generative-language", "model_requested": model,
               "endpoint": URL.format(model=model), "prompt_sha256": sha256(prompt.encode()).hexdigest(), "passage_sha256": psha, "passage_file": passage_path.name,
               "source_ref": source_ref, "generation": {"temperature": 0, "maxOutputTokens": max_output_tokens, "responseMimeType": "application/json", "thinkingConfig": thinking_config(thinking)},
               "credential": "read in process from environment or the configured env file; sent only in a request header; never logged, printed or written",
               "model_content_handling": "parsed as JSON data; validated against the bounded declarative grammar; never executed or evaluated"}
    if dry_run:
        receipt["dry_run"] = True
        return receipt
    res = call(prompt, model, max_output_tokens=max_output_tokens, thinking=thinking)
    receipt.update({"model_version_reported": res["model_version"], "finish_reason": res["finish_reason"], "usage_reported_by_provider": res["usage"],
                    "wall_s": res["wall_s"], "attempts": res["attempts"], "response_sha256": sha256(res["text"].encode()).hexdigest()})
    (out_dir / "response.raw.txt").write_text(res["text"])
    try:
        proposal = parse_proposal(res["text"])
    except ExtractError as e:
        receipt["outcome"] = {"stage": "parse", "status": "model_output_rejected", "detail": str(e)}
        (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n")
        return receipt
    (out_dir / "proposal.json").write_text(json.dumps(proposal, indent=1, sort_keys=True) + "\n")
    request = {"schema": "frontier.formalize.request/1",
               "claim": {"id": case_id, "text": claim_text[:1000], "source": {"ref": source_ref, "locator": locator, "text_sha256": psha}},
               "proposal": proposal, "options": {"controls": True, "lean_statement": True}}
    (out_dir / "request.json").write_text(json.dumps(request, indent=1, sort_keys=True) + "\n")
    response = propose(request)
    (out_dir / "propose_response.json").write_text(json.dumps(response, indent=1, sort_keys=True) + "\n")
    receipt["proposal_sha256"] = sha256(json.dumps(proposal, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt["outcome"] = {"stage": "propose", "status": response.get("status", response.get("code")), "schema": response.get("schema"),
                          "refusal_codes": [r.get("code") for r in response.get("refusals", [])], "error_detail": response.get("detail")}
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n")
    return receipt


def repair_prompt(base_prompt: str, previous: dict, response: dict) -> str:
    """Feed the checker's own findings back, as data. Only what the checker measured is passed: dimension errors and failed or rejected controls."""
    findings = [f"constraint {d['constraint']}: {d.get('error')}" for d in response.get("dimension_report", []) if d.get("ok") is False]
    findings += [f"refusal {r.get('code')}: {r.get('reason')}" for r in response.get("refusals", [])]
    if str(response.get("schema", "")).endswith("error/1"):
        findings.append(f"the grammar rejected the proposal ({response.get('code')}): {response.get('detail')}. Division is only allowed by a rational LITERAL; "
                        "express a law like w = P*L^3/(3*E*I) in multiplied-out form, e.g. 3*E*I*w == P*L^3.")
    return (base_prompt + "\n\nYOUR PREVIOUS PROPOSAL (JSON):\n" + json.dumps(previous, sort_keys=True) + "\n\nTHE OFFLINE CHECKER REPORTED (status "
            + str(response.get("status")) + "):\n" + "\n".join("- " + f for f in findings) + "\n\nReturn a corrected full proposal as one JSON object with the same keys. "
            "Change only what is needed to fix what the checker reported; do not weaken a constraint merely to make it pass; keep unresolved questions honest.\n")


def run_repair(parent_dir: Path, out_dir: Path, model: str = DEFAULT_MODEL, max_output_tokens: int = MAX_OUTPUT_TOKENS, thinking: str | None = None) -> dict:
    """One bounded repair round after a checker rejection. The parent's receipt, proposal and checker response are inputs; the result is recorded like any run."""
    from frontier.formalize import propose
    parent_receipt = json.loads((parent_dir / "receipt.json").read_text())
    previous = json.loads((parent_dir / "proposal.json").read_text())
    response0 = json.loads((parent_dir / "propose_response.json").read_text())
    request0 = json.loads((parent_dir / "request.json").read_text())
    prompt = repair_prompt((parent_dir / "prompt.txt").read_text(), previous, response0)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prompt.txt").write_text(prompt)
    receipt = {"schema": "engineering.formalize.extraction-receipt/1", "adapter": ADAPTER, "case": parent_receipt["case"], "round": "repair", "repair_of": parent_dir.name,
               "parent_prompt_sha256": parent_receipt["prompt_sha256"], "parent_proposal_sha256": parent_receipt.get("proposal_sha256"),
               "parent_checker_status": response0.get("status", response0.get("code")), "provider": "google-generative-language", "model_requested": model, "prompt_sha256": sha256(prompt.encode()).hexdigest(),
               "passage_sha256": parent_receipt["passage_sha256"], "generation": {"temperature": 0, "maxOutputTokens": max_output_tokens, "responseMimeType": "application/json", "thinkingConfig": thinking_config(thinking)},
               "model_content_handling": "parsed as JSON data; validated against the bounded declarative grammar; never executed or evaluated"}
    res = call(prompt, model, max_output_tokens=max_output_tokens, thinking=thinking)
    receipt.update({"model_version_reported": res["model_version"], "finish_reason": res["finish_reason"], "usage_reported_by_provider": res["usage"], "wall_s": res["wall_s"],
                    "attempts": res["attempts"], "response_sha256": sha256(res["text"].encode()).hexdigest()})
    (out_dir / "response.raw.txt").write_text(res["text"])
    try:
        proposal = parse_proposal(res["text"])
    except ExtractError as e:
        receipt["outcome"] = {"stage": "parse", "status": "model_output_rejected", "detail": str(e)}
        (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n")
        return receipt
    (out_dir / "proposal.json").write_text(json.dumps(proposal, indent=1, sort_keys=True) + "\n")
    request = {**request0, "proposal": proposal}
    (out_dir / "request.json").write_text(json.dumps(request, indent=1, sort_keys=True) + "\n")
    response = propose(request)
    (out_dir / "propose_response.json").write_text(json.dumps(response, indent=1, sort_keys=True) + "\n")
    receipt["proposal_sha256"] = sha256(json.dumps(proposal, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt["outcome"] = {"stage": "propose", "status": response.get("status", response.get("code")), "schema": response.get("schema"),
                          "refusal_codes": [r.get("code") for r in response.get("refusals", [])], "error_detail": response.get("detail")}
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n")
    return receipt


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engineering.formalize.extract")
    ap.add_argument("--case", choices=["cantilever", "oca2"])
    ap.add_argument("--repair-of", default=None, help="directory of a prior run whose checker rejection is fed back for one repair round")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-output-tokens", type=int, default=MAX_OUTPUT_TOKENS)
    ap.add_argument("--thinking", default=None, help="level:low | budget:N (recorded in the receipt)")
    a = ap.parse_args(argv)
    if a.repair_of:
        r = run_repair(Path(a.repair_of), Path(a.out), a.model, a.max_output_tokens, a.thinking)
        print(json.dumps({k: r.get(k) for k in ("case", "round", "repair_of", "parent_checker_status", "usage_reported_by_provider", "outcome", "response_sha256")}, sort_keys=True))
        return 0
    if not a.case:
        ap.error("--case or --repair-of is required")
    from . import cases
    req = {"cantilever": cases.cantilever_request, "oca2": cases.oca2_request}[a.case]()
    passage = HERE / "sources" / req["claim"]["source"]["locator"].split("sources/")[-1].split(";")[0].strip()
    r = run(a.case, req["claim"]["text"], passage, req["claim"]["source"]["ref"], req["claim"]["source"]["locator"], Path(a.out), a.model, a.dry_run, a.max_output_tokens, a.thinking)
    print(json.dumps({k: r.get(k) for k in ("case", "model_requested", "model_version_reported", "usage_reported_by_provider", "outcome", "prompt_sha256", "response_sha256", "dry_run")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
