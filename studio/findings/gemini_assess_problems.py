"""Assess every Frontier problem for data-resolvability, using Delphi's own five dimensions.

This is a PROVIDER STANCE at scale, not truth. We measured this morning that this same model,
as a third assessor on Delphi claims, scored BELOW an always-answer-the-mode baseline. So these
are recorded as what they are: one model's opinion, useful for triage and for nothing else.

What it is actually for: 250 of our problems are `recorded` rather than `actionable` because
nobody has said what would settle them. Triage tells us WHERE to spend a human.
"""
from __future__ import annotations
import json, os, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path

DIMS = ["data-existence", "data-adequacy", "analysis-feasibility", "discriminating-power", "operationalizability"]
VERDICTS = ["resolvable-now", "partially-resolvable", "not-resolvable-with-public-data", "not-operationalizable"]
URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
SCHEMA = {"type": "object", "properties": {
    "dimensions": {"type": "object", "properties": {d: {"type": "number"} for d in DIMS}, "required": DIMS},
    "verdict": {"type": "string", "enum": VERDICTS}, "confidence": {"type": "number"},
    "named_datasets": {"type": "array", "items": {"type": "string"}},
    "what_would_settle_it": {"type": "string"},
    "summary": {"type": "string"}},
    "required": ["dimensions", "verdict", "confidence", "named_datasets", "what_would_settle_it", "summary"]}

PROMPT = """Assess whether this open research problem could be settled using PUBLIC datasets that exist today.

TITLE: {title}
QUESTION: {question}
WHAT IS KNOWN: {known}
STATED DATA ACCESS: {data}

Score 0.0-1.0 on each: data-existence (do relevant public data exist today), data-adequacy (adequate
coverage/resolution/quality for THIS question), analysis-feasibility (could a competent analyst run it
with ordinary tools), discriminating-power (would the result distinguish this from rival explanations,
or merely be consistent with it), operationalizability (can it be made precise and testable at all).

Then: a verdict from {verdicts}; any datasets you can NAME (do not credit data you cannot name - an
unnamed dataset is low data-existence, not a guess); and `what_would_settle_it`, one concrete sentence
naming the measurement or computation, which is the field this problem is missing.

Be willing to score low. Most open biological problems are NOT settleable from public data, and saying
so is the correct answer. Correlational data that cannot separate a mechanism from its alternatives
scores LOW on discriminating-power however much of it exists."""


def gemini(model, prompt, key):
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0, "maxOutputTokens": 8000,
                                            "responseMimeType": "application/json", "responseSchema": SCHEMA}}).encode()
    req = urllib.request.Request(URL.format(m=model, k=key), data=body, headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                d = json.loads(r.read().decode())
            cand = d["candidates"][0]
            text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
            if not text.strip():
                raise ValueError(f"empty: finishReason={cand.get('finishReason')} usage={d.get('usageMetadata',{})}")
            return json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(4 * (attempt + 1))


def main():
    drafts_path, out_path, model = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "gemini-3-flash-preview")
    key = os.environ["GEMINI_API_KEY"]
    drafts = [json.loads(l) for l in Path(drafts_path).read_text().splitlines() if l.strip()]
    print(f"problems: {len(drafts)}  model: {model}", file=sys.stderr)

    def one(d):
        p = d["payload"]
        try:
            got = gemini(model, PROMPT.format(title=p["title"], question=p["question"],
                                              known=p["known_state"][:2000], data=p["data_access"][:1200],
                                              verdicts=", ".join(VERDICTS)), key)
            return {"id": d["id"], "completeness": p["completeness"], "ok": True, "assessment": got,
                    "score": round(sum(got["dimensions"].values()) / 5, 4)}
        except Exception as exc:
            return {"id": d["id"], "completeness": p["completeness"], "ok": False, "error": str(exc)[:240]}

    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(one, drafts))
    done = [r for r in rows if r["ok"]]
    for i, r in enumerate(rows):
        if not r["ok"]:
            print(f"  ERROR {r['id']}: {r['error'][:100]}", file=sys.stderr)
    out = {"model": model, "source": drafts_path,
           "source_sha256": sha256(Path(drafts_path).read_bytes()).hexdigest(),
           "n": len(rows), "assessed": len(done), "errors": len(rows) - len(done), "rows": rows,
           "note": "PROVIDER STANCE, not truth. The same model scored BELOW an always-answer-the-mode "
                   "baseline as a third assessor on Delphi claims (findings/README-third-assessor.md). "
                   "Use for triage only; no problem's status changes because a model scored it."}
    Path(out_path).write_text(json.dumps(out, indent=1))
    print(f"assessed {len(done)}/{len(rows)}", file=sys.stderr)


if __name__ == "__main__":
    main()
