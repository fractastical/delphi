"""Nebius CPU-job entry: pip-install numpy/scipy, run cpu_reference on inputs/pilot_cells.json with 4 processes, write to $COPS_OUT."""
import os, subprocess, sys
r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "numpy", "scipy"], capture_output=True, text=True)
print("pip rc", r.returncode, r.stderr[-300:], flush=True)
sys.exit(subprocess.call([sys.executable, "frontier_compute/cpu_reference.py", os.environ.get("CELLS", "inputs/pilot_cells.json"), os.environ["COPS_OUT"], "4"]))
