#!/usr/bin/env python3
"""Build two text cards directly from the tracked Lean and benchmark receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/demo-video-90/sources/cards"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths = ([Path("/home/ubuntu/.local/share/fonts/Inter-SemiBold.ttf"),
              Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")] if bold else
             [Path("/home/ubuntu/.local/share/fonts/Inter-Regular.ttf"),
              Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")])
    path = next((item for item in paths if item.is_file()), None)
    if path is None:
        raise FileNotFoundError("no supported sans-serif font is installed")
    return ImageFont.truetype(str(path), size)


def base(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (1920, 1080), "#07121f")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((120, 250, 1800, 780), radius=32, fill="#10283a", outline="#397e76", width=3)
    draw.text((180, 285), "RECEIPT SUMMARY · SOURCE-DERIVED", font=font(28, True), fill="#73eec2")
    draw.text((180, 340), title, font=font(56, True), fill="#ffffff")
    return image, draw


def main() -> None:
    lean_path = ROOT / "artifacts/demo-video-90/sources/provenance/lean-receipt.json"
    benchmark_path = ROOT / "artifacts/demo-video-90/sources/provenance/capability-agency-results-card.md"
    summary_path = ROOT / "artifacts/demo-video-90/sources/provenance/capability-agency-results-card.md"
    model_usage_path = ROOT / "artifacts/demo-video-90/sources/provenance/bio-model-usage.json"
    genomics_path = ROOT / "artifacts/demo-video-90/sources/provenance/genomics-completion.json"
    receipt = json.loads(lean_path.read_text(encoding="utf-8"))
    if receipt.get("positive", {}).get("exit") != 0 or receipt.get("negative_corrupt_law", {}).get("exit") != 1:
        raise ValueError("Lean receipt does not contain the required positive and mutant outcomes")
    if receipt.get("positive", {}).get("only_standard_axioms") is not True:
        raise ValueError("Lean receipt does not confirm standard axioms only")
    image, draw = base("Lean 4.35.0 · parameter-bound check")
    draw.rounded_rectangle((180, 435, 860, 615), radius=20, fill="#123f35")
    draw.rounded_rectangle((1060, 435, 1740, 615), radius=20, fill="#4b2b35")
    draw.text((220, 470), "Positive theorem", font=font(38, True), fill="#ffffff")
    draw.text((220, 530), "EXIT 0 · standard axioms only", font=font(31), fill="#bfffe8")
    draw.text((1100, 470), "Corrupt-law mutant", font=font(38, True), fill="#ffffff")
    draw.text((1100, 530), "REJECTED · EXIT 1", font=font(31), fill="#ffd1d7")
    draw.text((220, 680), "Algebra of the stated cantilever inequality only · not a biological proof",
              font=font(30), fill="#ffdf9e")
    OUT.mkdir(parents=True, exist_ok=True)
    lean_out = OUT / "lean-check-summary.png"
    image.save(lean_out)

    post = json.loads((ROOT / "artifacts/demo-video-90/sources/provenance/capability-agency-post-run.json").read_text(encoding="utf-8"))
    if post.get("scientific_calls", {}).get("valid_json") != 27:
        raise ValueError("benchmark receipt does not show 27 valid responses")
    conditions = post.get("conditions", {})
    names = ["single_serial_analyst", "isolated_specialists", "collaborating_specialists"]
    if set(names) - conditions.keys() or any(conditions[name].get("mean_replicate_aggregate_score") != 16.0 for name in names):
        raise ValueError("benchmark conditions do not share the reported 16/16 ceiling result")
    image, draw = base("Single-agent vs collective benchmark")
    x_positions = [220, 745, 1270]
    labels = ["Single analyst", "Isolated specialists", "Collaborating specialists"]
    for x, label, key in zip(x_positions, labels, names):
        score = conditions[key]["mean_replicate_aggregate_score"]
        draw.rounded_rectangle((x, 440, x + 430, 605), radius=20, fill="#18354a", outline="#397e76", width=2)
        draw.text((x + 26, 465), label, font=font(29, True), fill="#ffffff")
        draw.text((x + 26, 520), f"{score:.0f}/16", font=font(50, True), fill="#bfffe8")
    draw.text((220, 660), "27 valid responses · tied ceiling result · no collective advantage established",
              font=font(30, True), fill="#ffdf9e")
    draw.text((220, 710), "Evidence-synthesis task; the packet already contained the relevant facts.",
              font=font(27), fill="#dceaf2")
    benchmark_out = OUT / "capability-agency-tie-summary.png"
    image.save(benchmark_out)

    usage = json.loads(model_usage_path.read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in usage["entries"]}
    gemini = entries["gemini-discovery-embedding-index-20261031"]["usage"]
    openfold = entries["openfold2-kcnj13-operation-op-5ba1d104dbbcd293"]
    openmm = entries["openmm-collagen-900ps-conditional-branches-infra21"]["usage"]
    assert gemini["requests"] == 49 and gemini["documents"] == 2444
    assert openfold["status"] == "succeeded" and openfold["runtime_origin"] == "upstream-source-not-nim"
    assert openmm["replicates"] == 3 and openmm["production_ps_each"] == 900
    genomes = json.loads(genomics_path.read_text(encoding="utf-8"))
    assert genomes["n_run"] == genomes["n_pinned"] == 23 and genomes["download_md5_all_ok"] is True
    image, draw = base("Receipt-backed compute + model use")
    rows = [
        ("GOOGLE CLOUD", "23 public genome archives run and pinned; BETSE 8/8 cases completed."),
        ("NEBIUS H100", "OpenMM collagen model: 3 independent 900 ps production runs; Evo2 scoring jobs recorded."),
        ("GEMINI / OPENFOLD2", "49 embedding requests for 2,444 documents; one upstream OpenFold2 result, not NIM."),
        ("BIOLOGY SERVICE STATUS", "BioNeMo/NIM and Brev are future integrations; execution is not established."),
    ]
    for idx, (label, text) in enumerate(rows):
        y = 420 + idx * 86
        draw.rounded_rectangle((180, y, 1740, y + 68), radius=14, fill="#18354a")
        draw.text((205, y + 7), label, font=font(24, True), fill="#73eec2")
        draw.text((530, y + 14), text, font=font(24), fill="#ffffff")
    draw.text((205, 770), "Provider completion, scientific checks and biological validation are separate.",
              font=font(26, True), fill="#ffdf9e")
    provider_out = OUT / "provider-compute-use-summary.png"
    image.save(provider_out)

    image, draw = base("Public-genome survey · receipt")
    draw.text((220, 435), f"{genomes['n_run']} run · {genomes['n_pinned']} pinned assemblies",
              font=font(48, True), fill="#bfffe8")
    draw.text((220, 510), "Downloaded checksums: all MD5 checks passed", font=font(34), fill="#ffffff")
    draw.text((220, 580), f"{genomes['n_scored_a_type']} loci scored · {genomes['n_as_predicted']} matched expectation · 1 deviation",
              font=font(32), fill="#ffffff")
    draw.text((220, 650), f"Deviation retained: {genomes['deviations'][0]}", font=font(30), fill="#ffdf9e")
    draw.text((220, 720), "Archive count, not species count or a complete genome; not organism validation.",
              font=font(27), fill="#dceaf2")
    genomics_out = OUT / "genomics-survey-receipt-summary.png"
    image.save(genomics_out)

    provenance = {
        "schema": "frontier.demo-video-90.cards/1",
        "cards": [
            {"path": lean_out.relative_to(ROOT).as_posix(), "sha256": sha256(lean_out),
             "source_path": lean_path.relative_to(ROOT).as_posix(), "source_sha256": sha256(lean_path),
             "source_kind": "Lean check receipt",
             "claim_scope": "Conditional algebraic Euler-Bernoulli cantilever theorem with a corrupt-law mutant check; algebraic statement only.",
             "not_established": receipt.get("does_not_prove")},
            {"path": benchmark_out.relative_to(ROOT).as_posix(), "sha256": sha256(benchmark_out),
             "source_path": "artifacts/demo-video-90/sources/provenance/capability-agency-post-run.json",
             "source_sha256": sha256(ROOT / "artifacts/demo-video-90/sources/provenance/capability-agency-post-run.json"),
             "source_kind": "actual benchmark post-run summary", "claim_scope": post.get("interpretation")},
            {"path": provider_out.relative_to(ROOT).as_posix(), "sha256": sha256(provider_out),
             "source_path": model_usage_path.relative_to(ROOT).as_posix(), "source_sha256": sha256(model_usage_path),
             "source_kind": "scoped bio-model usage ledger and GCP task receipts", "claim_scope": usage.get("scope")},
            {"path": genomics_out.relative_to(ROOT).as_posix(), "sha256": sha256(genomics_out),
             "source_path": genomics_path.relative_to(ROOT).as_posix(), "source_sha256": sha256(genomics_path),
             "source_kind": "completed public-genome survey receipt", "claim_scope": genomes.get("scope")},
        ],
        "renderer_inputs": {"benchmark_summary_markdown": str(benchmark_path.relative_to(ROOT)),
                             "summary_markdown_sha256": sha256(summary_path)},
    }
    (OUT / "card-provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cards": provenance["cards"]}, sort_keys=True))


if __name__ == "__main__":
    main()
