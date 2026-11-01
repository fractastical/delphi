"""Recompute a pinned prospective fin-ray predicate, without calling it biology."""
from hashlib import sha256
import json
import math
import re
import subprocess


def verify(sources, path):
    ensemble = sources.read(path)
    if ensemble.get("schema") != "frontier.assurance.ensemble/1":
        raise ValueError("unsupported ensemble schema")
    protocol_path = ensemble["protocol"]["path"]
    protocol = sources.read(protocol_path)
    expected = ensemble["protocol"]["sha256"]
    if sources.pin(protocol_path)["sha256"] != expected or protocol["predicate"] != ensemble["predicate"]:
        raise ValueError("protocol or predicate mismatch")
    commit, revision = ensemble["protocol_commit"], ensemble["run_code_revision"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("invalid protocol/run revision")
    frozen = subprocess.check_output(["git", "-C", str(sources.root), "show", commit + ":" + protocol_path], timeout=5)
    if sha256(frozen).hexdigest() != expected:
        raise ValueError("committed protocol bytes do not match")
    if subprocess.run(["git", "-C", str(sources.root), "merge-base", "--is-ancestor", commit, revision], timeout=5, capture_output=True).returncode:
        raise ValueError("protocol commit does not precede declared run-code revision")
    if protocol["predicate"].get("declared_before_runs") is not True:
        raise ValueError("predicate not declared prospectively")
    records, seen, numerator, dependencies = {}, set(), 0, set()
    for row in ensemble["runs"]:
        if row["id"] in seen or row["protocol_sha256"] != expected:
            raise ValueError("duplicate trial or protocol mismatch")
        seen.add(row["id"])
        pointer = row["result_artifact"]
        match = re.fullmatch(r"\$\.candidates\[(\d+)\]\.runs\[(\d+)\]", pointer["selector"])
        if not match:
            raise ValueError("unsupported result selector")
        if pointer["path"] not in records:
            records[pointer["path"]] = sources.read(pointer["path"])
        if sources.pin(pointer["path"])["sha256"] != pointer["sha256"]:
            raise ValueError("result artifact digest mismatch")
        all_runs = records[pointer["path"]]
        candidate_index, run_index = map(int, match.groups())
        candidate = all_runs["candidates"][candidate_index]
        actual = candidate["runs"][run_index]
        if actual["id"] != row["id"] or candidate["candidate"] != ensemble["candidate"]:
            raise ValueError("trial/candidate mismatch")
        input_bytes = json.dumps({"draw": all_runs["draws"][run_index], "candidate": ensemble["candidate"]}, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if sha256(input_bytes).hexdigest() != row["input_sha256"]:
            raise ValueError("input digest mismatch")
        passed = True
        for case in ("uniform", "tip_same_total_force"):
            metrics = actual["cases"][case]["summary"]
            if metrics != row["summary"][case]:
                raise ValueError("saved metrics and ensemble summary differ")
            tip, slope = metrics["tip_over_L"], metrics["max_slope_rad"]
            if not math.isfinite(tip) or not math.isfinite(slope):
                raise ValueError("nonfinite trial metrics")
            passed &= abs(tip) <= protocol["predicate"]["tip_over_length_limit"] and abs(slope) <= protocol["predicate"]["slope_limit_rad"]
        if type(row["passed"]) is not bool or row["passed"] != passed or actual["passed"] != passed:
            raise ValueError("predicate result mismatch")
        numerator += int(passed)
        dependencies.update(row["shared_input_groups"])
    denominator = len(seen)
    if not denominator or denominator != protocol["parameter_draws"] or denominator != ensemble["denominator"] or numerator != ensemble["numerator"]:
        raise ValueError("empty ensemble or numerator/denominator mismatch")
    if ensemble["fraction"] != numerator / denominator:
        raise ValueError("reported fraction mismatch")
    return {"candidate": ensemble["candidate"], "status": "predicate_recomputed", "numerator": numerator, "denominator": denominator,
            "fraction": numerator / denominator, "predicate": ensemble["predicate"], "protocol_commit": commit, "run_code_revision": revision,
            "region_ids": sorted({region for row in ensemble["runs"] for region in row["region_ids"]}),
            "shared_input_groups": sorted(dependencies), "biological_success_probability": None,
            "scope": "Fraction over the declared simulated scenarios only; paired load shapes/meshes are one trial, not biological success probability",
            "ordering_check": "Committed protocol bytes match; protocol commit is ancestor of declared pre-run code revision. Actual wall-time execution ordering is author-reported, not independently witnessed.",
            "evidence": [sources.pin(path), sources.pin(protocol_path), *[sources.pin(name) for name in records]]}
