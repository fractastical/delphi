#!/usr/bin/env python3
"""Reusable release / rollback command for the Frontier web service. Standard library only (runs before the service venv exists).

Layout (ROOT defaults to /data/services/delphi-frontier):
    releases/<40-hex sha>/        an immutable `git archive` of exactly that committed SHA + build-info.json + .release-complete
    releases/history.jsonl        append-only record of every prepare/deploy/rollback attempt and its result
    app            -> releases/<sha>      the symlink the service runs from (WorkingDirectory=ROOT/app); swapped atomically
    app.previous   -> releases/<sha>      the release `app` pointed to before the last switch
    venv/                          root's service virtualenv (not touched here)

    prepare   archive an exact committed SHA into releases/<sha> and write build-info.json from a SUPPLIED checks receipt.
    deploy    switch `app` to a prepared release, restart the unit, wait for health; on ANY failure switch back and restart again.
    rollback  switch to app.previous (or --to SHA) with the same restart + health + automatic fall-back.
    verify    read-only: recompute the git tree hash of releases/<sha> and compare it with git (--repo) and with build-info.json.
    adopt     (plan-first) mark an existing hand-built releases/<sha> as complete so it can be rolled back TO, ONLY after its files are shown byte-identical to the
              commit (build-info.json and __pycache__ are the only allowed extras); adds one marker file, nothing else.
    status    read-only view of the above.

Rules it enforces: only committed content is archived (the working tree can never leak in); a release directory is never edited, replaced or deleted and is made
read-only; the predecessor stays on disk and stays addressable; the checks receipt must name the SAME sha and every check must have passed (else refused unless
--allow-failed-checks, which is recorded in build-info); `deploy` and `rollback` only PLAN unless --apply is given; the only commands ever run are the fixed ones in
`check_argv` (git read/archive, `systemctl --user` restart/is-active/show of the one unit, one import smoke test with the release's own venv python, and, ONLY
with --nginx-install, a fixed set of sudo/nginx steps). It does not touch the database, does not edit nginx unless asked, and starts nothing by itself.

Exit codes: 0 ok / planned; 2 usage; 3 refused (state or inputs; nothing changed); 4 checks failed (refused); 10 deploy failed and rolled back cleanly;
11 deploy failed AND the roll back failed (service state needs a human); 12 nginx step failed and was reverted.
"""
import argparse
import fcntl
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROOT = Path("/data/services/delphi-frontier")
UNIT = "delphi-frontier-web.service"
PORT = 8971
SHA40 = re.compile(r"^[0-9a-f]{40}$")
NGINX_CONF = "frontier.morphoswarm.ai.conf"
NGINX_DEST = "/etc/nginx/conf.d/" + NGINX_CONF
SMOKE = "import frontier.web, frontier.system_status, frontier.beliefs_api, frontier.engineering_api"
CHECK_KEYS = ("name", "command", "exit", "passed", "total", "at", "result")


class Refused(Exception):
    code = 3


class ChecksFailed(Refused):
    code = 4


def utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_tree_sha(d: Path, ignore_top=frozenset(), ignore_dirs=frozenset({"__pycache__"}), report: list | None = None) -> str | None:
    """The git tree object id of the files under `d`, computed from the bytes on disk with git's own rules (blob = sha1("blob <n>\\0"+bytes), mode 100644/100755/120000,
    entries sorted with directories compared as "name/", empty directories omitted). Comparing it with `git rev-parse <sha>^{tree}` shows the directory holds EXACTLY the
    committed files. `ignore_top` names files ignored at the top level (build metadata); `ignore_dirs` names directories ignored anywhere (bytecode caches). Whatever was ignored
    is appended to `report`, so an extra is visible, never silent."""
    def rec(p: Path, rel: str):
        ents = []
        for c in sorted(os.scandir(p), key=lambda e: e.name):
            r = f"{rel}{c.name}"
            st = c.stat(follow_symlinks=False)
            if (not rel and c.name in ignore_top) or (stat.S_ISDIR(st.st_mode) and c.name in ignore_dirs):
                if report is not None:
                    report.append(r + ("/" if stat.S_ISDIR(st.st_mode) else ""))
                continue
            if stat.S_ISLNK(st.st_mode):
                body = os.readlink(c.path).encode()
                mode, h = b"120000", hashlib.sha1(b"blob %d\0" % len(body) + body).digest()
            elif stat.S_ISDIR(st.st_mode):
                h = rec(Path(c.path), r + "/")
                if h is None:
                    continue
                mode = b"40000"
            elif stat.S_ISREG(st.st_mode):
                hh = hashlib.sha1(b"blob %d\0" % st.st_size)
                with open(c.path, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        hh.update(chunk)
                mode, h = (b"100755" if st.st_mode & 0o111 else b"100644"), hh.digest()
            else:
                raise Refused(f"special file in release: {r}")
            name = c.name.encode()
            ents.append((name + (b"/" if mode == b"40000" else b""), mode, name, h))
        if not ents:
            return None
        body = b"".join(m + b" " + n + b"\0" + h for _, m, n, h in sorted(ents))
        return hashlib.sha1(b"tree %d\0" % len(body) + body).digest()
    out = rec(Path(d), "")
    return out.hex() if out else None


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------------------- the only commands this tool may run
def check_argv(argv: list, venv_python: str) -> None:
    a = list(argv)
    ok = (a[:1] == ["git"] and len(a) >= 4 and a[1] == "-C" and a[3] in ("cat-file", "rev-parse", "archive", "ls-tree"))
    ok = ok or (a[:2] == ["systemctl", "--user"] and len(a) >= 4 and a[2] in ("restart", "is-active", "show") and a[3] == UNIT and (a[2] != "show" or a[4:] == ["-p", "ActiveState", "-p", "NRestarts"]) and (a[2] == "show" or len(a) == 4))
    ok = ok or a == [venv_python, "-c", SMOKE]
    ok = ok or (a[:2] == ["sudo", "-n"] and a[2:] in (["nginx", "-t"], ["systemctl", "reload", "nginx"]))
    ok = ok or (a[:3] == ["sudo", "-n", "install"] and len(a) == 7 and a[3:5] == ["-m", "644"] and a[6] == NGINX_DEST and a[5].endswith("/deploy/nginx/" + NGINX_CONF))
    ok = ok or (a[:3] == ["sudo", "-n", "cp"] and len(a) == 6 and a[3] == "-p" and a[4] == NGINX_DEST and a[5].startswith(NGINX_DEST + ".bak-"))
    ok = ok or (a[:3] == ["sudo", "-n", "mv"] and len(a) == 5 and a[3] == NGINX_DEST and a[4].startswith(NGINX_DEST + ".failed-"))
    ok = ok or (a[:3] == ["sudo", "-n", "cp"] and len(a) == 6 and a[3] == "-p" and a[4].startswith(NGINX_DEST + ".bak-") and a[5] == NGINX_DEST)
    if not ok:
        raise Refused(f"command not on the fixed list: {a[:3]}")


class Ops:
    """Real operations. Tests substitute a fake with the same methods."""

    def run(self, argv, timeout=60, cwd=None, env=None):
        done = subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
        return done.returncode, done.stdout

    def archive(self, repo: str, sha: str):
        p = subprocess.Popen(["git", "-C", repo, "archive", "--format=tar", sha], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return p, p.stdout

    def health(self, port: int, timeout: float = 2.0):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as r:
                return r.status, json.loads(r.read(4096))
        except urllib.error.HTTPError as e:
            return e.code, None
        except (OSError, ValueError):
            return None, None

    def sleep(self, s):
        time.sleep(s)


# ---------------------------------------------------------------------------------------- release store
class Release:
    def __init__(self, root: Path = DEFAULT_ROOT, ops: Ops | None = None, port: int = PORT, out=print):
        self.root, self.ops, self.port, self.out = Path(root), ops or Ops(), port, out
        self.releases = self.root / "releases"
        self.app, self.previous = self.root / "app", self.root / "app.previous"
        self.history = self.releases / "history.jsonl"
        self.venv_python = str(self.root / "venv" / "bin" / "python")

    # -- small helpers
    def say(self, **kv):
        self.out(json.dumps(kv, sort_keys=True))

    def _run(self, argv, **kw):
        check_argv(argv, self.venv_python)
        return self.ops.run(argv, **kw)

    def log(self, **kv):
        self.releases.mkdir(parents=True, exist_ok=True)
        with self.history.open("a") as f:
            f.write(json.dumps({"at": utc(), **kv}, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def dest(self, sha: str) -> Path:
        if not SHA40.fullmatch(sha or ""):
            raise Refused("a release is addressed by a full 40-hex commit SHA")
        return self.releases / sha

    def is_prepared(self, sha: str) -> bool:
        d = self.dest(sha)
        return (d / ".release-complete").is_file() and (d / "build-info.json").is_file()

    def current(self) -> Path | None:
        if self.app.is_symlink():
            return Path(os.readlink(self.app))
        if self.app.exists():
            raise Refused(f"{self.app} exists and is not a symlink; this tool will not replace a real directory (move it into releases/ yourself)")
        return None

    @staticmethod
    def sha_of(target: Path | None) -> str | None:
        return target.name if target and SHA40.fullmatch(target.name) else None

    def lock(self):
        self.releases.mkdir(parents=True, exist_ok=True)
        f = (self.releases / ".lock").open("w")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Refused("another release operation is running") from None
        return f

    # -- prepare
    @staticmethod
    def read_checks(path: Path, sha: str, allow_failed: bool) -> dict:
        try:
            d = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            raise Refused("checks receipt is not readable JSON") from None
        if not isinstance(d, dict) or d.get("schema") != "frontier.release.checks/1" or d.get("sha") != sha:
            raise Refused("checks receipt must be {schema: frontier.release.checks/1, sha: <this exact sha>, checks: [...]}: a receipt for another commit is not accepted")
        checks = d.get("checks")
        if not isinstance(checks, list) or not checks or len(checks) > 40:
            raise Refused("checks receipt needs 1..40 checks")
        clean = []
        for c in checks:
            if not isinstance(c, dict) or not isinstance(c.get("name"), str) or not isinstance(c.get("command"), str) or type(c.get("exit")) is not int or not isinstance(c.get("at"), str):
                raise Refused("each check needs name, command, integer exit and at")
            clean.append({k: (c[k][:300] if isinstance(c[k], str) else c[k]) for k in CHECK_KEYS if k in c and isinstance(c[k], (str, int, bool))})
        failed = [c["name"] for c in clean if c["exit"] != 0]
        if failed and not allow_failed:
            raise ChecksFailed("refusing to prepare a release with failing checks: " + ", ".join(failed))
        return {"checks": clean, "all_passed": not failed, "receipt_sha256": sha256_file(Path(path))}

    def prepare(self, repo: str, sha: str, checks_path: Path, allow_failed: bool = False) -> dict:
        dest = self.dest(sha)
        rc, _ = self._run(["git", "-C", repo, "cat-file", "-e", sha + "^{commit}"])
        if rc != 0:
            raise Refused("that SHA is not a commit in the given repository")
        rc, tree = self._run(["git", "-C", repo, "rev-parse", sha + "^{tree}"])
        tree = tree.strip()
        if rc != 0 or not SHA40.fullmatch(tree):
            raise Refused("cannot resolve the commit's tree")
        if dest.exists():
            if self.is_prepared(sha):
                self.say(step="prepare", result="already_prepared", sha=sha)
                return {"result": "already_prepared", "sha": sha}
            raise Refused(f"{dest} exists but is not a complete release; it is left untouched")
        info = self.read_checks(checks_path, sha, allow_failed)
        self.releases.mkdir(parents=True, exist_ok=True)
        with self.lock():
            tmp = self.releases / f".partial-{sha}-{os.getpid()}"
            tmp.mkdir()
            try:
                return self._build_release(tmp, repo, sha, dest, tree, info)
            except BaseException:
                import shutil
                shutil.rmtree(tmp, ignore_errors=True)                                    # only our own unfinished temp directory; never a release
                raise

    def _build_release(self, tmp, repo, sha, dest, tree, info):
        proc, stream = self.ops.archive(repo, sha)
        h = hashlib.sha256()

        class Tee(io.RawIOBase):
            def readable(self):
                return True

            def readinto(self, b):
                n = stream.readinto(b) or 0
                h.update(bytes(b[:n]))
                return n
        buf = io.BufferedReader(Tee())
        with tarfile.open(fileobj=buf, mode="r|") as tar:
            tar.extractall(tmp, filter="data")                                   # refuses absolute paths, "..", device nodes, links that escape
        buf.read()                                                               # drain the padding so git can exit and the hash covers the whole stream
        if proc.wait() != 0:
            raise Refused("git archive failed; nothing was installed")
        files = sum(1 for p in tmp.rglob("*") if p.is_file())
        if files == 0:
            raise Refused("the archive was empty")
        if git_tree_sha(tmp, ignore_dirs=frozenset()) != tree:
            raise Refused("the extracted files do not hash to the commit's git tree; nothing was installed")
        info_doc = {"schema": "frontier.build-info/1", "release_sha": sha, "tree_sha": tree, "built_at": utc(), "archive_sha256": h.hexdigest(),
                    "files": files, "checks": info["checks"], "checks_all_passed": info["all_passed"], "checks_receipt_sha256": info["receipt_sha256"]}
        (tmp / "build-info.json").write_text(json.dumps(info_doc, indent=1, sort_keys=True) + "\n")
        (tmp / ".release-complete").write_text(json.dumps({"sha": sha, "tree_sha": tree, "prepared_at": info_doc["built_at"]}) + "\n")
        for p in sorted(tmp.rglob("*"), key=lambda q: len(q.parts), reverse=True):      # read-only files and directories: the release is immutable
            if not p.is_symlink():
                p.chmod(p.stat().st_mode & ~0o222)
        tmp.chmod(tmp.stat().st_mode & ~0o222)
        os.rename(tmp, dest)
        self.log(action="prepare", sha=sha, tree_sha=tree, archive_sha256=info_doc["archive_sha256"], checks_all_passed=info["all_passed"], result="prepared")
        self.say(step="prepare", result="prepared", sha=sha, files=files, archive_sha256=info_doc["archive_sha256"], checks_all_passed=info["all_passed"])
        return {"result": "prepared", "sha": sha, "archive_sha256": info_doc["archive_sha256"]}

    META = frozenset({"build-info.json", ".release-complete"})

    def differences(self, repo: str, sha: str, d: Path, limit: int = 10) -> list:
        """Paths whose bytes differ between git's commit and the directory (diagnostic; never changes anything)."""
        rc, out = self._run(["git", "-C", repo, "ls-tree", "-r", sha])
        want = {}
        for line in out.splitlines():
            meta, path = line.split("\t", 1)
            mode, typ, blob = meta.split()
            want[path] = (mode, blob)
        diffs, seen = [], set()
        for p in sorted(d.rglob("*")):
            rel = p.relative_to(d).as_posix()
            if p.is_dir() or rel in self.META or "__pycache__" in p.parts:
                continue
            seen.add(rel)
            if rel not in want:
                diffs.append(f"extra: {rel}")
            else:
                data = os.readlink(p).encode() if p.is_symlink() else p.read_bytes()
                if hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() != want[rel][1]:
                    diffs.append(f"differs: {rel}")
        diffs += [f"missing: {k}" for k in sorted(set(want) - seen)]
        return diffs[:limit]

    def verify(self, sha: str, repo: str | None = None) -> dict:
        """Read-only. Does releases/<sha> hold exactly the committed files? Ignores only build metadata and bytecode caches and REPORTS them."""
        d = self.dest(sha)
        if not d.is_dir() or d.is_symlink():
            raise Refused("that release directory does not exist")
        ignored: list = []
        dir_tree = git_tree_sha(d, ignore_top=self.META, report=ignored)
        claimed = None
        try:
            claimed = json.loads((d / "build-info.json").read_text()).get("tree_sha")
        except (OSError, ValueError, AttributeError):
            pass
        res = {"sha": sha, "dir_tree_sha": dir_tree, "claimed_tree_sha": claimed, "matches_claimed_tree": (dir_tree == claimed) if claimed else None,
               "ignored_not_hashed": sorted(set(ignored))}
        if repo:
            rc, out = self._run(["git", "-C", repo, "rev-parse", sha + "^{tree}"])
            git_tree = out.strip() if rc == 0 else None
            res["git_tree_sha"] = git_tree
            res["matches_git"] = (dir_tree == git_tree) if git_tree else None
            if res["matches_git"] is False:
                res["differences"] = self.differences(repo, sha, d)
        else:
            res["matches_git"] = None
            res["note"] = "no --repo given: only consistency with the tree recorded in build-info.json was checked, not equality with the git commit"
        self.say(step="verify", **res)
        return res

    def adopt(self, sha: str, apply: bool = False, repo: str | None = None) -> dict:
        """Mark a release directory that was built by hand (so it has no .release-complete) as a complete release, so it can be rolled back TO. Adds one
        marker file; changes nothing else in the directory, does not make it read-only, and requires a build-info.json that names the same SHA."""
        d = self.dest(sha)
        if d.is_symlink() or not d.is_dir():
            raise Refused("that release directory does not exist")
        if (d / ".release-complete").is_file():
            self.say(step="adopt", result="already_complete", sha=sha)
            return {"result": "already_complete"}
        try:
            bi = json.loads((d / "build-info.json").read_text())
        except (OSError, ValueError):
            raise Refused("build-info.json is missing or unreadable; refusing to adopt") from None
        if not isinstance(bi, dict) or bi.get("release_sha") != sha:
            raise Refused("build-info.json does not name this SHA; refusing to adopt")
        if not repo:
            raise Refused("adopt needs --repo: a 40-hex directory name is a claim, so the files are compared with the commit before anything is accepted")
        v = self.verify(sha, repo)
        if v["matches_git"] is not True:
            raise Refused("the directory is not byte-identical to the commit (ignoring only build-info.json and __pycache__): " + "; ".join(v.get("differences", ["git tree unavailable"])))
        if not apply:
            self.say(step="adopt", result="plan_only", sha=sha, verified_against_git=True, ignored=v["ignored_not_hashed"],
                     note="would add .release-complete marking this directory as an adopted, NOT immutable release")
            return {"result": "plan_only"}
        marker = {"sha": sha, "adopted": True, "adopted_at": utc(), "verified_against_git": True, "tree_sha": v["git_tree_sha"], "ignored_not_hashed": v["ignored_not_hashed"],
                  "note": "built outside deploy/release.py; contents compared with the commit's git tree at adoption, then not sealed read-only"}
        (d / ".release-complete").write_text(json.dumps(marker) + "\n")
        self.log(action="adopt", sha=sha, result="adopted")
        self.say(step="adopt", result="adopted", sha=sha)
        return {"result": "adopted"}

    # -- switch machinery
    def preflight(self, sha: str):
        if not self.is_prepared(sha):
            raise Refused("that release is not prepared; run `prepare` first")
        bi = json.loads((self.dest(sha) / "build-info.json").read_text())
        if bi.get("release_sha") != sha:
            raise Refused("build-info.json does not name this release")
        if not Path(self.venv_python).exists():
            raise Refused("the service venv python is missing")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1", "PYTHONPATH": str(self.dest(sha))}
        rc, _ = self._run([self.venv_python, "-c", SMOKE], timeout=60, cwd=str(self.dest(sha)), env=env)
        if rc != 0:
            raise Refused("the release does not import under the service venv; nothing was changed")
        return bi

    def atomic_link(self, link: Path, target: Path):
        tmp = link.with_name(f".{link.name}.new.{os.getpid()}")
        if tmp.is_symlink() or tmp.exists():
            tmp.unlink()
        os.symlink(target, tmp)
        os.replace(tmp, link)                                                       # rename(2) over a symlink: readers see the old or the new target, never none

    def restart_and_wait(self, timeout: float, stable: int = 3) -> dict:
        rc, out = self._run(["systemctl", "--user", "show", UNIT, "-p", "ActiveState", "-p", "NRestarts"])
        before = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
        rc, _ = self._run(["systemctl", "--user", "restart", UNIT], timeout=120)
        if rc != 0:
            return {"ok": False, "why": "systemctl restart failed"}
        deadline, good, last = time.monotonic() + timeout, 0, "no response"
        while time.monotonic() < deadline:
            self.ops.sleep(1.0)
            active = self._run(["systemctl", "--user", "is-active", UNIT])[1].strip() == "active"
            status, body = self.ops.health(self.port)
            if active and status == 200 and isinstance(body, dict) and body.get("status") == "ok":
                good += 1
                if good >= stable:
                    _, out = self._run(["systemctl", "--user", "show", UNIT, "-p", "ActiveState", "-p", "NRestarts"])
                    after = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
                    if after.get("NRestarts") not in (None, before.get("NRestarts")) and before.get("NRestarts") is not None:
                        return {"ok": False, "why": "the unit restarted itself while being watched (crash loop)"}
                    return {"ok": True, "health_checks_in_a_row": good}
            else:
                good, last = 0, f"active={active} health={status}"
        return {"ok": False, "why": "not healthy within the time limit: " + last}

    def switch(self, sha: str, action: str, apply: bool, health_timeout: float, nginx: bool) -> dict:
        self.preflight(sha)
        cur = self.current()
        cur_sha = self.sha_of(cur)
        plan = {"action": action, "to": sha, "from": cur_sha, "steps": ["swap app symlink atomically", f"systemctl --user restart {UNIT}", f"health check http://127.0.0.1:{self.port}/api/health (3 in a row)",
                                                                        "on failure: restore the previous symlink, restart, health check again"] + (["install nginx vhost (explicit flag)"] if nginx else [])}
        if cur_sha == sha:
            self.say(step=action, result="already_current", sha=sha)
            return {"result": "already_current", "sha": sha}
        if not apply:
            self.say(step=action, result="plan_only", plan=plan, note="re-run with --apply to do it")
            return {"result": "plan_only", "plan": plan}
        with self.lock():
            self.log(action=action, event="start", to=sha, **{"from": cur_sha})
            old_prev = Path(os.readlink(self.previous)) if self.previous.is_symlink() else None
            if cur is not None:
                self.atomic_link(self.previous, cur)                                 # the predecessor stays addressable
            self.atomic_link(self.app, self.dest(sha))
            self.say(step=action, event="swapped", to=sha, **{"from": cur_sha})
            res = self.restart_and_wait(health_timeout)
            if res["ok"]:
                self.log(action=action, event="done", to=sha, **{"from": cur_sha}, result="ok", health=res)
                self.say(step=action, result="ok", sha=sha)
                return {"result": "ok", "sha": sha, "health": res}
            self.say(step=action, event="failed", why=res["why"], rolling_back_to=cur_sha)
            if cur is None:
                self.app.unlink()                                                    # first deployment: restore "no app", the symlink is the only thing we created
                self.log(action=action, event="failed", to=sha, result="failed_no_predecessor", why=res["why"])
                return {"result": "failed_no_predecessor", "why": res["why"]}
            self.atomic_link(self.app, cur)
            if old_prev is not None:
                self.atomic_link(self.previous, old_prev)                            # a failed attempt leaves `previous` exactly as it was
            back = self.restart_and_wait(health_timeout)
            self.log(action=action, event="rollback", to=cur_sha, result="rolled_back" if back["ok"] else "rollback_failed", why=res["why"], health=back)
            self.say(step=action, result="rolled_back" if back["ok"] else "rollback_failed", why=res["why"], sha=cur_sha)
            return {"result": "rolled_back" if back["ok"] else "rollback_failed", "why": res["why"], "restored": cur_sha}

    def deploy(self, sha, apply=False, health_timeout=30.0, nginx=False):
        return self.switch(sha, "deploy", apply, health_timeout, nginx)

    def rollback(self, to=None, apply=False, health_timeout=30.0):
        if to is None:
            if not self.previous.is_symlink():
                raise Refused("there is no previous release recorded (app.previous is absent)")
            to = self.sha_of(Path(os.readlink(self.previous)))
            if to is None:
                raise Refused("app.previous does not point at a release directory")
        return self.switch(to, "rollback", apply, health_timeout, False)

    # -- nginx (only when asked)
    def install_nginx(self, sha: str, apply: bool) -> dict:
        src = str(self.dest(sha) / "deploy" / "nginx" / NGINX_CONF)
        if not Path(src).is_file():
            raise Refused("that release has no nginx vhost file")
        plan = ["backup the installed vhost if any", "install the release's vhost (mode 644)", "nginx -t", "reload nginx on success; on failure restore the backup and do NOT reload"]
        if not apply:
            self.say(step="nginx", result="plan_only", plan=plan)
            return {"result": "plan_only"}
        stamp = utc().replace(":", "")
        had = Path(NGINX_DEST).exists()
        bak = f"{NGINX_DEST}.bak-{stamp}"
        if had:
            self._run(["sudo", "-n", "cp", "-p", NGINX_DEST, bak])
        rc, _ = self._run(["sudo", "-n", "install", "-m", "644", src, NGINX_DEST])
        ok = rc == 0 and self._run(["sudo", "-n", "nginx", "-t"])[0] == 0
        if ok:
            ok = self._run(["sudo", "-n", "systemctl", "reload", "nginx"])[0] == 0
            self.log(action="nginx", sha=sha, result="installed" if ok else "reload_failed")
            return {"result": "installed" if ok else "reload_failed"}
        if had:
            self._run(["sudo", "-n", "cp", "-p", bak, NGINX_DEST])
        else:
            self._run(["sudo", "-n", "mv", NGINX_DEST, f"{NGINX_DEST}.failed-{stamp}"])      # moved aside, not deleted
        self.log(action="nginx", sha=sha, result="reverted")
        raise Refused("nginx test failed; the previous vhost state was restored and nginx was not reloaded")

    # -- read-only status
    def status(self) -> dict:
        cur = None
        try:
            cur = self.sha_of(self.current())
        except Refused as e:
            cur = f"not a symlink: {e}"
        prev = self.sha_of(Path(os.readlink(self.previous))) if self.previous.is_symlink() else None
        rels = []
        for d in sorted(self.releases.glob("*")) if self.releases.is_dir() else []:
            if SHA40.fullmatch(d.name):
                bi = {}
                try:
                    bi = json.loads((d / "build-info.json").read_text())
                except (OSError, ValueError):
                    pass
                rels.append({"sha": d.name, "complete": (d / ".release-complete").is_file(), "built_at": bi.get("built_at"), "checks_all_passed": bi.get("checks_all_passed")})
        tail = []
        if self.history.is_file():
            tail = [json.loads(l) for l in self.history.read_text().splitlines()[-10:]]
        return {"app": cur, "previous": prev, "releases": rels, "history_tail": tail}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="release.py", description=__doc__.split("\n")[0])
    p.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--port", type=int, default=PORT)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("--repo", required=True)
    a.add_argument("--sha", required=True)
    a.add_argument("--checks", required=True, type=Path)
    a.add_argument("--allow-failed-checks", action="store_true")
    d = sub.add_parser("deploy")
    d.add_argument("--sha", required=True)
    d.add_argument("--apply", action="store_true")
    d.add_argument("--health-timeout", type=float, default=30.0)
    d.add_argument("--nginx-install", action="store_true", help="also install deploy/nginx/frontier.morphoswarm.ai.conf from this release (sudo; explicit only)")
    r = sub.add_parser("rollback")
    r.add_argument("--to")
    r.add_argument("--apply", action="store_true")
    r.add_argument("--health-timeout", type=float, default=30.0)
    o = sub.add_parser("adopt", help="mark an existing hand-built release directory as complete so it can be rolled back to")
    o.add_argument("--sha", required=True)
    o.add_argument("--repo", help="a git repository containing the commit; REQUIRED: the directory is compared byte for byte with it")
    o.add_argument("--apply", action="store_true")
    v = sub.add_parser("verify", help="read-only: does releases/<sha> hold exactly the committed files?")
    v.add_argument("--sha", required=True)
    v.add_argument("--repo")
    sub.add_parser("status")
    args = p.parse_args(argv)
    rel = Release(args.root, port=args.port)
    try:
        if args.cmd == "prepare":
            rel.prepare(args.repo, args.sha, args.checks, args.allow_failed_checks)
        elif args.cmd == "deploy":
            res = rel.deploy(args.sha, args.apply, args.health_timeout)
            if args.nginx_install and res["result"] in ("ok", "already_current", "plan_only"):
                rel.install_nginx(args.sha, args.apply)
            return {"rolled_back": 10, "failed_no_predecessor": 10, "rollback_failed": 11}.get(res["result"], 0)
        elif args.cmd == "adopt":
            rel.adopt(args.sha, args.apply, args.repo)
        elif args.cmd == "verify":
            return 0 if rel.verify(args.sha, args.repo)["matches_git" if args.repo else "matches_claimed_tree"] is True else 3
        elif args.cmd == "rollback":
            res = rel.rollback(args.to, args.apply, args.health_timeout)
            return {"rolled_back": 10, "rollback_failed": 11}.get(res["result"], 0)
        else:
            print(json.dumps(rel.status(), indent=1, sort_keys=True))
    except Refused as e:
        print(json.dumps({"refused": str(e)}), file=sys.stderr)
        return 12 if "nginx test failed" in str(e) else e.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
