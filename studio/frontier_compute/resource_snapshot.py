"""Refresh public-safe allocation state; never treat allocation as utilization.

This only reads provider state. It does not dispatch, cancel, or retain job specs,
environment variables, injected files, or other teams' identifiers.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import statistics
from zoneinfo import ZoneInfo

PREFIXES = ("delphi-evolve-ops-", "bioservices-")
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "CANCELED", "STOPPED", "DELETED", "ERROR", "SUCCEEDED"}


def telemetry_summary(label: str, path: Path) -> dict:
    """Summarize actual device samples, retaining their original time window."""
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("empty telemetry")
    utilization = [float(row["utilization.gpu"]) for row in rows]
    if not all(0 <= value <= 100 for value in utilization):
        raise ValueError("invalid GPU utilization sample")

    def stamp(value):
        return datetime.strptime(value.strip(), "%Y/%m/%d %H:%M:%S.%f").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "task_label": label, "source": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "window_utc": [stamp(rows[0]["timestamp"]), stamp(rows[-1]["timestamp"])],
        "samples": len(rows), "sample_period_ms": 1000,
        "gpu_utilization_pct_mean": statistics.mean(utilization),
        "gpu_utilization_pct_max": max(utilization),
        "gpu_samples_ge90pct": sum(value >= 90 for value in utilization),
        "gpu_memory_used_mib_max": max(float(row["memory.used"]) for row in rows),
        "power_w_mean": statistics.mean(float(row["power.draw"]) for row in rows),
        "interpretation": "Historical sampled allocation window, including setup and artifact emission; not current utilization or a project-wide average.",
    }


def summarize(document: dict, observed: datetime) -> dict:
    if document.get("next_page_token"):
        raise ValueError("provider listing is paginated; refusing incomplete counts")
    own = []
    shared = Counter()
    for job in document.get("items", []):
        metadata, status, spec = (job.get(key, {}) for key in ("metadata", "status", "spec"))
        state = str(status.get("state", "UNKNOWN")).upper()
        shared[state] += 1
        if not metadata.get("name", "").startswith(PREFIXES):
            continue
        preset = str(spec.get("preset", ""))
        capacity = {name: int(value) for value, name in re.findall(r"(\d+)(gpu|vcpu|gb)", preset)}
        own.append({
            "id": metadata.get("id"), "name": metadata.get("name"),
            "created_at": metadata.get("created_at"), "state": state,
            "platform": spec.get("platform"), "preset": preset,
            "requested_capacity": capacity,
        })
    active = [row for row in own if row["state"] not in TERMINAL]
    states = dict(Counter(row["state"] for row in own))
    return {
        "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
        "scope": "Own job names beginning delphi-evolve-ops- or bioservices-; other-team state counts only",
        "own_job_count": len(own), "job_states": states, "own_jobs": own, "active_jobs": active,
        "shared_state_counts": dict(shared),
        "active_allocations": {
            "instances": len(active),
            "running_instances": sum(row["state"] == "RUNNING" for row in active),
            "pulling_instances": sum(row["state"] == "IMAGE_PULLING" for row in active),
            "gpus": sum(row["requested_capacity"].get("gpu", 0) for row in active),
            "vcpus": sum(row["requested_capacity"].get("vcpu", 0) for row in active),
            "memory_gb": sum(row["requested_capacity"].get("gb", 0) for row in active),
            "jobs_with_unknown_capacity": sum(not row["requested_capacity"] for row in active),
            "interpretation": "Requested capacity of nonterminal jobs, including startup. RUNNING is not measured GPU utilization. Kernel utilization is unknown until sampled telemetry is collected.",
        },
        "current_gpu_utilization_pct": None,
    }


def refresh(path: Path, cli: str) -> dict:
    start = datetime.now(timezone.utc)
    result = subprocess.run(
        [cli, "--profile", "hackathon", "ai", "job", "list", "--format", "json"],
        capture_output=True, text=True, timeout=45, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"provider read failed with exit {result.returncode}; old snapshot retained")
    observed = datetime.now(timezone.utc)
    snapshot = summarize(json.loads(result.stdout), observed)
    snapshot["live_state_request_window_utc"] = [start.isoformat(), observed.isoformat()]
    inventory = json.loads(path.read_text())
    prior = inventory["compute"]["nebius"]
    inventory["compute"]["nebius"] = {**prior, **snapshot}
    local = observed.astimezone(ZoneInfo("America/Los_Angeles"))
    offset = local.strftime("%z")
    inventory["observed_at"] = {
        "utc": snapshot["observed_at_utc"],
        "seattle": local.strftime("%Y-%m-%d %H:%M:%S %Z") + f" (UTC{offset[:3]}:{offset[3:]})",
    }
    inventory["scope"]["nebius_filter"] = snapshot["scope"]
    inventory["scope"]["limitations"] = list(dict.fromkeys([
        *inventory["scope"]["limitations"],
        "Only Nebius job allocation state was refreshed at observed_at; other evidence retains its own original timestamp.",
    ]))
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(inventory, indent=2) + "\n")
    temporary.replace(path)
    return snapshot


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("results/resources/resource-inventory.json"))
    parser.add_argument("--cli", default=str(Path.home() / ".nebius/bin/nebius"))
    args = parser.parse_args()
    print(json.dumps(refresh(args.inventory, args.cli), indent=2))
