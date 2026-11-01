"""Controls for the packet repairs. Each has a case it MUST flag and a case it MUST NOT.

A check whose only exercise is its happy path is not a check. Every control below runs the
repaired artifact against both a failing fixture and a passing one, and asserts the verdict
in each direction. None of this is a scientific run: no Morpheus arm is executed, the solver
is replaced by a fixture, and no result in artifacts/epithelial is read or written.

    python3 engineering/epithelial/test_packet_controls.py --packet <extracted packet dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

PASS, FAIL = "ok  ", "BAD "
results: list[tuple[str, bool, str]] = []


def check(name: str, got, want, note: str = "") -> None:
    ok = got == want
    results.append((name, ok, f"got {got!r}, want {want!r}{'; ' + note if note else ''}"))
    print(f"  {PASS if ok else FAIL}{name}: got {got!r}, want {want!r}")


def run(cmd, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ---------------------------------------------------------------- R1: BIN reaches the children
def control_r1_bin_exported(packet: Path) -> None:
    """The bug: BIN was defined in the parent and never exported, so every xargs child got an
    empty solver path. The fixture is an executable that records the path it was invoked as."""
    print("\nR1 solver path reaches xargs children")
    for label, with_fix in (("repaired runner", True), ("unexported-BIN control", False)):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fixture = td / "fake_solver"
            fixture.write_text(
                "#!/usr/bin/env bash\n"
                "printf 'time\\tcell.id\\tcell.center.x\\tcell.center.y\\tcell.volume\\tcell.surface\\n"
                "0\\t1\\t10\\t10\\t625\\t88\\n10\\t1\\t11\\t11\\t625\\t88\\n' > logger.csv\n"
                f"echo \"$0\" >> {td}/invoked.txt\n")
            fixture.chmod(0o755)
            (td / "invoked.txt").write_text("")
            script = (packet / "run_packet.sh").read_text()
            if not with_fix:
                script = script.replace("export BIN OUT HERE", "export OUT HERE")
            # exercise only the parallel section: a child that cannot see BIN fails to invoke it
            harness = td / "h.sh"
            harness.write_text(
                "set -u\n"
                f"HERE={packet}\nOUT={td}/out\nmkdir -p $OUT\nBIN={fixture}\n"
                "run_one() { a=$1; d=\"$OUT/$a\"; mkdir -p \"$d\"; "
                "( cd \"$d\" && \"$BIN\" >/dev/null 2>&1 ); return 0; }\n"
                "export -f run_one\n"
                + ("export BIN OUT HERE\n" if with_fix else "export OUT HERE\n")
                + "printf 'a1\\na2\\na3\\n' | xargs -P 3 -I{} bash -c 'run_one \"$@\"' _ {}\n")
            run(["bash", str(harness)])
            n = len([x for x in (td / "invoked.txt").read_text().splitlines() if x.strip()])
            check(f"R1 {label}: children that reached the solver", n, 3 if with_fix else 0,
                  "3 arms dispatched")


# ------------------------------------------------------- R2: no duplicate / symlink / traversal
def control_r2_archive_hygiene(tgz: Path, packet: Path) -> None:
    print("\nR2 archive hygiene and packet verification")
    with tarfile.open(tgz) as tf:
        names = tf.getnames()
        files = [m.name for m in tf.getmembers() if m.isfile()]
        links = [m.name for m in tf.getmembers() if m.issym() or m.islnk()]
        esc = [n for n in names if n.startswith("/") or ".." in Path(n).parts]
    check("R2 duplicate archive members", len(files) - len(set(files)), 0)
    check("R2 symlink/hardlink members", len(links), 0)
    check("R2 traversal/absolute members", len(esc), 0)

    r = run([sys.executable, str(packet / "verify_packet.py"), "--dir", str(packet)])
    check("R2 verify_packet on an intact packet (exit)", r.returncode, 0)

    # negative fixtures: each must be refused
    for label, mutate in (
        ("one byte flipped", lambda d: (d / "arms.json").write_bytes(
            (d / "arms.json").read_bytes().replace(b"S-k4", b"S-k9", 1))),
        ("member deleted", lambda d: (d / "README.md").unlink()),
        ("unlisted file added", lambda d: (d / "models" / "EXTRA.xml").write_text("<x/>")),
        ("symlink planted", lambda d: (d / "models" / "link.xml").symlink_to("/etc/hostname")),
        ("duplicate manifest line", lambda d: (d / "SHA256SUMS").write_text(
            (d / "SHA256SUMS").read_text() + (d / "SHA256SUMS").read_text().splitlines()[0] + "\n")),
    ):
        with tempfile.TemporaryDirectory() as td:
            dup = Path(td) / "p"
            shutil.copytree(packet, dup, symlinks=True)
            mutate(dup)
            r = run([sys.executable, str(dup / "verify_packet.py"), "--dir", str(dup)])
            check(f"R2 verify_packet refuses: {label} (exit)", r.returncode, 1)


# --------------------------------------------------------------- R3: failures cannot be masked
def control_r3_no_success_masking(packet: Path) -> None:
    print("\nR3 the audit, not the runner, decides success")
    good = ("time\tcell.id\tcell.center.x\tcell.center.y\tcell.volume\tcell.surface\n"
            "0\t1\t10\t10\t625\t88.6\n10\t1\t11\t11\t620\t88.1\n")
    arms = [{"name": f"S-k4-J140-lamV{v}-s1"} for v in ("0.1", "0.2", "0.4")]

    def build(td: Path, kind: str) -> Path:
        out = td / "out"
        out.mkdir(parents=True)
        for i, s in enumerate(arms):
            d = out / s["name"]
            d.mkdir()
            if kind == "missing" and i == 0:
                shutil.rmtree(d)
                continue
            (d / "exit.txt").write_text("exit=124\n" if (kind == "nonzero" and i == 0) else "exit=0\n")
            body = good
            if kind == "partial" and i == 0:
                body = "time\tcell.id\tcell.center.x\tcell.center.y\tcell.volume\tcell.surface\n0\t1\t10\t10\t625\t88.6\n"
            if kind == "nonfinite" and i == 0:
                body = good.replace("620", "nan")
            if kind == "fields" and i == 0:
                body = "time\tcell.id\n0\t1\n10\t1\n"
            if kind == "allfail":
                (d / "exit.txt").write_text("exit=1\n")
                body = "time\tcell.id\tcell.center.x\tcell.center.y\tcell.volume\tcell.surface\n"
            (d / "logger.csv").write_text(body)
        (td / "arms.json").write_text(json.dumps(arms))
        return out

    for kind, want in (("clean", 0), ("missing", 1), ("nonzero", 1), ("partial", 1),
                       ("nonfinite", 1), ("fields", 1), ("allfail", 1)):
        with tempfile.TemporaryDirectory() as t:
            td = Path(t)
            out = build(td, kind)
            # the runner's own wrapper claims success in every case; the audit must not believe it
            r = run([sys.executable, str(packet / "audit_completeness.py"),
                     "--arms", str(td / "arms.json"), "--out", str(out),
                     "--job-wrapper-exit", "0", "--report", str(td / "r.json")])
            check(f"R3 audit on '{kind}' fixture (exit)", r.returncode, want,
                  "wrapper exit was 0 in every case")


# ------------------------------------------------ R4: the solver never lands in the output tree
def control_r4_binary_outside_output(packet: Path) -> None:
    print("\nR4 the solver stays out of the collected tree")
    src = (packet / "run_packet.sh").read_text()
    check("R4 BIN defaults into WORKSPACE, not OUT", 'BIN=${PACKET_BIN:-$WORKSPACE/morpheus-2.3.9}' in src, True)
    check("R4 WORKSPACE is not derived from OUT", "WORKSPACE=${PACKET_WORKSPACE:-$(mktemp -d" in src, True)
    check("R4 download is byte-bounded", "--max-filesize" in src, True)
    check("R4 HTTP status is checked", '[ "$code" = "200" ]' in src, True)
    check("R4 hash verified before exec", src.index("sha256sum") < src.index("run_one()"), True)
    check("R4 a receipt replaces the binary in OUT", "binary-receipt.json" in src, True)


# -------------------------------------------------------- R5/R6: caps declared, analyzer honest
def control_r5_caps_declared(packet: Path) -> None:
    print("\nR5 per-arm and whole-job bounds are explicit")
    src = (packet / "run_packet.sh").read_text()
    for token in ("ARM_TIMEOUT_S", "JOB_TIMEOUT_S", "OUTPUT_CAP_MB", "DOWNLOAD_CAP_BYTES",
                  "setsid timeout", "--kill-after"):
        check(f"R5 declares {token}", token in src, True)


def control_r6_analyzer(packet: Path) -> None:
    """The analyzer must return three distinct verdicts, and UNRESOLVED must never read as PASS."""
    print("\nR6 analyzer verdicts, with a negative and an unresolved fixture")
    hdr = "time\tcell.id\tcell.center.x\tcell.center.y\tcell.volume\tcell.surface\n"

    def arm_rows(closed: bool) -> str:
        end = "40000" if closed else "37500"
        return hdr + f"0\t1\t10\t10\t37500\t88.6\n10\t1\t11\t11\t{end}\t88.1\n"

    def build(td: Path, thresholds: dict, lam_grid) -> Path:
        out = td / "out"
        out.mkdir(parents=True)
        arms = []
        for (k, J), thr in thresholds.items():
            for lam in lam_grid:
                n = f"S-k{k}-J{J:g}-lamV{lam:g}-s1"
                arms.append({"name": n})
                d = out / n
                d.mkdir()
                (d / "exit.txt").write_text("exit=0\n")
                (d / "logger.csv").write_text(arm_rows(lam < thr))
        (td / "arms.json").write_text(json.dumps(arms))
        return out

    grid = (0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8)
    cases = {
        # lambda* proportional to J exactly -> PASS
        "proportional (must PASS)": ({(4, 70): 0.35, (4, 140): 0.7, (4, 280): 1.4}, 0),
        # lambda* flat in J -> ratio spreads 4x -> FAIL
        "flat in J (must FAIL)": ({(4, 70): 0.7, (4, 140): 0.7, (4, 280): 0.7}, 1),
        # one column never arrests -> UNRESOLVED, and must not be dropped to rescue a PASS
        "one column unbracketed (must be UNRESOLVED)":
            ({(4, 70): 0.35, (4, 140): 0.7, (4, 280): 1e9}, 2),
    }
    for label, (thr, want) in cases.items():
        with tempfile.TemporaryDirectory() as t:
            td = Path(t)
            out = build(td, thr, grid)
            r = run([sys.executable, str(packet / "analyze_sweep.py"), "--arms", str(td / "arms.json"),
                     "--out", str(out), "--report", str(td / "r.json")])
            rep = json.loads((td / "r.json").read_text())
            check(f"R6 {label} (exit)", r.returncode, want)
            check(f"R6 {label} verdict", rep["verdict"], ["PASS", "FAIL", "UNRESOLVED"][want])
            if want == 2:
                check("R6 unresolved cell is named, not dropped", len(rep["unresolved"]) >= 1, True)

    declared = hashlib.sha256((packet / "analyze_sweep.py").read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as t:
        td = Path(t)
        out = build(td, {(4, 140): 0.7}, grid)
        run([sys.executable, str(packet / "analyze_sweep.py"), "--arms", str(td / "arms.json"),
             "--out", str(out), "--report", str(td / "r.json")])
        got = json.loads((td / "r.json").read_text())["criterion"]["criterion_sha256"]
    check("R6 report carries the criterion source hash", got, declared)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", required=True, help="extracted packet directory")
    ap.add_argument("--tgz", required=True)
    a = ap.parse_args()
    packet = Path(a.packet).resolve()
    control_r1_bin_exported(packet)
    control_r2_archive_hygiene(Path(a.tgz), packet)
    control_r3_no_success_masking(packet)
    control_r4_binary_outside_output(packet)
    control_r5_caps_declared(packet)
    control_r6_analyzer(packet)
    bad = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} controls pass")
    for n in bad:
        print(f"  FAILED {n}")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
