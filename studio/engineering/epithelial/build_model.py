"""Build an epithelial gap-closure CPM from Morpheus' pinned upstream Example-Protrusion.

Source XML is read from a pinned upstream blob, never from a working copy.
Every edit is a named string replacement that must match exactly once, or the build refuses.

This is NOT a reproduction of any published model. The geometric construction
(Voronoi monolayer, wound made by removing central cells, no proliferation) follows
Bai & Zeng 2023; their MECHANICS is 3D continuum finite-element with cohesive-zone
traction-separation laws, which a Cellular Potts Model does not implement and this
file does not claim to reproduce. CPM parameters come from the upstream example
(Niculescu, Textor & de Boer 2015 Act model) and are in model units, uncalibrated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

UPSTREAM = "https://gitlab.com/morpheus.lab/morpheus.git"
TAG = "v2.3.9"
XML_PATH = "Examples/CPM/Protrusion_2D.xml"
BASE_SHA256 = "da2a27c8e552041ee4a51d7ff1e7332466f5180762642c997594731c92737db2"
BINARY_URL = "https://gitlab.com/morpheus.lab/morpheus/-/package_files/178666119/download"
BINARY_SHA256 = "3d9a6e5a4cb86824b745500df1474596d39cce5deed24f767c0841df0f94d5ad"

# Declared scale mapping. Not a fit: mean cell area is set to 625 lattice nodes by
# construction (64 seeds on a 200x200 lattice), and equated to the mean cell area implied
# by the 26 um average cell diameter that Bai & Zeng 2023 take from experimental
# measurement. Everything else in the model stays in model units.
LATTICE = 200
NODES_TOTAL = LATTICE * LATTICE
NOMINAL_CELLS = 64
NODES_PER_CELL = NODES_TOTAL // NOMINAL_CELLS          # 625
CELL_DIAM_UM = 26.0                                    # Bai & Zeng 2023, Methods
CELL_AREA_UM2 = 3.141592653589793 * (CELL_DIAM_UM / 2) ** 2
NODE_AREA_UM2 = CELL_AREA_UM2 / NODES_PER_CELL         # ~0.84949 um^2
NODE_LEN_UM = NODE_AREA_UM2 ** 0.5                     # ~0.92168 um


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch_base(clone: Path) -> str:
    raw = subprocess.run(["git", "-C", str(clone), "show", f"{TAG}:{XML_PATH}"],
                         check=True, capture_output=True, text=True).stdout
    got = sha(raw.encode())
    if got != BASE_SHA256:
        raise SystemExit(f"refused: upstream {XML_PATH}@{TAG} sha256 {got}, pinned {BASE_SHA256}")
    return raw


def edits(arm: dict) -> list[tuple[str, str, str]]:
    """(name, old, new). Order is irrelevant; each old must occur exactly once."""
    wound = ""
    if arm["wound_r2"] > 0:
        wound = ('\n            <CellDeath name="wound"><Condition>time &lt; 1 and '
                 f'(cell.center.x-{LATTICE // 2})^2 + (cell.center.y-{LATTICE // 2})^2 '
                 f'&lt; {arm["wound_r2"]}</Condition></CellDeath>')
    population = f"""<CellPopulations>
        <Population type="amoeba" size="{NOMINAL_CELLS}">
            <InitDistribute number-of-cells="{NOMINAL_CELLS}" probability="1" mode="regular"/>
            <InitVoronoi/>
        </Population>
    </CellPopulations>"""
    return [
        ("stop-and-seed", '<StopTime value="15000"/>',
         f'<StopTime value="{arm["stop"]}"/>\n        <RandomSeed value="{arm["seed"]}"/>'),
        ("volume-constraint", '<VolumeConstraint target="2500" strength="50"/>',
         f'<VolumeConstraint target="{NODES_PER_CELL}" strength="{arm["lambda_v"]}"/>'),
        ("surface-constraint", '<SurfaceConstraint target="1" strength="5" mode="aspherity"/>',
         f'<SurfaceConstraint target="1" strength="{arm["lambda_s"]}" mode="aspherity"/>'),
        ("protrusion-strength", '<Protrusion field="act" strength="80" maximum="200"/>',
         f'<Protrusion field="act" strength="{arm["protrusion"]}" maximum="200"/>'),
        ("contact-cell-medium", '<Contact type1="amoeba" type2="medium" value="140"/>',
         f'<Contact type1="amoeba" type2="medium" value="{arm["j_cell_medium"]}"/>'),
        ("mcs-duration", '<MCSDuration value="1"/>', f'<MCSDuration value="{arm["mcs"]}"/>'),
        ("wound-by-cell-death", '<ConnectivityConstraint/>',
         f'<ConnectivityConstraint/>{wound}'),
        ("confluent-monolayer", "__POPULATION__", population),
        ("log-volume-and-surface",
         '                <Symbol symbol-ref="cell.center.y"/>\n            </Input>',
         '                <Symbol symbol-ref="cell.center.y"/>\n'
         '                <Symbol symbol-ref="cell.volume"/>\n'
         '                <Symbol symbol-ref="cell.surface"/>\n            </Input>'),
        ("log-one-file", '<TextOutput file-separation="cell"/>', '<TextOutput/>'),
        ("log-interval", '<Logger time-step="10">', f'<Logger time-step="{arm["log_step"]}">'),
        # gnuplot is absent on the preflight host; spatial frames come from TiffPlotter,
        # which writes the actual CPM lattice rather than a re-drawing of logged numbers.
        ("spatial-frames-without-gnuplot", '<ModelGraph format="svg" include-tags="#untagged" reduced="false"/>',
         f'<TiffPlotter format="guess" timelapse="true" compression="true" time-step="{arm["frame_step"]}">\n'
         '            <Channel symbol-ref="cell.id" exclude-medium="false"/>\n'
         '        </TiffPlotter>'),
    ]


def build(base: str, arm: dict) -> tuple[str, list[str]]:
    # The population block is matched as a whole span, so it is substituted in first
    # against a sentinel to keep every other edit a plain exactly-once replacement.
    lo, hi = base.index("<CellPopulations>"), base.index("</CellPopulations>") + len("</CellPopulations>")
    xml = base[:lo] + "__POPULATION__" + base[hi:]
    names = []
    for name, old, new in edits(arm):
        n = xml.count(old)
        if n != 1:
            raise SystemExit(f"refused: edit {name!r} matches {n} times (need exactly 1)")
        xml = xml.replace(old, new)
        names.append(name)
    return xml, names


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clone", required=True)
    ap.add_argument("--arm-json", required=True, help="one arm dict from the frozen protocol")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    arm = json.loads(Path(a.arm_json).read_text()) if Path(a.arm_json).exists() else json.loads(a.arm_json)
    base = fetch_base(Path(a.clone))
    xml, names = build(base, arm)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "model.xml").write_text(xml)
    (out / "build.json").write_text(json.dumps({
        "arm": arm, "upstream": UPSTREAM, "tag": TAG, "xml_path": XML_PATH,
        "base_sha256": BASE_SHA256, "model_sha256": sha(xml.encode()), "edits": names,
        "binary_url": BINARY_URL, "binary_sha256": BINARY_SHA256,
        "scale": {"node_area_um2": NODE_AREA_UM2, "node_length_um": NODE_LEN_UM,
                  "nodes_per_cell": NODES_PER_CELL, "lattice_nodes": NODES_TOTAL,
                  "lattice_um": LATTICE * NODE_LEN_UM,
                  "basis": "mean cell area set to 625 nodes by construction, equated to the area of a "
                           "26 um diameter disc (Bai & Zeng 2023 Methods, experimental cell size ref 45)"},
    }, indent=1))
    print(arm["name"], sha(xml.encode())[:12], len(names), "edits")


if __name__ == "__main__":
    main()
