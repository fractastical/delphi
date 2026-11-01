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
    provenance = {
        "schema": "frontier.demo-video-90.cards/1",
        "cards": [
            {"path": lean_out.relative_to(ROOT).as_posix(), "sha256": sha256(lean_out),
             "source_path": lean_path.relative_to(ROOT).as_posix(), "source_sha256": sha256(lean_path),
             "source_kind": "Lean check receipt", "claim_scope": receipt.get("does_not_prove")},
            {"path": benchmark_out.relative_to(ROOT).as_posix(), "sha256": sha256(benchmark_out),
             "source_path": "artifacts/demo-video-90/sources/provenance/capability-agency-post-run.json",
             "source_sha256": sha256(ROOT / "artifacts/demo-video-90/sources/provenance/capability-agency-post-run.json"),
             "source_kind": "actual benchmark post-run summary", "claim_scope": post.get("interpretation")},
        ],
        "renderer_inputs": {"benchmark_summary_markdown": str(benchmark_path.relative_to(ROOT)),
                             "summary_markdown_sha256": sha256(summary_path)},
    }
    (OUT / "card-provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cards": provenance["cards"]}, sort_keys=True))


if __name__ == "__main__":
    main()
