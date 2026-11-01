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


def render_compiler_loop() -> Path:
    provenance = ROOT / "artifacts/demo-video-science/sources/provenance"
    report_path = provenance / "biodesign-compiler-report.json"
    report = json.loads(report_path.read_text())
    assert report.get("compiled") and report.get("contract")
    image = Image.new("RGB", (1920, 1080), "#07121f")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((60, 54, 1860, 1026), radius=32, fill="#0d2234", outline="#4f8c86", width=3)
    title = ImageFont.truetype(str(BOLD), 48)
    sub = ImageFont.truetype(str(BOLD), 28)
    body = ImageFont.truetype(str(FONT), 25)
    draw.text((112, 86), "A biological compiler · proposed two-way design", font=title, fill="#ffffff")
    draw.text((112, 172), "FORWARD · sequence to function hypothesis", font=sub, fill="#8ce6c1")
    draw.text((112, 425), "INVERSE · target function to candidate sequences", font=sub, fill="#ffb2d1")
    forward = ["candidate DNA", "forward predictions", "function hypothesis", "targeted test"]
    inverse = ["target function", "candidate sequence set", "cheap filters", "forward predictions / test"]
    boxes_x = [112, 552, 992, 1432]
    for y, labels, color in ((224, forward, "#253f56"), (477, inverse, "#462e4a")):
        for i, label in enumerate(labels):
            box=(boxes_x[i],y,boxes_x[i]+330,y+118)
            draw.rounded_rectangle(box,radius=18,fill=color,outline="#8ca7ba",width=2)
            lines=textwrap.wrap(label,width=20)
            draw.multiline_text((box[0]+18,box[1]+28),"\n".join(lines),font=sub,fill="#f2f7fb",spacing=4)
            if i<3:
                draw.line((box[2]+10,y+59,boxes_x[i+1]-16,y+59),fill="#ffdda2",width=5)
                x=boxes_x[i+1]-20; draw.polygon([(x,y+49),(x+14,y+59),(x,y+69)],fill="#ffdda2")
    draw.rounded_rectangle((112, 642, 1762, 720),radius=16,fill="#1d3344")
    draw.text((142, 660),"Observed measurements and tests update both candidate sets and target assumptions",font=body,fill="#e5eef5")
    draw.text((112, 760),"CURRENT FRONTIER CHECKER",font=sub,fill="#8ce6c1")
    draw.text((112, 808),"Pins linked artifacts and checks scope; it does not generate or build a DNA sequence.",font=body,fill="#e5eef5")
    draw.text((112, 854),"Open: sequence→cell program · expression→growth · growth→stiffness",font=body,fill="#ffdda2")
    draw.text((112, 942),"PROPOSED WORKFLOW · no end-to-end molecular or organism design was executed",font=sub,fill="#ffb2d1")
    path=ROOT / "artifacts/demo-video-science/sources/cards/biological-compiler-bidirectional.png"
    path.parent.mkdir(parents=True,exist_ok=True);image.save(path,optimize=True);return path


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
    compiler_readme = provenance / "biodesign-compiler-README.md"
    compiler_report = json.loads((provenance / "biodesign-compiler-report.json").read_text())
    assert "no model is run, no network, no GPU" in compiler_readme.read_text(encoding="utf-8")
    unresolved = {row["bridge"] for result in compiler_report["compiled"] for row in result.get("unresolved_bridges", [])}
    assert {"expression->growth", "growth->EI", "blueprint->cell_program"}.issubset(unresolved)
    compiler_card = render("biological-compiler-scope.png", "Biological compiler · intended output", "CURRENT FRONTIER ARTIFACT CHECKER · NOT DNA DESIGN", [
        ("Intended outputs", "Candidate DNA · build plan · validation strategy"),
        ("Implemented today", "Pins and checks linked artifacts across separate model layers."),
        ("Open interfaces", "Expression → growth · growth → stiffness · blueprint → cell program remain unresolved."),
        ("Scope", "No sequence-to-organism compiler or biological build was executed."),
    ])
    bidirectional_card = render_compiler_loop()
    comparison_card = render("fish-design-comparison-status.png", "Compare dimensions, not a single similarity score", "REFERENCE · COMPUTATIONAL CANDIDATE · NATURAL ANALOG", [
        ("Zebrafish reference", "Published fin-proportion genetics and source-specific genome context."),
        ("Engineered candidate", "Digital geometry and bounded model outputs; no built or validated organism."),
        ("Natural flying fish", "Published morphology sources; no matched mechanics-to-flight calibration in this project."),
        ("Across each", "Gene context · fin shape · mechanics · behavior. Unavailable links stay open."),
    ])
    alphafold_card = render("prediction-needs-testing.png", "A prediction is a hypothesis to test", "STRUCTURE-PREDICTION ANALOGY · NOT DNA OR ORGANISM DESIGN", [
        ("Analogy", "AlphaFold-type structure predictions can guide experiments; predictions still require testing."),
        ("Here", "Sequence continuations and simulations are computational candidates, not functional evidence."),
        ("Source", "AlphaFold 3 original paper · Nature (2024), DOI 10.1038/s41586-024-07487-w"),
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
    evo_path = provenance / "evo2-output-checks.json"
    evo = json.loads(evo_path.read_text())
    assert evo["new_model_calls"] == 0 and evo["biological_validation"] is False
    evo_card = render("evo2-continuations-limit.png", "Sequence continuations are computational candidates", "SEPARATE EVO2 EXPLORATION · NOT A PROMOTER ASSAY", [
        ("Stored outputs", "Sequence continuations and same-model likelihood checks were recorded in a separate exploration."),
        ("Limit", "Likelihood and motif scores do not establish promoter activity, cell-specific expression, or flight."),
        ("Independent audit", "Sequence hashes and saved score rows checked; no new model call or sequence generation for this card."),
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
        (compiler_card, [str((provenance / "biodesign-compiler-README.md").relative_to(ROOT)), str((provenance / "biodesign-compiler-report.json").relative_to(ROOT))], "Drawn from exact compiler README/report; expected output is separate from current artifact checking."),
        (bidirectional_card, [str((provenance / "biodesign-compiler-README.md").relative_to(ROOT)), str((provenance / "biodesign-compiler-report.json").relative_to(ROOT))], "Explicitly proposed forward and inverse design flows; current linked-artifact checker and unresolved interfaces are shown separately."),
        (comparison_card, [str(map_path.relative_to(ROOT)), str(genetics_path.relative_to(ROOT))], "Structured status display; no unverified comparison metric or phenotype score."),
        (alphafold_card, ["https://www.nature.com/articles/s41586-024-07487-w", str(evo_path.relative_to(ROOT))], "Source-cited analogy only: predictions are candidates requiring tests, not DNA design."),
        (genetics, [str(genetics_path.relative_to(ROOT))], "Source-based summary from a fact-check note with the primary article citation."),
        (print_card, [str(print_path.relative_to(ROOT))], "Summary transcribed from the checked r4 assembly record; not evidence of physical printing."),
        (cfd_card, [str(cfd_path.relative_to(ROOT))], "Card reflects the C1 gate field in the recorded GPU receipt; no fish-flight validation claim."),
        (evo_card, [str(evo_path.relative_to(ROOT))], "Derived from independently checked stored-output audit; no sequence bytes exposed and no new inference."),
        (mcp, [str(mcp_path.relative_to(ROOT))], "Derived from the tracked MCP usage documentation."),
    ]:
        rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size,
                     "source_paths": origin, "source_sha256": {p: sha(ROOT / p) for p in origin if (ROOT / p).is_file()},
                     "note": note})
    (OUT / "card-provenance.json").write_text(json.dumps({"schema": "frontier.science-demo-cards/1", "cards": rows}, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
