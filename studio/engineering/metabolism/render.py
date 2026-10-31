"""Render the v3 outputs as diagrams and an animation. Every number is read from the stored result files; nothing is interpolated or typed in.

  python render.py ARTIFACT_DIR     (needs matplotlib and ffmpeg)
"""
import csv, json, subprocess, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.animation import FuncAnimation, FFMpegWriter

BANNER = "ASSUMED medium (not published) · UPTAKE-UNCAPPED · generic Danio rerio GEM · steady-state FBA, no time · not fin- or tissue-specific"
BG, INK, MUTED, BLUE, ORANGE, RED = "#101418", "#e8edf2", "#8b98a5", "#4aa3df", "#f0a030", "#ff5a4d"


def load(d):
    r = json.load(open(d + "/metabolism_results.json"))
    fl = {x["reaction_id"]: x for x in csv.DictReader(open(d + "/flux_table_pfba_o2_20.csv"))}
    return r, fl, json.load(open(d + "/o2_source_diagnostic.json")), json.load(open(d + "/egc_test.json"))


def style(fig):
    fig.patch.set_facecolor(BG)
    fig.text(0.5, 0.985, BANNER, ha="center", va="top", color=ORANGE, fontsize=8.5, weight="bold")


def ax_style(ax):
    ax.set_facecolor(BG)
    for s in ax.spines.values(): s.set_color(MUTED)
    ax.tick_params(colors=INK); ax.xaxis.label.set_color(INK); ax.yaxis.label.set_color(INK); ax.title.set_color(INK)


def network(d, r, fl):
    f = lambda i: float(fl[i]["flux"])
    nodes = {  # id: (x, y, label, reaction ids shown) - the layout is hand-set, the numbers come from the table
        "glc": (0.08, 0.84, "glucose uptake", ["MAR09034"]), "hk": (0.08, 0.64, "hexokinase", ["MAR04394"]), "pk": (0.08, 0.44, "pyruvate kinase", ["MAR04358"]),
        "tca": (0.32, 0.64, "TCA: succinate-CoA ligase", ["MAR04152"]), "c1": (0.32, 0.44, "complex I", ["MAR06921"]), "c3": (0.32, 0.24, "complex III", ["MAR06918"]),
        "o2in": (0.58, 0.84, "O2 uptake (medium)", ["MAR09048"]), "o2gen": (0.58, 0.64, "O2 made internally", ["MAR04071"]), "c4": (0.58, 0.44, "complex IV (uses O2)", ["MAR06914"]), "atp": (0.58, 0.24, "ATP synthase", ["MAR06916"]),
        "b6": (0.86, 0.84, "pyridoxal uptake", ["MAR09400"]), "b6o": (0.86, 0.64, "pyridoxine secreted", ["MAR09144"]), "ara": (0.86, 0.44, "arachidonate uptake", ["MAR00568"]), "co2": (0.86, 0.24, "CO2 secreted", ["MAR09058"])}
    edges = [("glc", "hk"), ("hk", "pk"), ("pk", "tca"), ("tca", "c1"), ("c1", "c3"), ("c3", "c4"), ("c4", "atp"), ("o2in", "o2gen"), ("o2gen", "c4"), ("b6", "o2gen"), ("o2gen", "b6o"), ("ara", "tca"), ("c4", "co2")]
    fig, ax = plt.subplots(figsize=(13, 7.8)); style(fig); ax.set_facecolor(BG); ax.axis("off"); ax.set_xlim(-0.08, 1.08); ax.set_ylim(0.0, 1.0)
    pinned = {n for n, v in nodes.items() if abs(f(v[3][0])) >= 999.9}
    HW, HH = 0.1, 0.04
    def edge_point(cx, cy, tx, ty):                        # where the centre-to-centre line leaves the box, plus a small gap
        dx, dy = tx - cx, ty - cy; k = min(HW / abs(dx) if dx else 9, HH / abs(dy) if dy else 9) * 1.12
        return cx + dx * k, cy + dy * k
    for a_, b_ in edges:                                   # schematic links only: the numbers are in the boxes, nothing is computed between boxes
        (x1, y1, *_), (x2, y2, *_) = nodes[a_], nodes[b_]
        ax.add_patch(FancyArrowPatch(edge_point(x1, y1, x2, y2), edge_point(x2, y2, x1, y1), arrowstyle="-|>", mutation_scale=11, lw=1.3, color=BLUE, alpha=0.75))
    for n, (x, y, label, ids) in nodes.items():
        col = RED if n in pinned else MUTED
        ax.add_patch(FancyBboxPatch((x - HW, y - HH), 2 * HW, 2 * HH, boxstyle="round,pad=0.004,rounding_size=0.01", fc="#1b222a", ec=col, lw=2.2 if n in pinned else 1))
        ax.text(x, y + 0.014, label, ha="center", va="center", color=INK, fontsize=8.4, weight="bold")
        ax.text(x, y - 0.018, "%s  flux %s" % (ids[0], ("%+.4g" % f(ids[0]))), ha="center", va="center", color=RED if n in pinned else MUTED, fontsize=7.8)
    import textwrap
    cap = ("Source: flux_table_pfba_o2_20.csv (parsimonious FBA, O2 uptake limit 20, glucose cap 10; units assumed mmol/gDW/h). Arrows are schematic links between boxes, not computed flows; every number is a stored reaction flux. Red box = flux at the +-1000 bound.\n"
           "READ: O2 uptake is %.0f but complex IV runs at %.0f: the O2 balance of this table shows %s supplying O2 internally at %+.0f, next to the uncapped pyridoxal/pyridoxine exchanges. TCA runs at %.0f, far more than 10 glucose can feed; the solution also takes up arachidonate at %.0f. "
           "This is a flux pattern of the model under an uncapped medium, not a measurement of fish metabolism." % (-f("MAR09048"), f("MAR06914"), "MAR04071", f("MAR04071"), f("MAR04152"), -f("MAR00568")))
    ax.text(-0.07, 0.115, "\n".join(textwrap.fill(par, 165) for par in cap.split("\n")), color=INK, fontsize=8, va="top")
    ax.set_title("Zebrafish-GEM energy-flow network at the baseline solution", color=INK, fontsize=12, pad=22)
    fig.savefig(d + "/energy_flow_network.png", dpi=130, facecolor=BG); plt.close(fig)


def sweep(d, r, dg):
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.8)); style(fig)
    s = r["o2_sweep"]
    ax[0].plot([x["o2_uptake_limit"] for x in s], [x["biomass"] for x in s], "o-", color=BLUE); ax[0].set(xlabel="O2 uptake limit", ylabel="biomass objective flux", title="Oxygen sweep (as run)")
    ax[0].set_ylim(0, 0.4); ax[0].text(0.5, 0.06, "flat-ish: O2 is also made internally\n(see right panel)", transform=ax[0].transAxes, color=ORANGE, fontsize=8, ha="center")
    for lim, c in ((20, BLUE), (0, ORANGE)):
        t = [x for x in r["atp_tradeoff"] if x["o2_uptake_limit"] == lim]; ax[1].plot([x["forced_atp_hydrolysis"] for x in t], [x["biomass"] for x in t], "o-", color=c, label="O2 limit %d" % lim)
    ax[1].set(xlabel="forced ATP hydrolysis (MAR03964 lower bound)", ylabel="biomass objective flux", title="ATP maintenance vs growth"); ax[1].set_ylim(0, 0.4); ax[1].legend(facecolor=BG, labelcolor=INK, edgecolor=MUTED)
    labs, vals, cols = [], [], []
    for x in dg["results"]:
        labs.append("O2 limit %d\n%s" % (x["o2_uptake_limit"], "MAR04071\nblocked" if x["MAR04071_blocked"] else "MAR04071\nfree")); vals.append(max(x["biomass"], 0)); cols.append(RED if x["MAR04071_blocked"] else BLUE)
    ax[2].bar(range(4), vals, color=cols); ax[2].set_xticks(range(4)); ax[2].set_xticklabels(labs, fontsize=8); ax[2].set(ylabel="biomass objective flux", title="Diagnostic: block the internal O2 source"); ax[2].set_ylim(0, 0.4)
    for i, v in enumerate(vals): ax[2].text(i, v + 0.008, "%.3g" % v, ha="center", color=INK, fontsize=9)
    for a in ax: ax_style(a)
    fig.tight_layout(rect=(0, 0, 1, 0.95)); fig.savefig(d + "/o2_atp_sweep_diagram.png", dpi=125, facecolor=BG); plt.close(fig)


def animate(d, r, dg):
    s = r["o2_sweep"]; fig, ax = plt.subplots(1, 2, figsize=(10.8, 5.4), gridspec_kw={"width_ratios": [1.5, 1]}); style(fig)
    HOLD, N = 8, len(s)                                            # frames per stored sweep point; each point is an actual solve, nothing is interpolated
    bars = [(("blocked" if x["MAR04071_blocked"] else "free"), x["o2_uptake_limit"], max(x["biomass"], 0)) for x in dg["results"]]
    def draw(k):
        for a in ax: a.clear(); ax_style(a)
        i = min(k // HOLD, N - 1); done = k >= N * HOLD
        ax[0].plot([x["o2_uptake_limit"] for x in s[: i + 1]], [x["biomass"] for x in s[: i + 1]], "o-", color=BLUE)
        ax[0].plot([s[i]["o2_uptake_limit"]], [s[i]["biomass"]], "o", ms=13, color=ORANGE); ax[0].set(xlim=(-2, 52), ylim=(0, 0.4), xlabel="O2 uptake limit (assumed units)", ylabel="biomass objective flux", title="Stored sweep: one solve per point")
        ax[0].text(0.03, 0.9, "O2 limit %g\nbiomass %.4f\nglucose uptake %.3g\nO2 exchange %.3g" % (s[i]["o2_uptake_limit"], s[i]["biomass"], s[i]["glc_flux"], s[i]["o2_flux"]), transform=ax[0].transAxes, color=INK, fontsize=9, va="top")
        ax[1].set(ylim=(0, 0.4), title="Same medium, MAR04071 free vs blocked", ylabel="biomass objective flux")
        if done:
            for j, (lab, lim, v) in enumerate(bars): ax[1].bar(j, v, color=RED if lab == "blocked" else BLUE); ax[1].text(j, v + 0.008, "%.3g" % v, ha="center", color=INK, fontsize=8)
            ax[1].set_xticks(range(4)); ax[1].set_xticklabels(["O2 %d\n%s" % (l, b) for b, l, _ in bars], fontsize=7.5)
            ax[1].text(0.5, 0.93, "with the internal O2 source blocked,\ngrowth needs the O2 uptake", transform=ax[1].transAxes, color=ORANGE, fontsize=8.5, ha="center", va="top")
        else: ax[1].set_xticks([]); ax[1].text(0.5, 0.5, "diagnostic follows", transform=ax[1].transAxes, color=MUTED, ha="center")
    total = N * HOLD + 30
    anim = FuncAnimation(fig, draw, frames=total, interval=100)
    w = FFMpegWriter(fps=10, codec="libx264", extra_args=["-pix_fmt", "yuv420p", "-threads", "2", "-crf", "26"], metadata={"title": "Zebrafish-GEM O2 sweep (assumed medium, uptake-uncapped)"})
    anim.save(d + "/o2_sweep.mp4", writer=w, dpi=100); draw(total - 1); fig.savefig(d + "/o2_sweep_poster.png", dpi=110, facecolor=BG); plt.close(fig)


def main(d):
    import hashlib
    r, fl, dg, eg = load(d); network(d, r, fl); sweep(d, r, dg); animate(d, r, dg)
    sh = lambda n: hashlib.sha256(open(d + "/" + n, "rb").read()).hexdigest()
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration", "-of", "json", d + "/o2_sweep.mp4"], capture_output=True, text=True, check=True).stdout)["streams"][0]
    shown = ["MAR09034", "MAR04394", "MAR04358", "MAR04152", "MAR06921", "MAR06918", "MAR09048", "MAR04071", "MAR06914", "MAR06916", "MAR09400", "MAR09144", "MAR00568", "MAR09058"]
    man = {"banner": BANNER, "inputs": {n: sh(n) for n in ("metabolism_results.json", "flux_table_pfba_o2_20.csv", "o2_source_diagnostic.json", "egc_test.json")},
           "outputs": {n: sh(n) for n in ("energy_flow_network.png", "o2_atp_sweep_diagram.png", "o2_sweep.mp4", "o2_sweep_poster.png")},
           "network_fluxes_shown": {i: float(fl[i]["flux"]) for i in shown}, "arrows": "schematic links, not computed flows",
           "animation": {"fps": 10, "frames_per_sweep_point": 8, "sweep_points": len(r["o2_sweep"]), "interpolated": False, "ffprobe": probe, "bytes": len(open(d + "/o2_sweep.mp4", "rb").read())},
           "render_code_sha256": hashlib.sha256(open(__file__, "rb").read()).hexdigest(), "labels": ["ASSUMED", "UPTAKE-UNCAPPED", "no time", "not fin- or tissue-specific"]}
    json.dump(man, open(d + "/render_manifest.json", "w"), indent=1)
    print("rendered", d)

if __name__ == "__main__": main(sys.argv[1])
