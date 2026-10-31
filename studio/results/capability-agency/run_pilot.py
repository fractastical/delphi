#!/usr/bin/env python3
"""Run the frozen, public-input capability/agency pilot once, without retries."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
MODEL = "models/gemini-3.8-flash"
MAX_INPUT = 9600
MAX_OUTPUT = 400
MAX_PROMPT_BYTES = 9000
MAX_TOTAL_TOKENS = 270_000


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def auth_key() -> str:
    path = Path.home() / ".config/morphoswarm/gemini.env"
    if not path.exists() or path.stat().st_mode & 0o077:
        raise RuntimeError("Gemini credential file missing or permissions are broader than 0600")
    with path.open() as stream:
        for line in stream:
            if line.startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
                if key:
                    return key
    raise RuntimeError("GEMINI_API_KEY not found in configured credential file")


def prompt_for(packet: dict, rep: int, turn: int, role: str,
               earlier: list[dict]) -> str:
    prior = []
    for item in earlier:
        prior.append({"turn_id": item["turn"], "actor_role": item["role"],
                      "sha256": item["sha256"], "response": item["parsed"]})
    payload = {
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
        "systemInstruction": {
            "parts": [{"text": (
                "You are one analyst in a controlled public-data science evaluation. "
                "Use only the supplied public input packet and deterministic outputs. "
                "Do not browse, call tools, inspect files, or add outside facts. "
                "Return one JSON object matching the response contract exactly, with "
                "both task objects. Cite each task using its DOI. Choose only a "
                "decision_code listed in the packet. No markdown or prose outside JSON."
            )}]
        },
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": MAX_OUTPUT,
            "seed": seed,
            "responseMimeType": "application/json",
        },
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read(1_000_000)
            status = response.status
        decoded = json.loads(raw)
        candidates = decoded.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        content = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        try:
            parsed = json.loads(content) if isinstance(content, str) else None
        except json.JSONDecodeError:
            parsed = None
        meta = {
            "http_status": status,
            "provider_response_id": decoded.get("responseId"),
            "model_returned": decoded.get("modelVersion", MODEL),
            "provider_returned": "Google Generative Language API",
            "candidate_finish_reason": candidates[0].get("finishReason") if candidates else None,
            "usage": decoded.get("usageMetadata"),
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
    if prereg.get("status") != "FROZEN_BEFORE_MODEL_CALLS" or "PENDING" in prereg.get("registered_utc", ""):
        print(json.dumps({"error": "preregistration_not_frozen"}))
        return 1
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
    reserved_tokens = 0
    stop_after_current = False
    for rep in range(1, 4):
        rep_key = f"repeat_{rep}"
        seed = prereg["matched_budget_and_access"]["model_and_parameters"]["seed_per_repeat"][rep - 1]
        for condition in order[rep_key]:
            earlier: list[dict] = []
            roles = role_sets[condition]
            for turn, role in enumerate(roles, start=1):
                visible_prior = [] if condition == "isolated_specialists" else earlier
                prompt = prompt_for(packet, rep, turn, role, visible_prior)
                if len(prompt.encode()) > MAX_PROMPT_BYTES:
                    print(json.dumps({"error": "prompt_byte_limit", "repeat": rep, "condition": condition, "turn": turn}))
                    return 3
                # Reserve the preregistered worst-case token ceiling before any network request.
                reserve = MAX_INPUT + MAX_OUTPUT
                if reserved_tokens + reserve > MAX_TOTAL_TOKENS:
                    print(json.dumps({"error": "token_ceiling", "repeat": rep, "condition": condition, "turn": turn}))
                    return 4
                reserved_tokens += reserve
                parsed, meta = call_model(key, prompt, seed)
                usage = meta.get("usage") if isinstance(meta.get("usage"), dict) else {}
                input_tokens = usage.get("promptTokenCount")
                output_tokens = usage.get("candidatesTokenCount")
                total_tokens = usage.get("totalTokenCount")
                usage_over_ceiling = (
                    isinstance(input_tokens, int) and input_tokens > MAX_INPUT
                ) or (
                    isinstance(output_tokens, int) and output_tokens > MAX_OUTPUT
                ) or (
                    isinstance(total_tokens, int) and total_tokens > MAX_INPUT + MAX_OUTPUT
                )
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
                    "usage_protocol_deviation": usage_over_ceiling,
                    "response": parsed,
                    **meta,
                }
                path = outdir / f"r{rep}-{condition}-t{turn}.json"
                path.write_text(json.dumps(call, indent=2, ensure_ascii=False) + "\n")
                all_calls.append(call)
                print(json.dumps({"repeat": rep, "condition": condition, "turn": turn,
                                  "http_status": meta.get("http_status"),
                                  "valid_json": meta.get("parse_valid_json", False),
                                  "usage_protocol_deviation": usage_over_ceiling,
                                  "usage": meta.get("usage")}, ensure_ascii=False), flush=True)
                if usage_over_ceiling:
                    stop_after_current = True
                    break
                if parsed is not None:
                    response_text = meta.get("response_text") or ""
                    earlier.append({"turn": turn, "role": role,
                                    "sha256": sha(response_text.encode()), "parsed": parsed})
            if stop_after_current:
                break
        if stop_after_current:
            break
    summary = {
        "experiment_id": prereg["experiment_id"],
        "completed_utc": now(),
        "preregistration_sha256": prereg_hash,
        "packet_sha256": packet_hash,
        "scheduled_calls": 27,
        "actual_recorded_calls": len(all_calls),
        "maximum_reserved_tokens": reserved_tokens,
        "actual_provider_cost_usd": None,
        "provider_billing_meter_available": False,
        "usage": [c.get("usage") for c in all_calls],
        "call_files": sorted(p.name for p in outdir.glob("*.json")),
    }
    (outdir / "run_manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 6 if stop_after_current else 0


if __name__ == "__main__":
    raise SystemExit(main())
