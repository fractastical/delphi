# BioModels connector

Bounded, read-only access to BioModels plus one real replay. Everything here is a *connector and
simulation* component: discovered, retrieved and replayed are separate receipts (SPEC-005).

## Model chosen

**BIOMD0000001047, Collier 1996, "Delta Notch intercellular signalling and lateral inhibition"**
(curated, SBML L2V4, BioModels revision 3). Two cells, four state variables (`delta1/2`,
`notch1/2`), non-dimensionalised ODEs. Source paper: Collier JR, Monk NA, Maini PK, Lewis JH,
*J Theor Biol* 1996, PubMed 9015458. File sha256
`da21ab52edba14b61e41ee87df7a8bb2f367a1206e6e822602f1e75271fae8e2` (43,277 bytes), equal to the hash
BioModels' own metadata declares.

Why this one: developmental patterning by cell-cell signalling, curated, tiny, and executable with
an established solver. Not chosen for flying fish; see "Applicability".

## What was read, and how deeply

| Source | Read level |
| --- | --- |
| BioModels model metadata JSON for BIOMD0000001047 | full-text |
| `delta_notch.xml` | full-text: parsed completely; compartments, species, parameters, rules, initial assignments, reactions, unit definitions and annotations are in `receipts/*/model_inventory.json` |
| BioModels FAQ (`/faq`), Licence section | full-text of that section |
| BioModels terms of use | could-not-access: redirects to a login form |
| Collier 1996 paper | abstract only, via the BioModels `synopsis`; full text not read |

## Licence

BioModels' FAQ states all models are under CC0. The terms page it points to was not readable, and no
model metadata carries a licence field, so this is BioModels' claim, not a reading of the terms.
`client.LICENCE` records exactly that. The SBML bytes are not committed here; the connector
re-fetches them and refuses any file whose size and sha256 differ from BioModels' declaration.

## Interface

```
PYTHONPATH=. python3 -m connectors.biomodels search "lateral inhibition" --limit 5
PYTHONPATH=. python3 -m connectors.biomodels metadata BIOMD0000001047
PYTHONPATH=. python3 -m connectors.biomodels fetch BIOMD0000001047 --dest <dir>
PYTHONPATH=. python3 -m connectors.biomodels replay BIOMD0000001047 --dest <dir> --out connectors/biomodels/receipts/BIOMD0000001047
```

Exit 0 = done and every control passed, 1 = replay ran and a control failed, 2 = refused (reason on stderr as JSON).

Python: `BioModelsClient.search / metadata / fetch`, `inspect_sbml(bytes) -> Model`,
`replay_collier1996(bytes, pinned_sha256, out_dir)`.

* Hosts are allow-listed (`www.biomodels.org`, `biomodels.org`, `www.ebi.ac.uk`), https only, redirects
  re-checked; 1 request/s; JSON capped at 2 MB, models at 5 MB; limit capped at 25.
* `search` uses BioModels' own index. On 2026-10-31 that index answered HTTP 200 with
  `matches: -1` and no models for every query (including an exact accession) for a stretch of the
  session; a later call returned results. A `-1` total is reported as `primary_status: degraded`
  and the EBI Search BioModels domain is used instead, labelled as the source. It is never read
  as zero results.
* A PyPI `libroadrunner` wheel names `libpython3.13.so.1.0` without a path; `load_engine` preloads
  the running interpreter's own libpython once. If that fails the replay reports not-run; no
  substitute engine exists.

## Fail-closed SBML subset

Supported: L2/L3 core, concentration-based species, parameters, function definitions, assignment
rules, initial assignments, kinetic laws over `ci cn plus minus times divide power`.
Refused by name: events, algebraic/rate rules, constraints, delay/time/rateOf csymbols,
stoichiometryMath, boundary/constant/amount species, required packages, DOCTYPE/ENTITY, any other
MathML operator, undefined symbols. `tests/test_biomodels.py` has a case per refusal and a
positive control.

## Replay

Engine: libroadrunner 2.10.0 (CVODE, rtol 1e-10, atol 1e-14), single thread, 0 to 60 at 601 points.
The horizon is mine; the file declares no simulation settings. Three scenarios: the file's own
initial conditions (cell 2 starts 1% below cell 1); an unperturbed symmetric baseline; and a
`b = 0` counterfactual that is **not in the source**.

Controls (values in `receipt.json`, asserted in `tests/test_biomodels_replay.py`):
tolerance convergence; independent scipy LSODA and fixed-step RK4 (observed order about 4.1) over right-hand sides
evaluated from the parsed SBML; a derivative cross-check of that evaluator against roadrunner's
rates with a mutated evaluator (`h = 3`) that must be rejected; patterned end state is a fixed point;
the symmetric fixed point has a positive Jacobian eigenvalue.

Limit: the independent evaluator reads the same file, so these check the engine, not the file's
fidelity to the paper.

Result: as published, the cells end in opposite states (delta1 ~0.990, delta2 ~0.010; notch the
reverse); the baseline stays symmetric because its symmetric fixed point is unstable and exact
symmetry is preserved; with `b = 0` no pattern forms. This is a simulation of a published model.
It is not an observation, and it does not validate the paper.

## Quantities, units, provenance

* Units: no compartment, species or parameter references a unit. The file defines unitDefinitions
  for the SBML L2 defaults (second, mole, litre, metre) that apply by omission. The model is
  non-dimensional; no SI quantity is asserted and no time scale is known.
* Initial conditions (from the file): delta1 = notch1 = 0.999999999999985/0.999999999999987,
  delta2 = notch2 = 0.99. Parameters: a 0.01, b 100, h 2, k 2, mu 1, rho 1 (four are re-set through
  initialAssignments).
* Organism: the file annotates NCBI taxonomy id 7215 (name not resolved here) and tissue/cell
  identifier BTO:0006223; UniProt P10041 (Delta) and P07207 (Notch) are annotated as `isVersionOf`.
* Whether each parameter was measured, fitted or assumed: unknown from the file; paper not read.

## Applicability to flying-fish development (proposed, not established)

This is not a flying-fish model, and nothing here says Delta-Notch lateral inhibition operates in
any tissue relevant to flying-fish flight morphology. A cross-species analogy would be a *proposed*
coupling, needing at least:

1. A named flying-fish trait and tissue where lateral inhibition is claimed, with evidence.
2. Notch and Delta orthologs identified in a flying-fish genome and their expression in that tissue.
3. A mapping from the dimensionless variables and time to measurable quantities and a real time scale.
4. A cell-neighbourhood geometry; this model has exactly two cells.
5. Parameter values (or ranges) for the target, with source and uncertainty; none transfer from the file.
6. An independent check that the pattern, not just the equations, appears in a proxy or target tissue.
