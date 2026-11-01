# Vendored scripts

Unmodified copies of `gh_scripts/*.py` from https://github.com/lamm-mit/CategoryTheoryDesign at
commit `fa8100bad1b43525f28106da94a7f055730fb325` (Apache License 2.0, copyright the authors; see
`LICENSE`). They are the Grasshopper components of Marom, Tibbits, Zardini & Buehler (2026),
"A category-theoretic framework from biological mechanics to engineered stimulus-response systems",
J. Mech. Phys. Solids 106780, doi:10.1016/j.jmps.2026.106780.

Only the pure-Python components are copied (no Rhino imports): stimulus collectors, the Nat and Art
chains from fibre to element, and `geo.py`. `viz.py`, `comp.py`, `spec.py` and the machine profile
are not used. `SHA256SUMS` records the hashes; `analysis.py` checks them before running.
Do not edit these files: the test runs them as published.
