"""Freeze the machine-readable publication bundle for the 240-arm fixed-horizon challenge.

Collects, with hashes, in one file: the source pins, the frozen criterion and the native FAIL
exactly as returned, the raw return's own manifest SHA, the independent audit, the figure
files, and the review references. Nothing here recomputes a verdict or edits a native field;
it records what exists so a reader can re-derive any of it.

Root owns the site. This writes only numerical source, artifacts and the card's companions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_FILES = ("engineering/epithelial/build_model.py", "engineering/epithelial/protocol.py",
              "engineering/epithelial/run_arms.py", "engineering/epithelial/analyze.py",
              "engineering/epithelial/audit_return.py", "engineering/epithelial/check_card.py",
              "engineering/epithelial/plot_brackets.py", "engineering/epithelial/make_packet.py",
              "engineering/epithelial/packet_files/run_packet.sh",
              "engineering/epithelial/packet_files/analyze_sweep.py",
              "engineering/epithelial/packet_files/audit_completeness.py",
              "engineering/epithelial/packet_files/verify_packet.py",
              "artifacts/epithelial/protocol.json", "artifacts/epithelial/protocol-r2.json",
              "artifacts/epithelial/results.json", "artifacts/epithelial/results-r2.json",
              "artifacts/epithelial/sweep-audit.json",
              "artifacts/epithelial/packet/epithelial-sweep-packet.tgz",
              "docs/epithelial-repair-card.md")
FIGS = ("artifacts/epithelial/figures/threshold-brackets-light.png",
        "artifacts/epithelial/figures/threshold-brackets-light.svg",
        "artifacts/epithelial/figures/threshold-brackets-dark.png",
        "artifacts/epithelial/figures/threshold-brackets-dark.svg")
MEDIA = ("artifacts/epithelial/media/A1-baseline.mp4",
         "artifacts/epithelial/media/A1-baseline_poster.png",
         "artifacts/epithelial/media/A2-motility-off.mp4",
         "artifacts/epithelial/media/A2-motility-off_poster.png")


def h(p: Path) -> dict:
    b = p.read_bytes()
    return dict(sha256=hashlib.sha256(b).hexdigest(), bytes=len(b))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--return-dir", required=True)
    ap.add_argument("--native-runs", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    R, RET = Path(a.repo), Path(a.return_dir)
    audit = json.loads((R / "artifacts/epithelial/sweep-audit.json").read_text())
    native = json.loads((RET / "science/j-scaling-report.json").read_text())

    bundle = dict(
        schema="frontier.epithelial-publication-bundle.v1",
        frozen_at_commit=a.commit,
        branch="work/epithelial-repair",
        base="origin/codex/frontier-demo-20261031 at 25370ab",
        scope="Additive publication packet for the 240-arm fixed-horizon challenge. The local "
              "36-run videos and the local G9 result are preserved and not superseded.",
        ownership=dict(
            mine="numerical source, artifacts and docs/epithelial-repair-card.md",
            not_mine=["scripts/reuse_study_site.py", "site/js/reuse-studies.js",
                      "site tests — root owns the UI and these were not edited"]),

        native_result=dict(
            note="READ exactly as returned. No native field or criterion was changed.",
            verdict=native["verdict"],
            criterion=native["criterion"],
            per_gap=native["per_gap"], counts=native["counts"],
            completeness=json.loads((RET / "science/completeness.json").read_text())["complete"],
            runner_exit=0, analyzer_exit=1),

        raw_return=dict(
            path=str(RET),
            files=971, bytes=97404808,
            manifest_sha256="39f32c4d97c86aecab6e1dd02b3147cca8d029652ba2380adf99a10d06e116f7",
            rehashed_by="infra on sb02 after collection, every size/SHA matched; and "
                        "independently by the native reviewer (all 971 file pins)",
            service=dict(finished_utc="2026-11-01T06:48:19Z", wall_s=346.040, cpu_s=2627.156,
                         host="owned 8 vCPU VM02", start_pdt="2026-10-31 23:41:51",
                         operation="operation-1793515311260-65f315306e508-9bfa6bf9-e56f22cd"),
            spatial_states=0,
            movie_possible=False,
            movie_note="the packet deletes TIFF frames by design, so no spatial movie can be "
                       "rendered from this return; logs alone cannot justify one"),

        local_native_runs=dict(
            path=a.native_runs, arms=36, read_only=True,
            manifest_sha256="938b242d5cbf742cb782bf29893e387d10560f71f324c32d464160f2534aa160"),

        solver=dict(name="Morpheus", tag="v2.3.9",
                    binary_sha256="3d9a6e5a4cb86824b745500df1474596d39cce5deed24f767c0841df0f94d5ad",
                    base_example="Examples/CPM/Protrusion_2D.xml",
                    base_sha256="da2a27c8e552041ee4a51d7ff1e7332466f5180762642c997594731c92737db2",
                    verified_on_vm=True),

        headline=dict(
            fixed_horizon_scope="closure observed at sampled times <= 1000 model units",
            minimum_feasible_spread={k: v["min_feasible_spread"] for k, v in audit["interval_audit"].items()},
            frozen_tolerance=2.0,
            exponent_feasible_bounds={k: v["exponent_feasible_bounds"] for k, v in audit["interval_audit"].items()},
            predicted_exponent=1.0,
            interval_supported=True,
            late_window_unit="per arm; seed means are a labelled companion field only",
            long_horizon_threshold="unknown",
            gap_size_scaling="untested at this resolution, not refuted (see card section 6)"),

        files=dict(
            source={f: h(R / f) for f in REPO_FILES},
            figures={f: h(R / f) for f in FIGS},
            preserved_media={f: h(R / f) for f in MEDIA}),

        review_refs=[
            dict(kind="infra source review of the packet",
                 file="messages/infra-to-epithelial-packet-review.md", outcome="6 blockers, all repaired at e2f74f2"),
            dict(kind="infra admission checks",
                 file="messages/infra-to-epithelial-admission-checks.md", outcome="38 fixtures passed; admitted"),
            dict(kind="independent review (bounded, 36 native runs)",
                 file="messages/epithelial-independent-review.md",
                 outcome="tally, floor arithmetic, G9 summary wording, G1b frozen-rule scope"),
            dict(kind="infra horizon/prose review",
                 file="messages/infra-epithelial-horizon-review.md",
                 outcome="minimum feasible spread added; asymptotic claims withdrawn"),
            dict(kind="independent review of the 240-arm sweep",
                 file="messages/epithelial-sweep-independent-review.md",
                 outcome="FAIL upheld and interval-supported; per-arm vs seed-mean correction"),
        ],
        corrections_applied=[
            "gate tally 9 -> 8 -> 7 pass (G6 descriptive, G8 unevaluable, G1b incomplete)",
            "1875 is the residual gap; 625 nodes (25.0%) is the passive fill ceiling",
            "G9's 1.414 is a bracket geometric-mean summary, one doubling at one gap size",
            "G1b assessed INCOMPLETE rather than narrowed to shared times; reported PASS kept as history",
            "k=4 vs k=7 Phi intervals overlap -> refutation of constant Phi* withdrawn",
            "ARRESTED scoped to StopTime 1000; three asymptotic horizon claims withdrawn",
            "late-window deltas reported per arm, not from seed means",
        ],
        card_pins="engineering/epithelial/check_card.py, 102/102 matching at this commit",
    )
    Path(a.out).write_text(json.dumps(bundle, indent=1))
    d = hashlib.sha256(Path(a.out).read_bytes()).hexdigest()
    print(f"{a.out}\n  bundle sha256 {d}\n  source files {len(REPO_FILES)}, figures {len(FIGS)}, "
          f"preserved media {len(MEDIA)}")


if __name__ == "__main__":
    main()
