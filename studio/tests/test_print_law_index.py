"""Print law index (artifacts/print-law-index.json): it is current, it covers exactly the files the site publishes,
its numbers are the bytes' numbers, failed thresholds stay failed, no law is related to a file without an evidence
record, and the frozen artifacts it reads are untouched.

Builds the index once in memory (~30 s); run without the Postgres fixtures:
    pytest --noconftest tests/test_print_law_index.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("manifold3d")

from engineering import print_law_index as PLI

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "artifacts/print-law-index.schema.json").read_text())
FROZEN_AT = {"r1-strong": "19f4546", "r1-light": "19f4546", "r2-light": "1fac368", "r3-daane": "361480f",
             "r4-daane-printfix": "bd2fcf3"}


@pytest.fixture(scope="module")
def built():
    try:
        return PLI.build()
    except subprocess.CalledProcessError as e:
        pytest.skip(f"a pinned commit is not in this clone: {e.cmd}")


@pytest.fixture(scope="module")
def idx(built):
    return built[0]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def conform(obj, schema, path="$"):
    """The subset of JSON Schema this schema uses: const, enum, type, required, properties, items."""
    if "const" in schema:
        assert obj == schema["const"], path
    if "enum" in schema:
        assert obj in schema["enum"], f"{path}: {obj!r}"
    types = schema.get("type")
    if types:
        types = [types] if isinstance(types, str) else types
        py = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool,
              "null": type(None)}
        assert any(isinstance(obj, py[t]) and not (t in ("integer", "number") and isinstance(obj, bool))
                   for t in types), f"{path}: {type(obj).__name__} not {types}"
    if isinstance(obj, dict):
        for k in schema.get("required", []):
            assert k in obj, f"{path}: missing {k}"
        for k, sub in schema.get("properties", {}).items():
            if k in obj:
                conform(obj[k], sub, f"{path}.{k}")
    if isinstance(obj, list) and "items" in schema:
        for i, x in enumerate(obj):
            conform(x, schema["items"], f"{path}[{i}]")


def test_committed_index_and_page_are_what_the_builder_writes(built):
    idx, text = built
    assert (ROOT / "artifacts/print-law-index.json").read_text() == text
    assert (ROOT / "docs/print-law-index.md").read_text() == PLI.doc(idx)


def test_index_conforms_to_its_schema_and_the_check_catches_a_missing_field(idx):
    conform(idx, SCHEMA)
    broken = copy.deepcopy(idx)
    del broken["files"][0]["checks"]
    with pytest.raises(AssertionError):                     # positive control: the conformance check can fail
        conform(broken, SCHEMA)


def published_paths() -> set[str]:
    """What scripts/build_site.py model_downloads publishes: .stl/.glb/.zip members of each print manifest's files,
    plus a ZIP pinned by a download.json sidecar."""
    out = set()
    manifests = [ROOT / "artifacts" / n / "manifest.json" for n in ("print-v3", "print-v2", "print")]
    manifests += sorted((ROOT / "artifacts/glider").glob("*/manifest.json"))
    for m in manifests:
        d = m.parent.relative_to(ROOT).as_posix()
        out |= {f"{d}/{rel}" for rel in json.loads(m.read_text())["files"]
                if Path(rel).suffix.lower() in {".stl", ".glb", ".zip"}}
        side = m.parent / "download.json"
        if side.exists():
            out.add(json.loads(side.read_text())["path"])
    return out


def test_index_covers_exactly_the_published_print_files(idx):
    paths = [f["path"] for f in idx["files"]]
    assert len(paths) == len(set(paths))
    assert set(paths) == published_paths()
    assert sum(1 for p in paths if p.endswith(".stl")) == len(list((ROOT / "artifacts").glob("glider/*/stl/*.stl"))) \
        + sum(len(list((ROOT / "artifacts" / n / "stl").glob("*.stl"))) for n in ("print", "print-v2", "print-v3"))


def test_each_row_carries_its_files_bytes_and_mass(idx):
    for f in idx["files"]:
        b = (ROOT / f["path"]).read_bytes()
        assert f["sha256"] == sha(b) and f["bytes"] == len(b), f["path"]
        if f["kind"] == "stl_part":
            assert f["mass_g"] == pytest.approx(f["volume_mm3"] * f["material"]["density_kg_m3"] * 1e-6, rel=1e-6)
            assert f["material"]["density_kg_m3"] == 1220.0 and "not weighed" in f["mass_basis"]
        elif f["kind"].startswith("stl_"):
            assert f["mass_g"] is None and f["material"]["density_kg_m3"] is None   # resin not chosen: no mass
            assert f["conditional_mass_g_at_1220_kg_m3"] == pytest.approx(f["volume_mm3"] * 1220e-6, rel=1e-6)
        else:
            assert f["mass_g"] is None and f["volume_mm3"] is None


def test_glider_masses_agree_with_the_frozen_manifests(idx):
    for f in idx["files"]:
        if f["kind"] != "stl_part":
            continue
        m = json.loads((ROOT / "artifacts/glider" / f["revision"] / "manifest.json").read_text())
        part = next(p for p in m["parts"] if p["id"] == f["part_id"])
        assert f["mass_g"] == pytest.approx(part["mass_properties"]["mass_g"], rel=1e-4), f["path"]


def test_no_law_is_related_to_a_file_without_an_evidence_record(idx):
    evidence = {law["id"]: law["evidence"] for law in idx["laws"]}
    for rec in idx["files"] + idx["assemblies"]:
        for x in rec["law_relations"]:
            assert x["law_id"] in evidence
            if x["relation"] in ("governing", "checked"):
                assert evidence[x["law_id"]], (rec.get("path", rec["id"]), x["law_id"])
        if "law_ids" in rec:
            assert rec["law_ids"] == [x["law_id"] for x in rec["law_relations"] if x["relation"] != "not_applicable"]
    for law in idx["laws"]:
        for e in law["evidence"]:
            if not e["recomputed_in_this_index"] and e["artifact_sha256"]:
                assert e["commit"], (law["id"], e["what"])         # another agent's run is pinned by commit


def test_failed_thresholds_stay_failed_and_no_launch_is_cleared(idx):
    assert len(idx["assemblies"]) == 5
    for a in idx["assemblies"]:
        b = {x["id"]: x for x in a["budgets"]}
        assert b["legacy_threshold_10_5g"]["value_g"] == 10.5
        assert all(x["verdict"] == "fail" and x["compared_mass_g"] > x["value_g"] for x in a["budgets"])
        assert a["launch_status"]["status"] == "not_cleared"
        m = json.loads((ROOT / "artifacts/glider" / a["revision"] / "manifest.json").read_text())
        cap = m["trim_speed_hand"].get(PLI.CAP_KEY)
        if cap is not None:
            assert b["area_specific_8ms_cl05"]["value_g"] == pytest.approx(cap, rel=1e-6)
        assert a["dry"]["mass_g"] == pytest.approx(m["nominal_assembly"]["dry"]["mass_g"], rel=1e-6)
        assert {c["id"]: c["status"] for c in a["checks"]}["ballast_row_moment_balance"] == "pass"


def test_withdrawn_files_are_exactly_the_left_parts_filed_as_right(idx):
    defects = json.loads((ROOT / "artifacts/glider/KNOWN_DEFECTS.json").read_text())
    revs = set(defects["right_hand_print_files_are_left_parts"]["revisions"])
    for f in idx["files"]:
        right_fin = f["kind"] == "stl_part" and (f["part_id"] or "").split("-")[0].endswith("_R")
        assert bool(f["withdrawn"]) == (right_fin and f["revision"] in revs), f["path"]
        if right_fin:
            st = {c["id"]: c["status"] for c in f["checks"]}["chirality_mirror_pair"]
            assert st == ("fail" if f["revision"] in revs else "pass"), f["path"]


def test_findings_are_true_of_the_frozen_bytes(idx):
    ids = {f["id"] for f in idx["findings"]}
    assert {"right_hand_print_files_are_left_parts", "body_thin_wall_near_forward_catch_slot",
            "biological_constraints_kept_names_v3a", "assembly_md_cg_window_superseded"} <= ids
    for rev in ("r3-daane", "r4-daane-printfix"):             # the prose inconsistency is still there, unedited
        m = json.loads((ROOT / "artifacts/glider" / rev / "manifest.json").read_text())
        assert m["biological_constraints"]["kept"].startswith("v3a") and "v3c" in m["source_candidate"]["id"]
    assert "44" in (ROOT / "artifacts/glider/r4-daane-printfix/ASSEMBLY.md").read_text()


def test_frozen_revisions_and_the_bundle_are_unchanged():
    for rev, commit in FROZEN_AT.items():
        for rel in ("manifest.json", "flight_model.json"):
            p = f"artifacts/glider/{rev}/{rel}"
            try:
                old = subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{p}"], check=True,
                                     capture_output=True).stdout
            except subprocess.CalledProcessError:
                pytest.skip(f"{commit} not in this clone")
            assert (ROOT / p).read_bytes() == old, p
    z = "artifacts/glider/r4-daane-printfix/print-set-r4-daane-printfix.zip"
    old = subprocess.run(["git", "-C", str(ROOT), "show", f"bd2fcf3:{z}"], check=True, capture_output=True).stdout
    assert (ROOT / z).read_bytes() == old


def test_the_page_says_calculated_not_measured(idx):
    page = PLI.doc(idx)
    assert "measured" not in page.lower() and "not weighed" in page
