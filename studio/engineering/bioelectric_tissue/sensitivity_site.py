"""Read-only gallery adapter for the recovered BETSE K+ sensitivity run.

The worker's eight trajectories and failed render receipt are kept verbatim.
The gallery movie and poster are a local reconstruction from those saved
states; this adapter verifies the local and worker-returned hashes before
publishing either media file.
"""
from __future__ import annotations

from hashlib import sha256
import json
import posixpath


DIRECTORY = "artifacts/bioelectric-tissue/sensitivity-v1"
CONDITIONS = (
    "baseline",
    "k2_open",
    "k2_blocked",
    "k5_open",
    "k5_blocked",
    "k10_open",
    "k10_blocked",
    "k10_open_half_dt",
)


def build_card(read, publish_media):
    """Validate the pinned run bundle and return its simulation card."""
    index = json.loads(read(f"{DIRECTORY}/index.json"))
    if index.get("schema") != "frontier.betse-k-sensitivity.artifact/1":
        raise ValueError("Unsupported BETSE sensitivity artifact schema")
    if index.get("status") != "complete_with_local_render_recovery":
        raise ValueError("BETSE sensitivity artifact is not a complete recovered run")

    pins = {}
    for item in index.get("files", []):
        rel = item.get("path", "")
        if not rel or rel.startswith("/") or ".." in rel.split("/") or posixpath.normpath(rel) != rel:
            raise ValueError("Unsafe BETSE sensitivity artifact path")
        if rel in pins:
            raise ValueError(f"Duplicate BETSE sensitivity artifact pin: {rel}")
        pins[rel] = item
    if not pins:
        raise ValueError("BETSE sensitivity artifact has no pinned files")

    verified = {}
    for rel, item in pins.items():
        raw = read(f"{DIRECTORY}/{rel}")
        if len(raw) != item.get("bytes") or sha256(raw).hexdigest() != item.get("sha256"):
            raise ValueError(f"BETSE sensitivity digest/size mismatch: {rel}")
        verified[rel] = raw

    def pinned_json(rel):
        if rel not in verified:
            raise ValueError(f"Unpinned BETSE sensitivity input: {rel}")
        return json.loads(verified[rel])

    worker_prefix = "worker-return/"
    worker_receipt = pinned_json("worker-return/collection_receipt.json")
    dispatch = pinned_json("worker-return/dispatch.json")
    protocol = pinned_json("worker-return/protocol.json")
    completion = pinned_json("worker-return/completion.json")
    status = pinned_json("worker-return/snapshot-status.json")
    summary = pinned_json("reconstructed/summary.json")
    local_render = summary["local_render"]

    renderer = index["local_reconstruction"]["renderer"]
    if sha256(read(renderer)).hexdigest() != index["local_reconstruction"]["renderer_sha256"]:
        raise ValueError("Local reconstruction renderer hash mismatch")
    archive_path = index.get("source_archive_path")
    if not archive_path or sha256(read(archive_path)).hexdigest() != index.get("source_archive_sha256"):
        raise ValueError("Pinned worker source archive hash mismatch")

    if not worker_receipt.get("complete"):
        raise ValueError("Worker artifact collection is not marked complete")
    if worker_receipt.get("manifest_sha256") != summary.get("returned_collection_manifest_sha256"):
        raise ValueError("Worker collection manifest pin differs from reconstructed summary")
    if worker_receipt.get("manifest_sha256") != index.get("worker_collection_manifest_sha256"):
        raise ValueError("Worker collection manifest pin differs from artifact index")
    if dispatch.get("spec", {}).get("task_id") != "betse-k-sensitivity-v1":
        raise ValueError("Unexpected BETSE task id")
    if dispatch.get("spec", {}).get("source_sha256") != summary.get("source_archive_sha256"):
        raise ValueError("Source archive hash differs from dispatch")
    if dispatch.get("spec", {}).get("source_commit") != summary.get("source_commit"):
        raise ValueError("Source commit differs from dispatch")
    if completion.get("exit_code") != 1 or status.get("exit_code") != 1:
        raise ValueError("Expected original worker render failure receipt is missing")
    if "libx264" not in summary.get("render_failure", "") or not summary.get("rendered_locally_from_saved_states"):
        raise ValueError("Expected local reconstruction after worker render failure is missing")

    worker_files = {x["path"]: x for x in worker_receipt.get("artifacts", [])}
    for rel, item in worker_files.items():
        local_rel = f"{worker_prefix}{rel}"
        if local_rel not in pins:
            raise ValueError(f"Worker-return file missing from canonical bundle: {rel}")
        pin = pins[local_rel]
        if pin["sha256"] != item["sha256"] or pin["bytes"] != item["bytes"]:
            raise ValueError(f"Worker-return receipt mismatch: {rel}")

    # Original, partial, and reconstructed arrays must all preserve each
    # completed worker trajectory byte-for-byte. The renderer reads only the
    # reconstructed copy, which itself is pinned to the returned copy.
    if tuple(protocol.get("conditions", [{}])[i].get("id") for i in range(len(protocol.get("conditions", [])))) != CONDITIONS:
        raise ValueError("Sensitivity condition order/identity differs from frozen protocol")
    if set(summary.get("simulation_exit_codes", {})) != set(CONDITIONS):
        raise ValueError("Simulation result does not contain all eight frozen conditions")
    if any(value != 0 for value in summary["simulation_exit_codes"].values()):
        raise ValueError("One or more BETSE simulations failed")
    if not summary.get("numerical_checks", {}).get("all_eight_progress_completed"):
        raise ValueError("Worker progress did not confirm all eight conditions completed")
    if not summary.get("numerical_checks", {}).get("saved_vs_partial_arrays_identical"):
        raise ValueError("Saved and partial worker arrays were not recorded identical")

    for case in CONDITIONS:
        name = summary["files"][case]["trajectory"].replace("\\", "/")
        digest = summary["files"][case]["trajectory_sha256"]
        worker_path = f"worker-return/{name}"
        partial_path = f"worker-return/partial/{case}.npz"
        reconstructed_path = f"reconstructed/{name}"
        for rel in (worker_path, partial_path, reconstructed_path):
            if rel not in pins or pins[rel]["sha256"] != digest:
                raise ValueError(f"Trajectory pin mismatch for {case}: {rel}")

    render_check = summary["numerical_checks"].get("half_step_comparison", {})
    if render_check.get("coarse_dt_s") != 0.001 or render_check.get("fine_dt_s") != 0.0005:
        raise ValueError("Expected single-condition timestep check is missing")
    if "one simulated condition only" not in render_check.get("note", ""):
        raise ValueError("Timestep check scope is not explicit")

    video_name = "reconstructed/sensitivity.mp4"
    poster_name = "reconstructed/sensitivity-poster.png"
    video_sha = local_render["video"]["sha256"]
    poster_sha = local_render["poster"]["sha256"]
    for name, digest in ((video_name, video_sha), (poster_name, poster_sha)):
        if name not in pins or pins[name]["sha256"] != digest:
            raise ValueError(f"Local reconstructed media hash mismatch: {name}")
    if worker_files.get("sensitivity.mp4", {}).get("bytes") != 0:
        raise ValueError("Worker render failure should be preserved as a zero-byte output")

    state, video_href = publish_media("sensitivity.mp4", video_sha)
    poster_state, poster_href = publish_media("sensitivity-poster.png", poster_sha)
    k_open = summary["effects_vs_same_packet_baseline"]
    half_dt = render_check
    return {
        "id": "betse-k-sensitivity-v1",
        "title": "BETSE potassium-permeability sensitivity with gap-junction controls",
        "scales": ["cellular", "tissue"],
        "evidence_kind": "SimulationResult; eight completed numerical conditions, with local media reconstructed from returned states",
        "model": {
            "name": "BETSE 1.5.0 electrodiffusion on one generic 2-D hexagonal patch",
            "context": f"One shared initialized world; {summary['cells']} cells and {summary['membranes']} membranes. Seven baseline/permeability/junction conditions plus one half-step numerical check; {summary['frames_per_run']} saved states per condition. Dm_K multipliers are dimensionless sensitivity settings, not estimates for a channel.",
        },
        "time": {
            "units": "seconds of model time",
            "note": "Each run covers 4 s after the shared initialization and is sampled every 0.1 s. The half-step check compares the 10× open-junction condition only.",
        },
        "video": {
            "file": "sensitivity.mp4",
            "sha256": video_sha,
            "note": "Reconstructed locally from the eight returned trajectory arrays after the worker's separate render failed; not a new simulation.",
        },
        "video_state": state,
        "video_href": video_href,
        "poster_href": poster_href if poster_state == "present_verified" else None,
        "poster_is_figure": True,
        "numerical_checks": [
            {"name": "Worker run completion", "result": "8/8 simulation exit codes 0; each returned trajectory matches its partial checkpoint by SHA-256"},
            {"name": "Open-junction K+ permeability ×2, ×5, ×10", "result": "; ".join(f"×{m}: targeted peak ΔVm {k_open[f'k{m}_open']['targeted_peak_dVm_mV']:.2f} mV, untargeted {k_open[f'k{m}_open']['other_peak_dVm_mV']:.2f} mV" for m in (2, 5, 10))},
            {"name": "Gap-junction blocked arms", "result": "; ".join(f"×{m}: targeted peak ΔVm {k_open[f'k{m}_blocked']['targeted_peak_dVm_mV']:.2f} mV, untargeted {k_open[f'k{m}_blocked']['other_peak_dVm_mV']:.2f} mV" for m in (2, 5, 10))},
            {"name": "Single-condition timestep check", "result": f"10× open-junction only; dt {half_dt['coarse_dt_s']:g} vs {half_dt['fine_dt_s']:g} s: max |ΔVm| {half_dt['max_abs_delta_Vm_mV']:.5f} mV and max |Δconcentration| {half_dt['max_abs_delta_concentration_mmol_L']:.3g} mmol/L; not an empirical error bound"},
            {"name": "Worker rendering", "result": f"FAILED separately (exit {summary['render_process_exit_code']}): {summary['render_failure']} Local saved-state reconstruction produced the gallery media."},
        ],
        "parameter_unknowns": [
            "Dm_K multipliers are generic BETSE controls and are not calibrated to a channel; no Kcnj13/Kir2.1 abundance, gating or measured conductance is parameterized.",
            "One generated world and one run per condition; no biological replicates.",
            "No fish or fin calibration; no tissue-voltage-to-growth mapping is fitted or implied.",
        ],
        "open_questions": [
            "Which measured cell-type voltage and permeability data would calibrate this patch? See artifacts/bioelectric-tissue/model_interface.json.",
            "How would tissue voltage map to a fin growth law? No such bridge is implemented; see artifacts/bioelectric-tissue/model_interface.json and docs/bioelectric-tissue.md.",
        ],
        "equations": [],
        "sources": [
            {"label": "Frozen BETSE sensitivity protocol", "locator": f"{DIRECTORY}/worker-return/protocol.json; SHA-256 {pins['worker-return/protocol.json']['sha256']}"},
            {"label": "Provider return and render-failure receipt", "locator": f"{DIRECTORY}/worker-return/collection_receipt.json; GCS manifest SHA-256 {worker_receipt['manifest_sha256']}"},
            {"label": "Related bioelectric model interface", "locator": "artifacts/bioelectric-tissue/model_interface.json; measured voltage/permeability and tissue-voltage-to-growth mappings remain unknown"},
        ],
        "limitations": [
            "Generic simulated patch only; no measurement, fish calibration, fin model, channel identification or biological validation.",
            "The worker's renderer failed after all eight simulations succeeded. The displayed video and poster are local reconstructions from the returned arrays.",
            "The timestep check covers only the 10× open-junction case; it is not a general solver-error bound.",
        ],
        "couplings": [],
        "manifest": f"{DIRECTORY}/index.json",
        "native": True,
        "artifacts": [
            {"path": f"{DIRECTORY}/{rel}", "sha256": pins[rel]["sha256"], "bytes": pins[rel]["bytes"]}
            for rel in (
                "worker-return/protocol.json",
                "worker-return/collection_receipt.json",
                "worker-return/completion.json",
                "reconstructed/summary.json",
                "reconstructed/sensitivity.mp4",
                "reconstructed/sensitivity-poster.png",
                *[f"worker-return/trajectories/{case}.npz" for case in CONDITIONS],
            )
        ],
    }
