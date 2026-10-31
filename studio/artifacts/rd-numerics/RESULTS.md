# Training-only RD discretization audit: simulations completed, auxiliary reproduction failed

Provider job `aijob-e00qzdzsh5mj8pvbd2` completed all five preregistered
configurations: N64/dt.02, N64/.01, N64/.005, N128/.005, N256/.005. Each contains
48 paired initial conditions from training settings0–15 and seedindices0,1,2,
with saved dimensionless model times50,100,150,200. No network was trained or
loaded and no held-out outcome was read. The frozen DDPM source/configuration,
preregistration and checkpoints were untouched. All values are model units;
this is a Schnakenberg solver audit, not calibrated fish biology.

All15 returned file hashes, executed-source hashes, input identities, native
shapes/masks and960 paired rows were independently checked. All960 native saved
snapshots (192perconfiguration) were finite, nonnegative and below the frozen
absolute1000 limit. No intermediate-state stability claim is made. Actual H100
float64/TF32off configuration wall times were4.01,7.96,15.85,15.87,15.89seconds;
the provider container work was63.3seconds, excluding image startup. The tiny
CPU/CUDA solver parity check was6.22e-15 against its unchanged1e-9 bound.

## Paired numerical differences, not error bounds

At tau200, over48 declared pairs perrow, the original cloud metrics are:

| Comparison | Median relative L2 u | Median relative L2 v | Maximum relative L2 u | Maximum relative L2 v |
|---|---:|---:|---:|---:|
|64/.02 to64/.01|0.0009751|0.0006144|0.0028190|0.0011234|
|64/.01 to64/.005|0.0002460|0.0001559|0.0006764|0.0002792|
|64/.005 to128/.005|2.93e-9|1.36e-10|2.85e-5|2.42e-6|
|128/.005 to256/.005|1.32e-12|5.11e-13|1.37e-11|5.69e-12|
|64/.02 to256/.005|0.0012210|0.0007703|0.0034950|0.0013932|

Fields were compared using the frozen analytic cosine projection onto the common
64-mode grid, without interpolation. The finest result is not an exact solution;
these discrepancies are not rigorous error bounds. The five-point axial design
does not estimate space×time interaction. First16 training settings do not bound
the whole prior or held-out accuracy. No convergence PASS was preregistered or
assigned. Empirical accuracy remains unknown. IC pairs share settings and are not
independent biological samples.

## Failed independent metric reproduction remains failed

The original bit-for-bit comparison was false. A separately frozen, pre-reading
roundoff comparison (rtol1e-10,atol1e-12) also failed:66 scalar discrepancies,
all in `finer_power_fraction_above_common_cutoff` for setting8. No tolerance
was widened. No categorical/mode comparison differed between returned and
recomputed metrics. Maximum RMS and relative-L2 recomputation differences were
9.18e-16 and1.20e-15; mean/amplitude differences reproduced exactly.

Every mismatch has exact row/channel/metric paths and saved/recomputed values in
`recalculation-diagnosis.json`, with native field mean, amplitude, spectral power
and the denominator. Maximum auxiliary ratio discrepancy was5.9098e-6. All66
involve nearly uniform fields (native standard deviation≤8.90e-10);54 have the
fixed1e-24 denominator floor active. At row481,u: mean1.4477623, std4.5782e-13,
nonconstant power2.1383e-25, high-mode power9.7501e-27, denominator1e-24. The ratio
was0.009755994 returned versus0.009750084 recomputed. Separate constant/centered
field calculations expose numerical leakage; they do not replace any original
metric. These observations support cancellation/normalization sensitivity in
nearly uniform fields; the exact contribution of individual library kernels was
not isolated. The reproduction failure is not relabeled as a pass.

All18 originally reported mode-change pairs occur in setting8, with native u
standard deviation≤1.18e-12. The source mode classifier has no amplitude gate.
Every original mode label/change remains in the artifacts, with amplitude context
in `mode-change-diagnosis.json`; they should not be presented as robust pattern
transitions. An amplitude-qualified spectral diagnostic would require a new,
separate protocol, not post-hoc replacement of frozen trained-model metrics.

`analysis/summary.json` and plots use ORIGINAL saved cloud metrics and explicitly
carry `independent_metric_reproduction_status: FAILED`; the report-only CLI
returns exit1. Raw arrays and original metrics are unchanged. The failure-first
artifact `recalculation-failure.json` remains separate. Source hashes and different
simulation/diagnosis/plot provenance are retained. No model was retuned.

See [paired discrepancy figure](analysis/paired-discrepancies.png),
[actual paired fields](analysis/actual-fields.png),
[summary](analysis/summary.json), [frozen protocol](../../engineering/rd_numerics/PREREG.md),
and [raw receipt](cuda-run/receipt.json). Scenario rows in the field figure are
48 separate1-D simulations, not a2-D biological tissue image.
