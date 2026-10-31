"""Species comparison graph: sourced analogues and engineered forms, with conjectured routes kept apart."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

NODES = [
    {"id": "hemiramphidae", "label": "Halfbeaks (Hemiramphidae)\nnon-gliding; paraphyletic grade", "group": "extant",
     "source": "Lovejoy, Iranpour & Collette 2004, Integr. Comp. Biol. 44:366-377, PMID 21676722",
     "read_level": "abstract (relayed: messages/flying-fish-constraints.md)"},
    {"id": "oxyporhamphus", "label": "Oxyporhamphus micropterus\nenlarged pectorals, does not fly", "group": "extant",
     "source": "Davenport 1992, J. Mar. Biol. Assoc. UK 72:25-39",
     "read_level": "abstract (relayed by fable-lead); reported reason: centre of gravity far behind the pectorals; "
                   "not used in geometry"},
    {"id": "exocoetus", "label": "Exocoetus (two-wing)\npectorals 91.8% of wing area", "group": "extant",
     "source": "Fish 1990 Tables I, IV", "read_level": "full-text (read by this worker)"},
    {"id": "cypselurus", "label": "Cypselurus (four-wing)\npectorals 76.0% of wing area", "group": "extant",
     "source": "Fish 1990 Tables I, IV", "read_level": "full-text (read by this worker)"},
    {"id": "zebrafish", "label": "Zebrafish lat4a x kcnh2a fin phenocopy\n(experimental; not used in geometry)",
     "group": "experimental",
     "source": "Daane et al. 2021, Curr. Biol. 31:5052-5061, doi:10.1016/j.cub.2021.08.054, PMC9172250",
     "read_level": "full-text via r.jina.ai of PMC (this worker); a mechanism hypothesis for larger paired fins, "
                   "shown in zebrafish only; transfer to a halfbeak is unestablished"},
    {"id": "daane_s1a", "label": "Beloniform fin / SL, 109 museum specimens\n(Daane et al. 2021 Data S1A)",
     "group": "extant",
     "source": "Daane et al. 2021 Data S1A (mmc2.xlsx, sha256 1ac98650...); summary in "
               "artifacts/print/sources/daane2021-S1A-summary.json",
     "read_level": "supplement downloaded and parsed by this worker; ratios recomputed from raw lengths"},
    {"id": "potanichthys", "label": "Potanichthys xingyiensis\nTriassic four-wing glider (convergent)", "group": "fossil",
     "source": "Xu et al. 2013, Proc. R. Soc. B 280:20122261", "read_level": "listing + search-summary (relayed)"},
    {"id": "A", "label": "Form A: short-fin precursor-inspired\n(solver: rejected)", "group": "engineered"},
    {"id": "B", "label": "Form B: two-wing glider\n(solver: satisfies declared constraints)", "group": "engineered"},
    {"id": "C", "label": "Form C: four-wing glider\n(solver: satisfies declared constraints)", "group": "engineered"},
]

EDGES = [
    {"from": "hemiramphidae", "to": "exocoetus", "kind": "phylogeny_sourced",
     "label": "flyingfishes nested within halfbeaks", "source": "Lovejoy et al. 2004 (abstract)"},
    {"from": "hemiramphidae", "to": "cypselurus", "kind": "phylogeny_sourced",
     "label": "flyingfishes nested within halfbeaks", "source": "Lovejoy et al. 2004 (abstract)"},
    {"from": "hemiramphidae", "to": "A", "kind": "informs_design", "label": "elongate lower jaw (qualitative)"},
    {"from": "daane_s1a", "to": "A", "kind": "informs_design", "label": "halfbeak pectoral and pelvic / SL medians"},
    {"from": "daane_s1a", "to": "B", "kind": "informs_design", "label": "Exocoetus volitans pelvic / SL"},
    {"from": "daane_s1a", "to": "C", "kind": "informs_design", "label": "Cheilopogon furcatus pelvic / SL"},
    {"from": "exocoetus", "to": "B", "kind": "informs_design", "label": "Table I fits at 0.1 kg"},
    {"from": "cypselurus", "to": "C", "kind": "informs_design", "label": "Table I fits at 0.1 kg"},
    {"from": "potanichthys", "to": "C", "kind": "convergent_analogy", "label": "same configuration, unrelated lineage"},
    {"from": "A", "to": "B", "kind": "conjectured_route",
     "label": "conjecture only: not demonstrated, not claimed reachable"},
    {"from": "A", "to": "C", "kind": "conjectured_route",
     "label": "conjecture only: not demonstrated, not claimed reachable"},
]

STYLE = {
    "phylogeny_sourced": dict(color="#2b6cb0", ls="-", lw=1.6),
    "informs_design": dict(color="#555555", ls="-", lw=1.0),
    "convergent_analogy": dict(color="#8a6d00", ls=":", lw=1.4),
    "conjectured_route": dict(color="#c0392b", ls="--", lw=1.6),
}
POS = {"hemiramphidae": (0, 4), "oxyporhamphus": (0, 2.8), "exocoetus": (0, 1.6), "cypselurus": (0, 0.4),
       "zebrafish": (0, 6.4), "daane_s1a": (0, 5.2), "potanichthys": (0, -0.8), "A": (2.6, 4.4), "B": (2.6, 2.2), "C": (2.6, 0.2)}
FILL = {"extant": "#e3eefa", "experimental": "#eef7e3", "fossil": "#f6eedc", "engineered": "#fbe6e3"}


def graph_json() -> dict:
    return {"schema": "frontier.print.species_graph/1", "nodes": NODES, "edges": EDGES,
            "rules": ["engineered forms are not organisms or ancestors",
                      "conjectured_route edges are hypotheses with no demonstration; they are drawn dashed red",
                      "phylogeny_sourced edges are the only phylogenetic statements, with their read level",
                      "two- vs four-wing design is functional, not phylogenetic (Fish 1990 p.398)",
                      "an experimental node with no edge informs no geometry"]}


def render_graph(path) -> None:
    fig, ax = plt.subplots(figsize=(9.5, 7.2), dpi=110)
    for e in EDGES:
        (x0, y0), (x1, y1) = POS[e["from"]], POS[e["to"]]
        st = STYLE[e["kind"]]
        rad = 0.35 if e["kind"] == "conjectured_route" else 0.0
        ax.add_patch(FancyArrowPatch((x0 + 0.9, y0), (x1 - 0.9, y1) if x1 != x0 else (x1 + 0.9, y1),
                                     connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>", mutation_scale=10,
                                     color=st["color"], linestyle=st["ls"], linewidth=st["lw"]))
    for n in NODES:
        x, y = POS[n["id"]]
        ax.text(x, y, n["label"], ha="center", va="center", fontsize=7.2,
                bbox=dict(boxstyle="round,pad=0.35", fc=FILL[n["group"]], ec="#666666", lw=0.6))
    ax.text(0, 7.3, "Sourced analogues (extant, experimental, fossil)", ha="center", fontsize=9, weight="bold")
    ax.text(2.6, 7.3, "Engineered props (this repository)", ha="center", fontsize=9, weight="bold")
    handles = [plt.Line2D([0], [0], **{k: v for k, v in STYLE[k2].items() if k in ("color", "lw")},
                          linestyle=STYLE[k2]["ls"], label=k2.replace("_", " ")) for k2 in STYLE]
    ax.legend(handles=handles, loc="lower center", fontsize=7, ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.06))
    ax.set_xlim(-1.2, 3.8); ax.set_ylim(-1.6, 7.7); ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, metadata={"Software": None})
    plt.close(fig)
