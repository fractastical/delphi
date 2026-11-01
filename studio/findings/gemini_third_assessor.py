"""Third-assessor calibration for Delphi's dataset-resolvability layer.

Delphi already carries 1,224 dataset-resolvability assessments over 612 claims from TWO
assessors (a grok and a gpt). This runs Gemini as an independent THIRD assessor on a
stratified sample of claims that already have both, so its agreement with the existing two
can be MEASURED before anything it says is used anywhere.

That is the point: a model assessment is a provider stance, never accepted truth. Without a
calibration arm there is no way to tell a useful third opinion from noise with a confident
voice.
"""
from __future__ import annotations
import json, os, random, re, sys, time, urllib.request

DELPHI = "https://delphisci-mcp.fly.dev/mcp"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
DIMS = ["data-existence", "data-adequacy", "analysis-feasibility", "discriminating-power", "operationalizability"]
VERDICTS = ["resolvable-now", "partially-resolvable", "not-resolvable-with-public-data", "not-operationalizable"]


def mcp(method, params, _id=[0]):
    _id[0] += 1
    body = json.dumps({"jsonrpc": "2.0", "id": _id[0], "method": method, "params": params}).encode()
    req = urllib.request.Request(DELPHI, data=body, headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read().decode()
    # The body is either one JSON document or an SSE stream. A line-based scan alone breaks on a
    # large chunked payload, because a fragment can still start with "{".
    candidates = [raw]
    candidates += [l[6:] for l in raw.splitlines() if l.startswith("data: ")]
    for text in candidates:
        text = text.strip()
        if not text.startswith("{"):
            continue
        try:
            d = json.loads(text)
        except json.JSONDecodeError:
            continue
        if "error" in d:
            raise RuntimeError(d["error"])
        if "result" in d:
            c = d["result"].get("content") or []
            if c and c[0].get("type") == "text":
                inner = c[0]["text"]
                try:
                    return json.loads(inner)
                except json.JSONDecodeError:
                    raise RuntimeError("tool returned non-JSON text: " + inner[:300])
            return d["result"]
    raise RuntimeError("no parseable result: " + raw[:300])


# Gemini 3 spends THINKING tokens from the same output budget. At maxOutputTokens=1200 the model
# finished thinking and had nothing left to emit, so 11 of 24 calls returned a candidate with no
# text part at all. That is a harness defect and it looked exactly like a model failure. The fix is
# a real budget plus structured output, so the reply cannot be prose even when the model would
# rather explain itself.
SCHEMA = {
    "type": "object",
    "properties": {
        "dimensions": {"type": "object", "properties": {d: {"type": "number"} for d in DIMS},
                       "required": DIMS},
        "verdict": {"type": "string", "enum": VERDICTS},
        "confidence": {"type": "number"},
        "named_datasets": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["dimensions", "verdict", "confidence", "named_datasets", "summary"],
}


def gemini(model, prompt, key):
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0, "maxOutputTokens": 8000,
                                            "responseMimeType": "application/json",
                                            "responseSchema": SCHEMA}}).encode()
    req = urllib.request.Request(GEMINI.format(m=model, k=key), data=body,
                                 headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                d = json.loads(r.read().decode())
            cand = d["candidates"][0]
            text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
            if not text.strip():
                # Say WHY it was empty, so the next failure is diagnosable instead of mysterious.
                raise ValueError(f"empty reply: finishReason={cand.get('finishReason')} "
                                 f"usage={d.get('usageMetadata', {})}")
            return text
        except Exception as exc:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))


PROMPT = """You are assessing whether a scientific claim could be settled using PUBLIC datasets that exist today.

CLAIM TITLE: {title}
CLAIM STATEMENT: {statement}
STATED SCOPE/CONTEXT: {context}

Score each dimension from 0.0 to 1.0:
- data-existence: do relevant public data actually exist today?
- data-adequacy: are they adequate in coverage, resolution and quality for THIS claim?
- analysis-feasibility: could a competent analyst run the analysis with ordinary tools?
- discriminating-power: would the result distinguish this claim from its leading rivals, or only be consistent with it?
- operationalizability: can the claim be turned into a precise testable statement at all?

Then give an overall verdict, one of: {verdicts}

Rules. Judge the claim AS STATED, inside its stated scope. Correlational data that cannot separate a
mechanism from its alternatives scores LOW on discriminating-power even when data-existence is high.
Do not credit data you cannot name. If you are unsure a dataset exists, that is low data-existence,
not a guess. Be willing to score low: most historical mechanism claims are not settleable from public
data, and saying so is the correct answer.

Reply with ONLY a JSON object:
{{"dimensions": {{"data-existence": 0.0, "data-adequacy": 0.0, "analysis-feasibility": 0.0, "discriminating-power": 0.0, "operationalizability": 0.0}}, "verdict": "...", "confidence": 0.0, "named_datasets": ["..."], "summary": "two sentences"}}"""


def parse(raw):
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("no JSON in reply")
    d = json.loads(m.group(0))
    if set(d["dimensions"]) != set(DIMS):
        raise ValueError(f"dimension set mismatch: {sorted(d['dimensions'])}")
    if d["verdict"] not in VERDICTS:
        raise ValueError(f"verdict not in enum: {d['verdict']}")
    return d


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    model = sys.argv[2] if len(sys.argv) > 2 else "gemini-3-flash-preview"
    key = os.environ["GEMINI_API_KEY"]
    random.seed(20261031)

    ranked = mcp("tools/call", {"name": "delphi_rank_claims",
                                "arguments": {"type": "dataset-resolvability/0.2.0", "limit": 500}})
    print(f"ranked claims available: {len(ranked)}", file=sys.stderr)

    # Stratify by the EXISTING consensus score so the sample is not all easy or all hard.
    ranked.sort(key=lambda r: r["score"])
    buckets, per = 4, max(1, n // 4)
    size = len(ranked) // buckets
    sample = []
    for b in range(buckets):
        chunk = ranked[b * size:(b + 1) * size] if b < buckets - 1 else ranked[b * size:]
        sample += random.sample(chunk, min(per, len(chunk)))

    rows, errors = [], []
    for i, r in enumerate(sample):
        cid = r["claim"].rsplit("/", 1)[-1]
        try:
            full = mcp("tools/call", {"name": "delphi_get_claim", "arguments": {"id": cid}})
            f = full.get("fields", {})
            raw = gemini(model, PROMPT.format(title=f.get("rdfs:label", r["title"]),
                                              statement=f.get("dct:description", ""),
                                              context=f.get("delphi:context", "none stated"),
                                              verdicts=", ".join(VERDICTS)), key)
            got = parse(raw)
            prior = [{"assessor": a["assessor"].rsplit("/", 1)[-1], "score": a["score"],
                      "verdict": a["verdict"], "dimensions": a.get("dimensions", {})}
                     for a in full.get("assessments", [])]
            rows.append({"claim": cid, "domain": r["domain"].rsplit("/", 1)[-1],
                         "title": f.get("rdfs:label", r["title"]),
                         "consensus_score": r["score"], "consensus_verdicts": r["verdicts"],
                         "prior_assessments": prior, "gemini": got,
                         "gemini_score": round(sum(got["dimensions"].values()) / 5, 4)})
            print(f"  [{i+1}/{len(sample)}] {cid}: gemini {got['verdict']} "
                  f"({rows[-1]['gemini_score']:.2f}) vs consensus {r['score']:.2f}", file=sys.stderr)
        except Exception as exc:
            errors.append({"claim": cid, "error": str(exc)[:300]})
            print(f"  [{i+1}/{len(sample)}] {cid}: ERROR {str(exc)[:120]}", file=sys.stderr)

    out = {"model": model, "n_requested": n, "n_assessed": len(rows), "n_errors": len(errors),
           "errors": errors, "rows": rows,
           "note": "Gemini is a THIRD provider stance. Nothing here is accepted truth, and no claim's "
                   "status changes because a model scored it."}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
