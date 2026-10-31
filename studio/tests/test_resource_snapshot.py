from datetime import datetime, timezone
import json
import pytest

from frontier_compute.resource_snapshot import ownership_class, summarize, summarize_shared, telemetry_summary


def test_allocation_counts_include_bioservices_without_leaking_specs():
    jobs = {"items": [
        {"metadata": {"id": "ours", "name": "bioservices-assay"},
         "status": {"state": "IMAGE_PULLING"},
         "spec": {"preset": "1gpu-16vcpu-200gb", "environment_variables": {"token": "secret"}}},
        {"metadata": {"id": "done", "name": "delphi-evolve-ops-done"},
         "status": {"state": "COMPLETED"}},
        {"metadata": {"id": "foreign-private-id", "name": "foreign-private-name"},
         "status": {"state": "RUNNING"}},
    ]}
    result = summarize(jobs, datetime(2026, 10, 31, tzinfo=timezone.utc))
    assert result["own_job_count"] == 2
    assert result["active_allocations"]["gpus"] == 1
    assert result["active_allocations"]["running_instances"] == 0
    assert result["active_allocations"]["pulling_instances"] == 1
    assert result["shared_state_counts"]["RUNNING"] == 1
    assert result["current_gpu_utilization_pct"] is None
    encoded = json.dumps(result)
    assert "secret" not in encoded and "foreign-private" not in encoded


def test_unknown_capacity_is_not_invented():
    result = summarize({"items": [{"metadata": {"name": "delphi-evolve-ops-new"}}]},
                       datetime.now(timezone.utc))
    assert result["active_allocations"]["instances"] == 1
    assert result["active_allocations"]["gpus"] == 0
    assert result["active_jobs"][0]["requested_capacity"] == {}
    assert result["active_allocations"]["jobs_with_unknown_capacity"] == 1


def test_incomplete_provider_listing_is_refused():
    with pytest.raises(ValueError, match="paginated"):
        summarize({"items": [], "next_page_token": "more"}, datetime.now(timezone.utc))


def test_controller_counts_bioservices_but_does_not_claim_ownership():
    from frontier_compute.vendor.compute_ops.batch import Batch, W

    worker = W("bio-job", "bioservices-test", "job", "gpu-h100-sxm", "1gpu-16vcpu-200gb", "RUNNING")
    controller = Batch({"items": []})
    assert controller.ours_active_gpus([worker]) == 1
    assert controller.owned_ids() == {}


def test_telemetry_retains_zero_samples_and_original_window(tmp_path):
    path = tmp_path / "samples.csv"
    path.write_text("timestamp,utilization.gpu,memory.used,power.draw\n"
                    "2026/10/31 21:00:00.000,0,10,50\n"
                    "2026/10/31 21:00:01.000,100,20,400\n")
    result = telemetry_summary("fixture", path)
    assert result["samples"] == 2
    assert result["gpu_utilization_pct_mean"] == 50
    assert result["gpu_samples_ge90pct"] == 1
    assert result["window_utc"] == ["2026-10-31T21:00:00Z", "2026-10-31T21:00:01Z"]


def test_telemetry_refuses_unmeasured_values(tmp_path):
    path = tmp_path / "samples.csv"
    path.write_text("timestamp,utilization.gpu,memory.used,power.draw\n"
                    "2026/10/31 21:00:00.000,NaN,10,50\n")
    with pytest.raises(ValueError, match="invalid"):
        telemetry_summary("fixture", path)


def test_historical_attribution_is_exact_and_keeps_current_scope_separate():
    old = {"id": "old-owned", "name": "prior-scale"}
    jobs = {"items": [
        {"metadata": {**old, "created_at": "2026-10-30T20:00:00Z"}, "status": {"state": "COMPLETED"}},
        {"metadata": {"id": "current", "name": "delphi-evolve-ops-current", "created_at": "2026-10-31T20:00:00Z"}, "status": {"state": "RUNNING"}},
        {"metadata": {"id": "unattributed-private-id", "name": "prior-scale-similar", "created_at": "2026-10-31T20:00:00Z"}, "status": {"state": "RUNNING"}},
    ]}
    observed = datetime(2026, 10, 31, 23, tzinfo=timezone.utc)
    result = summarize(jobs, observed, [old])
    assert result["own_job_count"] == result["current_frontier_job_count"] == 1
    assert result["team_job_count"] == 2 and result["historical_team_job_count"] == 1
    assert result["unattributed_job_count"] == 1
    shared = summarize_shared(jobs, observed, [old])
    assert shared["ownership_breakdown"] == {"historical_team": 1, "current_frontier": 1, "unattributed": 1}
    assert sum(row["jobs"] for row in shared["counts"]["today"] if row["group"] == "ours") == 1
    assert "unattributed-private-id" not in json.dumps(shared)


def test_historical_identity_mismatch_refuses_attribution():
    with pytest.raises(ValueError, match="ID/name mismatch"):
        ownership_class({"metadata": {"id": "old", "name": "changed"}}, [{"id": "old", "name": "original"}])
