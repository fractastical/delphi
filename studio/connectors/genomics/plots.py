"""Plotted views drawn only from the committed artifacts. Writes data/genomics/plots/*.svg and plot_manifest.json.

Every mark is a row of an artifact whose sha256 is recorded beside the figure. A square means "this annotation exists", not a level;
no square means "not curated", not "not expressed".

  PYTHONPATH=. python3 -m connectors.genomics.plots
"""

from __future__ import annotations

import csv
import hashlib
import json
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "genomics"
PLOTS = OUT / "plots"
plt.rcParams.update({"svg.hashsalt": "delphi-genomics", "svg.fonttype": "none", "font.size": 9})
PERIODS = ["Zygote", "Cleavage", "Blastula", "Gastrula", "Segmentation", "Pharyngula", "Hatching", "Larval", "Juvenile", "Adult"]   # ZFIN stage periods in developmental order
PUB_COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00"]


def wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(fig, name: str) -> Path:
    p = PLOTS / name
    fig.savefig(p, format="svg", metadata={"Date": None, "Creator": "delphi-frontier genomics connector"})
    plt.close(fig)
    return p


def expression_matrix(gene: str):
    rows = [r for r in csv.DictReader(open(OUT / "zfin_expression_selected.csv")) if r["symbol"] == gene]
    stages = sorted({r["start_stage"] for r in rows}, key=lambda s: (PERIODS.index(s.split(":")[0]) if s.split(":")[0] in PERIODS else 99, s))
    structs = sorted({r["structure"] for r in rows}, key=lambda s: (s == "whole organism", s))
    pubs = sorted({r["publication"] for r in rows})
    fig, ax = plt.subplots(figsize=(8.4, 2.6 + 0.30 * len(structs)))
    for r in rows:
        dodge = (pubs.index(r["publication"]) - (len(pubs) - 1) / 2) * 0.22     # one slot per publication so overlapping annotations stay visible
        ax.scatter(stages.index(r["start_stage"]) + dodge, structs.index(r["structure"]), s=90, marker="s", color=PUB_COLORS[pubs.index(r["publication"]) % 5], zorder=3)
    assert len({(r["start_stage"], r["structure"], r["publication"]) for r in rows}) <= len(rows)
    ax.set_xticks(range(len(stages)), stages, rotation=35, ha="right")
    ax.set_yticks(range(len(structs)), structs)
    ax.set_xlim(-0.6, len(stages) - 0.4); ax.set_ylim(-0.6, len(structs) - 0.4)
    ax.grid(alpha=0.25, zorder=0)
    ax.set_title(wrap(f"ZFIN curated wildtype expression annotations for {gene} (zebrafish): {len(rows)} annotations; assay(s): {', '.join(sorted({r['assay'] for r in rows}))}", 90), fontsize=9, loc="left")
    for i, p in enumerate(pubs):
        ax.scatter([], [], marker="s", color=PUB_COLORS[i % 5], label=p)
    ax.legend(title="publication (ZFIN id)", fontsize=7, loc="center left", bbox_to_anchor=(1.01, 0.5))
    fig.text(0.01, 0.012, wrap("A square = a curated annotation exists, not a level. No square = not curated, not 'not expressed'. Start stage shown; squares of different publications are offset side by side.", 120), fontsize=7, color="0.3")
    fig.subplots_adjust(bottom=0.42 if len(structs) < 8 else 0.34, left=0.17, right=0.80, top=0.86)
    return fig, rows


def correlations(gene: str, k: int = 12):
    rows = [r for r in csv.DictReader(open(OUT / "daniocell_correlations.csv")) if r["gene"] == gene]
    pos = [(r["partner_gene"], float(r["r_all_cells"])) for r in rows if r["direction"] == "positive"][:k]
    neg = [(r["partner_gene"], float(r["r_all_cells"])) for r in rows if r["direction"] == "negative"][:5]
    items = pos + neg[::-1]
    fig, ax = plt.subplots(figsize=(6.6, 0.28 * len(items) + 1.1))
    ax.barh(range(len(items)), [v for _, v in items], color=["#0072B2" if v > 0 else "#D55E00" for _, v in items])
    ax.set_yticks(range(len(items)), [n for n, _ in items]); ax.invert_yaxis(); ax.axvline(0, color="0.3", lw=0.8)
    ax.set_xlabel("Pearson r across all Daniocell cells (as listed on the gene page)")
    ax.set_xlim(-0.12, 0.12)
    ax.set_title(wrap(f"Daniocell: genes most correlated with {gene}, all cells (top {len(pos)} positive, {len(neg)} negative)", 70), fontsize=9, loc="left")
    fig.text(0.01, 0.012, wrap(f"Weak correlations (largest |r| = {max(abs(v) for _, v in items):.3f}); expression co-variation only: no interaction, regulation or function is shown.", 95), fontsize=7, color="0.3")
    fig.subplots_adjust(bottom=0.2, left=0.24, right=0.97, top=0.88)
    return fig, items


def flyingfish_hits():
    fly = json.loads((OUT / "flyingfish_receipts.json").read_text())
    good = [g for g in fly["selected_genes"] if g["usable"]]
    good.sort(key=lambda g: (g["zebrafish_gene"], -g["identity_pct"]))
    fig, ax = plt.subplots(figsize=(7.4, 0.26 * len(good) + 2.0))
    ax.barh(range(len(good)), [g["identity_pct"] for g in good], color="#009E73")
    ax.set_yticks(range(len(good)), [f"{g['zebrafish_gene']}  ({g['inferred_gene_model']}, {g['scaffold']})" for g in good], fontsize=7)
    ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_xlabel("amino-acid identity of the best SwissProt BLASTP hit (%)")
    ax.set_title(wrap("Mirrorwing flyingfish gene models whose best SwissProt hit is a gene of the fin / mechanosensation set", 70), fontsize=9, loc="left")
    fig.text(0.01, 0.012, wrap("Best-hit homology from the authors' annotation, not orthology; paralogs (a/b) unresolved; the gene-model id comes from a position-rank mapping that passed a per-gene length check.", 105), fontsize=6.8, color="0.3")
    fig.subplots_adjust(bottom=0.17, left=0.36, right=0.97, top=0.91)
    return fig, good


def main() -> int:
    PLOTS.mkdir(exist_ok=True)
    code = sha(Path(__file__))
    man = {"manifest_schema": "genomics-plot-manifest-0.1 (connector-local)", "plots_code_sha256": code, "matplotlib": matplotlib.__version__, "plots": []}
    specs = [("kcnh2a_zfin_expression.svg", "ZFIN curated expression annotations for kcnh2a", ["zfin_expression_selected.csv"], "expression_correlation", "Danio rerio", lambda: expression_matrix("kcnh2a")),
             ("kcnk5b_zfin_expression.svg", "ZFIN curated expression annotations for kcnk5b", ["zfin_expression_selected.csv"], "expression_correlation", "Danio rerio", lambda: expression_matrix("kcnk5b")),
             ("kcnh2a_daniocell_correlations.svg", "Daniocell gene-page correlations for kcnh2a", ["daniocell_correlations.csv", "artifacts/daniocell_page_kcnh2a.html"], "expression_correlation", "Danio rerio", lambda: correlations("kcnh2a")),
             ("flyingfish_best_hits.svg", "Flyingfish gene models with a fin-set best SwissProt hit", ["flyingfish_receipts.json", "artifacts/flyingfish_swissprot_best_hits_selected.tsv", "artifacts/flyingfish_selected_gene_models.gff3"], "sequence_annotation", "Hirundichthys speculiger", flyingfish_hits)]
    for name, title, inputs, cls, species, fn in specs:
        fig, data = fn()
        out = save(fig, name)
        man["plots"].append({"file": f"data/genomics/plots/{name}", "sha256": sha(out), "bytes": out.stat().st_size, "title": title, "evidence_class": cls, "species": species, "marks": len(data),
                             "inputs": [{"path": f"data/genomics/{i}", "sha256": sha(OUT / i)} for i in inputs]})
    (PLOTS / "plot_manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True))
    print([(p["file"].split("/")[-1], p["marks"], p["bytes"]) for p in man["plots"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
