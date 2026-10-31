"""Write artifacts/fin-patch: protocol.json (frozen case), reference.json, poster.png, manifest.json.

    python -m engineering.coupled_mechanics.fin_patch_run artifacts/fin-patch
"""
from __future__ import annotations

import hashlib
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

from . import fin_geometry as fg
from . import fin_patch as fpch
from . import thin_airfoil as ta

PKG = Path(__file__).resolve().parent


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build(g):
    ref = ta.reference(g)
    two_d = ta.reference(g, lifting_line=False)
    rec = ta.record(ref, g)
    tgt = fpch.member_target(g)
    tr = fpch.transfer_load(rec, tgt)
    attempts = {}
    for name, t in (("whole_fin_3d_target", fpch.member_target(g, claim="whole_fin_3d")),):
        try:
            fpch.transfer_load(rec, t)
            attempts[name] = {"verdict": "accepted", "note": "analytic records are not dimensionality-gated"}
        except Exception as e:  # noqa: BLE001 - recorded, not swallowed
            attempts[name] = {"verdict": "refused", "detail": str(e)}
    gaps = [
        {"id": "G1-fan-width", "kind": "dimensional", **fpch.fan_width_gap(ref, tr)},
        {"id": "G2-section-not-3d", "kind": "cross-scale",
         "detail": "patch sections are 2D strips; finite span enters only via alpha_eff (elliptic lifting line, "
                   f"assumed; AR {ref['aspect']['AR']:.2f}); 2D bracket is {1/(ref['alpha_eff_rad']/ref['alpha_rad']):.2f}x larger"},
        {"id": "G3-leading-edge-singularity", "kind": "dimensional",
         "detail": "inviscid dCp ~ 1/sqrt(xi) at the leading edge, which IS ray 0; the strip load is finite but a "
                   "sampled strip under-counts it as sqrt(row width) (measured in tests); a resolved viscous "
                   "section has no singularity, so the reference is a bracket, not a target"},
        {"id": "G4-regime", "kind": "cross-scale",
         "detail": f"declared U {ta.DEFAULT_FLOW['U_m_s']['value']} m/s and alpha {ta.DEFAULT_FLOW['alpha_deg']['value']} deg are "
                   "unsourced; v3a pose has alpha 0 (fin plane contains the stream), so its own load is zero; "
                   "no free surface, body interference, dihedral flow or sweep correction beyond du = cos(lambda) ds"},
        {"id": "G5-thickness", "kind": "dimensional",
         "detail": "membrane 0.10 mm and ray_max 0.6 mm are assumed (components.json); taper unknown; the patch "
                   "therefore carries two declared variants rather than one geometry"},
        {"id": "G6-branched-rays", "kind": "cross-scale",
         "detail": "rays 1-14 branch; a straight Euler-Bernoulli member is not their geometry, so only ray 0 is a member"},
        {"id": "G7-structure-unknown", "kind": "cross-scale",
         "detail": "EI(x) and ray section (c, I) unknown and preserved: loads only, no deflection or stress"},
        {"id": "G8-global-cfd", "kind": "dimensional",
         "detail": "cfd3d v1 global flow carries the 0.10 mm membrane as a 3.7-cell shell at h 1.8-7.2 mm; its fin "
                   "jumps are smeared and are not used here (cfd3d's own refusal)"},
    ]
    reference = {"schema": "frontier.coupled.fin-patch-reference/1", "evidence_kind": "analytic",
                 "reference": {k: v for k, v in ref.items() if k != "L_exact"}, "L_exact": str(ref["L_exact"]),
                 "two_d_bracket_q_N_per_m": [st["q_true_N_per_m"] for st in two_d["stations"]],
                 "record": rec, "transfer": tr, "attempts": attempts, "gaps": gaps,
                 "verdict": ("ANALYTIC REFERENCE ONLY. The resolved patch has not run; ray-0 load from a "
                             "simulated flow remains BLOCKED until cfd3d returns resolved sections.")}
    return ref, reference


def render(g, ref, reference, out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fp = fg.fin_plane(g)
    outline = np.array([fg.to_plane(fp, p) for p in g["panels"]["outline_m"]])
    fig, ax = plt.subplots(1, 3, figsize=(16, 5.4), dpi=110)
    ax[0].fill(outline[:, 1] * 1e3, outline[:, 0] * 1e3, color="#e8eef6", ec="k", lw=0.6)
    for r in g["rays"]["rays"]:
        for pl in r["polylines_m"]:
            uw = np.array([fg.to_plane(fp, p) for p in pl])
            ax[0].plot(uw[:, 1] * 1e3, uw[:, 0] * 1e3, color="#d62728" if r["index"] == 0 else "#888", lw=1.6 if r["index"] == 0 else 0.5)
    for st in ref["stations"]:
        ax[0].plot([st["w_le_m"] * 1e3, st["w_aft_m"] * 1e3], [st["u_m"] * 1e3] * 2, color="#1f77b4", lw=0.8)
        ax[0].plot([st["w_le_m"] * 1e3, (st["w_le_m"] + st["xi_strip"] * st["chord_m"]) * 1e3], [st["u_m"] * 1e3] * 2,
                   color="#d4a000", lw=4)
    ax[0].set_aspect("equal")
    ax[0].set_xlabel("chordwise w = x - x0 [mm] (stream +x)")
    ax[0].set_ylabel("spanwise u [mm]")
    ax[0].set_title("v3a pectoral_L (candidate e8c2b666): ray 0 = leading edge (red)\n"
                    "patch sections (blue), ray-0 tributary strip (gold)", fontsize=9)

    mid = ref["stations"][2]
    xi = np.linspace(1e-4, 1, 600)
    ax[1].plot(xi, ta.dcp(xi, ref["alpha_eff_rad"]), color="k")
    m = xi <= mid["xi_strip"]
    ax[1].fill_between(xi[m], 0, ta.dcp(xi[m], ref["alpha_eff_rad"]), color="#d4a000", alpha=0.6)
    ax[1].set_ylim(0, 4)
    ax[1].set_xlabel("x / c")
    ax[1].set_ylabel("dCp (ventral - dorsal)")
    ax[1].set_title(f"ANALYTIC thin airfoil at s/L = 0.5, alpha_eff {np.degrees(ref['alpha_eff_rad']):.2f} deg\n"
                    f"ray-0 strip = {mid['xi_strip']*100:.1f}% of chord carries "
                    f"{mid['strip_fraction_of_section_lift']*100:.1f}% of section lift", fontsize=9)

    s = [float(Fraction(x)) for x in reference["transfer"]["s_m"]]
    ax[2].plot(s, [st["q_true_N_per_m"] for st in ref["stations"]], "-o", color="#d62728", label="strip load (local width)")
    ax[2].plot(s, reference["transfer"]["q_N_per_m"], "--s", color="#1f77b4", label="contract load (one declared width)")
    ax[2].plot(s, reference["two_d_bracket_q_N_per_m"], ":", color="#888", label="2D bracket (no lifting line)")
    gap = reference["gaps"][0]
    ax[2].set_title(f"ray-0 line load, declared U 5 m/s, alpha 5 deg (assumed)\n"
                    f"contract F / strip F = {gap['F_contract_over_strip']:.3f}, M ratio {gap['M_contract_over_strip']:.3f}",
                    fontsize=9)
    ax[2].set_xlabel("s along ray 0 [m]")
    ax[2].set_ylabel("q [N/m]")
    ax[2].legend(fontsize=8)
    fig.suptitle("Fin-patch case prepared; resolved run NOT executed. Analytic reference only; EI and ray section unknown",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(out / "poster.png")
    plt.close(fig)


def main(argv):
    out = Path(argv[1] if len(argv) > 1 else "artifacts/fin-patch")
    out.mkdir(parents=True, exist_ok=True)
    g = fg.load()
    proto = fpch.protocol(g)
    ref, reference = build(g)
    fpch.write_json(out / "protocol.json", proto)
    fpch.write_json(out / "reference.json", reference)
    render(g, ref, reference, out)
    code = {f"engineering/coupled_mechanics/{p.name}": _sha(p) for p in sorted(PKG.glob("*.py"))}
    inputs = {f"artifacts/fish3d/fish3d-v3a-fan/{k}": v for k, v in g["sha256"].items()}
    manifest = {"schema": "frontier.coupled.manifest/1",
                "outputs": {n: {"sha256": _sha(out / n), "byte_size": (out / n).stat().st_size}
                            for n in ("protocol.json", "reference.json", "poster.png")},
                "code_files": code, "inputs": inputs,
                "note": "protocol.json is frozen before any patch run; reference is analytic; poster is a render"}
    fpch.write_json(out / "manifest.json", manifest)
    print(proto["protocol_sha256"], manifest["outputs"])


if __name__ == "__main__":
    main(sys.argv)
