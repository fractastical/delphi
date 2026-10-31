#!/usr/bin/env python3
"""Neutral JSON transport/configuration check; not part of the science pilot."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
MODEL = "models/gemini-3.8-flash"
PROMPT = "Return only a JSON object with status set to ready and count set to integer 3."
MAX_OUTPUT = 1200
THINKING_LEVEL = "low"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_auth_key() -> str:
    spec = importlib.util.spec_from_file_location("pilot_runner", HERE / "run_pilot.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner.auth_key()


def main() -> int:
    started = utc_now()
    prompt_hash = sha(PROMPT.encode())
    record = {
        "schema": "frontier.capability-agency.schema-smoke/1",
        "purpose": "Neutral JSON transport/configuration smoke test; excluded from science outcomes.",
        "request_started_utc": started,
        "model": MODEL,
        "endpoint": API,
        "generation_config": {
            "temperature": 0,
            "maxOutputTokens": MAX_OUTPUT,
            "responseMimeType": "application/json",
            "seed": 882031,
            "thinkingConfig": {"thinkingLevel": THINKING_LEVEL},
        },
        "prompt_sha256": prompt_hash,
        "secret_values_recorded": False,
    }
    try:
        key = load_auth_key()
        body = {
            "contents": [{"role": "user", "parts": [{"text": PROMPT}]}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": MAX_OUTPUT,
                "seed": 882031,
                "responseMimeType": "application/json",
                "thinkingConfig": {"thinkingLevel": THINKING_LEVEL},
            },
        }
        req = urllib.request.Request(
            API,
            data=json.dumps(body).encode(),
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=90) as response:
            decoded = json.loads(response.read(1_000_000))
            record["http_status"] = response.status
        candidates = decoded.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        record.update({
            "model_version": decoded.get("modelVersion"),
            "finish_reason": candidates[0].get("finishReason") if candidates else None,
            "usage_metadata": decoded.get("usageMetadata"),
            "response_text": text,
            "response_sha256": sha(text.encode()),
            "parsed_json": parsed,
            "schema_check_passed": parsed == {"status": "ready", "count": 3},
            "elapsed_seconds": round(time.monotonic() - t0, 3),
        })
    except urllib.error.HTTPError as exc:
        raw_error = exc.read(16_000)
        try:
            error_value = json.loads(raw_error)
            message = error_value.get("error", {}).get("message")
        except (json.JSONDecodeError, AttributeError):
            message = raw_error.decode("utf-8", errors="replace")
        record.update({"http_status": exc.code, "error": "provider_http_error",
                       "error_message": str(message).replace(key, "[REDACTED]") if 'key' in locals() else str(message)})
    except Exception as exc:
        record.update({"error_type": type(exc).__name__})
    record["request_finished_utc"] = utc_now()
    attempt = 1
    while (HERE / f"neutral_schema_smoke_attempt{attempt}.json").exists():
        attempt += 1
    record["attempt"] = attempt
    out = HERE / f"neutral_schema_smoke_attempt{attempt}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: record.get(k) for k in ("http_status", "model_version", "finish_reason", "usage_metadata", "parsed_json", "schema_check_passed", "error_type", "error_message")}))
    return 0 if record.get("schema_check_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
