#!/usr/bin/env python3
"""Pin the selected, already-existing site captures and simulation clips."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_demo_cards import main as build_cards


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/demo-video-90"
SOURCE = OUT / "sources"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(rel: str, label: str, provenance: str, kind: str = "image") -> dict:
    path = ROOT / rel
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(rel)
    return {"path": rel, "sha256": sha256(path), "kind": kind, "label": label,
            "provenance": provenance}


def shot(duration: float, layout: str, sources: list[dict], badge: str = "") -> dict:
    result = {"duration_s": duration, "layout": layout, "sources": sources}
    if badge:
        result["badge"] = badge
    return result


def main() -> None:
    build_cards()
    story_path = OUT / "edit-storyboard.json"
    story = json.loads(story_path.read_text(encoding="utf-8"))
    cut = story["cuts"][0]
    scenes = {scene["id"]: scene for scene in cut["scenes"]}

    # Reuse each visual source only as a short, separately labeled cutaway.
    media = {
        "goal": {
            "badge": "Goal routes to existing questions and projects · no organism generated",
            "shots": [
                shot(4.5, "single", [source("artifacts/demo-video-90/sources/goal-interaction/goal-interaction.mp4",
                      "Live goal routing · recorded interaction", "Live read-only Home interaction; no Project, Annotation or Action write.", "video")]),
                shot(0.5, "single", [source("artifacts/demo-video-90/sources/goal-interaction/goal-routed-result.png",
                      "Existing Flying fish project · routed result", "Same read-only interaction; real returned project and open-work result.")]),
            ],
        },
        "commons": {
            "badge": "Claim + source + context + evidence · imported claims are not automatically true",
            "shots": [
                shot(7.0, "single", [source("artifacts/demo-video-90/sources/captures/07z-claim-equations-zoom.png",
                      "Claim detail · equation, context and source", "Captured Knowledge claim view; release dc57df01cf266cbf91514bf20cd5e0b8757b5759.")]),
                shot(8.0, "single", [source("artifacts/demo-video-90/sources/captures/08-knowledge-graph.png",
                      "Evidence and requirement graph", "Captured live Knowledge graph; exact source capture manifest is pinned.")]),
            ],
        },
        "human_control": {
            "badge": "Choose parameters · inspect equations · challenge exact versions · plan a test",
            "shots": [
                shot(2.5, "single", [source("artifacts/demo-video-90/sources/captures/04-studio-scale-navigation.png",
                      "Studio scale navigation", "Captured Studio navigation across the represented model scales.")]),
                shot(3.0, "single", [source("artifacts/demo-video-90/sources/captures/21z-experimentation-plan-zoom.png",
                      "Prospective experiment planner · assumed costs", "Prospective Bayesian design under explicit assumed prior and noise; not measured biology.")]),
                shot(2.5, "single", [source("artifacts/demo-video-90/sources/captures/05-studio-project-design-review.png",
                      "Exact-version project challenges", "Captured Project design review; discussions remain attached to exact versions.")]),
            ],
        },
        "swarm": {
            "headline": "Specialists, reviewers and a shared frontier",
            "shots": [
                shot(7.0, "single", [source("artifacts/demo-video-90/sources/captures/27-system-overview.png",
                      "11 contributing harnesses · supported minimum · agent-contributors.json · 8:09pm PDT",
                      "Separate harness identity class; ledger observed 2026-10-31 8:09pm PDT; exact ledger SHA is in source-index.json.")],
                     "11 contributing harnesses · supported minimum · 8:09pm PDT"),
                shot(6.0, "single", [source("artifacts/demo-video-90/sources/media/r4-assembled.png",
                      "3 native collaborators · agent-contributors.json · 8:09pm PDT",
                      "Separate native identity class; root-attested disjointness; 3 native collaborators in the contributor ledger.")],
                     "3 native collaborators · separate identity class · 8:09pm PDT"),
            ],
        },
        "validation": {
            "badge": "Lean checks model algebra only · the matched-budget comparison tied at 16/16",
            "shots": [
                shot(6.0, "single", [source("artifacts/demo-video-90/sources/cards/lean-check-summary.png",
                      "Lean receipt · positive theorem and corrupt-law mutant", "Derived card from the tracked Lean receipt; theorem scope is stated algebra only.")]),
                shot(6.0, "single", [source("artifacts/demo-video-90/sources/cards/capability-agency-tie-summary.png",
                      "Single-agent vs collective benchmark · 16/16 each", "Derived card from 27 valid v3 responses; ceiling result, no collective advantage established.")]),
            ],
        },
        "scales": {
            "badge": "Separate bounded models · no molecular-to-organism validation or parameter transfer",
            "shots": [
                shot(3.0, "single", [source("artifacts/demo-video-90/sources/captures/11-blueprints-sources.png",
                      "Genomic archive sources · retrieved inputs", "Captured curated genome archive view; 23 assemblies are retrieval inputs, not functional validation.")]),
                shot(11.0, "grid-4", [
                    source("artifacts/demo-video-90/sources/simulations/openmm-collagen-fragment.mp4",
                           "OpenMM · collagen fragment · simulated", "CUDA OpenMM trajectory from a collagen-like experimental fragment; not native fish collagen.", "video"),
                    source("artifacts/demo-video-90/sources/betse-k-sensitivity-v1/reconstructed/sensitivity.mp4",
                           "BETSE · generic patch · not calibrated", "Eight returned dimensionless Dm_K sensitivity trajectories; generic patch, not fin calibrated.", "video"),
                    source("artifacts/demo-video-90/sources/simulations/aeroelastic-coupled-states.mp4",
                           "Fin aeroelasticity · model study", "Separate computational fin-mechanics response; no cellular or molecular calibration.", "video"),
                    source("artifacts/demo-video-90/sources/simulations/schooling-encoded-rules.mp4",
                           "Schooling · encoded rules only", "Saved ecology model playback under encoded interaction rules; not organism validation.", "video"),
                ]),
            ],
        },
        "ecosystem": {
            "badge": "Used providers/models are receipt-pinned · future integrations are labeled separately",
            "shots": [
                shot(6.0, "single", [source("artifacts/demo-video-90/sources/captures/13-system-provider-outcomes.png",
                      "USED · Nebius H100, Google Cloud CPU/L4, Gemini, Evo2, upstream OpenFold2", "Named provider and model receipts; OpenFold2 operation is upstream source, not NVIDIA NIM.")],
                     "USED: Nebius H100 · Google Cloud · Gemini · Evo2 scoring · upstream OpenFold2 · local OpenResearch"),
                shot(6.0, "single", [source("artifacts/demo-video-90/sources/captures/14-system-receipts.png",
                      "FUTURE · NVIDIA BioNeMo/NIM and Brev", "Integration opportunities only; BioNeMo/NIM runtime is not established.")],
                     "FUTURE INTEGRATIONS: NVIDIA BioNeMo/NIM and Brev · execution not established"),
            ],
        },
        "close": {
            "badge": "Computational designs and explicit unknowns · frontier.morphoswarm.ai",
            "shots": [
                shot(5.0, "single", [source("artifacts/demo-video-90/sources/captures/08-knowledge-graph.png",
                      "Versioned evidence commons", "Captured graph links claims, evidence and requirements; these do not by themselves validate an organism.")]),
                shot(6.0, "single", [source("artifacts/demo-video-90/sources/media/clip-home-mesh-orbit-partial.mp4",
                      "Candidate mesh · actual captured orbit", "Live Home WebGL mesh orbit capture; not a fabricated simulation frame.", "video")]),
            ],
        },
    }

    for scene_id, scene in scenes.items():
        entry = media[scene_id]
        source_total = sum(float(item["duration_s"]) for item in entry["shots"])
        if source_total <= 0:
            raise ValueError(f"media shots have no source duration for {scene_id}")
        elapsed = 0.0
        for index, item in enumerate(entry["shots"]):
            duration = (float(scene["duration_s"]) - elapsed if index == len(entry["shots"]) - 1
                        else float(scene["duration_s"]) * float(item["duration_s"]) / source_total)
            item["duration_s"] = duration
            elapsed += duration
        entry["headline"] = entry.get("headline", scene["headline"])

    capture_manifest = OUT / "sources/source-index.json"
    source_index = json.loads(capture_manifest.read_text(encoding="utf-8"))
    indexed_paths = {row["path"] for row in source_index["files"]}
    for scene_spec in media.values():
        for shot_spec in scene_spec["shots"]:
            for source_spec in shot_spec["sources"]:
                rel = source_spec["path"]
                if rel in indexed_paths:
                    continue
                path = ROOT / rel
                source_index["files"].append({"path": rel, "sha256": sha256(path), "bytes": path.stat().st_size,
                                              "origin_path": source_spec["provenance"],
                                              "origin_commit": None,
                                              "note": "Derived visual is pinned by its source inputs in the card provenance record."})
                indexed_paths.add(rel)
    source_index["editable_storyboard"] = {
        "path": story_path.relative_to(ROOT).as_posix(), "sha256": sha256(story_path),
        "audio_source_storyboard_path": story["audio_source_storyboard_path"],
        "audio_source_storyboard_sha256": story["audio_source_storyboard_sha256"],
    }
    source_index["tts_source_manifest"] = {
        "path": "artifacts/demo-video-90/tts-manifest.json",
        "sha256": sha256(ROOT / "artifacts/demo-video-90/tts-manifest.json"),
        "provider_requests": json.loads((OUT / "tts-manifest.json").read_text(encoding="utf-8")).get("provider_requests_this_run"),
    }
    source_index["editorial_audio_manifest"] = {
        "path": "artifacts/demo-video-90/tts-manifest-edited.json",
        "sha256": sha256(OUT / "tts-manifest-edited.json"),
        "tempo": json.loads((OUT / "tts-manifest-edited.json").read_text(encoding="utf-8"))["audio_postprocessing"]["tempo"],
    }
    capture_manifest.write_text(json.dumps(source_index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    capture_sha = sha256(capture_manifest)
    output = {
        "schema": "frontier.demo-video.media-map/1",
        "storyboard_commit": "cda661cd0036aa072a25069b32625dd57e9c2b45",
        "site_release_sha": source_index["site_release_sha"],
        "capture_manifest_path": capture_manifest.relative_to(ROOT).as_posix(),
        "capture_manifest_sha256": capture_sha,
        "source_capture_release_shas": [row["origin_release_sha"] for row in source_index["source_capture_sets"] if row.get("origin_release_sha")],
        "cuts": {cut["id"]: media},
    }
    path = OUT / "media-map.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path), "scenes": len(media)}, sort_keys=True))


if __name__ == "__main__":
    main()
