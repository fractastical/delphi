"""Fittest-style trust-or-escalate routing for delphisci assessor truth scores.

Fittest serves an ML potential's answer only if the committee agrees (sigma_F < tau) and a Beta
posterior P(correct), learned from DFT labels, is high enough; otherwise it sends the structure to
DFT. Here the committee is the two truth assessors in docs/claims.json, sigma is |p_a - p_b|, and the
"DFT labels" are claims with an outcome that does not come from an assessor: a decisive data test
(supports / refutes) or a recorded proof status (proved / refuted). A flagged claim is sent to an
executable test or human review instead of being reported on its assessor score.

Two verdict rules are compared under leave-one-out (each labelled claim is routed by a ledger that
never saw its own label):
  point  Fittest's rule: trust if sigma < tau and the posterior mean P(correct) >= 0.5.
  lower  trust if sigma < tau and the 5th percentile of P(correct) >= 0.5, so a bucket with few
         labels cannot be trusted on its point estimate (the failure seen in pilot.py).
Standard library plus numpy only.
"""

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "docs" / "claims.json"
OUT = Path(__file__).parent / "routing-results.json"
TAU_PERCENTILE = 70
CONFIDENT_MARGIN = 0.2
# A proof shows a formal statement follows from its assumptions, not that organisms satisfy them,
# while truth scores judge the empirical claim, so only data tests calibrate the routing ledger.
LEDGER_SOURCE = "data-test"
GRID = np.linspace(1e-6, 1 - 1e-6, 20001)


def beta_stats(k, n):
    a, b = 1 + k, 1 + n - k
    logpdf = (a - 1) * np.log(GRID) + (b - 1) * np.log1p(-GRID) - (
        math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b))
    cdf = np.cumsum(np.exp(logpdf))
    cdf /= cdf[-1]
    return {"mean": a / (a + b), "q05": float(GRID[np.searchsorted(cdf, 0.05)]),
            "q95": float(GRID[np.searchsorted(cdf, 0.95)]), "labels": n}


def label_of(c):
    test = c.get("data_test") or {}
    if test.get("verdict") in ("supports", "refutes"):
        return int(test["verdict"] == "supports"), "data-test"
    if c.get("status") == "proved":
        return 1, "proof"
    if c.get("status") == "refuted":
        return 0, "proof"
    return None, None


def corpus(c):
    cid = c["id"]
    if cid.startswith("darwin"):
        return "darwin-origin"
    if cid.startswith("thompson"):
        return "thompson-growth-form"
    if cid.startswith("wolfram"):
        return "wolfram-nks"
    if cid.startswith("levin"):
        return "levin-papers"
    return "math-bio-claims"


def load():
    rows = []
    for c in json.loads(CLAIMS.read_text())["claims"]:
        scores = {t["assessor"]: t["p_true"] for t in c.get("truth_by") or []}
        if len(scores) != 2:
            continue
        (na, pa), (nb, pb) = sorted(scores.items())
        label, source = label_of(c)
        rows.append({"id": c["id"], "corpus": corpus(c), "label": label, "label_source": source,
                     "candidates": {na: pa, nb: pb, "mean": (pa + pb) / 2},
                     "sigma": abs(pa - pb), "testability": c.get("testability"),
                     "existing_test": (c.get("data_test") or {}).get("verdict")})
    return rows


def bucket(r, tau):
    margin = abs(r["candidates"]["mean"] - 0.5)
    return ("agree" if r["sigma"] < tau else "disagree",
            "confident" if margin >= CONFIDENT_MARGIN else "uncertain")


def fit_ledger(rows, tau):
    counts = defaultdict(lambda: [0, 0])
    for r in rows:
        b = bucket(r, tau)
        for name, p in r["candidates"].items():
            correct = int((p >= 0.5) == bool(r["label"]))
            counts[(b, name)][0] += correct
            counts[(b, name)][1] += 1
    return counts


def route(r, tau, counts, rule):
    b = bucket(r, tau)
    posts = {name: beta_stats(*counts.get((b, name), (0, 0))) for name in r["candidates"]}
    served = max(posts, key=lambda n: (posts[n]["mean"], n == "mean"))
    post = posts[served]
    reasons = []
    if r["sigma"] >= tau:
        reasons.append(f"assessor disagreement {r['sigma']:.2f} >= tau {tau:.2f}")
    score = post["mean"] if rule == "point" else post["q05"]
    if score < 0.5:
        what = "P(correct)" if rule == "point" else "P(correct) 5th percentile"
        reasons.append(f"{what} = {score:.2f} < 0.5 ({post['labels']} labels in bucket)")
    return {"verdict": "send_to_exec" if reasons else "trust", "served": served,
            "p_true": r["candidates"][served], "trust_score": post["mean"],
            "trust_90ci": [post["q05"], post["q95"]], "labels_behind_score": post["labels"],
            "bucket": "/".join(b), "reasons": reasons}


def evaluate(labelled, tau, rule):
    tally = Counter()
    misses = []
    for i, r in enumerate(labelled):
        counts = fit_ledger(labelled[:i] + labelled[i + 1:], tau)
        d = route(r, tau, counts, rule)
        wrong = (d["p_true"] >= 0.5) != bool(r["label"])
        key = ("trusted" if d["verdict"] == "trust" else "flagged") + ("_wrong" if wrong else "_right")
        tally[key] += 1
        if key == "trusted_wrong":
            misses.append({"id": r["id"], "label": r["label"], "label_source": r["label_source"],
                           "served": d["served"], "p_true": round(d["p_true"], 3),
                           "sigma": round(r["sigma"], 3), "bucket": d["bucket"]})
    n = len(labelled)
    wrong = tally["trusted_wrong"] + tally["flagged_wrong"]
    return {
        "rule": rule, "n": n,
        "trusted": tally["trusted_right"] + tally["trusted_wrong"],
        "flagged": tally["flagged_right"] + tally["flagged_wrong"],
        "silent_failures": tally["trusted_wrong"],
        "caught_failures": tally["flagged_wrong"],
        "assessor_wrong_total": wrong,
        "share_of_failures_caught": round(tally["flagged_wrong"] / wrong, 3) if wrong else None,
        "trusted_accuracy": round(tally["trusted_right"] / max(1, tally["trusted_right"] + tally["trusted_wrong"]), 3),
        "silent_failure_claims": misses,
    }


def baseline(labelled):
    out = {}
    for name in labelled[0]["candidates"]:
        right = sum((r["candidates"][name] >= 0.5) == bool(r["label"]) for r in labelled)
        out[name] = {"accuracy": round(right / len(labelled), 3), "wrong": len(labelled) - right}
    return out


def main():
    rows = load()
    tau = float(np.percentile([r["sigma"] for r in rows], TAU_PERCENTILE))
    labelled = [r for r in rows if r["label"] is not None]
    by_source = {s: [r for r in labelled if r["label_source"] == s] for s in ("data-test", "proof")}

    evaluation = {}
    for name, subset in [("all", labelled), *by_source.items()]:
        evaluation[name] = {"baseline_trust_everything": baseline(subset),
                            "point": evaluate(subset, tau, "point"),
                            "lower": evaluate(subset, tau, "lower")}

    counts = fit_ledger(by_source[LEDGER_SOURCE], tau)
    ledger = {f"{'/'.join(b)}:{name}": beta_stats(k, n) for (b, name), (k, n) in sorted(counts.items())}
    unlabelled = [r for r in rows if r["label_source"] != LEDGER_SOURCE]
    queue, per_corpus = [], defaultdict(Counter)
    for r in unlabelled:
        d = route(r, tau, counts, "lower")
        per_corpus[r["corpus"]][d["verdict"]] += 1
        if d["verdict"] == "send_to_exec":
            queue.append({"id": r["id"], "corpus": r["corpus"], "sigma": round(r["sigma"], 3),
                          "p_true": {k: round(v, 3) for k, v in r["candidates"].items()},
                          "testability": r["testability"], "existing_test": r["existing_test"],
                          "bucket": d["bucket"], "reasons": d["reasons"]})
    queue.sort(key=lambda q: (-q["sigma"], -(q["testability"] or 0)))

    out = {
        "source": str(CLAIMS.relative_to(ROOT)),
        "tau": round(tau, 4), "tau_percentile": TAU_PERCENTILE, "confident_margin": CONFIDENT_MARGIN,
        "claims": len(rows), "labelled": len(labelled),
        "labelled_by_source": {s: len(v) for s, v in by_source.items()},
        "label_balance": dict(Counter(r["label"] for r in labelled)),
        "evaluation_leave_one_out": evaluation,
        "ledger_source": LEDGER_SOURCE,
        "ledger": ledger,
        "unlabelled_routing_lower_rule": {k: dict(v) for k, v in sorted(per_corpus.items())},
        "exec_queue": queue,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")

    print(f"claims={len(rows)} labelled={len(labelled)} {out['labelled_by_source']} "
          f"balance={out['label_balance']} tau={tau:.3f}")
    for name, ev in evaluation.items():
        print(f"\n[{name}] baseline {ev['baseline_trust_everything']}")
        for rule in ("point", "lower"):
            e = ev[rule]
            print(f"  {rule:<5} n={e['n']} trusted={e['trusted']} flagged={e['flagged']} "
                  f"silent={e['silent_failures']} caught={e['caught_failures']}/{e['assessor_wrong_total']} "
                  f"trusted_acc={e['trusted_accuracy']}")
    print(f"\nledger ({LEDGER_SOURCE} labels):")
    for k, v in ledger.items():
        print(f"  {k:<32} mean={v['mean']:.2f} 90%=[{v['q05']:.2f},{v['q95']:.2f}] n={v['labels']}")
    print("\nunlabelled routing (lower rule):", out["unlabelled_routing_lower_rule"])
    print("exec queue:", len(queue), "top:", [q["id"] for q in queue[:10]])


if __name__ == "__main__":
    main()
