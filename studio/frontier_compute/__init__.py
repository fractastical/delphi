"""Frontier compute: GPU/CPU replication and numerical-sensitivity arms for the frozen NCA nonlinear-pattern sweep.

Vendored pinned sources live in frontier_compute/vendor (see SOURCE.md). Nothing here changes the frozen ensemble, outcome
definitions or criteria of scopedesk/oracles/nonlinear_sweep/PREREG.md. Evidence kind of every output: simulated (declared model).
"""
import sys
from pathlib import Path

VENDOR = Path(__file__).resolve().parent / "vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))
