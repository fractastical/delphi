"""Refresh public-safe allocation state; never treat allocation as utilization.

This only reads provider state. It does not dispatch, cancel, or retain job specs,
environment variables, injected files, or other teams' identifiers.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import statistics
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

PREFIXES = ("delphi-evolve-ops-", "bioservices-")
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "CANCELED", "STOPPED", "DELETED", "ERROR", "SUCCEEDED"}


def own_state_counts(jobs):
    """Stable typed counts from provider presets; missing capacity stays unknown."""
    counts = {kind: Counter() for kind in ("gpu", "cpu", "unknown")}
    for job in jobs:
        capacity = job.get("requested_capacity", {})
        kind = "gpu" if capacity.get("gpu", 0) > 0 else "cpu" if capacity.get("vcpu", 0) > 0 else "unknown"
        counts[kind][job["state"]] += 1
    return {kind: dict(states) for kind, states in counts.items()}


def refresh_usage(usage, snapshot, shared):
    """Keep website counts and attribution on the exact same provider window."""
    result = dict(usage)
    result.update({
        "observed_at_utc": snapshot["observed_at_utc"],
        "observed_at_seattle": shared["observed_at_seattle"],
        "provider_window_utc": snapshot["live_state_request_window_utc"],
        "own_jobs": snapshot["own_jobs"],
        "own_job_state_counts": own_state_counts(snapshot["own_jobs"]),
        "active_allocations": snapshot["active_allocations"],
        "instantaneous_gpu_utilization_pct": snapshot["current_gpu_utilization_pct"],
        "own_job_state_counts_scope": "Current Frontier prefix jobs only; resource kind comes from the provider preset, with absent capacity kept unknown.",
        "team_attribution": {
            **shared,
            "current_frontier_jobs": snapshot["current_frontier_job_count"],
            "historical_team_jobs": snapshot["historical_team_job_count"],
            "unattributed_jobs": snapshot["unattributed_job_count"],
        },
    })
    if "measured_terminal_container_work" in snapshot:
        result["measured_terminal_container_work"] = snapshot["measured_terminal_container_work"]
    return result


def telemetry_summary(label: str, path: Path) -> dict:
    """Summarize actual device samples, retaining their original time window."""
    with path.open() as stream:
        rows = [{key.strip().split(" [")[0]: value.strip() for key, value in row.items()}
                for row in csv.DictReader(stream)]
    if not rows:
        raise ValueError("empty telemetry")
    def number(row, key):
        value = float(row[key].split()[0])
        if not math.isfinite(value):
            raise ValueError("invalid GPU telemetry sample")
        return value

    utilization = [number(row, "utilization.gpu") for row in rows]
    if not all(0 <= value <= 100 for value in utilization):
        raise ValueError("invalid GPU utilization sample")

    times = [datetime.strptime(row["timestamp"], "%Y/%m/%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
             for row in rows]
    intervals_ms = [(later - earlier).total_seconds() * 1000 for earlier, later in zip(times, times[1:])]
    if any(interval <= 0 for interval in intervals_ms):
        raise ValueError("GPU telemetry timestamps are not strictly increasing")

    return {
        "task_label": label, "source": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "window_utc": [time.isoformat().replace("+00:00", "Z") for time in (times[0], times[-1])],
        "samples": len(rows), "sample_period_ms": statistics.median(intervals_ms) if intervals_ms else None,
        "sample_period_definition": "Median observed interval, not an assumed polling rate",
        "gpu_utilization_pct_mean": statistics.mean(utilization),
        "gpu_utilization_pct_max": max(utilization),
        "gpu_samples_ge90pct": sum(value >= 90 for value in utilization),
        "gpu_memory_used_mib_max": max(number(row, "memory.used") for row in rows),
        "power_w_mean": statistics.mean(number(row, "power.draw") for row in rows),
        "interpretation": "Historical sampled allocation window, including setup and artifact emission; not current utilization or a project-wide average.",
    }


def ownership_class(job, historical=()):
    """Read-only attribution; this never grants controller cancellation rights."""
    metadata = job.get("metadata", {})
    if metadata.get("name", "").startswith(PREFIXES):
        return "current_frontier"
    for row in historical:
        if metadata.get("id") == row["id"]:
            if metadata.get("name") != row["name"]:
                raise ValueError("Historical ownership ID/name mismatch")
            return "historical_team"
    return "unattributed"


def terminal_runtime_summary(directory, own_jobs):
    """Deduplicate measured container durations, retaining each exact receipt."""
    own = {row["id"]: row for row in own_jobs}
    rows = {}
    for path in sorted(Path(directory).rglob("manifest*.json")):
        document = json.loads(path.read_text())
        for run in document.get("owned", []):
            jid = run.get("id")
            result = run.get("result") or {}
            seconds = result.get("wall_s")
            if jid not in own or seconds is None:
                continue
            if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
                raise ValueError("Invalid measured container duration")
            if own[jid]["state"] not in TERMINAL:
                continue
            row = {"job_id": jid, "kind": "gpu" if "gpu" in own[jid]["preset"] else "cpu",
                   "provider_state": own[jid]["state"], "container_seconds": seconds,
                   "receipt": str(path), "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                   "truncated": result.get("truncated"), "timed_out": result.get("timed_out")}
            if jid in rows and rows[jid]["container_seconds"] != seconds:
                raise ValueError("Conflicting measured durations for one job")
            rows[jid] = row
    totals = {kind: {"jobs": sum(r["kind"] == kind for r in rows.values()),
                     "seconds": round(sum(r["container_seconds"] for r in rows.values() if r["kind"] == kind), 6)}
              for kind in ("gpu", "cpu")}
    return {"schema": "frontier.measured-container-runtime/1", "totals": totals,
            "rows": list(rows.values()),
            "scope": "Subset of exact owned terminal controller receipts, including failures. Container duration includes setup and emission; it is not GPU kernel time or all historical usage. GCP VM time is excluded."}


def summarize_shared(document, observed, historical=()):
    if document.get("next_page_token"):
        raise ValueError("provider listing is paginated; refusing incomplete counts")
    local = observed.astimezone(ZoneInfo("America/Los_Angeles"))
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    jobs = document.get("items", [])

    def key(job):
        group = "other_or_unattributed" if ownership_class(job, historical) == "unattributed" else "ours"
        kind = "gpu" if "gpu" in job.get("spec", {}).get("preset", "") else "cpu_or_unknown"
        return group, kind, job.get("status", {}).get("state", "UNKNOWN")

    def counts(rows):
        return [{"group": group, "kind": kind, "state": state, "jobs": count}
                for (group, kind, state), count in sorted(Counter(map(key, rows)).items())]

    today = [j for j in jobs if datetime.fromisoformat(j["metadata"]["created_at"].replace("Z", "+00:00")) >= midnight]
    return {
        "observed_at_utc": observed.isoformat(), "observed_at_seattle": local.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "classification": "Current Frontier prefixes plus exact historical team IDs verified against preserved source records. Remaining jobs are unattributed, not asserted to belong to another team. Cancellation permissions unchanged.",
        "listed_total": len(jobs), "today_start_utc": midnight.isoformat(),
        "ownership_breakdown": dict(Counter(ownership_class(j, historical) for j in jobs)),
        "earliest_listed_creation": min((j["metadata"]["created_at"] for j in jobs), default=None),
        "counts": {"all_listed": counts(jobs), "today": counts(today)},
        "current_gpu_jobs": {group: dict(Counter(key(j)[2] for j in jobs if key(j)[:2] == (group, "gpu") and key(j)[2] not in TERMINAL))
                             for group in ("ours", "other_or_unattributed")},
        "owner_field_names_present": sorted({key for j in jobs for key in j.get("metadata", {})
                                             if any(part in key.lower() for part in ("owner", "creator", "label"))}),
        "historical_attribution_ledger": "results/resources/team-job-ownership.json",
    }


def summarize(document: dict, observed: datetime, historical=()) -> dict:
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
    classes = Counter(ownership_class(j, historical) for j in document.get("items", []))
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
        "current_frontier_job_count": classes["current_frontier"],
        "historical_team_job_count": classes["historical_team"],
        "team_job_count": classes["current_frontier"] + classes["historical_team"],
        "unattributed_job_count": classes["unattributed"],
        "team_count_scope": "Current Frontier prefix count remains separate from exact-ID historical attribution; no cancellation permissions are changed.",
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
    document = json.loads(result.stdout)
    ledger_path = path.parent / "team-job-ownership.json"
    historical = json.loads(ledger_path.read_text())["historical_jobs"] if ledger_path.exists() else []
    snapshot = summarize(document, observed, historical)
    snapshot["live_state_request_window_utc"] = [start.isoformat(), observed.isoformat()]
    inventory = json.loads(path.read_text())
    prior = inventory["compute"]["nebius"]
    inventory["compute"]["nebius"] = {**prior, **snapshot}
    runtime_directory = path.parent.parent / "infra"
    if runtime_directory.is_dir():
        runtime = terminal_runtime_summary(runtime_directory, snapshot["own_jobs"])
        runtime_path = path.parent / "terminal-runtime-receipts.json"
        runtime_path.write_text(json.dumps(runtime, indent=2) + "\n")
        snapshot["measured_terminal_container_work"] = {
            **runtime["totals"], "scope": runtime["scope"], "receipt": str(runtime_path)}
        inventory["compute"]["nebius"]["measured_terminal_container_work"] = snapshot["measured_terminal_container_work"]
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
    shared_path = path.parent / "shared-job-counts.json"
    shared = summarize_shared(document, observed, historical)
    shared["request_window_utc"] = [start.isoformat(), observed.isoformat()]
    temporary = shared_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(shared, indent=2) + "\n")
    temporary.replace(shared_path)
    usage_path = path.parent / "hackathon-usage.json"
    if usage_path.exists():
        usage = refresh_usage(json.loads(usage_path.read_text()), snapshot, shared)
        temporary = usage_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(usage, indent=2) + "\n")
        temporary.replace(usage_path)
    return snapshot


def gcp_allocation(instances, quotas):
    """Only RUNNING owned VMs count as allocated; quota is a separate unit."""
    owned = [row for row in instances if row.get("name", "").startswith(("frontier-cpu-", "frontier-gpu-"))]
    running = [row for row in owned if row.get("status") == "RUNNING"]
    cpu = 0
    for row in running:
        match = re.search(r"(?:e2|g2)-standard-(\d+)$", row.get("machineType", ""))
        if not match:
            raise ValueError("Unknown owned machine type; cannot infer allocated CPUs")
        cpu += int(match.group(1))
    gpu = sum(acc.get("acceleratorCount", 0) for row in running for acc in row.get("guestAccelerators", []))
    allowed = {"name", "id", "status", "zone", "machineType", "lastStartTimestamp", "guestAccelerators"}
    quota_limits = {row.get("metric"): row.get("limit") for row in quotas}
    return {
        "instances": [{key: value for key, value in row.items() if key in allowed} for row in owned],
        "active_allocated_vcpus": cpu, "active_allocated_gpus": gpu,
        "active_cpu_vms": sum(not row.get("guestAccelerators") for row in running),
        "active_gpu_vms": sum(bool(row.get("guestAccelerators")) for row in running),
        "quotas": [row for row in quotas if row.get("metric") in ("CPUS_ALL_REGIONS", "GPUS_ALL_REGIONS")],
        "global_cpu_limit": quota_limits.get("CPUS_ALL_REGIONS"),
        "gpu_quota_granted": quota_limits.get("GPUS_ALL_REGIONS"),
        "instantaneous_cpu_utilization": None,
    }


def refresh_gcp(directory: Path, project: str) -> dict:
    """Read allocation/quota and timestamped CPU metrics without retaining tokens."""
    def command(args):
        result = subprocess.run(["gcloud", *args], capture_output=True, text=True, timeout=45)
        if result.returncode:
            raise RuntimeError(f"GCP read failed with exit {result.returncode}; no command output retained")
        return result.stdout

    start = datetime.now(timezone.utc)
    instances = json.loads(command(["compute", "instances", "list", "--project", project,
                                  "--format=json(name,id,status,zone,machineType,lastStartTimestamp,guestAccelerators)"]))
    quota = json.loads(command(["compute", "project-info", "describe", "--project", project, "--format=json(quotas)"]))
    result = gcp_allocation(instances, quota.get("quotas", []))
    result.update(project=project, observed_at_utc=datetime.now(timezone.utc).isoformat(),
                  request_started_utc=start.isoformat(), cost=None)
    running_ids = {str(row["id"]) for row in result["instances"] if row["status"] == "RUNNING"}
    metric = {"observed_utc": result["observed_at_utc"], "metric": "compute.googleapis.com/instance/cpu/utilization",
              "series": [], "scope": "Provider timestamped CPU fractions; allocation is not utilization; no scientific-success or billing inference"}
    if running_ids:
        token = command(["auth", "print-access-token"]).strip()
        query = urllib.parse.urlencode({
            "filter": 'metric.type="compute.googleapis.com/instance/cpu/utilization" AND resource.type="gce_instance"',
            "interval.startTime": (start - timedelta(minutes=15)).isoformat(),
            "interval.endTime": start.isoformat(), "view": "FULL", "pageSize": "1000",
        })
        request = urllib.request.Request(
            f"https://monitoring.googleapis.com/v3/projects/{project}/timeSeries?{query}",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("GCP metric response exceeds limit")
        document = json.loads(raw)
        if document.get("nextPageToken"):
            raise ValueError("GCP metrics paginated; refuse incomplete snapshot")
        metric["series"] = [row for row in document.get("timeSeries", [])
                            if row.get("resource", {}).get("labels", {}).get("instance_id") in running_ids]
    runtime_path = directory / "runtime-status.json"
    runtime = json.loads(runtime_path.read_text()) if runtime_path.exists() else {}
    runtime.update(result)
    runtime["status_update_utc"] = result["observed_at_utc"]
    runtime["active_vcpus"] = result["active_allocated_vcpus"]
    runtime["active_gpu_count"] = result["active_allocated_gpus"]
    runtime["metric_receipt"] = str(directory / "cpu-metric-current.json")
    runtime["state"] = "Read-only allocation snapshot; scientific stages retain their separately dated receipts."
    for path, payload in ((runtime_path, runtime), (directory / "cpu-metric-current.json", metric)):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n")
        temporary.replace(path)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("results/resources/resource-inventory.json"))
    parser.add_argument("--cli", default=str(Path.home() / ".nebius/bin/nebius"))
    parser.add_argument("--gcp-project", help="Refresh owned Google allocation/quota/CPU metrics instead of Nebius")
    args = parser.parse_args()
    snapshot = refresh_gcp(args.inventory.parent / "gcp", args.gcp_project) if args.gcp_project else refresh(args.inventory, args.cli)
    print(json.dumps(snapshot, indent=2))
