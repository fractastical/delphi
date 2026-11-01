import json
from pathlib import Path

import pytest

from engineering.observed_update.site import DIRECTORY, EXPECTED, build

ROOT = Path(__file__).resolve().parents[1]


class Inputs:
    def __init__(self, changed=None):
        self.changed = changed or {}
        self.seen = []

    def read(self, path):
        self.seen.append(path)
        return self.changed[path] if path in self.changed else (ROOT / path).read_bytes()


def test_card_publishes_all_pins_and_separates_observations_worsening_and_import():
    ins, out = Inputs(), {}
    card = build(ins, out)
    assert len(card["downloads"]) == 23 and len(out) == 25
    assert set("@" + DIRECTORY + "/" + name for name in EXPECTED) <= out.keys()
    assert card["facts"]["observed_rows"] == 109 and card["facts"]["new_measurements"] == 0
    error = card["facts"]["heldout_RMSE_log10"]
    assert error["heldout_before"] == pytest.approx(.0470889105916392)
    assert error["heldout_after"] > error["heldout_before"]
    assert card["facts"]["stale_cache_rejected"]
    assert card["facts"]["biological_success_probability"] is None
    assert card["poster_is_figure"] and card["video_href"] is None
    assert len(card["record_refs"]) == 6 and card["record_status"] == "imported_unreviewed; Action proposed"
    assert "component-purge-v2" in card["current_bundle_href"]
    assert "prepared-bundle-final" in card["historical_bundle_href"]
    assert "no independent biological validation" in card["model"]["context"]


def test_changed_artifact_is_refused_before_any_copy():
    path = DIRECTORY + "/source-observations.csv"
    out = {"sentinel": b"untouched"}
    with pytest.raises(ValueError, match="digest/size mismatch"):
        build(Inputs({path: (ROOT / path).read_bytes() + b"changed"}), out)
    assert out == {"sentinel": b"untouched"}


@pytest.mark.parametrize("mutation", ["escape", "duplicate", "href", "digest"])
def test_manifest_mutations_never_initiate_unlisted_reads(mutation):
    path = DIRECTORY + "/publication.json"
    manifest = json.loads((ROOT / path).read_text())
    row = manifest["files"][0]
    if mutation == "escape":
        row["path"] = DIRECTORY + "/../../secret"
    elif mutation == "duplicate":
        manifest["files"][0] = manifest["files"][1]
    elif mutation == "href":
        row["href"] = "https://example.com/external"
    else:
        row["sha256"] = "0" * 64
    ins, out = Inputs({path: json.dumps(manifest).encode()}), {}
    with pytest.raises(ValueError):
        build(ins, out)
    assert ins.seen == [path] and out == {}


def test_changed_import_receipt_is_refused_before_copy():
    path = DIRECTORY + "/live-import/public-receipt.json"
    receipt = json.loads((ROOT / path).read_text())
    receipt["inserted_total"] = 7
    out = {}
    with pytest.raises(ValueError, match="receipt digest changed"):
        build(Inputs({path: json.dumps(receipt).encode()}), out)
    assert out == {}
