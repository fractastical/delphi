import contextlib
import copy
import json
import time
from hashlib import sha256

import numpy as np

from engineering.aeroelastic import audit_fidelity as audit
from engineering.aeroelastic import fidelity, model, run

TINY = {"span": 4, "chord": 1}


def arm(tmp_path, kind, compliance=0.8, mesh="l32x8"):
    """A real solve_arm result on a 4x1 lattice, filed under a declared non-reference identity."""
    folder = tmp_path / "arms" / f"chi{compliance}-u20-{mesh}-{kind}"
    result = run.solve_arm(
        compliance, 20.0, "tiny4x1", kind, folder, time.monotonic() + 120, TINY
    )
    return folder, result


def ledger():
    return audit.Ledger(audit.frozen()["tolerance"])


def rewrite_states(folder, result, change):
    data = dict(np.load(folder / "static-states.npz"))
    change(data)
    np.savez_compressed(folder / "static-states.npz", **data)
    result["static_state_artifact"]["sha256"] = sha256(
        (folder / "static-states.npz").read_bytes()
    ).hexdigest()


def test_clean_two_way_arm_reproduces_and_tampered_states_do_not(tmp_path):
    # compliance 0.8 genuinely exits the domain on a 4x1 lattice
    folder, result = arm(tmp_path, "two-way-static-feedback", compliance=0.2)
    assert result["status"] == "converged static feedback"
    clean = ledger()
    record = audit.audit_arm(clean, folder, result, model.protocol())
    assert record["final_pose_resolved"] and clean.findings == []

    def bump(data):
        data["pectoral_L__shape_load_N"][-1] *= 1.01

    rewrite_states(folder, result, bump)
    tampered = ledger()
    audit.audit_arm(tampered, folder, result, model.protocol())
    subjects = " ".join(x["subject"] for x in tampered.findings)
    assert "relaxation" in subjects and "final_pose_fresh_VLM_force" in subjects
    assert "lattice_A_m" in subjects or "closed_form_deflection" in subjects


def test_stale_hash_and_edited_CL_are_findings(tmp_path):
    folder, result = arm(tmp_path, "rigid")
    edited = copy.deepcopy(result)
    edited["iterations"][0]["CL_on_fixed_source_area"] += 1e-6
    found = ledger()
    audit.audit_arm(found, folder, edited, model.protocol())
    assert any(x["subject"].endswith(".0.CL") for x in found.findings)
    raw = bytearray((folder / "static-states.npz").read_bytes())
    raw[-30] ^= 0xFF
    (folder / "static-states.npz").write_bytes(bytes(raw))
    stale = ledger()
    # a corrupted archive may not even load; the identity finding is recorded before loading
    with contextlib.suppress(Exception):
        audit.audit_arm(stale, folder, result, model.protocol())
    assert stale.findings[0]["kind"] == "identity"


def test_genuine_domain_exit_is_reproduced_and_kept(tmp_path, monkeypatch):
    soft = copy.deepcopy(model.protocol())
    for fin in soft["parameters"]["EI_inputs"].values():
        fin["EI_Nm2_by_compliance"]["0.8"] /= 50
    monkeypatch.setattr(run, "protocol", lambda: soft)
    folder, result = arm(tmp_path, "one-way-frozen-load")
    assert result["status"] == "model-domain exit: proposed linear-beam shape"
    assert not result["valid_for_declared_transfer"] and result["flight"] is None
    found = ledger()
    record = audit.audit_arm(found, folder, result, soft)
    assert record["domain_exit"]["kind"] == "proposed"
    assert record["domain_exit"]["fins_outside_domain"]
    assert [x for x in found.findings if x["kind"] == "reproduction"] == []


def test_separate_three_grid_implementation_agrees_with_the_runner():
    fp = fidelity.fprotocol()
    tol = audit.frozen()["tolerance"]
    spans = {"main": 16, "fine": 24, "l32x8": 32, "l36x9": 36, "l64x16": 64}
    cases = [
        ({m: -0.0059 + 4e-4 * (16 / s) ** 2 for m, s in spans.items()}, 1e-9),
        ({m: 9e-5 + 2e-6 * (16 / s) ** 1.0 for m, s in spans.items()}, 1e-9),
        ({m: 1e-6 - 4e-6 * (16 / s) for m, s in spans.items()}, 1e-12),
        (
            dict(
                zip(spans, [-0.0059, -0.0060, -0.0058, -0.0061, -0.0059], strict=True)
            ),
            1e-9,
        ),
        ({m: -0.0059 + 4e-4 * (16 / s) ** 2 for m, s in spans.items()}, 1e-3),
        ({m: 0.25 for m in spans}, 0.0),
    ]
    for series, floor in cases:
        mine, _ = audit.judge(series, floor, fp, tol)
        assert mine == fidelity.classify(series, floor, fp)["status"], series


def test_whole_return_identity_and_completeness(tmp_path):
    out = tmp_path / "out"
    folder, _ = arm(out, "rigid")
    fp = fidelity.fprotocol()
    fidelity.receipt(out, time.monotonic(), None, fp)
    report = audit.audit(out, tmp_path / "audit.json")
    kinds = report["finding_counts"]
    identity = [x["subject"] for x in report["findings"] if x["kind"] == "identity"]
    # tests may run unpinned; the audit must then say so and nothing else
    assert identity == ([] if np.__version__ == "2.5.4" else ["environment"])
    assert "reproduction" not in kinds
    assert kinds["missing"] == 44 + 5  # 44 arms and 5 lattice controls not returned
    assert report["native_statuses"]["chi0.8-u20-l32x8-rigid"] == "computed rigid"
    raw = json.loads((folder / "result.json").read_text())
    raw["status"] = "computed rigid "
    (folder / "result.json").write_text(json.dumps(raw))
    changed = audit.audit(out, tmp_path / "audit2.json")
    assert any(
        x["kind"] == "identity" and x["subject"].endswith("result.json")
        for x in changed["findings"]
    )
    assert not changed["audit_passed"]
