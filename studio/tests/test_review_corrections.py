import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = json.loads((ROOT / "results/coordination/review-corrections.json").read_text())
CLASSES = {"author_self_correction", "root_review", "separate_harness_review", "native_review_then_root_review"}


def problems(e):
    out = [f"missing {k}" for k in ("submitted", "review", "correction", "recheck", "decision_changed", "information_used", "limits") if not e.get(k)]
    if e.get("review", {}).get("class") not in CLASSES:
        out.append("unknown review class")
    return out


def test_each_entry_has_all_evidence_links_and_a_known_review_class():
    assert 3 <= len(LEDGER["entries"]) <= 5
    assert all(problems(e) == [] for e in LEDGER["entries"])


def test_every_cited_commit_resolves():
    shas = set(re.findall(r"\b[0-9a-f]{7}\b|\b[0-9a-f]{40}\b", json.dumps(LEDGER)))
    assert shas
    for sha in shas:
        subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=ROOT, check=True)


def test_no_manufactured_advantage_or_percentage_claim():
    assert "not_claimed" in LEDGER and "retrospective" in LEDGER["nature"]
    text = json.dumps(LEDGER["entries"]).lower()
    assert "% improvement" not in text and "percent improvement" not in text
    seq = next(e for e in LEDGER["entries"] if e["id"] == "sequence-compiler-typed-inputs")
    assert "DIFFERENT check sets" in seq["recheck"]["caution"]
    assert "unknown" in LEDGER["counterfactual"]


def test_checker_is_not_vacuous_a_mutated_entry_fails_the_link_test():
    bad = json.loads(json.dumps(LEDGER["entries"][0]))
    bad["recheck"] = {}
    assert problems(bad) == ["missing recheck"]
    bad["review"]["class"] = "agent_count"
    assert "unknown review class" in problems(bad)
