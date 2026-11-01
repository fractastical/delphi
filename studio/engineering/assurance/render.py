"""Categorical schematic from assurance states; no invented anatomy/error values."""
from html import escape


def regional_svg(result):
    nodes = {node["id"]: node for node in result["nodes"] if node["kind"] == "region"}
    colors = {"unknown": "#89949f", "partial_scoped": "#d7a651", "declared_simulation_fraction": "#48a8ca", "refused": "#cf7166"}
    shapes = {
        "body": '<ellipse cx="270" cy="180" rx="175" ry="40"/>',
        "pectoral-left": '<polygon points="210,165 160,50 290,150"/>',
        "pectoral-right": '<polygon points="210,195 160,310 290,210"/>',
        "pelvic-left": '<polygon points="335,162 340,100 390,169"/>',
        "pelvic-right": '<polygon points="335,198 340,260 390,191"/>',
        "caudal": '<polygon points="420,180 490,120 478,180 490,240"/>',
    }
    output = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1160 550" role="img" aria-labelledby="title desc">',
              '<title id="title">Regional assurance: numerical checks and unknown biological accuracy</title>',
              '<desc id="desc">Categorical UI schematic only. All target-fish empirical accuracy is unknown. Body and pectoral numerical models have scoped computational evidence.</desc>',
              '<rect width="1160" height="550" fill="#091820"/>',
              '<g font-family="sans-serif" fill="#e6edf1"><text x="35" y="38" font-size="25">Where the evidence reaches — and where it stops</text>',
              '<text x="35" y="68" font-size="14">Categorical assurance vector · not a biological-success probability or measured spatial error</text>']
    for offset, dimension, title in [(20, "empirical_validation", "Target-fish biological accuracy"), (590, "numerical_fidelity", "Scoped numerical model checks")]:
        output.append(f'<g transform="translate({offset},95)"><text x="30" y="20" font-size="19">{title}</text>')
        for region, shape in shapes.items():
            state = nodes[region]["vector"][dimension]["status"]
            label = escape(nodes[region]["label"] + ": " + state)
            output.append(f'<g fill="{colors.get(state, "#89949f")}" stroke="#dce8ec" stroke-width="1.5"><title>{label}</title>{shape}</g>')
        output.append('</g>')
    output += ['<text x="45" y="465" font-size="15" fill="#aab9c1">Gray: unknown target accuracy / no applicable checked model</text>',
               '<text x="45" y="490" font-size="15" fill="#d7a651">Amber: partial computational evidence; inspect assumptions and uncalibrated transfer</text>',
               '<text x="45" y="525" font-size="13">Named UI regions only, not specimen geometry. Source hashes, equation stacks, controls and gaps: map.json.</text></g></svg>']
    return "\n".join(output) + "\n"
