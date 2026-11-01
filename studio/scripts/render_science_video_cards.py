#!/usr/bin/env python3
"""Render deterministic evidence cards from pinned Frontier records for science demos."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/demo-video-science/sources/cards"
FONT = Path("/home/ubuntu/.local/share/fonts/Inter-Regular.ttf")
BOLD = Path("/home/ubuntu/.local/share/fonts/Inter-SemiBold.ttf")
if not FONT.is_file():
    FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
if not BOLD.is_file():
    BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(name: str, title: str, kicker: str, sections: list[tuple[str, str]]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1920, 1080), "#07121f")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((60, 54, 1860, 1026), radius=32, fill="#0d2234", outline="#4f8c86", width=3)
    draw.text((112, 90), kicker, font=ImageFont.truetype(str(BOLD), 30), fill="#8ce6c1")
    draw.text((112, 150), title, font=ImageFont.truetype(str(BOLD), 54), fill="#ffffff")
    y = 260
    for heading, body in sections:
        draw.text((116, y), heading, font=ImageFont.truetype(str(BOLD), 34), fill="#ffdda2")
        y += 51
        for line in textwrap.wrap(body, width=86):
            draw.text((120, y), line, font=ImageFont.truetype(str(FONT), 28), fill="#e5eef5")
            y += 41
        y += 28
    path = OUT / name
    image.save(path, optimize=True)
    return path


def main() -> None:
    provenance = ROOT / "artifacts/demo-video-science/sources/provenance"
    receipt_path = provenance / "lean-demo-20261101-retry1.json"
    lean_path = provenance / "CantileverGuard.lean"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["positive"]["exit"] == 0 and receipt["negative_corrupt_law"]["exit"] == 1
    assert receipt["positive"]["only_standard_axioms"] is True
    lean = render("lean-cantilever-proof.png", "A conditional bound, checked", "LEAN 4 · HAND-AUTHORED STATEMENT", [
        ("Stated beam law", "3 E I d = P L³"),
        ("Stiffness assumption ⇒ bound", "10 P L² ≤ 3 E I  ⇒  d ≤ L / 10"),
        ("Fresh receipt", "3 positive theorems compiled · standard axioms only · corrupted-law control rejected"),
        ("Scope", "Algebra of the stated model only. No measured fin property or biological premise was established."),
    ])
    map_path = provenance / "design-control-map.json"
    design_map = json.loads(map_path.read_text())
    assert any("Daane 2021 Data S1A" in item.get("what_exists", "") for item in design_map.get("layers", []))
    specimen = render("specimen-length-evidence.png", "Measurements constrain candidate geometry", "SOURCE-DERIVED EVIDENCE · NOT A NEW MEASUREMENT", [
        ("Input", "Daane et al. 2021 Data S1A: fin length against standard length; n = 49 in the mapped fit."),
        ("Use", "A log–log allometric fit informs a candidate geometry over its stated specimen range."),
        ("Limit", "An observed association is not causal control, a tissue-mechanics measurement, or evidence of flight."),
    ])
    genetics_path = provenance / "science-video-genetics-facts.md"
    genetics_text = genetics_path.read_text(encoding="utf-8")
    assert "Daane et al., Current Biology2021" in genetics_text and "does not demonstrate aerial performance" in genetics_text
    genetics = render("zebrafish-fin-genetics.png", "Published fin phenotypes are a starting point", "PRIMARY-SOURCE CHECK · NOT A FRONTIER-GENERATED FISH", [
        ("Observed in zebrafish", "lat4a nr21 and kcnh2a longfin variants are associated with altered fin proportions in published work."),
        ("Study", "Daane et al., Current Biology (2021), Fig. 4 · DOI 10.1016/j.cub.2021.08.054"),
        ("Limit", "The result does not demonstrate aerial performance, engineered flight, or a genetic bridge to the models here."),
    ])
    print_path = provenance / "print-r4-assembly.md"
    print_text = print_path.read_text(encoding="utf-8")
    assert "every `_R` print file holds the LEFT part" in print_text and "In r4, each `_R` file is the mirror image" in print_text
    print_card = render("print-assembly-revision.png", "A caught export defect became a revision", "INDEPENDENT REVIEW · DIGITAL ASSEMBLY ONLY", [
        ("Defect", "Earlier right-side STL exports held the left-side part."),
        ("Correction", "r4 regenerated right-side files as mirror images and checked side, rotation and center of gravity."),
        ("Limit", "This is a digital fit prototype. Nothing here establishes printing, flight or launch readiness."),
    ])
    cfd_path = provenance / "cfd3d-gpu-receipt.json"
    cfd_receipt = json.loads(cfd_path.read_text())
    assert "C1" in cfd_receipt["science"] and cfd_receipt["completion"] == "complete"
    cfd_card = render("cfd-reference-gate.png", "A completed run can fail validation", "CFD REFERENCE CHECK · NOT A FISH-FLIGHT RESULT", [
        ("Recorded status", "C1 physical reference gate: FAILED. Controls were incomplete."),
        ("Interpretation", "A transport-complete GPU job is not the same as a validated model."),
        ("Boundary", "This benchmark failure does not measure a living fish or the beam-model assumptions."),
    ])
    mcp_path = provenance / "mcp.md"
    mcp_text = mcp_path.read_text(encoding="utf-8")
    assert "frontier_propose" in mcp_text and "frontier_get" in mcp_text
    mcp = render("mcp-contribution-surface.png", "Inspect, propose, challenge", "MCP · VERSIONED KNOWLEDGE SURFACE", [
        ("Read", "Retrieve exact claims, project context, evidence and lineage through declared tools."),
        ("Contribute", "Authenticated contributors can submit typed proposals and evidence references."),
        ("Boundary", "Proposals are queued for review; a request is not an executed simulation or accepted result."),
    ])
    rows = []
    for path, origin, note in [
        (lean, [str(receipt_path.relative_to(ROOT)), str(lean_path.relative_to(ROOT))], "Generated from the copied Lean source and exact fresh compiler receipt."),
        (specimen, [str(map_path.relative_to(ROOT)), "engineering/design_control/build.py"], "Source-derived card from the design-control map; no new measurement was made."),
        (genetics, [str(genetics_path.relative_to(ROOT))], "Source-based summary from a fact-check note with the primary article citation."),
        (print_card, [str(print_path.relative_to(ROOT))], "Summary transcribed from the checked r4 assembly record; not evidence of physical printing."),
        (cfd_card, [str(cfd_path.relative_to(ROOT))], "Card reflects the C1 gate field in the recorded GPU receipt; no fish-flight validation claim."),
        (mcp, [str(mcp_path.relative_to(ROOT))], "Derived from the tracked MCP usage documentation."),
    ]:
        rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size,
                     "source_paths": origin, "source_sha256": {p: sha(ROOT / p) for p in origin if (ROOT / p).is_file()},
                     "note": note})
    (OUT / "card-provenance.json").write_text(json.dumps({"schema": "frontier.science-demo-cards/1", "cards": rows}, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
