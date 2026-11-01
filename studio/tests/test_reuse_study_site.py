"""The reuse-study visual adapter verifies every hash before offering media, and the committed manifest is true to the files."""
import json
import sys
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import reuse_study_site as A  # noqa: E402


class Ins:
    def __init__(self, tamper=None):
        self.tamper, self.seen = tamper or {}, {}

    def read(self, rel):
        b = self.tamper[rel] if rel in self.tamper else (ROOT / rel).read_bytes()
        self.seen[rel] = sha256(b).hexdigest()
        return b

    def json(self, rel):
        return json.loads(self.read(rel))


def test_builds_and_offers_only_verified_media():
    out = {}
    r = A.build(Ins(), out, ROOT)
    v = r["visuals"][0]
    assert v["study"] == "tissue-microcarrier" and v["labels"]["model_only"] is True
    assert set(out) == {"@" + A.MANIFEST} | {"@" + x["path"] for x in v["media"].values()}
    assert v["sources_verified"] >= 17 and v["renderer_verified"] == 1
    assert sum(len(b) for b in out.values()) < A.MAX_MEDIA_BYTES


@pytest.mark.parametrize("target", ["artifacts/voxel-actuation/trajectory/travelling-voxels.csv", "engineering/reuse_visuals/render_voxel.py",
                                    "artifacts/reuse-study-visuals/tissue-microcarrier/poster.png"])
def test_any_changed_input_renderer_or_media_byte_refuses_and_adds_nothing(target):
    out = {}
    with pytest.raises(ValueError, match="mismatch"):
        A.build(Ins({target: (ROOT / target).read_bytes() + b"x"}), out, ROOT)
    assert out == {}


def test_manifest_digest_pin_and_path_allowlist(tmp_path):
    with pytest.raises(ValueError, match="manifest digest"):
        A.build(Ins(), {}, ROOT, expected_sha256="0" * 64)
    m = json.loads((ROOT / A.MANIFEST).read_text())
    for field, bad in (("sources", "docs/simulation-roadmap.md"), ("sources", "artifacts/voxel-actuation/../../README.md")):
        mm = json.loads(json.dumps(m))
        mm["visuals"][0][field][0]["path"] = bad
        p = "artifacts/reuse-study-visuals/bad.json"
        with pytest.raises(ValueError, match="allowlist"):
            A.build(Ins({p: json.dumps(mm).encode(), "artifacts/reuse-study-visuals/bad.json": json.dumps(mm).encode()}), {}, ROOT, manifest_path=p)
    mm = json.loads(json.dumps(m))
    mm["visuals"][0]["study"] = "flying-fish"
    with pytest.raises(ValueError, match="unknown study"):
        A.build(Ins({p: json.dumps(mm).encode()}), {}, ROOT, manifest_path=p)


def test_committed_manifest_keeps_failures_and_the_denominator_qualification():
    v = json.loads((ROOT / A.MANIFEST).read_text())["visuals"][0]
    text = json.dumps(v)
    assert "E zero-gravity control missed" in text and "did not converge" in text and "not a convergence proof" in text
    d = v["posthoc_denominators"]
    assert d["coarse"]["centre_span_mm"] == 40 and d["fine"]["centre_span_mm"] == 45 and d["coarse"]["outer_length_mm"] == d["fine"]["outer_length_mm"] == 50
    assert round(d["reported_ratio_difference_pct"], 2) == 2.73 and round(d["raw_si_difference_pct_of_coarse"], 2) == 15.57
    assert v["labels"]["envelope_mm"] == [50, 30, 30] and v["labels"]["assumed_mass_g"] == 45
    assert v["biological_carrier"]["status"].startswith("proposed") and v["engine_benchmark"]["gpu_required"] is False
    assert "orientations" in v["labels"]["csv_contents"]
