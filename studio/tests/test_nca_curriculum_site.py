import importlib.util
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def builder():
    spec = importlib.util.spec_from_file_location("nca_curriculum_site_builder", ROOT / "scripts/build_site.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gallery_retains_old_results_and_actual_curriculum_tradeoff():
    module = builder()
    output = {}
    cards = {x["id"]: x for x in module.nca_cards(module.Inputs(), output)}
    assert {"nca-pattern", "nca-seed-placement", "nca-curriculum"} <= cards.keys()
    card = cards["nca-curriculum"]
    assert "89/192" in card["title"] and card["video_state"] == "present_verified"
    text = str(card["numerical_checks"])
    assert "baseline 45/96, curriculum 44/96" in text
    assert "persistence" in text and "baseline 9/12; curriculum 3/12" in text
    assert "new left prefix 30" in text and "baseline 0/12; curriculum 9/12" in text
    assert sum(x["name"].startswith("paired initialization") for x in card["numerical_checks"]) == 4
    assert card["biological_success_probability"] is None
    assert "not this movie" in card["time"]["note"]
    assert "0 of 48" in cards["nca-pattern"]["title"] and "32 of 48" in cards["nca-seed-placement"]["title"]
    index = json.loads((ROOT / "artifacts/nca-curriculum/index.json").read_text())
    for source in card["sources"]:
        key = source["label"].replace(" ", "_")
        published = output["@" + source["href"]]
        assert hashlib.sha256(published).hexdigest() == index["artifacts"][key]["sha256"]
    assert json.loads(output["@" + card["manifest_href"]]) == index


def test_gallery_rejects_changed_audit_before_publishing_new_result():
    module = builder()
    inputs = module.Inputs()
    read = inputs.read

    def changed(path):
        raw = read(path)
        return raw + b" " if path == "artifacts/nca-curriculum/returned-analysis/audit.json" else raw

    inputs.read = changed
    with pytest.raises(ValueError, match="digest/size mismatch"):
        module.nca_cards(inputs, {})
