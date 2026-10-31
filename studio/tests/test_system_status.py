"""GET /api/system and frontier/system_status.py. Real PostgreSQL (scripts/test_postgres.sh), real HTTP; the two fixed commands use a recording fake except in
the one test that runs them for real."""
import ast
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import TOKENS, assessment, claim
from frontier import system_status as ss
from frontier.models import ref
from test_web import GATE, Web

ROOT = Path(__file__).resolve().parents[1]

SYSTEMCTL_OUT = """Id=delphi-frontier-web.service
LoadState=loaded
ActiveState=active
SubState=running
NRestarts=0
MemoryCurrent=104857600
TasksCurrent=7
ActiveEnterTimestamp=Sat 2026-10-31 12:00:00 PDT

Id=delphi-frontier-postgres.service
LoadState=loaded
ActiveState=active
SubState=running
NRestarts=2
MemoryCurrent=18446744073709551615
TasksCurrent=[not set]
ActiveEnterTimestamp=Sat 2026-10-31 11:50:00 PDT
"""
SHA = "ab" * 20


class Recorder:
    def __init__(self, sha=SHA, systemctl=SYSTEMCTL_OUT, delay=0.0):
        self.calls, self.sha, self.systemctl, self.delay = [], sha, systemctl, delay

    def __call__(self, argv, timeout):
        self.calls.append(tuple(argv))
        if self.delay:
            time.sleep(min(self.delay, timeout + 0.5))
            if self.delay > timeout:
                raise subprocess.TimeoutExpired(argv, timeout)
        return (0, self.sha + "\n") if tuple(argv) == ss.GIT_CMD else (0, self.systemctl)


@pytest.fixture
def site(tmp_path):
    s = tmp_path / "site"
    s.mkdir()
    (s / "index.html").write_text("<p>x</p>")
    return s


@pytest.fixture
def checkout(tmp_path):
    """A small fake deployed checkout with every file kind the page describes."""
    r = tmp_path / "app"
    (r / "tasks").mkdir(parents=True)
    (r / "specs").mkdir()
    (r / "deploy" / "system").mkdir(parents=True)
    (r / "results" / "compute").mkdir(parents=True)
    (r / "tasks" / "BUILD.md").write_text("# Board\n\n| Priority | Deliverable | Owner | Status / acceptance |\n| --- | --- | --- | --- |\n"
                                          "| P0 | Site | claude-02 | Implementing |\n| P1 | Search | dx-submit | Delivered |\n\n"
                                          "## Findings to correct during integration\n\n- First finding that continues\n  on a second line.\n- Second finding.\n\n## Other\n\n- not a finding\n")
    (r / "specs" / "SPEC-001-x.md").write_text("# SPEC-001 — Records\n\n**Status:** Draft · **Version:** 0.2.0\n")
    (r / "GOAL.md").write_text("# Delphi Frontier\n\n**What we know.**\n\nA living research commons.\n")
    receipts = {"jobs": [{"job_id": "aijob-1", "job_name": "ours-1", "job_state": "COMPLETED", "run_tag": "t1", "item": "i", "inner_rc": 0, "inner_wall_s": 191.6,
                          "timed_out": False, "returned_bundle_sha256": "3" * 64, "returned_bundle_bytes": 12, "secret_extra": "NOT-IN-ALLOWLIST",
                          "events": [{"kind": "cpu", "t": "2026-10-31T18:31:42Z"}, {"t": "2026-10-31T18:37:19Z"}]},
                         {"job_id": "aijob-2", "job_name": "ours-2", "job_state": "COMPLETED", "inner_wall_s": 125.6, "events": [{"kind": "gpu", "t": "2026-10-31T18:38:34Z"}]}],
                "price": "unavailable: the event exposes no price or usage receipt to participants (not zero)", "note": "ids copied from the controller manifest"}
    data = json.dumps(receipts).encode()
    (r / "results" / "compute" / "receipts.json").write_bytes(data)
    pins = {"schema": "frontier.system.receipt-pins/1", "pins": [{"id": "rc", "path": "results/compute/receipts.json", "sha256": hashlib.sha256(data).hexdigest(),
                                                                   "description": "pilot receipts", "pinned_from": "test"}]}
    (r / "deploy" / "system" / "receipt-pins.json").write_text(json.dumps(pins))
    (r / "build-info.json").write_text(json.dumps({"release_sha": SHA, "built_at": "2026-10-31T19:00:00Z",
                                                   "checks": [{"name": "suite", "command": "bash scripts/test_postgres.sh", "exit": 0, "passed": 122, "total": 122, "at": "2026-10-31T19:01:00Z"}]}))
    return r


def make_web(store, site, checkout, runner=None, **kw):
    return Web(store, site, system_root=checkout, system_runner=runner or Recorder(), **kw)


def seed(store):
    a = store.submit(TOKENS["alice"], "s1", claim(store, id="c-a"))["record"]
    store.submit(TOKENS["alice"], "s2", claim(store, id="c-b"))
    store.submit(TOKENS["alice"], "s3", claim(store, id="c-private", visibility="private"))
    store.review(TOKENS["bob"], "s4", assessment(ref(a), "bob"))
    return a


# ------------------------------------------------------------------ gate and shape
def test_system_is_gated_parameterless_and_every_section_is_labelled(store, site, checkout):
    w = make_web(store, site, checkout)
    try:
        assert w.req("GET", "/api/system", cookie=False)[0] == 401
        w.login()
        assert w.req("GET", "/api/system?x=1")[0] == 400 and w.req("POST", "/api/system", {})[0] in (400, 403, 405)
        s, body, h = w.json("GET", "/api/system")
        assert s == 200 and h["cache-control"] == "no-store" and body["schema"] == "frontier.system/1" and body["legend"]["measured"] and body["legend"]["worker_report"]
        for section in ("store", "process", "host", "services", "release", "build", "board", "specs", "goal", "resources"):
            assert body[section]["mode"] in ("measured", "worker_report"), section
        assert {k for k in ("store", "process", "host", "services", "release") if body[k]["mode"] == "measured"} == {"store", "process", "host", "services", "release"}
        assert {k for k in ("build", "board", "specs", "goal", "resources") if body[k]["mode"] == "worker_report"} == {"build", "board", "specs", "goal", "resources"}
        assert len(json.dumps(body)) < 100_000
    finally:
        w.close()


# ------------------------------------------------------------------ database counts are exact and public-only
def test_store_counts_match_the_database_and_exclude_private_rows(store, site, checkout):
    seed(store)
    snap = ss.SystemStatus(store, checkout, runner=Recorder()).snapshot()["store"]
    got = {(r["kind"], r["local_status"]): (r["versions"], r["heads"]) for r in snap["records_by_kind_and_local_status"]}
    assert got[("Claim", "accepted")] == (1, 1) and got[("Claim", "proposed")] == (1, 1)                    # c-a accepted, c-b proposed; c-private excluded
    assert sum(v for k, (v, h) in got.items() if k[0] == "Claim") == 2 and snap["public_only"] is True
    assert ("Assessment", "proposed") in got
    ev = {r["event_type"]: r["count"] for r in snap["events_by_type"]}
    assert ev["record_proposed"] == 2 and ev["review_recorded"] == 1 and ev["acceptance_changed"] == 1     # the private record's events are not counted
    assert snap["database"]["size_bytes"] > 0 and snap["database"]["uptime_seconds"] >= 0 and snap["namespace"] == store.namespace
    assert "c-private" not in json.dumps(snap)


def test_the_snapshot_writes_nothing(store, checkout):
    seed(store)
    before = ss.store_measurements(store)
    ss.SystemStatus(store, checkout, runner=Recorder()).snapshot()
    assert ss.store_measurements(store)["records_by_kind_and_local_status"] == before["records_by_kind_and_local_status"]
    with store.connection() as c:
        c.execute("SET TRANSACTION READ ONLY")
        with pytest.raises(Exception, match="read-only"):
            c.execute("INSERT INTO node_config VALUES (2, 'x', 1)")                                          # the guard the snapshot relies on really refuses writes
    assert "SET TRANSACTION READ ONLY" in (ROOT / "frontier" / "system_status.py").read_text()


# ------------------------------------------------------------------ /proc, process, labels
def test_host_and_process_numbers_are_real_and_labelled_shared_not_attributed():
    h, p = ss.host_measurements(), ss.process_measurements()
    live = open("/proc/loadavg").read().split()
    assert h["mode"] == "measured" and "Not attributable to any job, team or service" in h["scope"]
    assert abs(h["load_average"]["1m"] - float(live[0])) < 5 and h["cpu_count"] == os.cpu_count()
    assert h["memory_kb"]["MemTotal"] >= h["memory_kb"]["MemAvailable"] > 0
    assert p["scope"] == "this web process only" and p["resident_memory_kb"] > 0 and p["threads"] >= 1 and p["uptime_seconds"] >= 0
    assert set(p) == {"mode", "scope", "started_at", "uptime_seconds", "resident_memory_kb", "threads", "cpu_seconds", "python"}


def test_nothing_sensitive_is_exposed(store, site, checkout, monkeypatch):
    monkeypatch.setenv("FRONTIER_ACCESS_TOKEN", "ENV-SECRET-MARKER-123456")
    monkeypatch.setenv("FRONTIER_DSN", "host=/x password=hunter2-marker")
    w = make_web(store, site, checkout)
    try:
        w.login()
        text = w.req("GET", "/api/system")[2].decode()
    finally:
        w.close()
    for forbidden in ("ENV-SECRET-MARKER", "hunter2-marker", GATE, TOKENS["alice"], socket.gethostname(), os.path.expanduser("~"), "/home/", str(checkout),
                      "XDG_RUNTIME_DIR", "password", "NOT-IN-ALLOWLIST", '"cmdline"', '"environ"', "/proc/"):
        assert forbidden not in text, forbidden
    body = json.loads(text)
    assert str(os.getpid()) not in {str(v) for v in body["process"].values()} and "pid" not in body["process"]


# ------------------------------------------------------------------ fixed commands, parsing, budget
def test_only_the_two_fixed_commands_run_and_systemctl_output_is_parsed_strictly(store, checkout):
    rec = Recorder()
    snap = ss.SystemStatus(store, checkout, runner=rec).snapshot()
    assert rec.calls == [ss.GIT_CMD, ss.SYSTEMCTL_CMD]
    web, pg = snap["services"]["units"]
    assert web["unit"] == "delphi-frontier-web.service" and web["active_state"] == "active" and web["memory_current_bytes"] == 104857600 and web["tasks_current"] == 7
    assert pg["restarts"] == 2 and pg["memory_current_bytes"] is None and pg["tasks_current"] is None            # 2**64-1 and "[not set]" are not measurements
    assert snap["release"]["checkout_sha"] == SHA
    with pytest.raises(ValueError):
        ss.Fixed(checkout, rec).call(("ls", "/"))
    with pytest.raises(ValueError):
        ss.Fixed(checkout, rec).call(("systemctl", "--user", "show", "other.service"))
    assert [u["state"] for u in ss.parse_systemctl(None)] == ["unavailable", "unavailable"]
    assert [u["state"] for u in ss.parse_systemctl("garbage\nId=evil.service\nActiveState=active\n")] == ["unavailable", "unavailable"]


def test_a_slow_command_cannot_stretch_the_two_second_budget(store, checkout):
    t0 = time.monotonic()
    snap = ss.SystemStatus(store, checkout, runner=Recorder(delay=10)).snapshot()
    took = time.monotonic() - t0
    assert took < 3.5 and snap["release"]["checkout_sha"] is None and all(u["state"] == "unavailable" for u in snap["services"]["units"])
    assert snap["store"]["mode"] == "measured" and "records_by_kind_and_local_status" in snap["store"]           # the rest of the page still works


def test_the_real_fixed_commands_degrade_cleanly_here(store):
    snap = ss.SystemStatus(store).snapshot()                                      # real git and real systemctl, real checkout
    assert snap["release"]["checkout_sha"] is None or len(snap["release"]["checkout_sha"]) == 40
    assert len(snap["services"]["units"]) == 2 and all("unit" in u for u in snap["services"]["units"])


def test_no_shell_no_free_argv_in_the_source():
    src = (ROOT / "frontier" / "system_status.py").read_text()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "run" and getattr(n.func.value, "id", "") == "subprocess"]
    assert len(calls) == 1 and not any(k.arg == "shell" for k in calls[0].keywords)
    assert "os.system" not in src and "Popen" not in src and "environ.copy" not in src and "dict(os.environ" not in src


# ------------------------------------------------------------------ cache
def test_snapshots_are_cached_for_30_seconds_and_refresh_after(store, checkout):
    rec = Recorder()
    s = ss.SystemStatus(store, checkout, ttl=30, runner=rec)
    a = s.snapshot()
    b = s.snapshot()
    assert a["cache"]["cached"] is False and b["cache"]["cached"] is True and b["generated_at"] == a["generated_at"] and len(rec.calls) == 2
    assert ss.TTL_S == 30
    quick = ss.SystemStatus(store, checkout, ttl=0, runner=rec)
    quick.snapshot()
    assert quick.snapshot()["cache"]["cached"] is False and len(rec.calls) == 6


# ------------------------------------------------------------------ worker reports from files
def test_board_specs_goal_are_parsed_and_marked_worker_report(checkout):
    b = ss.board_report(checkout)
    assert b["mode"] == "worker_report" and b["rows"][0] == {"priority": "P0", "deliverable": "Site", "owner": "claude-02", "status_acceptance": "Implementing"}
    assert b["findings_to_correct"] == ["First finding that continues on a second line.", "Second finding."] and len(b["sha256"]) == 64
    sp = ss.specs_report(checkout)["specs"]
    assert sp == [{"id": "SPEC-001", "file": "SPEC-001-x.md", "title": "SPEC-001 — Records", "status_line": "**Status:** Draft · **Version:** 0.2.0", "sha256": sp[0]["sha256"]}]
    g = ss.goal_report(checkout)
    assert g["title"] == "Delphi Frontier" and g["summary"] == "**What we know.** A living research commons."


def test_the_real_tree_is_described_without_failing():
    m = ss.curated_manifest(ROOT)
    assert len(m["board"]["rows"]) >= 10 and all({"priority", "deliverable", "owner"} <= set(r) for r in m["board"]["rows"])
    assert {s["id"] for s in m["specs"]["specs"]} >= {"SPEC-001", "SPEC-005"} and m["goal"]["title"] == "Delphi Frontier"


def test_oversized_and_hostile_files_are_bounded(tmp_path):
    r = tmp_path / "x"
    (r / "tasks").mkdir(parents=True)
    (r / "tasks" / "BUILD.md").write_text("| a | b |\n| - | - |\n" + "".join(f"| {'x' * 400} | {i} |\n" for i in range(400)))
    b = ss.board_report(r)
    assert len(b["rows"]) == 100 and len(b["rows"][0]["a"]) == 300
    (r / "tasks" / "BUILD.md").write_bytes(b"x" * (ss.MAX_FILE + 1))
    assert ss.board_report(r)["status"] == "absent" and "bound" in ss.board_report(r)["reason"]
    (r / "GOAL.md").write_bytes(b"x" * (ss.MAX_FILE + 1))
    assert ss.goal_report(r)["status"] == "absent" and "bound" in ss.goal_report(r)["reason"]
    assert ss.read_small(r, "../outside")[0] is None and ss.read_small(r, "/etc/passwd")[0] is None and ss.read_small(r, ".git/config")[1] == "path not allowed"
    outside = tmp_path / "secret.txt"
    outside.write_text("S")
    (r / "link.txt").symlink_to(outside)
    assert ss.read_small(r, "link.txt")[0] is None


def test_build_info_is_validated_and_compared_with_the_measured_checkout_sha(checkout, store):
    ok = ss.build_report(checkout, SHA)
    assert ok["status"] == "reported" and ok["matches_checkout"] is True and ok["checks"][0]["passed"] == 122 and ok["mode"] == "worker_report"
    assert ss.build_report(checkout, "cd" * 20)["matches_checkout"] is False
    assert ss.build_report(checkout, None)["matches_checkout"] is None
    (checkout / "build-info.json").write_text(json.dumps({"release_sha": "main", "checks": []}))
    assert ss.build_report(checkout, SHA)["status"] == "invalid"
    (checkout / "build-info.json").write_text("{not json")
    assert ss.build_report(checkout, SHA)["status"] == "invalid" and "release_sha" not in ss.build_report(checkout, SHA)
    (checkout / "build-info.json").unlink()
    assert ss.build_report(checkout, SHA)["status"] == "absent" and "invented" in ss.build_report(checkout, SHA)["note"]


# ------------------------------------------------------------------ resources: pinned receipts, unknown cost
def test_pinned_receipts_are_described_and_cost_is_explicitly_unknown(checkout):
    r = ss.receipts_report(checkout)
    assert r["mode"] == "worker_report" and r["status"] == "ok" and r["receipt_files"][0]["status"] == "verified against its pin"
    assert [j["job_id"] for j in r["jobs"]] == ["aijob-1", "aijob-2"] and [j["kind"] for j in r["jobs"]] == ["cpu", "gpu"]
    assert r["jobs"][0]["first_event_at"] == "2026-10-31T18:31:42Z" and r["jobs"][0]["last_event_at"] == "2026-10-31T18:37:19Z"
    assert "secret_extra" not in r["jobs"][0] and "NOT-IN-ALLOWLIST" not in json.dumps(r)
    assert r["actual_cost"] == {"status": "unknown", "spend_usd": None, "reason": "unavailable: the event exposes no price or usage receipt to participants (not zero)"}
    assert r["utilization"]["status"] == "not_computed" and r["jobs_reported"] == 2 and r["sum_job_reported_wall_seconds"] == 317.2
    assert "Not billed time" in r["sum_note"]
    text = json.dumps(r).lower()
    assert "utilization_percent" not in text and "cost_usd" not in text and '"spend_usd": null' in text


def test_a_changed_missing_or_escaping_receipt_is_withheld(checkout):
    p = checkout / "results" / "compute" / "receipts.json"
    p.write_text(p.read_text().replace("aijob-1", "aijob-X"))
    r = ss.receipts_report(checkout)
    f = r["receipt_files"][0]
    assert f["status"].startswith("changed since it was pinned") and f["actual_sha256"] != f["pinned_sha256"] and r["jobs"] == [] and "aijob-X" not in json.dumps(r)
    p.unlink()
    assert ss.receipts_report(checkout)["receipt_files"][0]["status"] == "not present in this checkout"
    pins = json.loads((checkout / "deploy" / "system" / "receipt-pins.json").read_text())
    for bad in ("../../etc/hostname", "/etc/hostname", ".hidden/x"):
        pins["pins"][0]["path"] = bad
        (checkout / "deploy" / "system" / "receipt-pins.json").write_text(json.dumps(pins))
        assert ss.receipts_report(checkout)["receipt_files"][0]["status"] == "path not allowed", bad
    (checkout / "deploy" / "system" / "receipt-pins.json").write_text("{bad")
    assert ss.receipts_report(checkout)["status"] == "pins file invalid; nothing read"
    (checkout / "deploy" / "system" / "receipt-pins.json").unlink()
    assert ss.receipts_report(checkout)["status"].startswith("no pins file")


def test_the_shipped_pins_file_is_well_formed_and_points_at_a_repo_relative_path():
    d = json.loads((ROOT / "deploy" / "system" / "receipt-pins.json").read_text())
    assert d["schema"] == "frontier.system.receipt-pins/1" and d["pins"]
    for p in d["pins"]:
        assert ss.SHA64.fullmatch(p["sha256"]) and not Path(p["path"]).is_absolute() and ".." not in Path(p["path"]).parts


# ------------------------------------------------------------------ static manifest fallback
def test_manifest_cli_has_only_worker_reports_and_measures_nothing(checkout):
    out = subprocess.run([sys.executable, "-m", "frontier.system_status", "--manifest", "--root", str(checkout)], capture_output=True, text=True, timeout=30,
                         env={"PATH": os.environ["PATH"], "PYTHONPATH": str(ROOT)})
    assert out.returncode == 0
    m = json.loads(out.stdout)
    assert m["kind"] == "curated-manifest" and m["measured"].startswith("not measured") and "store" not in m and "host" not in m and "process" not in m
    assert all(m[k]["mode"] == "worker_report" for k in ("board", "specs", "goal", "build", "resources"))
    assert m["build"]["matches_checkout"] is None
