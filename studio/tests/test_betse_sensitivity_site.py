from pathlib import Path
from hashlib import sha256

import pytest

from engineering.bioelectric_tissue.sensitivity_site import DIRECTORY, build_card
from scripts.build_site import Inputs, engineering_cards


ROOT = Path(__file__).resolve().parents[1]


def test_betse_sensitivity_card_preserves_run_and_reconstruction_provenance():
    copied = []

    def publish(name, digest):
        copied.append((name, digest))
        return "present_verified", f"artifacts/simulations/betse-k-sensitivity-v1/{name}"

    card = build_card(lambda path: (ROOT / path).read_bytes(), publish)

    assert copied[:2] == [
        ("reconstructed/sensitivity.mp4", sha256((ROOT / f"{DIRECTORY}/reconstructed/sensitivity.mp4").read_bytes()).hexdigest()),
        ("reconstructed/sensitivity-poster.png", sha256((ROOT / f"{DIRECTORY}/reconstructed/sensitivity-poster.png").read_bytes()).hexdigest()),
    ]
    assert len(copied) == 6
    for rel, digest in copied:
        assert sha256((ROOT / DIRECTORY / rel).read_bytes()).hexdigest() == digest
    assert len([s for s in card["sources"] if s.get("href")]) == 3
    assert card["id"] == "betse-k-sensitivity-v1"
    assert "8/8 simulation exit codes 0" in card["numerical_checks"][0]["result"]
    assert "10× open-junction only" in card["numerical_checks"][3]["result"]
    assert "not an empirical error bound" in card["numerical_checks"][3]["result"]
    assert "worker's separate render failed" in card["video"]["note"]
    assert "not calibrated" in card["parameter_unknowns"][0]
    assert any("tissue voltage map to a fin growth law" in q for q in card["open_questions"])
    assert card["manifest"] == f"{DIRECTORY}/index.json"


def test_betse_sensitivity_card_refuses_changed_worker_array_before_media_copy():
    def raw_reader(path):
        return (ROOT / path).read_bytes()

    changed_path = f"{DIRECTORY}/worker-return/trajectories/k10_open.npz"

    def read(path):
        raw = raw_reader(path)
        return raw + b"tamper" if path == changed_path else raw

    with pytest.raises(ValueError, match="digest/size mismatch"):
        build_card(read, lambda *_: pytest.fail("Do not publish unverified media"))


def test_engineering_gallery_keeps_existing_betse_card_and_adds_sensitivity_card():
    cards = engineering_cards(Inputs(), {})
    ids = [card["id"] for card in cards]

    assert ids.count("betse-tissue") == 1
    assert ids.count("betse-k-sensitivity-v1") == 1
    card = next(item for item in cards if item["id"] == "betse-k-sensitivity-v1")
    assert card["video_state"] == "present_verified"
    assert "No such bridge" in " ".join(card["open_questions"])
