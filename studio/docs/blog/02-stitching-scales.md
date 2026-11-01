# Stitching simulations across scales without inventing the bridge
Date: 2026-11-01
Summary: A fish is molecules, cells, tissue, fins, a whole body and a school. We ran models at each level, then built a layer whose main job is to refuse connections the evidence does not support.

The flying-fish project needs answers that live at different scales. How does a signalling pattern set where a fin ray forms? How stiff is that ray? How does a stiff or flexible wing behave in air and in water? Each question has a model, and each model has its own variables, units and time scale. The tempting move is to wire the output of one into the input of the next and call the result a multiscale simulation.

We did not do that. Instead we asked, for every proposed connection: *may this output feed that input, and under what conditions?*

## Simulations that exist today

The site's Simulations page lists 31 recorded runs, each with a manifest, a verified video or figure, its equations and its limitations. They span the scales we care about:

- **Molecular:** molecular dynamics runs, and a hosted OpenFold2 structure prediction for the potassium-channel gene KCNJ13.
- **Cellular:** a replay of a published two-cell Delta-Notch model from BioModels, bioelectric cell models, and a mechanobiology clutch model.
- **Tissue and developmental:** reaction-diffusion fields, a multicellular tissue model, a neural cellular automaton for pattern generation, and an epithelial repair study.
- **Organ and organism:** fin-ray bilayer mechanics, 2D and GPU 3D flow solutions at two resolutions, an aeroelastic model, a fixed-launch glide model, and a central-pattern-generator behaviour model.

Every one is labelled as a simulation. None is presented as an observation.

## The coupling layer

Each model declares an interface as a small structured record (`frontier.model.interface/1`): named input and output ports, each with a quantity, a unit, a scale, a context (organism or design envelope), a provenance status (measured, fitted, assumed, simulated or unknown) and bounds. The checker is ordinary code that reads these records and the declared mapping; it does not run the simulations. The full contract is in the model-coupling document on the Documentation page. A proposed connection then gets one of three verdicts.

| Verdict | Meaning | May it run? |
|---|---|---|
| `composable` | Same quantity, exact unit conversion or a registered calibration. Dimension, scope, time and uncertainty all pass. | Yes |
| `scenario` | Only under named assumptions, with unknown bounds or uncertainty. | Yes, labelled, never as evidence about an organism |
| `refused` | A bridge is missing or inconsistent. | No |

The current manifest holds 13 proposed couplings: 4 composable, 5 scenario, 4 refused. None of this is exotic. Much of it is careful type and unit checking, and we do not present it as a research breakthrough. What matters is that it is applied to every bridge and that its refusals are published. The composable ones are the honest, boring ones: a wing area passed from the constraint model to the glide model, the same span, the same quantity in the same unit.

## The refusals are the point

One refused coupling is the one a reader is most tempted to draw: a Delta-Notch asymmetry from the two-cell model feeding fin flexural rigidity. The layer refuses it for stated reasons. No mapping exists. The scale changes from cell to organ. The context changes from the species named in the SBML file to the flying-fish design envelope. The Delta-Notch model (a published two-cell lateral-inhibition model) is non-dimensional as stored, so it cannot be identity-mapped to an SI quantity.

An assumption is never allowed to stand in for a jump across biological scale or species. That needs a calibration, a structural record of measured or fitted-to-measured data with a closed domain and an uncertainty. **No calibration is registered today**, so every cross-scale bridge is either refused or labelled assumption-level, and the missing bridge becomes an open question on the Studio page instead of a hidden constant.

The scenario verdicts are equally explicit. Passing the constraint solver's witness speed to the glide model as its release speed is allowed only as a scenario, because the glide model's own default is 1.5 times the stall speed and the identity mapping is an assumption. The manifest prints that assumption next to the result.

## What this buys

- Gaps are visible and routable. Each refusal says exactly which measurement would remove it, which feeds the experiment-planning view.
- A reader can tell a typed, unit-checked connection from a hopeful one without reading code.
- The failure we want to avoid, a polished pipeline whose joints are unsupported, cannot pass silently.

It also means we cannot yet say that our fish is a validated multiscale model. We can say what is connected, what is assumed and what is missing.

[Browse the simulations](#/simulations) or open [the engineering workspace](#/engineering) to see the interfaces and verdicts.
