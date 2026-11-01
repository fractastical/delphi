from pathlib import Path

import pytest

from engineering.fin_ray.site import build_card

ROOT = Path(__file__).resolve().parents[1]


def test_card_uses_actual_pinned_figure_and_keeps_scientific_limits():
    copied = []

    def media(name, sha):
        copied.append((name, sha))
        return "present_verified", "artifacts/simulations/fin-ray-bilaminar/" + name

    card = build_card(lambda path: (ROOT / path).read_bytes(), media)
    assert len(copied) == 1 and len(copied[0][1]) == 64
    assert "24/24 same-equation numerical comparisons" in card["model"]["context"]
    assert "no measured flying-fish material or whole-fin validation" in card["model"]["context"]
    assert card["poster_is_figure"] and card["video_href"] is None
    assert "UNRESOLVED" in card["numerical_checks"][2]["result"]
    assert "G=200 is not 200 Pa" in card["parameter_unknowns"][0]
    assert card["coupling_ports"]["input"][0] == "base_slide_over_L"


def test_card_refuses_changed_media_before_copy():
    def read(path):
        raw = (ROOT / path).read_bytes()
        return raw + b"mutation" if path.endswith("ray-response.png") else raw

    with pytest.raises(ValueError, match="digest/size mismatch"):
        build_card(read, lambda *_: pytest.fail("Changed media must not be published"))


def test_card_never_claims_published_media_when_copy_failed():
    card = build_card(lambda path: (ROOT / path).read_bytes(), lambda *_: ("declared_but_missing", None))
    assert card["poster_href"] is None and card["poster_state"] == "declared_but_missing"
