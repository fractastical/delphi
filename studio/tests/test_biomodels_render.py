"""The renderer draws only rows of receipt-verified replay CSVs, and its manifest matches the files it describes.

Needs /usr/bin/ffmpeg and matplotlib; no network. A short clip is rendered for structure and determinism;
the committed full-length video is checked by hash against its manifest.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("matplotlib")
from connectors.biomodels import render as rd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "connectors" / "biomodels"
RECEIPT_DIR = ROOT / "receipts" / "BIOMD0000001047"
VIDEO_DIR = ROOT / "video"
pytestmark = pytest.mark.skipif(not Path(rd.FFMPEG).exists(), reason="/usr/bin/ffmpeg not installed")


def test_tampered_csv_is_refused_before_anything_is_drawn(tmp_path):
    d = tmp_path / "r"
    shutil.copytree(RECEIPT_DIR, d)
    f = d / "trajectory_as_published.csv"
    lines = f.read_text().splitlines()
    lines[5] = lines[5].replace("e-", "e-0", 1) if "e-" in lines[5] else lines[5] + "0"
    f.write_text("\n".join(lines) + "\n")
    with pytest.raises(rd.RenderRefused, match="sha256"):
        rd.load(d)
    rd.load(RECEIPT_DIR)   # positive control: the untouched directory loads


def test_row_index_uses_only_existing_rows_in_order():
    n = 601
    rows = [rd.row_index(k, n) for k in range(rd.MOTION_FRAMES + rd.HOLD_FRAMES)]
    assert rows[0] == 0 and rows[rd.MOTION_FRAMES - 1] == n - 1 and rows[-1] == n - 1
    assert all(isinstance(r, int) and 0 <= r < n for r in rows) and rows == sorted(rows)
    assert set(rows[rd.MOTION_FRAMES - 1:]) == {n - 1}


def test_short_render_has_the_declared_structure_and_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "MOTION_FRAMES", 12)
    monkeypatch.setattr(rd, "HOLD_FRAMES", 4)
    a = rd.render(RECEIPT_DIR, tmp_path / "a", enforce_bounds=False)
    b = rd.render(RECEIPT_DIR, tmp_path / "b", enforce_bounds=False)
    assert a["render"]["frames_sha256"] == b["render"]["frames_sha256"], "the drawing must be deterministic"
    assert a["video"]["frames"] == 16 and (a["video"]["width"], a["video"]["height"]) == (1280, 720) and a["video"]["pix_fmt"] == "yuv420p"
    assert a["poster"]["width"] == 1280 and (tmp_path / "a" / "delta_notch_replay_poster.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    receipt = json.loads((RECEIPT_DIR / "receipt.json").read_text())
    assert {v["sha256"] for v in a["inputs"]["csv"].values()} == {receipt["output_sha256"][k] for k in a["inputs"]["csv"]}
    assert a["inputs"]["model_sha256"] == receipt["model"]["sha256"]
    assert a["time_mapping"]["interpolation"].startswith("none")


def test_a_different_dataset_changes_the_drawing(tmp_path, monkeypatch):
    """Negative control: frames_sha256 must depend on the data, or the determinism check proves nothing."""
    monkeypatch.setattr(rd, "MOTION_FRAMES", 12)
    monkeypatch.setattr(rd, "HOLD_FRAMES", 2)
    base = rd.render(RECEIPT_DIR, tmp_path / "a", enforce_bounds=False)["render"]["frames_sha256"]
    orig = rd.load

    def swapped(d):
        receipt, data = orig(d)
        data["as_published"], data["symmetric_baseline"] = data["symmetric_baseline"], data["as_published"]
        return receipt, data

    monkeypatch.setattr(rd, "load", swapped)
    assert rd.render(RECEIPT_DIR, tmp_path / "b", enforce_bounds=False)["render"]["frames_sha256"] != base


def test_committed_video_matches_its_manifest_and_makes_no_morphology_claim():
    man = json.loads((VIDEO_DIR / "delta_notch_replay_manifest.json").read_text())
    for rec in (man["video"], man["poster"]):
        p = VIDEO_DIR / rec["file"]
        assert rd.sha256_file(p) == rec["sha256"] and p.stat().st_size == rec["bytes"]
    assert 10 <= man["video"]["duration_s"] <= 20 and man["video"]["bytes"] < rd.MAX_VIDEO_BYTES
    assert rd.probe(VIDEO_DIR / man["video"]["file"])["frames"] == man["time_mapping"]["total_frames"]
    receipt = json.loads((RECEIPT_DIR / "receipt.json").read_text())
    for name, rec in man["inputs"]["csv"].items():
        assert rd.sha256_file(RECEIPT_DIR / name) == rec["sha256"] == receipt["output_sha256"][name]
    assert man["inputs"]["model_sha256"] == receipt["model"]["sha256"] and man["inputs"]["receipt_sha256"] == rd.sha256_file(RECEIPT_DIR / "receipt.json")
    assert man["render"]["code_sha256"] == rd.sha256_file(Path(rd.__file__)), "render.py changed since the video was made; re-render"
    text = json.dumps(man["claims"]).lower()
    for must in ("observed cell shape", "tissue", "a fin", "real time"):
        assert must in text
    assert "SIMULATION" in man["claims"]["captions"]["header"] and "not an observation" in man["claims"]["captions"]["footer"]
    assert "flying" not in json.dumps(man["claims"]["captions"]).lower()


def test_ffmpeg_decodes_the_committed_video_without_error():
    r = subprocess.run([rd.FFMPEG, "-v", "error", "-i", str(VIDEO_DIR / "delta_notch_replay.mp4"), "-f", "null", "-"], capture_output=True, text=True)
    assert r.returncode == 0 and r.stderr == ""


def test_manifest_obeys_the_published_schema_and_the_schema_rejects_known_violations():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((VIDEO_DIR / "delta_notch_replay_manifest.schema.json").read_text())
    man = json.loads((VIDEO_DIR / "delta_notch_replay_manifest.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    v = jsonschema.Draft202012Validator(schema)
    assert not list(v.iter_errors(man))
    def broken(edit):
        m = json.loads(json.dumps(man)); edit(m); return list(v.iter_errors(m))
    assert broken(lambda m: m["claims"]["does_not_show"].remove("a fin"))
    assert broken(lambda m: m["video"].update(sha256="xyz"))
    assert broken(lambda m: m["video"].update(duration_s=25.0))
    assert broken(lambda m: m["claims"]["captions"].update(footer="a pretty video"))
    assert broken(lambda m: m["inputs"]["csv"].pop(next(iter(m["inputs"]["csv"]))))
    assert broken(lambda m: m.update(extra="x"))
