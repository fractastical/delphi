"""Explicit mapping of the two reviewed, pinned Delphi Evolve JSON contracts.

Prior review labels are provenance, never new local acceptance. Source bytes are
kept verbatim under seeds/ so all mapping choices can be checked independently.
"""
import json
from hashlib import sha256
from pathlib import Path

from .models import ref

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "4fe9fb7b80173b017aa9d688a449116cc21b96e8"
SOURCE_BASE = f"https://github.com/kganjam/delphi-evolve/blob/{SOURCE_COMMIT}/site/review/"


def source(uri, locator, source_version=None, content_sha256=None):
    return {"uri": uri, "locator": locator, "source_version": source_version,
            "content_sha256": content_sha256, "content_available": False,
            "access": "public source reference; original paper availability not verified here", "license": None}


def seed(store, token, actor):
    results = []
    refs = {}
    data = json.loads((ROOT / "seeds/frontier-data.json").read_text())
    for n in data["nodes"]:
        draft = {"namespace": store.namespace, "kind": "Claim", "id": n["id"], "issuer": actor,
                 "source_uri": SOURCE_BASE + "frontier-data.json", "payload": {
                     "title": n["label"], "statement": n["statement"], "context": n["context"],
                     "assumptions": ["See exact source context; no independent source-fidelity review in this import."],
                     "limitations": [data["scope"]], "source": source(n["source_url"], n["id"], n["record_sha256"]),
                     "source_record_version": n["record_sha256"],
                     "prior_review": {k: n[k] for k in ("category", "review_title", "finding", "next_action", "evidence")}}}
        record = store.submit(token, "seed-claim-" + n["id"], draft)["record"]
        refs[n["id"]] = ref(record)
        results.append(ref(record))
    problems = json.loads((ROOT / "seeds/frontier-problems.json").read_text())["problems"]
    pending = list(problems)
    while pending:
        ready = [p for p in pending if all(dep in refs for dep in p["depends_on"])]
        if not ready:
            raise ValueError("Seed dependency cycle or absent dependency")
        for p in ready:
            draft = {"namespace": store.namespace, "kind": "Problem", "id": p["id"], "issuer": actor,
                     "source_uri": SOURCE_BASE + "frontier-problems.json", "payload": {
                         "title": p["title"], "known_state": p["known"], "question": p["question"],
                         "problem_kind": "resolved_scope_correction" if p["state"] == "resolved_in_review" else "project_gap",
                         "novelty_status": "Curated project question; no field-level novelty claim.",
                         "data_access": "Follow the pinned source; data-access gate is not established by this import.",
                         "completeness": "recorded",
                         "acceptance_criteria": [p["acceptance"]],
                         "falsifiers": [],
                         "next_action": p["next_action"], "required_capabilities": p["needs"],
                         "cost_stop_bounds": "No execution authorized by seed import. Freeze a bounded Action before work.",
                         "downstream_uses": p["unlocks"],
                         "dependencies": [refs[x] for x in p["depends_on"]],
                         "source": source(p["source"], p["id"], SOURCE_COMMIT), "original": p}}
            record = store.submit(token, "seed-problem-" + p["id"], draft)["record"]
            refs[p["id"]] = ref(record)
            results.append(ref(record))
            pending.remove(p)
    return results
