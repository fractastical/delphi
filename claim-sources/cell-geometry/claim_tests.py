# /// script
# requires-python = ">=3.10"
# dependencies = ["scipy"]
# ///
"""Write test-data/claim-tests/thompson-growth-form/... result.json files from results/summary.json.

Every number comes from summary.json (written by analyze.py). Verdict rules are stated
in each file's pass/fail criteria; they were written after the data were seen, so each
result is marked exploratory (not pre-registered).

    uv run claim-sources/cell-geometry/claim_tests.py
"""
import json
from pathlib import Path

from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "test-data" / "claim-tests" / "thompson-growth-form"
S = json.loads((HERE / "results" / "summary.json").read_text())
SOURCES = json.loads((HERE / "inputs" / "sources.json").read_text())
CTRL = S["controls"]
USED = {k: v for k, v in S["images"].items() if "excluded" not in v and v["sufficient"]}
NOT_USED = {k: v.get("excluded") or f"only {v['junctions_measured']} measurable junctions (minimum 30)"
            for k, v in S["images"].items() if "excluded" in v or not v["sufficient"]}
AGENT = {"kind": "local-agent", "model": "claude-opus-5.5", "run": "cursor local session, claim-sources/cell-geometry/", "date": "2026-10-31"}

PREREG_NOTE = ("Exploratory, not pre-registered: the images were segmented and inspected before the "
               "pass criterion was written. Treat the verdict as hypothesis-generating; a "
               "pre-registered replication on new images is needed before it counts as a test.")


def datasets():
    out = []
    for k in USED:
        m = SOURCES[k]
        out.append({
            "id": f"wikimedia-commons-{k}",
            "name": f"{m['commons_file'][5:]} (Wikimedia Commons)",
            "landing_url": m["source_page"],
            "doi": None,
            "version": "Commons thumbnail retrieved " + m["retrieved_at"][:10],
            "license": m["license"],
            "files": [{"download_url": m["download_url"], "retrieved_at": m["retrieved_at"],
                       "byte_size": m["download_bytes"], "sha256": m["download_sha256"]}],
            "role": f"{m['species'] or 'species not stated'}, {m['tissue']}",
        })
    return out


def common(claim_id):
    return {
        "claim_id": claim_id,
        "claim_iri": f"https://w3id.org/delphi/resource/claim/{claim_id}",
        "project": "thompson-growth-form",
        "status": "complete",
        "preregistered": False,
        "planned_datasets": [],
        "datasets": datasets(),
        "method": ("Cells in each image were segmented with Cellpose CPSAM v2 on the Nebius Scientific AI "
                   "Platform (claim-sources/cell-geometry/segment.py; operation IDs and model checksum in "
                   "claim-sources/cell-geometry/results/<image>/cellpose.json). claim-sources/cell-geometry/analyze.py closes inter-cell gaps, "
                   "finds points where three or more cells meet, estimates each wall's direction from wall pixels "
                   "0.08-0.25 median cell diameters from the junction, counts neighbours of cells fully surrounded "
                   "by segmented cells, and runs the same measurement on three synthetic tilings (hexagonal "
                   "lattice, brick wall, random Voronoi) as calibration."),
        "agent": AGENT,
    }


def per_tissue(keys):
    return {k: {x: USED[k].get(x) for x in keys} | {"species": USED[k]["species"]} for k in USED}


def ch07_04():
    r = common("thompson1917-ch07-04")
    rv = CTRL["random-voronoi"]
    near = [k for k, v in USED.items() if v["angle_sd"] < rv["angle_sd"] and v["frac_T_like"] < rv["frac_T_like"]]
    far = [k for k in USED if k not in near]
    r.update({
        "hypothesis": "If tissue cell walls meet three at a time at 120 degrees regardless of cell size, junction angles in real tissues cluster near 120 degrees more tightly than in a random partition of the plane, T-shaped junctions are rare, four cells do not meet at one point, and angle deviation does not depend on cell size.",
        "pass_criterion": f"{PREREG_NOTE} A tissue conforms if its junction-angle SD and its fraction of T-like junctions (largest angle >= 160 deg) are both below the random-Voronoi control. Supports if every usable tissue conforms; mixed if some do and some do not; refutes if none do.",
        "fail_criterion": "Refutes if no tissue has both an angle SD and a T-junction fraction below the random-Voronoi control.",
        "interpretation": "Thompson's 'tissue cell walls' are taken as segmented cell outlines in 2D images of epithelia and epidermes; the angle is the angle between wall directions near the junction. The compound eye is included as a packing of ommatidia, not of single cells.",
        "measured": {
            "value": len(near), "unit": "tissues (of those usable) whose junction-angle SD and T-junction fraction are both below the random-Voronoi control",
            "n": len(USED), "uncertainty": "one image per tissue",
            "extra": {
                "conforming": near, "non_conforming": far,
                "per_tissue": per_tissue(["junctions_measured", "angle_sd", "frac_all_within_15deg", "frac_T_like", "fourfold_or_more_fraction", "size_vs_dev_spearman"]),
                "controls": {k: {x: v[x] for x in ["angle_sd", "frac_T_like", "fourfold_or_more_fraction", "size_vs_dev_spearman"]} for k, v in CTRL.items()},
                "not_used": NOT_USED,
            },
        },
        "verdict": "supports" if not far else ("refutes" if not near else "mixed"),
        "confidence": 0.6,
        "caveats": [
            PREREG_NOTE,
            "One image per tissue, all from Wikimedia Commons; tissues were chosen by availability, not sampled.",
            "Four-way junction fractions are upper bounds: the random-Voronoi control, which has no true four-way vertices, scores 8.6% because close three-way junctions merge.",
            "Weak negative size-deviation correlations in some tissues also appear in the random control, so they are attributed to measurement noise in small cells.",
            "The Drosophila eye image is an SEM of a curved surface; projection distorts its angles.",
        ],
    })
    return r


def ch07_08():
    r = common("thompson1917-ch07-08")
    cv = [USED[k]["area_cv"] for k in USED]
    f6 = [USED[k]["frac_hexagons"] for k in USED]
    rho, p = stats.spearmanr(cv, f6)
    within = {k: USED[k]["local_size_het_vs_nonhex_spearman"] for k in USED}
    r.update({
        "hypothesis": "If hexagons are regular only where cells are equal in size, tissues with more uniform cell areas have a larger fraction of six-sided cells, and within a tissue cells in more size-heterogeneous neighbourhoods depart more from six sides.",
        "pass_criterion": f"{PREREG_NOTE} Supports if Spearman rho between tissue area CV and fraction of six-sided interior cells is <= -0.7 across usable tissues; mixed if between -0.7 and 0; refutes if >= 0.",
        "fail_criterion": "Refutes if the across-tissue rho is >= 0.",
        "interpretation": "Tests the size-uniformity part only; 'forces uniform' is not measured. This is a second, multi-tissue attempt; the pre-registered within-RPE test of the same claim is test-data/claim-tests/thompson-growth-form/thompson1917-ch07-08/result.json.",
        "measured": {
            "value": round(float(rho), 3), "unit": "Spearman rho, tissue area CV vs fraction of six-sided interior cells",
            "n": len(USED), "uncertainty": f"p = {p:.3g}",
            "extra": {
                "per_tissue": per_tissue(["interior_cells", "area_cv", "frac_hexagons", "neighbour_variance_mu2"]),
                "within_tissue_local_size_heterogeneity_vs_abs_sides_minus_6": within,
                "random_voronoi_control": {x: CTRL["random-voronoi"][x] for x in ["area_cv", "frac_hexagons", "local_size_het_vs_nonhex_spearman"]},
                "not_used": NOT_USED,
            },
        },
        "verdict": "supports" if rho <= -0.7 else ("refutes" if rho >= 0 else "mixed"),
        "confidence": 0.5,
        "caveats": [
            PREREG_NOTE,
            f"Only {len(USED)} tissues; the across-tissue correlation rests on five points.",
            "The random-Voronoi control shows the same within-image relation, so the result is a property of space-filling partitions in general and says nothing about forces.",
        ],
    })
    return r, float(p)


def ch07_10():
    r = common("thompson1917-ch07-10")
    means = {k: USED[k]["mean_neighbours"] for k in USED}
    close = [k for k, v in means.items() if abs(v - 6) <= 0.1]
    r.update({
        "hypothesis": "If close-packed cells of varying size are on average hexagonal, the mean number of neighbours of fully surrounded cells is 6.",
        "pass_criterion": f"{PREREG_NOTE} A tissue conforms if its mean neighbour number is within 0.1 of 6. Supports if most usable tissues conform.",
        "fail_criterion": "Refutes if most usable tissues have a mean neighbour number more than 0.1 from 6.",
        "interpretation": "Thompson's example is coral corallites; this tests the same statement on plant and animal cell sheets. Euler's formula forces a mean of 6 for any large planar tiling with three cells at every vertex, so agreement confirms the claim without testing a biological mechanism.",
        "measured": {
            "value": len(close), "unit": "usable tissues with mean neighbour number within 0.1 of 6",
            "n": len(USED), "uncertainty": "one image per tissue",
            "extra": {"per_tissue": per_tissue(["interior_cells", "mean_neighbours", "lewis_area_vs_sides_spearman"]),
                      "random_voronoi_control_mean_neighbours": CTRL["random-voronoi"]["mean_neighbours"],
                      "not_used": NOT_USED},
        },
        "verdict": "supports" if len(close) > len(USED) / 2 else "refutes",
        "confidence": 0.8,
        "caveats": [
            PREREG_NOTE,
            "A mean of 6 is a topological necessity for trivalent planar tilings (Euler), reproduced by the random-Voronoi control; it is not evidence for any biological mechanism.",
            "Grass epidermis falls short of 6, most likely because unsegmented stomata and hairs hide some neighbours.",
            "Corallites, Thompson's own example, were not tested.",
        ],
    })
    return r


def main():
    r04, (r08, p08), r10 = ch07_04(), ch07_08(), ch07_10()
    for r, path in [(r04, OUT / "thompson1917-ch07-04"), (r08, OUT / "thompson1917-ch07-08" / "cellpose-multi-tissue"), (r10, OUT / "thompson1917-ch07-10")]:
        path.mkdir(parents=True, exist_ok=True)
        (path / "result.json").write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n")
        print(path.relative_to(ROOT), r["verdict"], r["measured"]["value"])


if __name__ == "__main__":
    main()
