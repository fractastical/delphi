"""System page snapshot: what this node is doing and what is reported about the project, with every datum labelled `measured` or `worker_report`.

* `measured`: computed by THIS code, now, from the database (public rows only), this process, /proc totals and two fixed commands.
* `worker_report`: read from a file somebody wrote (the build board, specs, GOAL, a build-info file, pinned provider receipts). The file's sha256 is shown;
  nothing in it is checked against reality here.

Read-only and bounded: SELECTs inside a READ ONLY transaction, no job is launched, at most two FIXED commands (`git rev-parse HEAD`, `systemctl --user show` of
our two units) sharing a 2 s budget, result cached 30 s. Never output: environment, tokens, credential paths, host name or user names, other processes' command
lines, other teams' jobs. Utilization and spend are never inferred: provider receipts are pinned files (path + sha256) describing OUR jobs, a mismatching file is
withheld, and actual cost is stated as unknown unless a pinned receipt carries a billed figure (none does today).
"""
import argparse
import hashlib
import json
import os
import re
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

SCHEMA = "frontier.system/1"
ROOT = Path(__file__).resolve().parents[1]
SERVICE_UNITS = ("delphi-frontier-web.service", "delphi-frontier-postgres.service")      # fixed; never taken from a request
GIT_CMD = ("git", "rev-parse", "HEAD")
SYSTEMCTL_CMD = ("systemctl", "--user", "show", *SERVICE_UNITS, "--no-pager", "-p", "Id", "-p", "LoadState", "-p", "ActiveState", "-p", "SubState",
                 "-p", "NRestarts", "-p", "MemoryCurrent", "-p", "TasksCurrent", "-p", "ActiveEnterTimestamp")
BUDGET_S = 2.0
TTL_S = 30
MAX_FILE = 262144
STARTED = time.monotonic()
STARTED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
LEGEND = {"measured": "Computed by this service at the time shown from the database (public rows only), this process, /proc totals and fixed commands.",
          "worker_report": "Read from a file written by a person or worker. The file's sha256 is shown; its contents are not verified against anything."}
HOST_SCOPE = "Shared host totals. Not attributable to any job, team or service of ours."
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clip(value, n=300):
    return value[:n] if isinstance(value, str) else value


def read_small(root: Path, rel: str, limit: int = MAX_FILE) -> tuple[bytes | None, str]:
    """Read a repo-relative file that stays inside `root` (no absolute paths, no `..`, no dotfiles, no symlink escape). Returns (bytes|None, reason)."""
    p = Path(rel)
    if p.is_absolute() or any(part in ("", ".", "..") or part.startswith(".") for part in p.parts) or not p.parts:
        return None, "path not allowed"
    root = root.resolve()
    target = (root / p).resolve()
    if not target.is_relative_to(root):
        return None, "path not allowed"
    try:
        if not target.is_file():
            return None, "not present in this checkout"
        if target.stat().st_size > limit:
            return None, "file larger than the bound"
        return target.read_bytes(), "ok"
    except OSError:
        return None, "unreadable"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ fixed commands (shared 2 s budget)
class Fixed:
    """Runs only the fixed argv tuples above, with an explicit minimal environment, shell never, and one shared deadline."""

    def __init__(self, root: Path, runner=None):
        self.root, self.runner = root, runner or self._run
        self.deadline = time.monotonic() + BUDGET_S

    def _run(self, argv, timeout):
        uid = os.getuid()
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "XDG_RUNTIME_DIR": f"/run/user/{uid}",
               "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{uid}/bus", "LC_ALL": "C"}
        done = subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout, env=env, cwd=self.root)
        return done.returncode, done.stdout

    def call(self, argv: tuple):
        if argv not in (GIT_CMD, SYSTEMCTL_CMD):
            raise ValueError("only the fixed commands may run")
        left = self.deadline - time.monotonic()
        if left <= 0.05:
            return None
        try:
            rc, out = self.runner(argv, left)
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            return None
        return out if rc == 0 else None


def parse_systemctl(text: str | None) -> list[dict]:
    units = {u: {"unit": u, "state": "unavailable"} for u in SERVICE_UNITS}
    if text:
        for block in re.split(r"\n\s*\n", text.strip()):
            kv = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
            uid = kv.get("Id")
            if uid not in units:
                continue

            def num(v):
                return int(v) if v and v.isdigit() and int(v) < 2**62 else None        # "[not set]" and 2**64-1 are not measurements
            units[uid] = {"unit": uid, "state": "measured", "load_state": _clip(kv.get("LoadState"), 40), "active_state": _clip(kv.get("ActiveState"), 40),
                          "sub_state": _clip(kv.get("SubState"), 40), "restarts": num(kv.get("NRestarts")), "memory_current_bytes": num(kv.get("MemoryCurrent")),
                          "tasks_current": num(kv.get("TasksCurrent")), "active_since": _clip(kv.get("ActiveEnterTimestamp") or None, 60)}
    return [units[u] for u in SERVICE_UNITS]


# ------------------------------------------------------------------ /proc (measured)
def _proc(path: str, limit=65536) -> str | None:
    try:
        with Path(path).open("rb") as f:
            return f.read(limit).decode("ascii", "replace")
    except OSError:
        return None


import stat as _stat


class _OverBudget(Exception):
    pass


def tree_hash(d: Path, ignore_top=frozenset({"build-info.json", ".release-complete"}), ignore_dirs=frozenset({"__pycache__"}), max_files=20000, max_bytes=300_000_000,
              seconds=3.0) -> tuple[str | None, list, int]:
    """Git tree object id of the files under `d`, computed from the bytes on disk with git's rules (same algorithm as deploy/release.py `git_tree_sha`; a test keeps the two
    equal). Returns (tree_sha, ignored_names, files_hashed). Bounded; raises _OverBudget."""
    deadline, state, ignored = time.monotonic() + seconds, {"files": 0, "bytes": 0}, []

    def rec(p: Path, rel: str):
        ents = []
        for c in sorted(os.scandir(p), key=lambda e: e.name):
            r, st = f"{rel}{c.name}", c.stat(follow_symlinks=False)
            if (not rel and c.name in ignore_top) or (_stat.S_ISDIR(st.st_mode) and c.name in ignore_dirs):
                ignored.append(r + ("/" if _stat.S_ISDIR(st.st_mode) else ""))
                continue
            if _stat.S_ISLNK(st.st_mode):
                body = os.readlink(c.path).encode()
                mode, h = b"120000", hashlib.sha1(b"blob %d\0" % len(body) + body).digest()
            elif _stat.S_ISDIR(st.st_mode):
                h = rec(Path(c.path), r + "/")
                if h is None:
                    continue
                mode = b"40000"
            elif _stat.S_ISREG(st.st_mode):
                state["files"] += 1
                state["bytes"] += st.st_size
                if state["files"] > max_files or state["bytes"] > max_bytes or time.monotonic() > deadline:
                    raise _OverBudget
                hh = hashlib.sha1(b"blob %d\0" % st.st_size)
                with Path(c.path).open("rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        hh.update(chunk)
                mode, h = (b"100755" if st.st_mode & 0o111 else b"100644"), hh.digest()
            else:
                raise _OverBudget
            name = c.name.encode()
            ents.append((name + (b"/" if mode == b"40000" else b""), mode, name, h))
        if not ents:
            return None
        body = b"".join(m + b" " + n + b"\0" + h for _, m, n, h in sorted(ents))
        return hashlib.sha1(b"tree %d\0" % len(body) + body).digest()
    out = rec(Path(d), "")
    return (out.hex() if out else None), sorted(set(ignored)), state["files"]


DIRECTORY_CLAIM_LABEL = ("claim: the name of the releases/<sha> directory the code runs from. A directory name is not proof that its files equal that git commit; "
                         "`contents` checks the files against the tree hash that the release tool recorded in build-info.json, and only `release.py verify --repo` compares with git itself.")


def release_identity(root: Path, git_sha: str | None, tree_cache: dict | None = None) -> dict:
    """`sha` is MEASURED only through git (`git rev-parse HEAD` in a git checkout). A `git archive` release has no .git, so there the running directory's name is reported
    separately as a CLAIM (`directory_claim`), never promoted to `sha`/`deployed_sha`."""
    real = Path(root).resolve()
    dir_sha = real.name if SHA40.fullmatch(real.name) and real.parent.name == "releases" else None
    claim = None
    if dir_sha:
        marker = None
        try:
            mf = real / ".release-complete"                                   # a dotfile on purpose: written by deploy/release.py, outside read_small's allow-list
            marker = json.loads(mf.read_bytes()[:4096]).get("sha") == dir_sha if mf.is_file() and mf.stat().st_size <= 4096 else None
        except (OSError, ValueError, AttributeError):
            marker = None
        claimed_tree = None
        try:
            raw, _ = read_small(real, "build-info.json")
            t = json.loads(raw).get("tree_sha") if raw else None
            claimed_tree = t if isinstance(t, str) and SHA40.fullmatch(t) else None
        except (ValueError, AttributeError):
            pass
        cache = tree_cache if tree_cache is not None else {}
        hit = cache.get(str(real))
        if hit and time.monotonic() - hit[0] < 600:
            contents = {**hit[1], "cached_age_seconds": round(time.monotonic() - hit[0], 1)}
        else:
            t0 = time.monotonic()
            try:
                tree, ignored, files = tree_hash(real)
                contents = {"checked": True, "tree_sha_computed": tree, "tree_sha_recorded_in_build_info": claimed_tree, "files_hashed": files, "ignored_not_hashed": ignored,
                            "matches_recorded_tree": (tree == claimed_tree) if claimed_tree else None, "seconds": round(time.monotonic() - t0, 2),
                            "meaning": "Whether the files on disk are unchanged since the release tool recorded their git tree hash. That the recorded hash belongs to the named commit is the "
                                       "release tool's claim; `release.py verify --repo <git repo>` checks it against git."}
            except (_OverBudget, OSError):
                contents = {"checked": False, "reason": "tree hash exceeded its size/time budget or could not be read"}
            cache[str(real)] = (time.monotonic(), contents)
            contents = {**contents, "cached_age_seconds": 0.0}
        claim = {"label": DIRECTORY_CLAIM_LABEL, "sha": dir_sha, "marker_matches_name": marker, "contents": contents}
    return {"mode": "measured", "sha": git_sha, "sha_source": "git" if git_sha else None, "checkout_sha": git_sha, "directory_claim": claim,
            "source": "git rev-parse HEAD (fixed command), measured only when the deployed tree is a git checkout",
            "note": None if git_sha else "not measured: the deployed tree is not a git checkout (a git archive release has no .git) or the command exceeded its budget; see directory_claim"}


def host_measurements() -> dict:
    out = {"mode": "measured", "scope": HOST_SCOPE, "cpu_count": os.cpu_count()}
    la = _proc("/proc/loadavg")
    if la:
        a = la.split()
        out["load_average"] = {"1m": float(a[0]), "5m": float(a[1]), "15m": float(a[2])}
    mem = _proc("/proc/meminfo")
    if mem:
        kv = {m.group(1): int(m.group(2)) for m in re.finditer(r"^(MemTotal|MemAvailable|SwapTotal|SwapFree):\s+(\d+) kB", mem, re.M)}
        out["memory_kb"] = {k: kv.get(k) for k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")}
    psi = _proc("/proc/pressure/cpu")
    if psi:
        m = re.search(r"some avg10=([\d.]+) avg60=([\d.]+) avg300=([\d.]+)", psi)
        if m:
            out["cpu_pressure_some"] = {"avg10": float(m.group(1)), "avg60": float(m.group(2)), "avg300": float(m.group(3)), "note": "share of time some task waited for CPU"}
    return out


def process_measurements() -> dict:
    st = _proc("/proc/self/status") or ""
    rss = re.search(r"^VmRSS:\s+(\d+) kB", st, re.M)
    thr = re.search(r"^Threads:\s+(\d+)", st, re.M)
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return {"mode": "measured", "scope": "this web process only", "started_at": STARTED_AT, "uptime_seconds": round(time.monotonic() - STARTED, 1),
            "resident_memory_kb": int(rss.group(1)) if rss else None, "threads": int(thr.group(1)) if thr else None,
            "cpu_seconds": {"user": round(ru.ru_utime, 2), "system": round(ru.ru_stime, 2)}, "python": sys.version.split()[0]}


# ------------------------------------------------------------------ database (measured, public rows only, READ ONLY transaction)
def store_measurements(store) -> dict:
    with store.connection() as c:
        c.execute("SET TRANSACTION READ ONLY")
        by_kind = c.execute("""SELECT v.kind, s.status, count(*) AS n, count(h.version) AS heads FROM record_versions v JOIN local_states s USING(version)
                               LEFT JOIN heads h ON h.version = v.version WHERE v.visibility = 'public' GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
        ev = c.execute("""SELECT e.event_type, count(*) AS n FROM events e JOIN record_versions v ON v.version = e.event_version
                          WHERE v.visibility = 'public' GROUP BY 1 ORDER BY 1""").fetchall()
        by_ns = c.execute("SELECT v.namespace, count(*) AS n FROM record_versions v WHERE v.visibility = 'public' GROUP BY 1 ORDER BY 1").fetchall()
        db = c.execute("SELECT pg_database_size(current_database()) AS bytes, extract(epoch FROM now() - pg_postmaster_start_time()) AS up, "
                       "current_setting('server_version') AS version").fetchone()
    return {"mode": "measured", "public_only": True, "namespace": store.namespace,
            "counts_scope": "ALL public record versions in this database, across every namespace, including records imported from other nodes under their origin "
                            "namespace. `namespace` is only this node's own; see `versions_by_namespace` for the split.",
            "versions_by_namespace": [{"namespace": r["namespace"], "versions": r["n"]} for r in by_ns],
            "note": "Public rows only; private records are not counted. Counts are record VERSIONS; `heads` counts the current version of each record.",
            "records_by_kind_and_local_status": [{"kind": r["kind"], "local_status": r["status"], "versions": r["n"], "heads": r["heads"]} for r in by_kind],
            "events_by_type": [{"event_type": r["event_type"], "count": r["n"]} for r in ev],
            "database": {"size_bytes": int(db["bytes"]), "uptime_seconds": round(float(db["up"]), 1), "server_version": db["version"]}}


# ------------------------------------------------------------------ worker reports from files
def board_report(root: Path) -> dict:
    raw, why = read_small(root, "tasks/BUILD.md")
    if raw is None:
        return {"mode": "worker_report", "source": "tasks/BUILD.md", "status": "absent", "reason": why}
    text = raw.decode("utf-8", "replace")
    rows, header = [], None
    for line in text.splitlines():
        if line.startswith("|") and line.rstrip().endswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if header is None:
                header = [re.sub(r"[^a-z]+", "_", c.lower()).strip("_") for c in cells]
            elif len(cells) == len(header) and len(rows) < 100:
                rows.append({k: _clip(v) for k, v in zip(header, cells)})
    findings, grab = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            grab = line.lower().startswith("## findings")
        elif grab and line.startswith("- ") and len(findings) < 30:
            findings.append(_clip(line[2:].strip(), 400))
        elif grab and line.startswith("  ") and findings:
            findings[-1] = _clip(findings[-1] + " " + line.strip(), 400)
    return {"mode": "worker_report", "source": "tasks/BUILD.md", "sha256": sha256(raw), "rows": rows, "findings_to_correct": findings}


def specs_report(root: Path) -> dict:
    items = []
    d = (root / "specs")
    for p in sorted(d.glob("SPEC-*.md"))[:40] if d.is_dir() else []:
        raw, _ = read_small(root, f"specs/{p.name}")
        if raw is None:
            continue
        text = raw.decode("utf-8", "replace")
        title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), p.stem)
        status = next((l.strip() for l in text.splitlines() if l.lstrip().startswith("**Status:**")), None)
        items.append({"id": re.match(r"SPEC-\d+", p.stem).group(0), "file": p.name, "title": _clip(title), "status_line": _clip(status, 300), "sha256": sha256(raw)})
    return {"mode": "worker_report", "source": "specs/SPEC-*.md", "specs": items}


def goal_report(root: Path) -> dict:
    raw, why = read_small(root, "GOAL.md")
    if raw is None:
        return {"mode": "worker_report", "source": "GOAL.md", "status": "absent", "reason": why}
    lines = raw.decode("utf-8", "replace").splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), None)
    body = " ".join(l.strip() for l in lines if l.strip() and not l.startswith("#"))
    return {"mode": "worker_report", "source": "GOAL.md", "sha256": sha256(raw), "title": _clip(title), "summary": _clip(re.sub(r"\s+", " ", body), 1200)}


AUTHOR_LABEL = "author report: written when the release was cut (by deploy/release.py or by hand). Not verified here."


def build_report(root: Path, release_sha: str | None, compared_with: str | None = None, claimed_dir_sha: str | None = None) -> dict:
    """`build-info.json` at the checkout root is written by whoever cuts a release; this endpoint only validates its shape."""
    raw, why = read_small(root, "build-info.json")
    if raw is None:
        return {"mode": "worker_report", "label": AUTHOR_LABEL, "source": "build-info.json", "status": "absent", "reason": why,
                "note": "No build-info file: no release SHA or build checks are reported, and none are invented."}
    try:
        d = json.loads(raw)
        if not isinstance(d, dict) or not SHA40.fullmatch(str(d.get("release_sha", ""))):
            raise ValueError
        checks = []
        for c in (d.get("checks") or [])[:40]:
            if not isinstance(c, dict):
                raise ValueError
            checks.append({k: _clip(c.get(k)) if isinstance(c.get(k), str) else c.get(k) for k in ("name", "command", "exit", "passed", "total", "at", "result")
                           if isinstance(c.get(k), (str, int, bool, type(None)))})
    except ValueError:
        return {"mode": "worker_report", "label": AUTHOR_LABEL, "source": "build-info.json", "sha256": sha256(raw), "status": "invalid",
                "reason": "needs an object with a 40-hex release_sha and a list of check objects; contents not used"}
    extra = {k: d[k] for k in ("tree_sha", "archive_sha256", "checks_receipt_sha256") if isinstance(d.get(k), str) and (SHA40.fullmatch(d[k]) or SHA64.fullmatch(d[k]))}
    if isinstance(d.get("checks_all_passed"), bool):
        extra["checks_all_passed"] = d["checks_all_passed"]
    return {"mode": "worker_report", "label": AUTHOR_LABEL, "source": "build-info.json", "sha256": sha256(raw), "status": "reported", "release_sha": d["release_sha"],
            "built_at": _clip(d.get("built_at"), 40), "checks": checks, **extra,
            "matches_checkout": None if release_sha is None else release_sha == d["release_sha"], "compared_with": compared_with if release_sha else None,
            "matches_directory_claim": None if claimed_dir_sha is None else claimed_dir_sha == d["release_sha"],
            "matches_note": "`matches_checkout` compares with the SHA this service measured through git; null means no git checkout, so nothing was measured. "
                            "`matches_directory_claim` compares with the releases/<sha> directory NAME, which is only a claim."}


RECEIPT_FIELDS = ("job_id", "job_name", "job_state", "run_tag", "item", "controller_status", "inner_rc", "inner_wall_s", "timed_out",
                  "returned_bundle_bytes", "returned_bundle_sha256")


def receipts_report(root: Path, pins_rel: str = "deploy/system/receipt-pins.json") -> dict:
    out = {"mode": "worker_report", "source": "pinned provider receipts (deploy/system/receipt-pins.json)", "receipt_files": [], "jobs": [],
           "actual_cost": {"status": "unknown", "spend_usd": None,
                           "reason": "No pinned receipt carries a billed amount; spend is not estimated or inferred."},
           "utilization": {"status": "not_computed", "reason": "No provider usage receipt exists; job-reported wall seconds are not billed time or capacity utilization."}}
    raw, why = read_small(root, pins_rel)
    if raw is None:
        out["status"] = "no pins file: " + why
        return out
    try:
        pins = json.loads(raw)["pins"]
        assert isinstance(pins, list) and len(pins) <= 20
    except (ValueError, KeyError, AssertionError, TypeError):
        out["status"] = "pins file invalid; nothing read"
        return out
    for pin in pins:
        entry = {"id": _clip(pin.get("id"), 80), "path": _clip(pin.get("path"), 200), "pinned_sha256": pin.get("sha256"), "description": _clip(pin.get("description"), 300),
                 "pinned_from": _clip(pin.get("pinned_from"), 120)}
        data, why = read_small(root, str(pin.get("path", "")))
        if data is None:
            entry["status"] = why
        elif sha256(data) != pin.get("sha256"):
            entry.update(status="changed since it was pinned; contents withheld until the pin is updated", actual_sha256=sha256(data))
        else:
            entry.update(status="verified against its pin", actual_sha256=sha256(data))
            try:
                d = json.loads(data)
                for j in (d["jobs"] if isinstance(d.get("jobs"), list) else [])[:50]:
                    ev = [e for e in j.get("events", []) if isinstance(e, dict)]
                    job = {k: j[k] for k in RECEIPT_FIELDS if isinstance(j.get(k), (str, int, float, bool))}
                    job["kind"] = next((e["kind"] for e in ev if isinstance(e.get("kind"), str)), None)
                    stamps = [e["t"] for e in ev if isinstance(e.get("t"), str)]
                    job["first_event_at"], job["last_event_at"], job["receipt_id"] = (stamps[0] if stamps else None), (stamps[-1] if stamps else None), entry["id"]
                    out["jobs"].append({k: _clip(v) for k, v in job.items()})
                for k in ("price", "note"):
                    if isinstance(d.get(k), str):
                        entry[k] = _clip(d[k], 400)
                        if k == "price":
                            out["actual_cost"]["reason"] = _clip(d[k], 400)
            except (ValueError, TypeError, AttributeError):
                entry["status"] = "verified against its pin but not a receipts document; contents not used"
        out["receipt_files"].append(entry)
    walls = [j["inner_wall_s"] for j in out["jobs"] if isinstance(j.get("inner_wall_s"), (int, float))]
    out["jobs_reported"] = len(out["jobs"])
    out["sum_job_reported_wall_seconds"] = round(sum(walls), 1) if walls else None
    out["sum_note"] = "Sum of wall seconds the jobs reported about themselves. Not billed time, not capacity utilization."
    out["status"] = "ok" if out["receipt_files"] else "no pins"
    return out


def curated_manifest(root: Path = ROOT) -> dict:
    """The worker_report sections only, for the UI to fetch as a static file when /api/system is not ready. Nothing in it is measured."""
    return {"schema": SCHEMA, "generated_at": now_iso(), "kind": "curated-manifest", "legend": LEGEND,
            "measured": "not measured: this is a static manifest; load /api/system for measurements",
            "board": board_report(root), "specs": specs_report(root), "goal": goal_report(root), "build": build_report(root, None), "resources": receipts_report(root)}


# ------------------------------------------------------------------ the snapshot
class SystemStatus:
    def __init__(self, store, root: Path = ROOT, ttl: int = TTL_S, runner=None):
        self.store, self.root, self.ttl, self.runner = store, Path(root), ttl, runner
        self.lock, self.cached, self.tree_cache = Lock(), None, {}

    def _section(self, name, fn):
        try:
            return fn()
        except Exception:       # noqa: BLE001 - a failing section degrades alone; no exception text is exported
            return {"mode": "measured", "status": "unavailable", "section": name}

    def snapshot(self) -> dict:
        with self.lock:
            t = time.monotonic()
            if self.cached and t - self.cached[0] < self.ttl:
                return {**self.cached[1], "cache": {"ttl_seconds": self.ttl, "cached": True, "age_seconds": round(t - self.cached[0], 1)}}
            fixed = Fixed(self.root, self.runner)
            sha = fixed.call(GIT_CMD)
            sha = sha.strip() if sha and SHA40.fullmatch(sha.strip()) else None
            units = parse_systemctl(fixed.call(SYSTEMCTL_CMD))
            out = {"schema": SCHEMA, "generated_at": now_iso(), "legend": LEGEND,
                   "store": self._section("store", lambda: store_measurements(self.store)),
                   "process": self._section("process", process_measurements),
                   "host": self._section("host", host_measurements),
                   "services": {"mode": "measured", "source": "systemctl --user show (fixed command, our two units only)", "units": units},
                   "release": self._section("release", lambda: release_identity(self.root, sha, self.tree_cache)),
                   "deployed_sha": None, "claimed_sha": None,
                   "build": None,
                   "board": self._section("board", lambda: board_report(self.root)),
                   "specs": self._section("specs", lambda: specs_report(self.root)),
                   "goal": self._section("goal", lambda: goal_report(self.root)),
                   "resources": self._section("resources", lambda: receipts_report(self.root)),
                   "limits": {"read_only": True, "fixed_command_budget_seconds": BUDGET_S, "launches_jobs": False,
                              "not_exposed": ["environment", "tokens", "credential paths", "host name or user names", "other processes' command lines", "other teams' jobs"]}}
            rel = out["release"] if isinstance(out["release"], dict) else {}
            out["deployed_sha"] = rel.get("sha")                                     # MEASURED via git only
            dc = rel.get("directory_claim") or {}
            out["claimed_sha"] = dc.get("sha")                                        # the directory name: a claim, labelled in release.directory_claim
            out["build"] = self._section("build", lambda: build_report(self.root, out["deployed_sha"], "git" if out["deployed_sha"] else None, dc.get("sha")))
            self.cached = (t, out)
            return {**out, "cache": {"ttl_seconds": self.ttl, "cached": False, "age_seconds": 0.0}}


def main(argv=None):
    p = argparse.ArgumentParser(description="Print the curated worker_report manifest (static fallback for the System page). Measures nothing.")
    p.add_argument("--manifest", action="store_true", required=True)
    p.add_argument("--root", type=Path, default=ROOT)
    a = p.parse_args(argv)
    print(json.dumps(curated_manifest(a.root), indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
