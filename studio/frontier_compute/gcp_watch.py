"""Bounded read-only collection of newly published GCP task snapshots."""

import argparse
import json
from pathlib import Path
import time

from frontier_compute.gcp_artifacts import DEFAULT_BUCKET, GCS, collect


def watch(gcs, bucket, prefix, destination, state_path, *, max_bytes=3_200_000_000,
          runtime_s=86_400, interval_s=300, monotonic=time.monotonic,
          sleep=time.sleep, collector=collect):
    if not 1 <= runtime_s <= 86_400 or not 1 <= interval_s <= 3600:
        raise ValueError("Invalid bounded collection schedule")
    if not prefix.startswith(("jobs/frontier-cpu-", "jobs/frontier-gpu-")) or ".." in prefix.split("/"):
        raise ValueError("Only owned Frontier task prefixes are allowed")
    start = monotonic()
    generation = None
    events = []
    state_path = Path(state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    while monotonic() - start < runtime_s:
        event = {"observed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        terminal = False
        try:
            objects = gcs.list_objects(bucket, prefix.rstrip("/") + "/")
            manifests = [x for x in objects if "/manifests/" in x.get("name", "")
                         and x["name"].endswith(".json")]
            latest = max((int(x["generation"]) for x in manifests), default=None)
            if latest is not None and latest != generation:
                result = collector(gcs, bucket, prefix, Path(destination), max_bytes)
                event.update(state="collected", complete=result["complete"],
                             receipt=result["receipt_path"],
                             artifacts=len(result["artifacts"]))
                generation = latest
                terminal = result["complete"]
            else:
                event["state"] = "no_new_manifest"
        except (OSError, RuntimeError, ValueError, KeyError) as error:
            event.update(state="collection_error", error=str(error)[:1000])
        events.append(event)
        state = {"schema": "frontier.gcp-collection-watch/1", "bucket": bucket,
                 "prefix": prefix, "runtime_s": runtime_s, "interval_s": interval_s,
                 "complete_export": terminal, "events": events,
                 "scope": "Export completion is not scientific success; inspect the task exit code and gates in its receipt."}
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n")
        temporary.replace(state_path)
        print(json.dumps(event), flush=True)
        if terminal:
            return 0
        next_poll = min(start + runtime_s, monotonic() + interval_s)
        while monotonic() < next_poll:
            sleep(min(60, next_poll - monotonic()))
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--runtime-s", type=int, default=86_400)
    parser.add_argument("--interval-s", type=int, default=300)
    args = parser.parse_args()
    raise SystemExit(watch(GCS.local(), args.bucket, args.prefix, args.destination,
                           args.state, runtime_s=args.runtime_s, interval_s=args.interval_s))
