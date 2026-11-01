"""Synthetic transport events, never scientific outputs."""

import json

from frontier_compute.gcp_watch import watch


class Clock:
    now = 0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        assert seconds <= 60
        self.now += seconds


def test_unchanged_snapshot_is_not_downloaded_again_and_final_stops(tmp_path):
    clock = Clock()

    class Client:
        def list_objects(self, *_):
            return [{"name": "jobs/frontier-cpu-20261031-03/task/manifests/m.json",
                     "generation": "1" if clock.now < 600 else "2"}]

    calls = []

    def collector(*_):
        calls.append(clock.now)
        return {"complete": clock.now == 600, "receipt_path": "fixture.json", "artifacts": []}

    rc = watch(Client(), "bucket", "jobs/frontier-cpu-20261031-03/task", tmp_path,
               tmp_path / "watch.json", monotonic=clock.monotonic, sleep=clock.sleep,
               collector=collector, runtime_s=1000)
    assert rc == 0
    assert calls == [0, 600]
    assert json.loads((tmp_path / "watch.json").read_text())["complete_export"]


def test_transport_error_is_retained_and_deadline_does_not_claim_completion(tmp_path):
    clock = Clock()

    class Client:
        def list_objects(self, *_):
            raise RuntimeError("fixture unavailable")

    rc = watch(Client(), "bucket", "jobs/frontier-cpu-20261031-03/task", tmp_path,
               tmp_path / "watch.json", monotonic=clock.monotonic, sleep=clock.sleep,
               runtime_s=600)
    state = json.loads((tmp_path / "watch.json").read_text())
    assert rc == 2 and not state["complete_export"]
    assert len(state["events"]) == 2
    assert all(e["state"] == "collection_error" for e in state["events"])
