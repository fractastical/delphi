#!/usr/bin/env python3
"""Compute used so far, per model, and how well each model's output held up.

Usage: python3 scripts/usage/model-report.py   (writes scripts/usage/model-report.json)

Compute comes from local Cursor agent transcripts. They store user prompts, assistant text and
tool-call inputs, but not tool results, hidden reasoning or token counts, so the token figures
are estimates of visible output only (chars / 4). Cloud-agent runs are not in local transcripts.

Quality comes from the repo: dataset-resolvability assessments (coverage, dataset URLs that
failed to resolve, agreement with the other assessors), truth scores checked against proofs and
preregistered data tests, data-test authorship and re-execution, and Lean reports.
"""
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSCRIPTS = Path.home() / ".cursor/projects/Users-jdietz-Documents-GitHub-dev-delphisci/agent-transcripts"
OUT = Path(__file__).resolve().parent / "model-report.json"
PROJECTS = ["darwin-origin", "thompson-growth-form", "wolfram-nks", "levin-papers"]
ASSESSOR_MODEL = {"gpt": "gpt-5.6-sol-medium", "grok": "grok-4.7-high-fast",
                  "gemini": "gemini-4-argon-medium", "claude": "claude-opus-5.5"}
LABEL_MODEL = {"GPT-5.6 Sol": "gpt-5.6-sol-medium", "Grok 4.7": "grok-4.7-high-fast",
               "Gemini 4 Argon": "gemini-4-argon-medium"}
MAIN = "main chat model (not recorded)"
TS_RE = re.compile(r"<timestamp>(.*?)</timestamp>")
QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.S)
RAW_RE = re.compile(r"/raw/(gpt|grok|gemini|claude)/")


def parse_ts(s):
    return datetime.strptime(re.sub(r"\s*\(UTC[^)]*\)", "", s), "%A, %b %d, %Y, %I:%M %p")


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def normalize_model(m):
    m = m.lower()
    if "fable" in m:
        return "claude-fable-5.1"
    if "opus" in m:
        return "claude-opus-5.5"
    if "sonnet" in m:
        return "claude-sonnet-5.5"
    return m


def task_calls(records):
    for r in records:
        for c in r.get("message", {}).get("content", []):
            if c.get("type") != "tool_use":
                continue
            inp = c.get("input") or {}
            if c.get("name") == "CallDynamicTool" and inp.get("toolName") == "Task":
                inp = inp.get("arguments") or {}
            elif c.get("name") != "Task":
                continue
            if isinstance(inp, str):
                try:
                    inp = json.loads(inp)
                except json.JSONDecodeError:
                    continue
            if isinstance(inp, dict):
                yield inp


def category(text):
    t = text.lower()
    if "truth/" in t or "truth score" in t:
        return "truth scoring"
    if "assessment/" in t or "assess" in t:
        return "resolvability assessment"
    if "lean" in t:
        return "lean formalization"
    if "extract" in t:
        return "claim extraction"
    if "test" in t or "dataset" in t:
        return "data tests / datasets"
    return "other"


def summarize(path, records):
    s = {"user_turns": 0, "assistant_msgs": 0, "tool_calls": 0, "out_chars": 0, "errors": 0}
    stamps, first_query = [], None
    for r in records:
        if r.get("type") == "turn_ended" and r.get("status") != "success":
            s["errors"] += 1
        msg = r.get("message")
        if not msg:
            continue
        for c in msg["content"]:
            if r["role"] == "user" and c.get("type") == "text":
                s["user_turns"] += 1
                stamps += [parse_ts(t) for t in TS_RE.findall(c["text"])]
                q = QUERY_RE.search(c["text"])
                if first_query is None and q:
                    first_query = q.group(1)
            elif r["role"] == "assistant":
                if c.get("type") == "text":
                    s["out_chars"] += len(c.get("text", ""))
                elif c.get("type") == "tool_use":
                    s["tool_calls"] += 1
                    s["out_chars"] += len(json.dumps(c.get("input")))
        if r["role"] == "assistant":
            s["assistant_msgs"] += 1
    end = datetime.fromtimestamp(path.stat().st_mtime)
    s["minutes"] = round((end - stamps[0]).total_seconds() / 60, 1) if stamps else None
    s["started"] = stamps[0].isoformat() if stamps else None
    return s, first_query or ""


def load(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def compute():
    agents = []
    for top in sorted(p for p in TRANSCRIPTS.iterdir() if p.is_dir()):
        main = top / f"{top.name}.jsonl"
        if not main.exists():
            continue
        recs = load(main)
        s, q = summarize(main, recs)
        m = RAW_RE.search(q)
        model = ASSESSOR_MODEL[m.group(1)] if m else MAIN
        agents.append({"id": top.name, "parent": None, "model": model, "task": category(q) if m else "main chat", **s})
        prompts = {norm(t.get("prompt")): t for t in task_calls(recs)}
        for sub in sorted((top / "subagents").glob("*.jsonl")) if (top / "subagents").exists() else []:
            srecs = load(sub)
            ss, sq = summarize(sub, srecs)
            t = prompts.get(norm(sq))
            if t and t.get("model") and t["model"] != "inherit":
                model = t["model"]
            elif RAW_RE.search(sq):
                model = ASSESSOR_MODEL[RAW_RE.search(sq).group(1)]
            else:
                model = f"inherit ({MAIN})" if t else "unattributed"
            desc = (t or {}).get("description", "")
            agents.append({"id": sub.stem, "parent": top.name, "model": model,
                           "task": category(desc + " " + sq), "description": desc, **ss})
    by_model = defaultdict(lambda: Counter())
    by_task = defaultdict(lambda: Counter())
    for a in agents:
        for k in ("user_turns", "tool_calls", "out_chars", "errors"):
            by_model[a["model"]][k] += a[k]
            by_task[(a["model"], a["task"])][k] += a[k]
        by_model[a["model"]]["agents"] += 1
        by_model[a["model"]]["minutes"] += a["minutes"] or 0
        by_task[(a["model"], a["task"])]["agents"] += 1
    for c in list(by_model.values()) + list(by_task.values()):
        c["est_output_tokens"] = round(c["out_chars"] / 4)
        if "minutes" in c:
            c["minutes"] = round(c["minutes"])
    return agents, {k: dict(v) for k, v in by_model.items()}, \
        [{"model": m, "task": t, **v} for (m, t), v in sorted(by_task.items())]


DEAD = re.compile(r"http-(404|410)|ENOTFOUND|not-found", re.I)


def composite(scores):
    return statistics.mean(scores.values()) if scores else None


def resolvability():
    out = {}
    for p in PROJECTS:
        a = ROOT / "claim-sources" / p / "assessment"
        assigned = {f.name: {c.get("claim_id") or c.get("id") for c in json.loads(f.read_text())}
                    for f in sorted((a / "inputs").glob("*.json"))}
        dropped = json.loads((a / "dropped-datasets.json").read_text()) if (a / "dropped-datasets.json").exists() else []
        merged = {x["assessor"] for x in json.loads((a / "assessments.json").read_text())["assessments"]}
        rows = defaultdict(dict)
        per = {}
        for d in sorted((a / "raw").iterdir()):
            st = Counter()
            for f in sorted(d.glob("*.json")):
                try:
                    data = json.loads(f.read_text())
                except json.JSONDecodeError:
                    st["invalid_files"] += 1
                    continue
                st["batches"] += 1
                ids = {x["claim_id"] for x in data}
                st["missing_claims"] += len(assigned.get(f.name, set()) - ids)
                for x in data:
                    st["claims"] += 1
                    st["datasets_proposed"] += len(x.get("candidate_datasets") or [])
                    rows[x["claim_id"]][d.name] = x
            if d.name in merged:
                drops = [x for x in dropped if x["assessor"] == d.name]
                st["datasets_checked"] = st["datasets_proposed"]
                st["datasets_dead"] = sum(1 for x in drops if DEAD.search(x["status"]))
                st["datasets_unreachable"] = len(drops) - st["datasets_dead"]
            st["batches_assigned"] = len(assigned)
            per[d.name] = st
        dev, agree = defaultdict(list), defaultdict(list)
        for claim, by in rows.items():
            if len(by) < 2:
                continue
            for m, x in by.items():
                others = [composite(o["scores"]) for n, o in by.items() if n != m]
                dev[m].append(abs(composite(x["scores"]) - statistics.mean(others)))
                agree[m].append(statistics.mean(o["verdict"] == x["verdict"] for n, o in by.items() if n != m))
        for m, st in per.items():
            st["mean_abs_dev_from_others"] = round(statistics.mean(dev[m]), 3) if dev[m] else None
            st["verdict_agreement"] = round(statistics.mean(agree[m]), 3) if agree[m] else None
            st["shared_claims"] = len(dev[m])
            per[m] = dict(st)
        out[p] = per
    total = defaultdict(Counter)
    for per in out.values():
        for m, st in per.items():
            for k in ("batches", "batches_assigned", "claims", "missing_claims", "invalid_files",
                      "datasets_proposed", "datasets_checked", "datasets_dead", "datasets_unreachable"):
                total[m][k] += st.get(k, 0)
    for m, t in total.items():
        n = t["datasets_checked"]
        t["dead_rate"] = round(t["datasets_dead"] / n, 3) if n else None
        t["failed_rate"] = round((t["datasets_dead"] + t["datasets_unreachable"]) / n, 3) if n else None
    return out, {m: dict(t) for m, t in total.items()}


def auc(pos, neg):
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 3)


def pearson(x, y):
    mx, my = statistics.mean(x), statistics.mean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return sxy / (sum((a - mx) ** 2 for a in x) ** 0.5 * sum((b - my) ** 2 for b in y) ** 0.5)


def truth():
    claims = json.loads((ROOT / "docs/claims.json").read_text())["claims"]
    checks = {
        "data tests (supports=1, refutes=0)": lambda c: {"supports": 1, "refutes": 0}.get((c.get("data_test") or {}).get("verdict")),
        "proof status (proved=1, refuted=0)": lambda c: {"proved": 1, "refuted": 0}.get(c.get("status")),
    }
    out = {}
    for name, label_of in checks.items():
        res = {}
        for label, model in LABEL_MODEL.items():
            pairs = [(label_of(c), a["p_true"]) for c in claims for a in c.get("truth_by") or []
                     if a["assessor"] == label and label_of(c) is not None]
            if not pairs:
                continue
            pos = [p for y, p in pairs if y == 1]
            neg = [p for y, p in pairs if y == 0]
            res[model] = {"n": len(pairs), "n_true": len(pos), "n_false": len(neg),
                          "mean_p_when_true": round(statistics.mean(pos), 3) if pos else None,
                          "mean_p_when_false": round(statistics.mean(neg), 3) if neg else None,
                          "brier": round(statistics.mean((p - y) ** 2 for y, p in pairs), 3),
                          "auc": auc(pos, neg)}
        out[name] = res
    both = [(d["GPT-5.6 Sol"], d["Grok 4.7"]) for c in claims
            for d in [{a["assessor"]: a["p_true"] for a in c.get("truth_by") or []}]
            if "GPT-5.6 Sol" in d and "Grok 4.7" in d]
    out["gpt_vs_grok"] = {"n": len(both), "pearson": round(pearson(*zip(*both)), 3),
                          "mean_abs_diff": round(statistics.mean(abs(a - b) for a, b in both), 3),
                          "mean_gpt": round(statistics.mean(a for a, _ in both), 3),
                          "mean_grok": round(statistics.mean(b for _, b in both), 3)}
    return out


def data_tests():
    status = {}
    for f in sorted((ROOT / "scripts/exec/runs").glob("2*.json")):
        for r in json.loads(f.read_text())["results"]:
            key = (r["kind"], r["claim_id"])
            if r["status"] != "skipped" or key not in status:
                status[key] = r["status"]
    by = defaultdict(lambda: {"tests": 0, "verdicts": Counter(), "exec": Counter(), "pass_fail_criteria": 0})
    for f in sorted((ROOT / "test-data/claim-tests").glob("*/*/result.json")):
        r = json.loads(f.read_text())
        ag = r.get("agent")
        model = normalize_model(ag.get("model", "unknown")) if isinstance(ag, dict) else "unrecorded"
        b = by[model]
        b["tests"] += 1
        b["verdicts"][r.get("verdict", "none")] += 1
        b["pass_fail_criteria"] += bool(r.get("test_contract") or (r.get("pass_criterion") and r.get("fail_criterion")))
        b["exec"][status.get(("data", f.parent.name), "not run")] += 1
    return {m: {**v, "verdicts": dict(v["verdicts"]), "exec": dict(v["exec"])} for m, v in by.items()}


def lean():
    out = Counter()
    for f in (ROOT / "claim-sources").glob("*/lean/reports/*.json"):
        for r in json.loads(f.read_text()):
            out[r.get("status")] += 1
    return dict(out)


def main():
    agents, by_model, by_task = compute()
    per_project, res_total = resolvability()
    report = {"built": datetime.now().isoformat(timespec="seconds"),
              "compute": {"by_model": by_model, "by_model_and_task": by_task, "agents": agents},
              "quality": {"resolvability_total": res_total, "resolvability_by_project": per_project,
                          "truth": truth(), "data_tests_by_author": data_tests(), "lean_reports": lean()}}
    OUT.write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "compute"} |
                     {"compute": {"by_model": by_model, "by_model_and_task": by_task}}, indent=1, default=str))


if __name__ == "__main__":
    main()
