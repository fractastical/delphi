"""Adapters from REAL Evolve traces to experiment rows. Read-only. Each row cites the files and the sha256 it came from.

Currently: the Lean-commons arms (delphi-evolve branch work/rethink-director, artifacts/commons/runs/<ARM>_r<k>/). Those runs record, per
arm-run, the board claims (which agent took which target, in what order), every model call and the certified targets.
"""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path


def _jsonl(p: Path):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def commons_rows(runs_dir: str) -> list[dict]:
    root = Path(runs_dir)
    rows = []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and len(p.name) > 3 and p.name[1:3] == "_r"):
        summary, attempts, board = d / "summary.json", d / "attempts.jsonl", d / "board.jsonl"
        if not (summary.exists() and attempts.exists() and board.exists()):
            continue
        s = json.loads(summary.read_text())
        calls = _jsonl(attempts)
        claims = [b for b in _jsonl(board) if b["kind"] == "claim"]
        proved = {x["task"] for x in s["proved"]}
        src_hash = sha256(sha256(summary.read_bytes()).hexdigest().encode() + sha256(attempts.read_bytes()).hexdigest().encode() + sha256(board.read_bytes()).hexdigest().encode()).hexdigest()
        seen = {}
        for b in claims:
            seen.setdefault(b["task"], b["seq"])
        for task, order in sorted(seen.items(), key=lambda kv: kv[1]):
            rows.append({"arm": d.name[0], "run": d.name, "problem_id": task, "cost": sum(1 for c in calls if c["task"] == task), "cost_unit": "model_calls",
                         "accepted": task in proved, "overturned": None, "claim_order": order,
                         "source_path": f"artifacts/commons/runs/{d.name}/{{summary,attempts,board}}.json[l]", "source_sha256": src_hash})
    return rows
