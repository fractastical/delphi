"""Explicitly posthoc descriptive paired-effect and rigid-constraint diagnostics."""

from hashlib import sha256
import json
from pathlib import Path

import numpy as np

from .model import ART, GEOM, dump, protocol


def run():
    p = protocol()
    summary = json.loads((ART / "production/summary.json").read_text())
    audit = json.loads((ART / "production-audit.json").read_text())
    if not audit["source_identity_passed"] or not audit["fixed_roundoff_reproduction"]:
        raise ValueError("Production audit failed")
    arms = {x["id"]: x for c in summary["contexts"] for x in c["arms"]}
    pairs = []
    moments = []
    for context in summary["contexts"]:
        compliance, speed = context["compliance"], context["speed_m_s"]
        for label, first, second in [
            ("one_way_minus_rigid", "rigid", "one-way-frozen-load"),
            ("two_way_minus_one_way", "one-way-frozen-load", "two-way-static-feedback"),
            ("two_way_minus_rigid", "rigid", "two-way-static-feedback"),
        ]:
            row = {
                "compliance": compliance,
                "speed_m_s": speed,
                "comparison": label,
                "meshes": {},
            }
            for mesh in ["main", "fine"]:
                old, new = [
                    arms[f"chi{compliance}-u{speed:g}-{mesh}-{arm}"]
                    for arm in [first, second]
                ]
                if not (
                    old["valid_for_declared_transfer"]
                    and new["valid_for_declared_transfer"]
                ):
                    row["meshes"][mesh] = {"available": False}
                    continue
                a, b = [
                    x["iterations"][-1]["CL_on_fixed_source_area"] for x in [old, new]
                ]
                delta = b - a
                row["meshes"][mesh] = {
                    "available": True,
                    "delta_CL": delta,
                    "delta_CL_over_rigid_CL": delta
                    / arms[f"chi{compliance}-u{speed:g}-{mesh}-rigid"]["iterations"][
                        -1
                    ]["CL_on_fixed_source_area"],
                    "delta_range_m_under_assumed_fixed_alpha_release": new["flight"][
                        "main"
                    ]["range_m"]
                    - old["flight"]["main"]["range_m"],
                    "abs_delta_CL_over_fixed_point_tolerance": abs(delta)
                    / p["gates"]["fixed_point_CL_absolute_change_max"],
                }
            if all(x["available"] for x in row["meshes"].values()):
                main, fine = [row["meshes"][m] for m in ["main", "fine"]]
                row["main_over_fine_delta_CL"] = (
                    main["delta_CL"] / fine["delta_CL"] if fine["delta_CL"] else None
                )
                row["main_over_fine_delta_range"] = (
                    main["delta_range_m_under_assumed_fixed_alpha_release"]
                    / fine["delta_range_m_under_assumed_fixed_alpha_release"]
                    if fine["delta_range_m_under_assumed_fixed_alpha_release"]
                    else None
                )
                row["signs_agree"] = bool(
                    np.sign(main["delta_CL"]) == np.sign(fine["delta_CL"])
                )
            pairs.append(row)
    source = json.loads((GEOM / "panels.json").read_text())["fins"]
    for arm in arms.values():
        if not arm.get("iterations"):
            continue
        for name, ledger in arm["iterations"][-1]["transfer"].items():
            eu = np.asarray(source[name]["fin_plane"]["e_u"])
            ew = np.asarray(source[name]["fin_plane"]["e_w"])
            n = np.cross(ew, eu)
            n *= 1 if n[2] >= 0 else -1
            axis = np.cross(eu, n)
            moment = np.asarray(ledger["total_moment_root_world_Nm"])
            constraint = np.asarray(ledger["constraint_moment_root_world_Nm"])
            force = np.asarray(ledger["total_force_world_N"])
            reaction = np.asarray(ledger["constraint_force_world_N"])
            bend = float(moment @ axis)
            torsion = float(constraint @ eu)
            moments.append(
                {
                    "arm_id": arm["id"],
                    "fin": name,
                    "bending_moment_Nm": bend,
                    "constraint_torsion_Nm": torsion,
                    "signed_torsion_over_bending": torsion / bend if bend else None,
                    "axial_constraint_force_N": float(reaction @ eu),
                    "signed_axial_constraint_fraction": float(reaction @ eu)
                    / max(float(np.linalg.norm(force)), 1e-30),
                    "constraint_force_norm_fraction": float(np.linalg.norm(reaction))
                    / max(float(np.linalg.norm(force)), 1e-30),
                    "initial_dihedral_deg": float(np.rad2deg(np.arcsin(eu[2]))),
                }
            )
    release = []
    from engineering.simulation.schema import G

    for arm in arms.values():
        if not arm.get("flight"):
            continue
        meta = arm["flight"]["main"]
        series = np.load(ART / "production" / arm["id"] / "glide-main.npz")
        speed = series["state_x_h_V_gamma"][:, 2]
        release.append(
            {
                "arm_id": arm["id"],
                "lift_over_weight_release": 0.5
                * p["parameters"]["rho_kg_m3"]
                * speed[0] ** 2
                * meta["reference_area_m2"]
                * meta["CL_fixed"]
                / (p["glide"]["mass_kg"] * G),
                "last_saved_dynamic_pressure_over_release": float(
                    (speed[-1] / speed[0]) ** 2
                ),
                "last_actual_saved_time_s": float(series["time_s"][-1]),
                "native_descent_contact_time_s": meta["time_s"],
            }
        )
    powers = []
    for speed in p["parameters"]["airspeeds_m_s"]:
        for mesh in ["main", "fine"]:
            values = [
                next(
                    row
                    for row in pairs
                    if row["comparison"] == "one_way_minus_rigid"
                    and row["speed_m_s"] == speed
                    and row["compliance"] == c
                )
                for c in p["parameters"]["compliance_design_values"]
            ]
            if all(
                row["meshes"][mesh]["available"] and row["meshes"][mesh]["delta_CL"]
                for row in values
            ):
                exponent = float(
                    np.polyfit(
                        np.log(p["parameters"]["compliance_design_values"]),
                        np.log(
                            [abs(row["meshes"][mesh]["delta_CL"]) for row in values]
                        ),
                        1,
                    )[0]
                )
                powers.append(
                    {
                        "speed_m_s": speed,
                        "mesh": mesh,
                        "descriptive_loglog_exponent_abs_deltaCL_vs_compliance": exponent,
                        "scope": "Posthoc three-point descriptor; not a convergence rate or material law",
                    }
                )
    result = {
        "schema": "frontier.aeroelastic.posthoc-diagnostics/1",
        "analysis_status": "DESCRIPTIVE POSTHOC; no new acceptance gate",
        "paired_effects": pairs,
        "constraint_moments_and_forces": moments,
        "three_point_effect_descriptors": powers,
        "fixed_shape_release_diagnostics": release,
        "native_lattice_gates": [
            row for c in summary["contexts"] for row in c["paired_refinement"]
        ],
        "review": {
            "path": "artifacts/aeroelastic/independent-review-claude07.md",
            "sha256": sha256(
                (ART / "independent-review-claude07.md").read_bytes()
            ).hexdigest(),
            "B1": "Ledger force/moment/virtual-work identities hold by construction; bookkeeping gates only detect an overridden normal vector, not wrong station/frame/scaling. Not independent transfervalidation.",
            "B2": "Absolute3%CL mesh gate cannot establish paired effects smaller than it. Deltas/ratios and fixed-point tolerance multiples are descriptive, no posthoc criterion replaces protocol.",
            "scope": "Bending-only torsion-rigid scaffold; no pitchtrim, viscousdrag or calibrated fin/glide performance. Release-mass/drag assumptions control descent.",
        },
        "summary_sha256": sha256(
            (ART / "production/summary.json").read_bytes()
        ).hexdigest(),
        "audit_sha256": sha256(
            (ART / "production-audit.json").read_bytes()
        ).hexdigest(),
        "analysis_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    dump(ART / "production-diagnostics.json", result)
    plot(result)
    print(
        "lattice gates",
        sum(x["lattice_gate_passed"] for x in result["native_lattice_gates"]),
        "/",
        len(result["native_lattice_gates"]),
    )
    for row in pairs:
        if row["compliance"] == 0.2 and row["speed_m_s"] == 20:
            print(row)
    print("power descriptors", powers)


def plot(result):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.8), layout="constrained")
    for speed, color in [(16.0, "#168aad"), (20.0, "#c44536")]:
        for mesh, style in [("main", "--o"), ("fine", "-s")]:
            for axis, comparison, sign in [
                (axes[0], "one_way_minus_rigid", -1),
                (axes[1], "two_way_minus_one_way", 1),
            ]:
                rows = sorted(
                    [
                        x
                        for x in result["paired_effects"]
                        if x["speed_m_s"] == speed and x["comparison"] == comparison
                    ],
                    key=lambda x: x["compliance"],
                )
                axis.loglog(
                    [x["compliance"] for x in rows],
                    [sign * x["meshes"][mesh]["delta_CL"] for x in rows],
                    style,
                    color=color,
                    label=f"{speed:g}m/s {mesh}",
                )
    axes[0].set(
        xlabel="Declared compliance (1)",
        ylabel="CL rigid − one-way (1)",
        title="Paired bending-only differences",
    )
    axes[1].axhline(
        protocol()["gates"]["fixed_point_CL_absolute_change_max"],
        color="black",
        linestyle=":",
        label="Frozen iteration tolerance",
    )
    axes[1].set(
        xlabel="Declared compliance (1)",
        ylabel="CL two-way − one-way (1)",
        title="Feedback increment versus tolerance",
    )
    axes[0].legend(fontsize=7)
    axes[1].legend(fontsize=7)
    rows = [
        x
        for x in result["constraint_moments_and_forces"]
        if x["arm_id"] == "chi0.2-u20-fine-two-way-static-feedback"
    ]
    axes[2].bar(
        range(len(rows)),
        [abs(x["signed_torsion_over_bending"]) for x in rows],
        color="#647b8e",
    )
    axes[2].set_xticks(
        range(len(rows)),
        [x["fin"].replace("pectoral", "pect").replace("pelvic", "pelv") for x in rows],
        rotation=25,
        fontsize=8,
    )
    axes[2].set(
        ylabel="|constraint torsion / bending| (1)",
        title="Unmodeled finite torsional compliance",
    )
    fig.suptitle(
        "POSTHOC descriptive diagnostics • torsion-rigid scaffold • no new acceptance gate",
        fontsize=13,
    )
    path = ART / "production-paired-effects.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    dump(
        ART / "production-paired-effects.provenance.json",
        {
            "source_sha256": sha256(
                (ART / "production-diagnostics.json").read_bytes()
            ).hexdigest(),
            "code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "output_sha256": sha256(path.read_bytes()).hexdigest(),
            "scope": "Posthoc descriptive plot of actual model values, not experimental evidence or a new pass threshold",
        },
    )


if __name__ == "__main__":
    run()
