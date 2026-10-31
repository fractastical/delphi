"""Lean checks for lean/Admissible.lean. They run real Lean over Mathlib; if Lean or the built project is missing they
SKIP and claim nothing. Honest by construction: exit codes are the compiler's own (no pipeline), the positive file must have
no error and no `sorry`, every axiom print must be the three standard axioms, and the negative controls must be rejected
INSIDE their own labelled mutant blocks while their true twins (same proof script) compile."""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJECT = Path(os.environ.get("FRONTIER_LEAN_PROJECT", "/data/artifacts/mathlib-probe"))
STANDARD = {"propext", "Classical.choice", "Quot.sound"}
EXPECTED_AXIOM_PRINTS = {"D_eq", "unstable_of_pos_eigenvalue", "exists_pos_eigenvalue_of_unstable", "unstable_iff_exists_pos_eigenvalue",
                         "trace_hypothesis_needed", "finite_domain_linearly_stable", "trace_neg_of_wellmixed",
                         "real_eigenvalue_neg_of_modeStable", "worked_continuum", "worked_unstable_iff", "worked_not_unstable_on_pi",
                         "worked_modeStable_on_pi", "worked_D_two_pi_one", "worked_unstable_on_two_pi",
                         "worked_not_modeStable_on_two_pi", "worked_growth_on_two_pi"}

lean_ok = shutil.which("lake") is not None and (PROJECT / "lakefile.toml").exists() and (PROJECT / ".lake").exists()
pytestmark = pytest.mark.skipif(not lean_ok, reason="Lean/Mathlib project not available")


def compile_text(src: str, label: str, timeout: int = 500):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / f"{label}.lean"
        f.write_text(src)
        cmd = ["lake", "env", "lean", "-j2", str(f)]
        if shutil.which("systemd-run"):
            cmd = ["systemd-run", "--user", "--scope", "-q", "-p", "TasksMax=128", "-p", "MemoryMax=12G", "-p", "MemorySwapMax=0",
                   "-p", f"RuntimeMaxSec={timeout}"] + cmd
        p = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, timeout=timeout + 60)
        return p.returncode, (p.stdout + p.stderr).replace(str(f), "FILE")   # returncode is the compiler's, not a pipeline's


@pytest.fixture(scope="module")
def positive():
    return compile_text((ROOT / "lean" / "Admissible.lean").read_text(), "positive")


@pytest.fixture(scope="module")
def controls():
    full = (ROOT / "lean" / "Admissible.lean").read_text()
    base = full[:full.index("section AxiomAudit")]
    part = (ROOT / "lean" / "AdmissibleControls.lean.part").read_text()
    src = base + "\n" + part
    lines = src.split("\n")
    blocks, cur = {}, None
    for i, l in enumerate(lines, 1):
        m = re.match(r"-- BEGIN (twin|mutant):(\w+)", l)
        if m: cur = (m.group(1), m.group(2), i)
        elif l.startswith("-- END") and cur: blocks[(cur[0], cur[1])] = (cur[2], i); cur = None
    code, out = compile_text(src, "controls")
    errs = [int(m.group(1)) for m in re.finditer(r"FILE:(\d+):\d+: error", out)]
    return code, out, blocks, errs


def test_positive_file_compiles_clean(positive):
    code, out = positive
    assert code == 0, out[-2000:]
    assert not re.search(r"error|sorry", out), out[-2000:]


def test_every_axiom_print_is_standard_and_complete(positive):
    code, out = positive
    prints = re.findall(r"'Admissible\.(\w+)' depends on axioms: \[([^\]]*)\]", out)
    assert {n for n, _ in prints} == EXPECTED_AXIOM_PRINTS
    for name, axs in prints:
        assert set(a.strip() for a in axs.split(",")) <= STANDARD, (name, axs)
    # "clean axioms" is necessary, not sufficient: the statements are pinned by the controls and by test_names_say_what_they_prove


def test_controls_are_rejected_only_inside_mutant_blocks(controls):
    code, out, blocks, errs = controls
    assert code != 0, "negative controls compiled: they test nothing"
    mutants = {k[1]: v for k, v in blocks.items() if k[0] == "mutant"}
    twins = {k[1]: v for k, v in blocks.items() if k[0] == "twin"}
    assert len(mutants) == 4 and len(twins) == 4
    in_mut = {n: [e for e in errs if a <= e <= b] for n, (a, b) in mutants.items()}
    assert all(in_mut[n] for n in mutants), in_mut            # every mutant is rejected
    assert not any(a <= e <= b for e in errs for (a, b) in twins.values()), errs   # no true twin is rejected
    assert all(any(a <= e <= b for a, b in mutants.values()) for e in errs), errs  # no error outside a mutant block


def test_sorry_is_caught_by_the_axiom_print():
    code, out = compile_text("import Mathlib.Tactic\ntheorem bad : (1:ℝ) = 2 := by sorry\n#print axioms bad\n", "sorrycontrol")
    assert code == 0 and "sorryAx" in out and "declaration uses" in out, out[-800:]


def test_names_say_what_they_prove():
    src = (ROOT / "lean" / "Admissible.lean").read_text()
    # the one-way predicate must not be called an iff, and the "stable" label must not sit on a mere non-instability
    assert not re.search(r"theorem unstable_iff_pos_eigenvalue\b", src)
    assert not re.search(r"theorem worked_stable_on_pi\b", src)
    assert re.search(r"theorem worked_not_unstable_on_pi\b", src) and re.search(r"theorem worked_modeStable_on_pi\b", src)
    assert re.search(r"theorem unstable_iff_exists_pos_eigenvalue\b", src) and re.search(r"theorem worked_unstable_on_two_pi\b", src)
