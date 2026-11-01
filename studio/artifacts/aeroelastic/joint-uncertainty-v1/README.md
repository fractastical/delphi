# Coupled FEM–VLM–descent scenario envelope

The frozen protocol is `protocol.json` (SHA-256 `817c7ac4da8a05c6f5f70beb9569398547f0defcd6aa34560f662955e6679d49`). The full computed run is `assay-v1/`; machine-readable output ports for assurance integration are in `assay-v1/output-ports.json`.

## Run record

- Protocol rows: 3 deterministic shared stress scenarios × 2 structural pressure policies × 2 VLM meshes × 3 coupling arms = 36 arm rows.
- Returned: 36/36 valid for this declared computational transfer; 0 failed, partial, unconverged, or model-domain-exit rows.
- Runtime: 85.05 s; output bytes: 16,195,996; output cap: 50,000,000 bytes.
- Environment: Python 3.13.12, NumPy 2.5.4, SciPy 1.17.1, CPU. No GPU or external provider calls; billing is unavailable (`dollars: null`).
- The assay ran as one serial Python worker with `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, inside a systemd scope with 4 GiB memory, swap disabled, 128-task limit, and 1,200 s runtime limit. The existing VLM/beam/glide code was reused.
- CPU quota was not enforced as a cgroup setting and full-run CPU utilization was not captured. A live `ps` sample during the exact-pin six-row pilot showed the worker at 186% CPU at one instant (less than two cores); this is a sample, not a peak-utilization receipt.
- Result SHA-256: `dabe32ff83309650bd0657a8b5918ed0432d75e8d5fa2624ec92657577ca97ec`.
- Receipt SHA-256: `e25556d53cdfb73259e00a728e535355f9269083544189181eeb84c4d32aeb6f`.

The protocol’s low-demand, nominal, and high-demand rows are assumptions, not a probability distribution or measured fish parameter uncertainty. EI, pressure/load, mass, and CD0 were co-varied by the frozen table. Unknown torsion, anisotropy, empirical aerodynamic coefficients, and cellular/genetic-to-fin calibration remain unknown.

## Selected paired results

Signed `two-way-static-feedback − rigid` effects at the main mesh under updated deformed-geometry pressure were:

| Assumed shared scenario | ΔCL | Δdescent range |
|---|---:|---:|
| Low demand | −0.000677006958 | −0.0565547 m |
| Nominal | −0.001336523277 | −0.122554 m |
| High demand | −0.002610707281 | −0.258161 m |

Under the frozen rigid-geometry pressure policy, paired ΔCL was exactly zero for these arms because the panel-force distribution was held fixed. This is a model-policy comparison, not evidence that a fish experiences either pressure field.

For the nominal updated-pressure feedback-minus-rigid paired ΔCL, the main-minus-fine mesh discrepancy was `+7.37343561e-6`; this is reported as a descriptive resolution estimate, not a validated error bound. The existing 3% absolute-CL mesh gate and conservative force/moment/virtual-work ledger do not independently validate tiny paired effects. Feedback residuals, iteration counts, and main-versus-half-step descent differences are preserved in `results.json` and are numerical-resolution diagnostics only.

The outputs are computed by a bending-only equivalent-fin scaffold and a separate rigidized point-mass glide. They are not observations, fish-specific predictions, biological-success probabilities, or calibrated cross-scale transfer results.
