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
    offered = {"@" + A.MANIFEST} | {"@" + x["path"] for c in r["visuals"] for x in c["media"].values()} | {"@" + d["href"] for c in r["visuals"] for d in c["downloads"]}
    assert set(out) == offered
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


def _epithelial():
    return next(v for v in json.loads((ROOT / A.MANIFEST).read_text())["visuals"] if v["study"] == "epithelial-repair")


def test_epithelial_entry_reports_the_files_own_gates_and_keeps_every_failure():
    v = _epithelial()
    g = v["summary"]["gates"]
    res = json.loads((ROOT / "artifacts/epithelial/results-r2.json").read_text())["gates"]
    assert g["total"] == len(res) == 13
    assert g["pass"] == sum(x["passed"] is True for x in res) and g["fail"] == sum(x["passed"] is False for x in res) == 3
    assert g["pass"] == 8 and g["descriptive"] == ["G6"] and g["unevaluable"] == ["G8"]      # G6 is descriptive, not a pass
    text = json.dumps(v)
    for needle in ("G4 fail", "G10 fail", "G12 fail", "G8 not_pass_fail", "not an observed point threshold", "not a physical law", "not supported in this model", "tested model hypothesis", "615.4", "21", "context-specific control"):
        assert needle in text
    pair = v["summary"]["pair"]
    assert pair["closes"]["state"] == "CLOSED" and pair["arrests"]["state"] == "ARRESTED"
    assert round(v["summary"]["passive_floor"]["closed_fraction"], 3) == 0.22
    assert "not minutes" in v["labels"]["time"] and v["labels"]["model_only"] is True
    assert {m["path"].rsplit("/", 1)[0] for k, m in v["media"].items() if k != "errata"} == {"artifacts/epithelial/media"}


def test_card_contract_keys_and_strict_text_downloads():
    cards = A.build(Ins(), {}, ROOT)["visuals"]
    for c in cards:
        assert {"id", "study", "title", "evidence_kind", "caveats", "records_kept", "video_href", "poster_href", "figure_href", "summary", "downloads"} <= set(c)
        assert all(d["href"].endswith(A.DOWNLOAD_SUFFIXES) for d in c["downloads"])
    ep = next(c for c in cards if c["study"] == "epithelial-repair")
    assert ep["video_href"].endswith("A1-baseline.mp4") and ep["video_arrest_href"].endswith("A2-motility-off.mp4") and ep["figure_href"] is None


def test_download_flag_on_non_text_and_wrong_source_prefix_are_refused():
    m = json.loads((ROOT / A.MANIFEST).read_text())
    p = "artifacts/reuse-study-visuals/bad.json"
    mm = json.loads(json.dumps(m))
    csv_src = next(s for s in mm["visuals"][0]["sources"] if s["path"].endswith("travelling-voxels.csv"))
    csv_src["download"] = True
    with pytest.raises(ValueError, match="download not allowed"):
        A.build(Ins({p: json.dumps(mm).encode()}), {}, ROOT, manifest_path=p)
    mm = json.loads(json.dumps(m))
    mm["visuals"][1]["sources"][0]["path"] = "artifacts/epithelial-repair/results.json"        # the old, wrong prefix
    with pytest.raises(ValueError, match="allowlist"):
        A.build(Ins({p: json.dumps(mm).encode()}), {}, ROOT, manifest_path=p)
    assert "artifacts/oxygen-diffusion-rule/" in A.SOURCE_PREFIXES


def test_card_errata_is_offered_beside_the_uncorrected_card():
    ep = next(c for c in A.build(Ins(), {}, ROOT)["visuals"] if c["study"] == "epithelial-repair")
    text = (ROOT / ep["errata_href"]).read_text()
    assert ep["errata_href"].endswith("epithelial-card-errata.md")
    assert "8 pass" in text and "625 nodes are filled" in text and "geometric mean" in text


def test_card_download_is_remapped_and_never_offered_without_errata():
    out = {}
    ep = next(c for c in A.build(Ins(), out, ROOT)["visuals"] if c["study"] == "epithelial-repair")
    card = next(d for d in ep["downloads"] if d["source_path"] == "docs/epithelial-repair-card.md")
    assert card["href"] == "artifacts/reuse-study-visuals/sources/epithelial-repair-card.md" and card["errata_required"] is True
    assert out["@" + card["href"]] == (ROOT / "docs/epithelial-repair-card.md").read_bytes() and "@docs/epithelial-repair-card.md" not in out
    m = json.loads((ROOT / A.MANIFEST).read_text())
    p = "artifacts/reuse-study-visuals/bad.json"
    mm = json.loads(json.dumps(m))
    del mm["visuals"][1]["media"]["errata"]
    with pytest.raises(ValueError, match="errata"):
        A.build(Ins({p: json.dumps(mm).encode()}), {}, ROOT, manifest_path=p)
    mm = json.loads(json.dumps(m))
    next(x for x in mm["visuals"][1]["sources"] if x["path"].endswith("epithelial-repair-card.md"))["site_path"] = "docs/elsewhere.md"
    with pytest.raises(ValueError, match="site path"):
        A.build(Ins({p: json.dumps(mm).encode()}), {}, ROOT, manifest_path=p)
