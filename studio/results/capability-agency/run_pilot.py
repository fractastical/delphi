#!/usr/bin/env python3
"""Run the frozen, public-input capability/agency pilot once, without retries."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-3.8-flash"
MAX_INPUT = 9600
MAX_OUTPUT = 400
MAX_SPEND = 0.25
IN_RATE = 0.75 / 1_000_000
OUT_RATE = 3.75 / 1_000_000
MAX_PROMPT_BYTES = 9000


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def auth_key() -> str:
    sys.path.insert(0, "/home/ubuntu/Orchestra")
    from orchestra.interactive_cli import session_env

    return session_env("openrouter", "codex", None, "default")["OPENROUTER_API_KEY"]


def prompt_for(packet: dict, condition: str, rep: int, turn: int, role: str,
               earlier: list[dict]) -> str:
    prior = []
    for item in earlier:
        prior.append({"sha256": item["sha256"], "response": item["parsed"]})
    payload = {
        "condition_id": condition,
        "replicate_id": rep,
        "turn_id": turn,
        "actor_role": role,
        "public_input_packet": packet,
        "prior_pinned_responses": prior,
        "instruction": (
            "Evaluate both tasks independently. Use prior notes critically. "
            "Choose a next action in each decision_code field. Return only the "
            "JSON object matching the packet response_contract."
        ),
    }
    return canonical(payload)


def call_model(key: str, prompt: str, seed: int) -> tuple[dict | None, dict]:
    body = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are one analyst in a controlled public-data science evaluation. "
                    "Use only the supplied public input packet and deterministic outputs. "
                    "Do not browse, call tools, inspect files, or add outside facts. "
                    "Return one JSON object matching the response contract exactly, with "
                    "both task objects. Cite each task using its DOI. Choose only a "
                    "decision_code listed in the packet. No markdown or prose outside JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": MAX_OUTPUT,
        "seed": seed,
        "response_format": {"type": "json_object"},
        "provider": {"sort": "price", "data_collection": "allow", "require_parameters": True},
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read(1_000_000)
            status = response.status
        decoded = json.loads(raw)
        content = decoded.get("choices", [{}])[0].get("message", {}).get("content")
        parsed = json.loads(content) if isinstance(content, str) else None
        meta = {
            "http_status": status,
            "provider_response_id": decoded.get("id"),
            "model_returned": decoded.get("model"),
            "provider_returned": decoded.get("provider"),
            "usage": decoded.get("usage"),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "response_text": content,
            "response_sha256": sha((content or "").encode()),
            "parse_valid_json": parsed is not None,
        }
        return parsed if isinstance(parsed, dict) else None, meta
    except urllib.error.HTTPError as exc:
        return None, {"http_status": exc.code, "error": "provider_http_error", "elapsed_seconds": round(time.monotonic() - started, 3)}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return None, {"error": type(exc).__name__, "elapsed_seconds": round(time.monotonic() - started, 3)}


def main() -> int:
    prereg = json.loads((HERE / "preregistration.json").read_text())
    packet_path = HERE / "public_input_packet.json"
    packet = json.loads(packet_path.read_text())
    packet_hash = sha(packet_path.read_bytes())
    prereg_hash = sha((HERE / "preregistration.json").read_bytes())
    try:
        key = auth_key()
    except Exception as exc:
        print(json.dumps({"error": "auth_unavailable", "type": type(exc).__name__}))
        return 2
    outdir = HERE / "runs" / prereg["experiment_id"]
    outdir.mkdir(parents=True, exist_ok=False)

    role_sets = {
        "single_serial_analyst": ["single_analyst"] * 3,
        "isolated_specialists": ["quantitative_analyst", "source_auditor", "model_coupler"],
        "collaborating_specialists": ["quantitative_analyst", "source_auditor", "model_coupler"],
    }
    order = prereg["call_order_by_repeat"]
    all_calls: list[dict] = []
    spend_upper = 0.0
    reported_spend = 0.0
    for rep in range(1, 4):
        rep_key = f"repeat_{rep}"
        seed = prereg["matched_budget_and_access"]["model_and_parameters"]["seed_per_repeat"][rep - 1]
        for condition in order[rep_key]:
            earlier: list[dict] = []
            roles = role_sets[condition]
            for turn, role in enumerate(roles, start=1):
                visible_prior = [] if condition == "isolated_specialists" else earlier
                prompt = prompt_for(packet, condition, rep, turn, role, visible_prior)
                if len(prompt.encode()) > MAX_PROMPT_BYTES:
                    print(json.dumps({"error": "prompt_byte_limit", "repeat": rep, "condition": condition, "turn": turn}))
                    return 3
                # Reserve the preregistered worst-case token ceiling before any network request.
                reserve = MAX_INPUT * IN_RATE + MAX_OUTPUT * OUT_RATE
                if spend_upper + reserve > MAX_SPEND:
                    print(json.dumps({"error": "spend_ceiling", "repeat": rep, "condition": condition, "turn": turn}))
                    return 4
                spend_upper += reserve
                parsed, meta = call_model(key, prompt, seed)
                call = {
                    "repeat": rep,
                    "condition": condition,
                    "turn": turn,
                    "role": role,
                    "seed": seed,
                    "created_utc": now(),
                    "prompt_sha256": sha(prompt.encode()),
                    "packet_sha256": packet_hash,
                    "preregistration_sha256": prereg_hash,
                    "visible_prior_response_sha256": [item["sha256"] for item in visible_prior],
                    "prompt_bytes": len(prompt.encode()),
                    "response": parsed,
                    **meta,
                }
                path = outdir / f"r{rep}-{condition}-t{turn}.json"
                path.write_text(json.dumps(call, indent=2, ensure_ascii=False) + "\n")
                all_calls.append(call)
                usage = meta.get("usage")
                if isinstance(usage, dict) and isinstance(usage.get("cost"), (int, float)):
                    reported_spend += float(usage["cost"])
                print(json.dumps({"repeat": rep, "condition": condition, "turn": turn,
                                  "http_status": meta.get("http_status"),
                                  "valid_json": meta.get("parse_valid_json", False),
                                  "usage": meta.get("usage")}, ensure_ascii=False), flush=True)
                if reported_spend > MAX_SPEND:
                    print(json.dumps({"error": "provider_reported_spend_ceiling", "reported_spend_usd": round(reported_spend, 6)}), flush=True)
                    return 5
                if parsed is not None:
                    response_text = meta.get("response_text") or ""
                    earlier.append({"sha256": sha(response_text.encode()), "parsed": parsed})
    summary = {
        "experiment_id": prereg["experiment_id"],
        "completed_utc": now(),
        "preregistration_sha256": prereg_hash,
        "packet_sha256": packet_hash,
        "scheduled_calls": 27,
        "actual_recorded_calls": len(all_calls),
        "worst_case_reserved_cost_usd": round(spend_upper, 6),
        "provider_reported_cost_sum_usd": round(reported_spend, 6) if reported_spend else None,
        "usage": [c.get("usage") for c in all_calls],
        "call_files": sorted(p.name for p in outdir.glob("*.json")),
    }
    (outdir / "run_manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
