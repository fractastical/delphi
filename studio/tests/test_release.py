"""deploy/release.py: real git repository, real tar, real symlinks; only systemctl, the health endpoint and the import smoke test are simulated (a release is
'healthy' iff its own flag.txt says ok, which models 'the service runs the code that app points at'). No database, no network, nothing under /data/services."""
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("frontier_release", Path(__file__).resolve().parents[1] / "deploy" / "release.py")
R = importlib.util.module_from_spec(SPEC)
sys.modules["frontier_release"] = R
SPEC.loader.exec_module(R)
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "PATH": os.environ["PATH"], "HOME": "/nonexistent"}


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True, env=GIT_ENV).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "src"
    r.mkdir()
    git(r, "init", "-q")
    return r


def commit(repo, flag="ok", extra=None):
    (repo / "flag.txt").write_text(flag)
    (repo / "frontier").mkdir(exist_ok=True)
    (repo / "frontier" / "web.py").write_text(f"# version flag={flag}\n")
    (repo / "deploy" / "nginx").mkdir(parents=True, exist_ok=True)
    (repo / "deploy" / "nginx" / R.NGINX_CONF).write_text(f"# vhost {flag}\n")
    for k, v in (extra or {}).items():
        (repo / k).write_text(v)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", f"v {flag}")
    return git(repo, "rev-parse", "HEAD")


def receipt(tmp_path, sha, exit_codes=(0,), name="checks.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"schema": "frontier.release.checks/1", "sha": sha, "checks": [
        {"name": f"check{i}", "command": "pytest -q", "exit": c, "passed": 10, "total": 10, "at": "2026-10-31T19:00:00Z"} for i, c in enumerate(exit_codes)]}))
    return p


class FakeOps(R.Ops):
    def __init__(self, root):
        self.root, self.log, self.restarts, self.nrestarts = Path(root), [], 0, 0
        self.smoke_ok, self.restart_ok, self.crash_after_restart, self.nginx_t_ok, self.listening = True, True, False, True, False

    def run(self, argv, timeout=60, cwd=None, env=None):
        self.log.append(tuple(argv))
        if argv[0] == "git":
            done = subprocess.run(list(argv), capture_output=True, text=True, env=GIT_ENV)
            return done.returncode, done.stdout
        if argv[0] == "systemctl":
            verb = argv[2]
            if verb == "restart":
                self.restarts += 1
                self.listening = self.restart_ok
                return (0 if self.restart_ok else 1), ""
            if verb == "is-active":
                return 0, "active\n" if self.listening else "failed\n"
            if verb == "show":
                return 0, f"ActiveState={'active' if self.listening else 'failed'}\nNRestarts={self.nrestarts}\n"
        if argv[0] == str(self.root / "venv" / "bin" / "python"):
            return (0 if self.smoke_ok else 1), ""
        if argv[:3] == ["sudo", "-n", "nginx"]:
            return (0 if self.nginx_t_ok else 1), ""
        if argv[0] == "sudo":
            return 0, ""
        raise AssertionError(argv)

    def health(self, port, timeout=2.0):
        app = self.root / "app"
        if not self.listening or not app.exists():
            return None, None
        if self.crash_after_restart and (app / "b.txt").exists():            # only the new (b) release crash-loops
            self.nrestarts += 1
        ok = (app / "flag.txt").read_text() == "ok"
        return (200, {"status": "ok"}) if ok else (503, None)

    def sleep(self, s):
        pass


@pytest.fixture
def rel(tmp_path):
    root = tmp_path / "svc"
    (root / "venv" / "bin").mkdir(parents=True)
    (root / "venv" / "bin" / "python").write_text("")
    ops = FakeOps(root)
    out = []
    return R.Release(root, ops=ops, out=out.append), ops, out


def prepared(rel, tmp_path, repo, flag="ok", extra=None):
    r, ops, out = rel
    sha = commit(repo, flag, extra)
    assert r.prepare(str(repo), sha, receipt(tmp_path, sha, name=f"c-{sha[:7]}.json"))["result"] == "prepared"
    return sha


# ------------------------------------------------------------------ prepare
def test_prepare_archives_exactly_the_committed_sha_and_writes_build_info(rel, tmp_path, repo):
    r, ops, out = rel
    sha = commit(repo, "ok", {"keep.txt": "committed"})
    (repo / "keep.txt").write_text("LOCAL EDIT NOT COMMITTED")
    (repo / "untracked-secret.env").write_text("TOKEN=x")
    res = r.prepare(str(repo), sha, receipt(tmp_path, sha))
    d = r.releases / sha
    assert res["result"] == "prepared" and (d / "keep.txt").read_text() == "committed" and not (d / "untracked-secret.env").exists()
    assert (d / "flag.txt").read_text() == "ok" and (d / ".release-complete").is_file()
    bi = json.loads((d / "build-info.json").read_text())
    tar = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", sha], capture_output=True, check=True, env=GIT_ENV).stdout
    assert bi["release_sha"] == sha and bi["tree_sha"] == git(repo, "rev-parse", sha + "^{tree}") and bi["archive_sha256"] == hashlib.sha256(tar).hexdigest()
    assert bi["checks_all_passed"] is True and bi["checks"][0]["exit"] == 0 and bi["checks_receipt_sha256"] and bi["built_at"].endswith("Z")
    assert not list(r.releases.glob(".partial-*"))
    assert json.loads(r.history.read_text().splitlines()[-1])["result"] == "prepared"


def test_a_prepared_release_is_immutable_and_idempotent(rel, tmp_path, repo):
    r, *_ = rel
    sha = prepared(rel, tmp_path, repo)
    d = r.releases / sha
    with pytest.raises(PermissionError):
        (d / "flag.txt").write_text("tampered")
    with pytest.raises(PermissionError):
        (d / "new.txt").write_text("x")
    assert not (stat.S_IMODE((d / "flag.txt").stat().st_mode) & 0o222) and not (stat.S_IMODE(d.stat().st_mode) & 0o222)
    before = json.loads((d / "build-info.json").read_text())
    assert r.prepare(str(repo), sha, receipt(tmp_path, sha, exit_codes=(0, 0), name="other.json"))["result"] == "already_prepared"
    assert json.loads((d / "build-info.json").read_text()) == before                       # the existing release is not rewritten


def test_prepare_refusals_change_nothing(rel, tmp_path, repo):
    r, *_ = rel
    sha = commit(repo)
    other = "f" * 40
    for bad_sha in ("main", sha[:7], sha.upper(), ""):
        with pytest.raises(R.Refused):
            r.prepare(str(repo), bad_sha, receipt(tmp_path, sha))
    with pytest.raises(R.Refused, match="not a commit"):
        r.prepare(str(repo), other, receipt(tmp_path, other))
    with pytest.raises(R.Refused, match="another commit"):
        r.prepare(str(repo), sha, receipt(tmp_path, other))                                  # a receipt for a different commit is not accepted
    with pytest.raises(R.ChecksFailed):
        r.prepare(str(repo), sha, receipt(tmp_path, sha, exit_codes=(0, 1)))
    bad = tmp_path / "bad.json"
    for content in ("{not json", json.dumps({"schema": "x"}), json.dumps({"schema": "frontier.release.checks/1", "sha": sha, "checks": []}),
                    json.dumps({"schema": "frontier.release.checks/1", "sha": sha, "checks": [{"name": "a", "command": "b", "exit": "0", "at": "t"}]})):
        bad.write_text(content)
        with pytest.raises(R.Refused):
            r.prepare(str(repo), sha, bad)
    assert not (r.releases / sha).exists() and not list(r.releases.glob(".partial-*"))
    (r.releases / sha).mkdir(parents=True)
    (r.releases / sha / "precious").write_text("x")
    with pytest.raises(R.Refused, match="not a complete release"):
        r.prepare(str(repo), sha, receipt(tmp_path, sha))
    assert (r.releases / sha / "precious").read_text() == "x"                                # an unknown directory is never touched


def test_failed_checks_can_be_prepared_only_with_the_explicit_flag_and_are_recorded(rel, tmp_path, repo):
    r, *_ = rel
    sha = commit(repo)
    r.prepare(str(repo), sha, receipt(tmp_path, sha, exit_codes=(1,)), allow_failed=True)
    assert json.loads((r.releases / sha / "build-info.json").read_text())["checks_all_passed"] is False


# ------------------------------------------------------------------ deploy
def test_deploy_is_a_plan_unless_applied(rel, tmp_path, repo):
    r, ops, out = rel
    sha = prepared(rel, tmp_path, repo)
    res = r.deploy(sha)
    assert res["result"] == "plan_only" and not r.app.exists() and ops.restarts == 0 and "--apply" in out[-1]


def test_first_deploy_then_second_deploy_keeps_the_predecessor(rel, tmp_path, repo):
    r, ops, out = rel
    v1 = prepared(rel, tmp_path, repo, "ok")
    assert r.deploy(v1, apply=True)["result"] == "ok"
    assert os.readlink(r.app) == str(r.releases / v1) and not r.previous.exists() and ops.restarts == 1
    v2 = prepared(rel, tmp_path, repo, "ok", {"second.txt": "2"})
    before = {p.name: p.read_bytes() for p in (r.releases / v1).iterdir() if p.is_file()}
    assert r.deploy(v2, apply=True)["result"] == "ok"
    assert os.readlink(r.app) == str(r.releases / v2) and os.readlink(r.previous) == str(r.releases / v1)
    assert (r.releases / v1).is_dir() and {p.name: p.read_bytes() for p in (r.releases / v1).iterdir() if p.is_file()} == before
    assert r.deploy(v2, apply=True)["result"] == "already_current" and ops.restarts == 2
    hist = [json.loads(l) for l in r.history.read_text().splitlines()]
    assert [h.get("event") or h["result"] for h in hist if h["action"] == "deploy"] == ["start", "done", "start", "done"]


def test_an_unhealthy_release_is_rolled_back_automatically(rel, tmp_path, repo):
    r, ops, out = rel
    good = prepared(rel, tmp_path, repo, "ok")
    r.deploy(good, apply=True)
    bad = prepared(rel, tmp_path, repo, "bad")
    res = r.deploy(bad, apply=True, health_timeout=5)
    assert res["result"] == "rolled_back" and res["restored"] == good and "not healthy" in res["why"]
    assert os.readlink(r.app) == str(r.releases / good) and ops.restarts == 3                 # deploy, failed-release restart, restore restart
    assert not r.previous.exists() or os.readlink(r.previous) != str(r.releases / bad)
    assert (r.releases / bad).is_dir()                                                          # the failed release is kept for inspection
    assert json.loads(r.history.read_text().splitlines()[-1])["result"] == "rolled_back"


def test_previous_pointer_is_left_as_it_was_after_a_failed_deploy(rel, tmp_path, repo):
    r, ops, out = rel
    a = prepared(rel, tmp_path, repo, "ok")
    r.deploy(a, apply=True)
    b = prepared(rel, tmp_path, repo, "ok", {"b.txt": "b"})
    r.deploy(b, apply=True)                                                                     # app=b, previous=a
    c = prepared(rel, tmp_path, repo, "bad", {"c.txt": "c"})
    assert r.deploy(c, apply=True, health_timeout=3)["result"] == "rolled_back"
    assert os.readlink(r.app) == str(r.releases / b) and os.readlink(r.previous) == str(r.releases / a)


def test_restart_failure_and_crash_loops_are_failures_too(rel, tmp_path, repo):
    r, ops, out = rel
    a = prepared(rel, tmp_path, repo, "ok")
    r.deploy(a, apply=True)
    b = prepared(rel, tmp_path, repo, "ok", {"b.txt": "b"})
    ops.restart_ok = False
    assert r.deploy(b, apply=True, health_timeout=2)["result"] == "rollback_failed"            # the unit cannot restart even the old release: loud, distinct
    assert os.readlink(r.app) == str(r.releases / a)
    ops.restart_ok = True
    ops.crash_after_restart = True
    res = r.deploy(b, apply=True, health_timeout=5)
    assert res["result"] == "rolled_back" and "crash loop" in res["why"]


def test_rollback_failure_is_reported_distinctly(rel, tmp_path, repo):
    r, ops, out = rel
    a = prepared(rel, tmp_path, repo, "ok")
    r.deploy(a, apply=True)
    b = prepared(rel, tmp_path, repo, "bad", {"b.txt": "b"})
    a_dir = r.releases / a
    # make the old release unhealthy as well (simulates a shared dependency outage): the fake keys health on the flag, so use a service that never comes up
    ops.listening = False
    ops.restart_ok = False
    res = r.deploy(b, apply=True, health_timeout=2)
    assert res["result"] == "rollback_failed" and res["restored"] == a and os.readlink(r.app) == str(a_dir)


def test_first_deployment_failure_restores_no_app_and_keeps_the_release(rel, tmp_path, repo):
    r, ops, out = rel
    bad = prepared(rel, tmp_path, repo, "bad")
    res = r.deploy(bad, apply=True, health_timeout=3)
    assert res["result"] == "failed_no_predecessor" and not r.app.exists() and not r.app.is_symlink() and (r.releases / bad).is_dir()


def test_preflight_failures_change_nothing(rel, tmp_path, repo):
    r, ops, out = rel
    a = prepared(rel, tmp_path, repo, "ok")
    r.deploy(a, apply=True)
    b = prepared(rel, tmp_path, repo, "ok", {"b.txt": "b"})
    restarts = ops.restarts
    ops.smoke_ok = False
    with pytest.raises(R.Refused, match="does not import"):
        r.deploy(b, apply=True)
    assert os.readlink(r.app) == str(r.releases / a) and ops.restarts == restarts
    ops.smoke_ok = True
    with pytest.raises(R.Refused, match="not prepared"):
        r.deploy("e" * 40, apply=True)
    (r.root / "venv" / "bin" / "python").unlink()
    with pytest.raises(R.Refused, match="venv python is missing"):
        r.deploy(b, apply=True)


def test_a_real_app_directory_is_never_replaced(rel, tmp_path, repo):
    r, ops, out = rel
    sha = prepared(rel, tmp_path, repo)
    r.app.mkdir()
    (r.app / "mine.txt").write_text("keep")
    with pytest.raises(R.Refused, match="not a symlink"):
        r.deploy(sha, apply=True)
    assert (r.app / "mine.txt").read_text() == "keep" and ops.restarts == 0


# ------------------------------------------------------------------ rollback
def test_rollback_goes_to_the_previous_release_and_by_sha(rel, tmp_path, repo):
    r, ops, out = rel
    a = prepared(rel, tmp_path, repo, "ok")
    r.deploy(a, apply=True)
    b = prepared(rel, tmp_path, repo, "ok", {"b.txt": "b"})
    r.deploy(b, apply=True)
    assert r.rollback()["result"] == "plan_only" and os.readlink(r.app) == str(r.releases / b)
    assert r.rollback(apply=True)["result"] == "ok" and os.readlink(r.app) == str(r.releases / a) and os.readlink(r.previous) == str(r.releases / b)
    assert (r.releases / b).is_dir()
    with pytest.raises(R.Refused, match="not prepared"):
        r.rollback(to="d" * 40, apply=True)
    fresh = R.Release(r.root / "other", ops=ops, out=out.append)
    with pytest.raises(R.Refused, match="no previous release"):
        fresh.rollback()


# ------------------------------------------------------------------ commands, nginx, atomicity, lock, CLI
@pytest.mark.parametrize("argv,ok", [
    (["git", "-C", "/r", "cat-file", "-e", "x"], True), (["git", "-C", "/r", "rev-parse", "x"], True), (["git", "-C", "/r", "push"], False), (["git", "log"], False),
    (["systemctl", "--user", "restart", R.UNIT], True), (["systemctl", "--user", "is-active", R.UNIT], True),
    (["systemctl", "--user", "show", R.UNIT, "-p", "ActiveState", "-p", "NRestarts"], True), (["systemctl", "--user", "show", R.UNIT, "-p", "Environment"], False),
    (["systemctl", "--user", "restart", "other.service"], False), (["systemctl", "--user", "stop", R.UNIT], False), (["systemctl", "restart", R.UNIT], False),
    (["systemctl", "--user", "restart", R.UNIT, "extra"], False), (["bash", "-c", "x"], False), (["rm", "-rf", "/"], False),
    (["sudo", "-n", "nginx", "-t"], True), (["sudo", "-n", "systemctl", "reload", "nginx"], True), (["sudo", "-n", "systemctl", "stop", "nginx"], False),
    (["sudo", "-n", "rm", "-rf", "/etc"], False), (["sudo", "-n", "install", "-m", "644", "/x/deploy/nginx/" + R.NGINX_CONF, R.NGINX_DEST], True),
    (["sudo", "-n", "install", "-m", "644", "/x/evil", R.NGINX_DEST], False), (["sudo", "-n", "install", "-m", "777", "/x/deploy/nginx/" + R.NGINX_CONF, R.NGINX_DEST], False),
    (["sudo", "-n", "install", "-m", "644", "/x/deploy/nginx/" + R.NGINX_CONF, "/etc/passwd"], False), (["sudo", "bash"], False)])
def test_only_fixed_commands_are_allowed(argv, ok):
    if ok:
        R.check_argv(argv, "/v/python")
    else:
        with pytest.raises(R.Refused):
            R.check_argv(argv, "/v/python")
    R.check_argv(["/v/python", "-c", R.SMOKE], "/v/python")
    with pytest.raises(R.Refused):
        R.check_argv(["/v/python", "-c", "import os"], "/v/python")


def test_nginx_is_untouched_unless_asked_and_a_failed_test_reverts(rel, tmp_path, repo, monkeypatch):
    r, ops, out = rel
    dest = tmp_path / "etc-nginx-frontier.conf"
    monkeypatch.setattr(R, "NGINX_DEST", str(dest))
    sha = prepared(rel, tmp_path, repo)
    r.deploy(sha, apply=True)
    assert not [c for c in ops.log if c[0] == "sudo"]                                         # no flag, no sudo, ever
    assert r.install_nginx(sha, apply=False)["result"] == "plan_only" and not [c for c in ops.log if c[0] == "sudo"]
    assert r.install_nginx(sha, apply=True)["result"] == "installed"
    seq = [list(c[2:]) for c in ops.log if c[0] == "sudo"]
    assert seq[0][0] == "install" and seq[1] == ["nginx", "-t"] and seq[2] == ["systemctl", "reload", "nginx"] and len(seq) == 3
    dest.write_text("# installed vhost\n")
    ops.log.clear()
    ops.nginx_t_ok = False
    with pytest.raises(R.Refused, match="nginx test failed"):
        r.install_nginx(sha, apply=True)
    seq = [list(c[2:]) for c in ops.log if c[0] == "sudo"]
    assert seq[0][0] == "cp" and seq[-1][0] == "cp" and ["systemctl", "reload", "nginx"] not in seq                # backed up, restored, never reloaded
    ops.log.clear()
    dest.unlink()
    with pytest.raises(R.Refused):
        r.install_nginx(sha, apply=True)
    assert [c[2:][0] for c in ops.log if c[0] == "sudo"][-1] == "mv" and "rm" not in [c[2] for c in ops.log if c[0] == "sudo"]     # moved aside, not deleted


def test_the_symlink_swap_is_atomic_readers_never_see_it_missing(tmp_path):
    root = tmp_path / "svc"
    r = R.Release(root, ops=R.Ops(), out=lambda *_: None)
    a, b = tmp_path / "A", tmp_path / "B"
    a.mkdir(), b.mkdir()
    r.atomic_link(r.app, a) if False else (root.mkdir(), os.symlink(a, r.app))
    stop, bad = threading.Event(), []

    def reader():
        while not stop.is_set():
            try:
                t = os.readlink(r.app)
                if t not in (str(a), str(b)):
                    bad.append(t)
            except OSError as e:
                bad.append(repr(e))
    t = threading.Thread(target=reader)
    t.start()
    for i in range(3000):
        r.atomic_link(r.app, b if i % 2 == 0 else a)
    stop.set()
    t.join()
    assert bad == [] and not list(root.glob(".app.new.*"))


def test_a_second_operation_is_refused_while_one_runs(rel):
    r, *_ = rel
    with r.lock():
        with pytest.raises(R.Refused, match="another release operation"):
            r.lock()


def test_status_is_read_only_and_cli_exit_codes(rel, tmp_path, repo):
    r, ops, out = rel
    a = prepared(rel, tmp_path, repo)
    r.deploy(a, apply=True)
    st = r.status()
    assert st["app"] == a and st["previous"] is None and st["releases"][0]["sha"] == a and st["releases"][0]["complete"] and st["history_tail"]
    py = [sys.executable, str(Path(R.__file__))]
    env = {"PATH": os.environ["PATH"]}
    s = subprocess.run(py + ["--root", str(r.root), "status"], capture_output=True, text=True, env=env)
    assert s.returncode == 0 and json.loads(s.stdout)["app"] == a
    bad = subprocess.run(py + ["--root", str(r.root), "deploy", "--sha", "main", "--apply"], capture_output=True, text=True, env=env)
    assert bad.returncode == 3 and "40-hex" in bad.stderr
    nochk = subprocess.run(py + ["--root", str(r.root), "prepare", "--repo", str(repo), "--sha", commit(repo, "ok", {"y.txt": "y"}), "--checks", str(tmp_path / "nope.json")],
                           capture_output=True, text=True, env=env)
    assert nochk.returncode == 3
    failing = subprocess.run(py + ["--root", str(r.root), "prepare", "--repo", str(repo), "--sha", commit(repo, "ok", {"z.txt": "z"}), "--checks",
                                   str(receipt(tmp_path, git(repo, "rev-parse", "HEAD"), exit_codes=(2,), name="f.json"))], capture_output=True, text=True, env=env)
    assert failing.returncode == 4


def test_the_module_is_standard_library_only():
    import ast
    tree = ast.parse(Path(R.__file__).read_text())
    mods = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert mods <= set(sys.stdlib_module_names), mods - set(sys.stdlib_module_names)


def handbuild(r, repo, sha, with_pycache=True):
    """A release directory built outside release.py: git archive extracted by hand, plus a hand-written build-info.json (and runtime bytecode)."""
    d = r.releases / sha
    d.mkdir(parents=True)
    subprocess.run(f"git -C {repo} archive {sha} | tar -x -C {d}", shell=True, check=True, env=GIT_ENV)
    (d / "build-info.json").write_text(json.dumps({"release_sha": sha, "built_at": "2026-10-31T19:24:06+00:00"}))
    if with_pycache:
        (d / "frontier" / "__pycache__").mkdir()
        (d / "frontier" / "__pycache__" / "web.cpython-313.pyc").write_bytes(b"\0\1")
    return d


def test_git_tree_sha_equals_gits_for_modes_symlinks_and_unicode(tmp_path, repo):
    (repo / "bin").mkdir()
    (repo / "bin" / "run.sh").write_text("#!/bin/sh\n")
    (repo / "bin" / "run.sh").chmod(0o755)
    (repo / "caf\u00e9.txt").write_text("x\n")
    (repo / "ln").symlink_to("flag.txt")
    sha = commit(repo)
    work = tmp_path / "w"
    work.mkdir()
    subprocess.run(f"git -C {repo} archive {sha} | tar -x -C {work}", shell=True, check=True, env=GIT_ENV)
    assert R.git_tree_sha(work) == git(repo, "rev-parse", sha + "^{tree}")
    (work / "flag.txt").write_text("other")
    assert R.git_tree_sha(work) != git(repo, "rev-parse", sha + "^{tree}")


def test_verify_shows_whether_a_directory_holds_exactly_the_committed_files(rel, tmp_path, repo):
    r, ops, out = rel
    sha = prepared(rel, tmp_path, repo, "ok", {"keep.txt": "k"})
    v = r.verify(sha, str(repo))
    assert v["matches_git"] is True and v["matches_claimed_tree"] is True and v["dir_tree_sha"] == v["git_tree_sha"] == git(repo, "rev-parse", sha + "^{tree}")
    assert set(v["ignored_not_hashed"]) == {"build-info.json", ".release-complete"}
    assert r.verify(sha)["matches_git"] is None and "not equality with the git commit" in r.verify(sha)["note"]       # without --repo it says what it did NOT check
    d = r.releases / sha
    d.chmod(0o755), (d / "keep.txt").chmod(0o644)
    (d / "keep.txt").write_text("tampered")
    v2 = r.verify(sha, str(repo))
    assert v2["matches_git"] is False and v2["matches_claimed_tree"] is False and v2["differences"] == ["differs: keep.txt"]


def test_adopt_requires_the_files_to_be_byte_identical_to_the_commit(rel, tmp_path, repo):
    r, ops, out = rel
    sha = commit(repo, "ok", {"keep.txt": "k"})
    d = handbuild(r, repo, sha)                                                              # identical except build-info.json and __pycache__: the allowed extras
    (r.root / "app").symlink_to(d)
    assert not r.is_prepared(sha) and r.status()["releases"][0]["complete"] is False
    with pytest.raises(R.Refused, match="needs --repo"):
        r.adopt(sha, apply=True)                                                               # a 40-hex name is never accepted on its own
    before = {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}
    assert r.adopt(sha, repo=str(repo))["result"] == "plan_only" and not (d / ".release-complete").exists()
    assert r.adopt(sha, apply=True, repo=str(repo))["result"] == "adopted" and r.is_prepared(sha)
    after = {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file() and p.name != ".release-complete"}
    assert after == before
    m = json.loads((d / ".release-complete").read_text())
    assert m["adopted"] is True and m["verified_against_git"] is True and m["tree_sha"] == git(repo, "rev-parse", sha + "^{tree}") and "frontier/__pycache__/" in m["ignored_not_hashed"]
    assert r.adopt(sha, apply=True, repo=str(repo))["result"] == "already_complete"
    nxt = prepared(rel, tmp_path, repo, "ok", {"nxt.txt": "n"})
    assert r.deploy(nxt, apply=True)["result"] == "ok" and os.readlink(r.previous) == str(d)
    assert r.rollback(apply=True)["result"] == "ok" and os.readlink(r.app) == str(d)


@pytest.mark.parametrize("damage,expect", [("modify", "differs: keep.txt"), ("extra", "extra: surprise.py"), ("missing", "missing: keep.txt"), ("mode", "differs: run.sh")])
def test_adopt_refuses_a_directory_that_is_not_the_commit_and_says_what_differs(rel, tmp_path, repo, damage, expect):
    r, *_ = rel
    sha = commit(repo, "ok", {"keep.txt": "k", "run.sh": "#!/bin/sh\n"})
    d = handbuild(r, repo, sha)
    if damage == "modify":
        (d / "keep.txt").write_text("edited after the build")
    elif damage == "extra":
        (d / "surprise.py").write_text("print(1)")
    elif damage == "missing":
        (d / "keep.txt").unlink()
    else:
        (d / "run.sh").chmod(0o755)                                                          # executable bit flips the git mode; the bytes alone would not show it
    with pytest.raises(R.Refused, match="not byte-identical") as e:
        r.adopt(sha, apply=True, repo=str(repo))
    if damage != "mode":
        assert expect in str(e.value)
    assert not (d / ".release-complete").exists()


def test_adopt_refuses_when_it_cannot_be_sure(rel, repo):
    r, *_ = rel
    sha = commit(repo)
    with pytest.raises(R.Refused, match="does not exist"):
        r.adopt(sha, apply=True, repo=str(repo))
    d = r.releases / sha
    d.mkdir(parents=True)
    with pytest.raises(R.Refused, match="missing or unreadable"):
        r.adopt(sha, apply=True, repo=str(repo))
    (d / "build-info.json").write_text(json.dumps({"release_sha": "ee" * 20}))
    with pytest.raises(R.Refused, match="does not name this SHA"):
        r.adopt(sha, apply=True, repo=str(repo))
    assert not (d / ".release-complete").exists()


def test_prepare_refuses_an_archive_whose_files_do_not_hash_to_the_commits_tree(rel, tmp_path, repo):
    import io
    import tarfile
    r, ops, out = rel
    sha = commit(repo, "ok", {"keep.txt": "k"})

    class Tampered(FakeOps):
        def archive(self, repo_path, s):
            real = subprocess.run(["git", "-C", repo_path, "archive", "--format=tar", s], capture_output=True, check=True, env=GIT_ENV).stdout
            buf = io.BytesIO()
            with tarfile.open(fileobj=io.BytesIO(real)) as src, tarfile.open(fileobj=buf, mode="w") as dst:
                for m in src:
                    f = src.extractfile(m) if m.isfile() else None
                    if m.name == "keep.txt":
                        data = b"tampered in transit"
                        m.size = len(data)
                        f = io.BytesIO(data)
                    dst.addfile(m, f)
            buf.seek(0)

            class P:
                def wait(self):
                    return 0
            return P(), buf
    r2 = R.Release(r.root, ops=Tampered(r.root), out=out.append)
    with pytest.raises(R.Refused, match="do not hash to the commit's git tree"):
        r2.prepare(str(repo), sha, receipt(tmp_path, sha))
    assert not (r.releases / sha).exists() and not list(r.releases.glob(".partial-*"))
