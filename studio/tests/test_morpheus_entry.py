from pathlib import Path

import pytest

from frontier_compute.morpheus_entry import last_logged_time


def test_actual_logger_with_trailing_blank_lines():
    root = Path(__file__).resolve().parents[1]
    log = root / "results/infra/morpheus/results/infra16-morpheus-full-horizon/parts/00-morpheus-three-arms/baseline/logger.csv"
    assert last_logged_time(log) == 2.0


@pytest.mark.parametrize("content", ['', '"t"\t"cell.id"\n\n'])
def test_empty_logger_is_not_a_finished_horizon(tmp_path, content):
    path = tmp_path / "logger.csv"
    path.write_text(content)
    assert last_logged_time(path) is None


def test_nonfinite_time_rejected(tmp_path):
    path = tmp_path / "logger.csv"
    path.write_text('"t"\t"cell.id"\nNaN\t1\n\n')
    with pytest.raises(ValueError, match="Nonfinite"):
        last_logged_time(path)
