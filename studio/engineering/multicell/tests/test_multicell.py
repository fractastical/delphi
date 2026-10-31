import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze  # noqa: E402
import run_morpheus  # noqa: E402

HDR = '"t"\t"cell.id"\t"CDK1"\t"APC"\t"g_l"\t"d"\t"cell.volume"\n'


def test_division_events_are_unique_times(tmp_path):
    rows = [(0, 1), (0.1, 1), (0.2, 2), (0.2, 3), (0.3, 2), (0.3, 3)]
    (tmp_path / "logger.csv").write_text(HDR + "".join(f"{t}\t{c}\t0.3\t0\t0.1\t0\t100\n" for t, c in rows))
    a = analyze.load(tmp_path)
    assert a["division_event_times"] == [0.2] and a["n_final"] == 2
    assert analyze.count_at(a, 0.1) == 1


def _repo(tmp_path, xml):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    f = tmp_path / run_morpheus.XML_PATH
    f.parent.mkdir(parents=True)
    f.write_text(xml)
    env = ["-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), *env, "commit", "-qm", "x"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "tag", run_morpheus.TAG], check=True)


def test_stage_refuses_when_an_edit_does_not_match_once(tmp_path):
    _repo(tmp_path, "<MorpheusModel version=\"1\"/>")
    with pytest.raises(SystemExit, match="refused"):
        run_morpheus.stage(tmp_path, 0.6, 1, True)
