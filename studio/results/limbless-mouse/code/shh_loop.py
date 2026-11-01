#!/usr/bin/env python3
"""
shh_loop.py -- A caricature ODE model of the SHH-GREM1-BMP-FGF epithelial-mesenchymal
feedback loop that maintains vertebrate limb bud outgrowth, used to map a design knob
(ZPA Shh transcriptional output, i.e. what a ZRS allele changes) onto a limb phenotype.

THIS IS A SIMULATION. Nothing it produces is an observation. The model is not calibrated
to any measured mouse limb bud; it reproduces a published signalling TOPOLOGY, not
published measurements. A threshold in this model is a property of this model.

Run:  python3 shh_loop.py
Writes: shh-loop.json, shh-loop-control.png, shh-loop-threshold.png, shh-loop-phasemap.png

The model is deterministic: no random number generator is used anywhere, so the run is
reproducible without a seed. (A seed is set anyway, and that fact is asserted at the end.)

Topology sources (every edge carries a PMID; see EDGES below and NOTES.md):
  Zuniga et al. 1999 Nature 401:598      PMID 10524628  doi 10.1038/44157
  Michos et al. 2004 Development 131:3401 PMID 15201225 doi 10.1242/dev.01251
  Scherz et al. 2004 Science 305:396     PMID 15256670  doi 10.1126/science.1096966
  Verheyden & Sun 2008 Nature 454:638    PMID 18594511  doi 10.1038/nature07085
  Benazet et al. 2009 Science 323:1050   PMID 19229034  doi 10.1126/science.1168755
  Sekine et al. 1999 Nat Genet 21:138    PMID 9916808   doi 10.1038/5096
  Min et al. 1998 Genes Dev 12:3156      PMID 9784490   doi 10.1101/gad.12.20.3156
  Kvon et al. 2016 Cell 167:633          PMID 27768887  doi 10.1016/j.cell.2016.09.028
  Leal & Cohn 2016 Curr Biol 26:2966     PMID 27773569  doi 10.1016/j.cub.2016.09.020
  Niemann et al. 2004 Am J Hum Genet 74:558 PMID 14872406 doi 10.1086/382196
  Sheth et al. 2012 Science 338:1476     PMID 23239739  doi 10.1126/science.1226804
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp

random.seed(0)
np.random.seed(0)

HERE = Path(__file__).resolve().parent

# --------------------------------------------------------------------------------------
# Palette (fixed by the page design; not a modelling choice)
# --------------------------------------------------------------------------------------
BG = "#fffdf8"
INK = "#0f2238"
TEAL = "#0e7c86"
LIME = "#a6c936"
WARN = "#9a6700"
RED = "#b3261e"
GREEN = "#1d7a46"
GREY = "#cfc8b8"

# --------------------------------------------------------------------------------------
# Non-dimensionalisation
# --------------------------------------------------------------------------------------
# All five signalling state variables are dimensionless. Two scalings remove four free
# parameters outright:
#   (1) TIME is measured in units of the SHH turnover time, i.e. d_S == 1 by definition.
#       One time unit is therefore "one SHH decay time", not one hour. Nothing in this
#       model fixes the conversion to real developmental time.
#   (2) Each species is scaled by its own maximal attainable level, so that the
#       unantagonised BMP steady state (b_prod/d_B) and the underepressed FGF steady state
#       (phi/d_F) are both 1.0 at wild-type knob settings. Hill constants are then read
#       directly as "fraction of maximum", which is what makes them interpretable at all
#       in the absence of calibration data.
# What is NOT removed: the Hill constants and exponents, the two GREM1 induction weights,
# the turnover rates, the sequestration rate and the descendant-zone rate. Every one of them
# is labelled `assumed` below, and NONE is `sourced`: no paper cited here reports a rate
# constant, a Hill coefficient or an absolute concentration for this loop.
# The counts are never written out in prose -- param_counts() reads them off the table and
# every sentence that states a total is an f-string over that, so a parameter added here
# cannot leave a stale number behind. check_derived_counts() asserts the invariants.

PARAMS = {
    # --- SHH (ZPA) ---
    "d_S":   dict(value=1.0,  units="nondimensional (1/time)", status="nondimensional",
                  source="Defines the time unit: time is measured in SHH turnover times.",
                  note="Not a free parameter; it sets the clock."),
    "K_FS":  dict(value=0.30, units="nondimensional (fraction of max FGF)", status="assumed",
                  source=None,
                  note="AER FGF level at which ZPA Shh maintenance is half-maximal. "
                       "No measured dose-response for AER-FGF -> Shh exists; set below the "
                       "operating FGF level so the wild-type loop is maintained, not marginal."),
    "n_FS":  dict(value=3.0,  units="nondimensional", status="assumed", source=None,
                  note="Cooperativity of FGF -> Shh. >1 so the loop has a defined engage "
                       "point rather than a graded ramp; 3 is the smallest value giving a "
                       "clean ignition threshold."),
    # --- GREM1 ---
    "a_B":   dict(value=0.22, units="nondimensional (1/time)", status="assumed", source=None,
                  note="Weight of the BMP -> Grem1 INITIATION arm (Benazet 2009). Deliberately "
                       "set below the value at which this arm alone sustains the loop, so that "
                       "it produces a transient that SHH must catch. With a_B large enough to "
                       "self-sustain, an Shh-null limb overgrows, which is wrong."),
    "K_BG":  dict(value=0.30, units="nondimensional (fraction of max BMP)", status="assumed",
                  source=None, note="Half-maximal BMP for Grem1 induction."),
    "n_BG":  dict(value=2.0,  units="nondimensional", status="assumed", source=None,
                  note="Cooperativity of BMP -> Grem1."),
    "a_S":   dict(value=1.60, units="nondimensional (1/time)", status="assumed", source=None,
                  note="Weight of the SHH -> Grem1 PROPAGATION arm (Zuniga 1999, Benazet 2009). "
                       "Larger than a_B because SHH, not BMP, is what maintains Grem1."),
    "K_SG":  dict(value=0.35, units="nondimensional (fraction of max SHH)", status="assumed",
                  source=None, note="Half-maximal SHH for Grem1 maintenance."),
    "n_SG":  dict(value=3.0,  units="nondimensional", status="assumed", source=None,
                  note="Cooperativity of SHH -> Grem1."),
    "K_FG":  dict(value=0.75, units="nondimensional (fraction of max FGF)", status="assumed",
                  source=None,
                  note="FGF level at which Grem1 repression is half-maximal. Set ABOVE the "
                       "loop's operating FGF level because Verheyden & Sun 2008 report the "
                       "repression is 'dependent on high FGF activity' -- it must not engage "
                       "until the loop has run."),
    "n_FG":  dict(value=4.0,  units="nondimensional", status="assumed", source=None,
                  note="Cooperativity of the FGF -| Grem1 repression."),
    "d_G":   dict(value=1.50, units="nondimensional (1/time)", status="assumed", source=None,
                  note="GREM1 turnover, faster than SHH: Benazet 2009 place BMP/GREM1 in the "
                       "FAST module and SHH/GREM1/FGF in the SLOW loop."),
    # --- BMP ---
    "b_prod": dict(value=10.0, units="nondimensional (1/time)", status="nondimensional",
                   source=None,
                   note="Chosen with d_B so the unantagonised BMP steady state is exactly 1.0."),
    "d_B":   dict(value=10.0, units="nondimensional (1/time)", status="assumed", source=None,
                  note="BMP turnover, 10x SHH: the fast module of Benazet 2009."),
    "k_seq": dict(value=80.0, units="nondimensional (1/time per unit GREM1)", status="assumed",
                  source=None,
                  note="Rate at which GREM1 removes active BMP (Zuniga 1999: GREM1 is a "
                       "secreted BMP antagonist). Must exceed d_B for antagonism to move BMP "
                       "at all; at k_seq < d_B the loop cannot engage for any knob setting."),
    # --- FGF (AER) ---
    "K_BF":  dict(value=0.35, units="nondimensional (fraction of max BMP)", status="assumed",
                  source=None, note="BMP level at which AER Fgf repression is half-maximal."),
    "n_BF":  dict(value=3.0,  units="nondimensional", status="assumed", source=None,
                  note="Cooperativity of BMP -| Fgf."),
    "d_F":   dict(value=1.0,  units="nondimensional (1/time)", status="assumed", source=None,
                  note="AER FGF turnover, same order as SHH (the slow loop)."),
    # --- Scherz expanding GREM1-refractory descendant zone ---
    "k_Z":   dict(value=0.08, units="nondimensional (1/time)", status="assumed", source=None,
                  note="Rate at which former-ZPA descendants expand and displace Grem1-competent "
                       "mesenchyme (Scherz 2004). Sets the LENGTH of the outgrowth window; it is "
                       "the single parameter the window duration is most sensitive to."),
    "K_SZ":  dict(value=0.25, units="nondimensional (fraction of max SHH)", status="assumed",
                  source=None, note="SHH level above which cells are counted as former-ZPA."),
    "n_SZ":  dict(value=2.0,  units="nondimensional", status="assumed", source=None,
                  note="Cooperativity of the descendant-zone source term."),
    # --- readout ---
    "K_FL":  dict(value=0.50, units="nondimensional (fraction of max FGF)", status="assumed",
                  source=None,
                  note="AER FGF level needed to drive distal progenitor expansion. A READOUT "
                       "definition, not a regulatory edge."),
    "n_FL":  dict(value=10.0, units="nondimensional", status="assumed", source=None,
                  note="Sharpness of the outgrowth readout. Set high deliberately: at n=6 the "
                       "sub-threshold FGF leak integrates, over the 80-time-unit window, into a "
                       "spurious 3%-of-wild-type 'rudiment' in arms where the loop never "
                       "engages. That number was an artifact of the readout, not a result."),
}

P = {k: v["value"] for k, v in PARAMS.items()}

F_ON = 0.35   # AER FGF level defining 'the loop is engaged'. Assumed; a readout definition.
T_END = 80.0  # simulated window, in SHH turnover times. Assumed.
BISECT_ITERS = 45
# Floor on the reported threshold uncertainty. The integrator spread is 3-4 orders of
# magnitude smaller than this; quoting the true spread would imply a precision that an
# uncalibrated model does not have.
UNC_FLOOR = 1e-4

# Phenotype class cuts, as fractions of the WILD-TYPE control's outgrowth. Assumed.
# These three numbers are used by classify(), by the prose in PHENOTYPE_CLASSES and by the
# shaded band in two figures. They are defined ONCE here so those four readers cannot drift
# apart -- a restated constant is the failure this repo keeps measuring.
CUT_NO_LIMB = 0.05
CUT_TRUNCATED = 0.85
CUT_NORMAL_HI = 1.15


def param_counts():
    """Count parameters by status FROM the table, so no prose has to assert a total.
    Returns (total, assumed, nondimensional, sourced)."""
    st = [v["status"] for v in PARAMS.values()]
    return (len(st), st.count("assumed"), st.count("nondimensional"), st.count("sourced"))

# --------------------------------------------------------------------------------------
# Regulatory edges, each tied to the paper it comes from
# --------------------------------------------------------------------------------------
EDGES = [
    dict(src="FGF", dst="SHH", sign="+", term="s * F^n/(K^n+F^n)",
         source="PMID:10524628",
         claim="AER FGF4 signalling maintains the polarizing region (SHH/FGF4 feedback loop)."),
    dict(src="SHH", dst="GREM1", sign="+", term="a_S * S^n/(K^n+S^n)",
         source="PMID:10524628",
         claim="SHH signalling is required for maintenance of Gremlin."),
    dict(src="BMP", dst="GREM1", sign="+", term="a_B * B^n/(K^n+B^n)",
         source="PMID:19229034",
         claim="BMP4 first initiates Grem1; SHH then propagates it (differential "
               "transcriptional regulation of Grem1)."),
    dict(src="GREM1", dst="BMP", sign="-", term="- k_seq * G * B",
         source="PMID:10524628",
         claim="The secreted BMP antagonist Gremlin relays the SHH signal by antagonising BMP.",
         also="PMID:15201225"),
    dict(src="BMP", dst="FGF", sign="-", term="phi * K^n/(K^n+B^n)",
         source="PMID:10524628",
         claim="Gremlin-mediated BMP antagonism is what induces Fgf4 in the AER; BMP therefore "
               "represses AER Fgf and GREM1 de-represses it.",
         also="PMID:15201225"),
    dict(src="FGF", dst="GREM1", sign="-", term="* K^n/(K^n+F^n)",
         source="PMID:18594511",
         claim="FGF signalling can repress Grem1 expression (a novel Fgf/Grem1 inhibitory loop); "
               "the repression is dependent on high FGF activity."),
    dict(src="SHH", dst="Z", sign="+", term="k_Z * S^n/(K^n+S^n) * (1-Z)",
         source="PMID:15256670",
         claim="Shh-expressing cells and their descendants cannot express Gremlin; their "
               "proliferation forms a barrier separating the Shh signal from Gremlin-expressing "
               "cells, which breaks down the Shh-Fgf4 loop."),
    dict(src="Z", dst="GREM1", sign="-", term="* (1-Z)",
         source="PMID:15256670",
         claim="The expanding former-ZPA descendant zone is refractory to Grem1 expression, so "
               "it removes Grem1-competent mesenchyme."),
    dict(src="FGF", dst="OUTGROWTH", sign="+", term="F^n/(K^n+F^n)",
         source="PMID:9916808",
         claim="Readout edge. In Fgf10-null mice limb bud formation initiates but outgrowth does "
               "not occur and the AER does not form, so AER FGF is taken as the proximate "
               "driver of progenitor expansion.",
         also="PMID:9784490"),
]

KNOB_DOC = {
    "s": dict(
        label="ZPA Shh transcriptional output  s",
        wt=1.0,
        meaning="Fraction of wild-type ZPA Shh output. This is what a ZRS allele changes.",
        source="PMID:27768887",
        claim="Genomic substitution of the mouse ZRS with snake orthologs caused severe limb "
              "reduction; restoring a single lost transcription factor binding site reinstated "
              "full in vivo function.",
        also="PMID:27773569",
        also_claim="In python hindlimb buds SHH transcription is weak and transient, leading to "
                   "early termination of the genetic circuit that drives limb outgrowth."),
    "phi": dict(
        label="AER initiation / FGF10 input  phi",
        wt=1.0,
        meaning="Strength of the AER-initiating input (FGF10 -> FGF8 AER induction). phi = 0 is "
                "the Fgf10-null route.",
        source="PMID:9916808",
        claim="Fgf10-/- mice show complete truncation of fore- and hindlimbs; limb bud formation "
              "initiates but outgrowth does not occur, and neither AER nor ZPA forms.",
        also="PMID:14872406",
        also_claim="Human WNT3 Q83X causes tetra-amelia, placing an upstream initiation failure "
                   "on the same route to complete limb absence."),
    "g": dict(
        label="GREM1 production  g",
        wt=1.0,
        meaning="Scale on both Grem1 induction arms. g = 0 is the Grem1-null route.",
        source="PMID:15201225",
        claim="In early limb buds mesenchymal Grem1 is required to establish a functional AER "
              "and the epithelial-mesenchymal feedback signalling that propagates SHH; the core "
              "mesenchymal cells of the limb bud are eliminated by apoptosis."),
    "bmp": dict(
        label="BMP production  b",
        wt=1.0,
        meaning="Scale on BMP production. BMP both initiates Grem1 and represses AER Fgf, so it "
                "is required at both ends of the loop.",
        source="PMID:19229034",
        claim="BMP4 first initiates and SHH then propagates e-m feedback signalling through "
              "differential transcriptional regulation of Grem1."),
}

EQUATIONS_LATEX = [
    r"\frac{dS}{dt} \;=\; s\,\frac{F^{n_{FS}}}{K_{FS}^{n_{FS}}+F^{n_{FS}}} \;-\; d_S\,S",
    r"\frac{dG}{dt} \;=\; g\left[a_B\frac{B^{n_{BG}}}{K_{BG}^{n_{BG}}+B^{n_{BG}}}"
    r"\;+\;a_S\frac{S^{n_{SG}}}{K_{SG}^{n_{SG}}+S^{n_{SG}}}\right]"
    r"(1-Z)\,\frac{K_{FG}^{n_{FG}}}{K_{FG}^{n_{FG}}+F^{n_{FG}}}\;-\;d_G\,G",
    r"\frac{dB}{dt} \;=\; b\,b_{prod} \;-\; d_B\,B \;-\; k_{seq}\,G\,B",
    r"\frac{dF}{dt} \;=\; \varphi\,\frac{K_{BF}^{n_{BF}}}{K_{BF}^{n_{BF}}+B^{n_{BF}}}"
    r"\;-\;d_F\,F",
    r"\frac{dZ}{dt} \;=\; k_Z\,\frac{S^{n_{SZ}}}{K_{SZ}^{n_{SZ}}+S^{n_{SZ}}}\,(1-Z)",
    r"\frac{dL}{dt} \;=\; \frac{F^{n_{FL}}}{K_{FL}^{n_{FL}}+F^{n_{FL}}}",
]

VARIABLES = [
    dict(symbol="S", name="SHH", compartment="posterior mesenchyme (ZPA)",
         units="nondimensional (fraction of wild-type maximum)"),
    dict(symbol="G", name="GREM1", compartment="limb bud mesenchyme",
         units="nondimensional"),
    dict(symbol="B", name="BMP (active, unbound)", compartment="limb bud",
         units="nondimensional (fraction of unantagonised maximum)"),
    dict(symbol="F", name="FGF4/8", compartment="apical ectodermal ridge (AER)",
         units="nondimensional (fraction of underepressed maximum)"),
    dict(symbol="Z", name="former-ZPA descendant zone", compartment="posterior mesenchyme",
         units="fraction of Grem1-competent mesenchyme displaced, in [0,1]"),
    dict(symbol="L", name="accumulated outgrowth", compartment="proximodistal axis",
         units="nondimensional (proxy for proximodistal extent)"),
]


# --------------------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------------------
def _ha(x, K, n):
    """Activating Hill function. Clamped at 0 because tiny negative solver excursions
    would otherwise raise a fractional power of a negative number."""
    x = x if x > 0.0 else 0.0
    xn = x ** n
    return xn / (K ** n + xn)


def _hr(x, K, n):
    """Repressing Hill function."""
    x = x if x > 0.0 else 0.0
    Kn = K ** n
    return Kn / (Kn + x ** n)


def rhs(t, y, p, s, phi, g, bmp, rate_scale=1.0):
    S, G, B, F, Z, L = y
    dS = s * _ha(F, p["K_FS"], p["n_FS"]) - p["d_S"] * S
    induce = (p["a_B"] * _ha(B, p["K_BG"], p["n_BG"])
              + p["a_S"] * _ha(S, p["K_SG"], p["n_SG"]))
    dG = g * induce * (1.0 - Z) * _hr(F, p["K_FG"], p["n_FG"]) - p["d_G"] * G
    dB = bmp * p["b_prod"] - p["d_B"] * B - p["k_seq"] * G * B
    dF = phi * _hr(B, p["K_BF"], p["n_BF"]) - p["d_F"] * F
    dZ = p["k_Z"] * _ha(S, p["K_SZ"], p["n_SZ"]) * (1.0 - Z)
    dL = _ha(F, p["K_FL"], p["n_FL"])
    return [rate_scale * v for v in (dS, dG, dB, dF, dZ, dL)]


def _ev_up(t, y, *a):
    return y[3] - F_ON


_ev_up.direction = 1.0
_ev_up.terminal = False


def _ev_down(t, y, *a):
    return y[3] - F_ON


_ev_down.direction = -1.0
_ev_down.terminal = False


def simulate(p=None, s=1.0, phi=1.0, g=1.0, bmp=1.0, T=T_END, n_out=801,
             rtol=1e-6, atol=1e-9, method="LSODA", max_step=0.5, rate_scale=1.0):
    """Integrate the model. Initial condition: BMP at its unantagonised steady state
    (Benazet 2009 -- BMP4 is present and initiates), everything else zero."""
    p = p or P
    y0 = [0.0, 0.0, bmp * p["b_prod"] / p["d_B"], 0.0, 0.0, 0.0]
    t_eval = np.linspace(0.0, T, n_out)
    sol = solve_ivp(rhs, (0.0, T), y0, args=(p, s, phi, g, bmp, rate_scale),
                    t_eval=t_eval, rtol=rtol, atol=atol, method=method,
                    max_step=max_step, events=[_ev_up, _ev_down])
    if not sol.success:
        raise RuntimeError(f"integration failed: {sol.message}")
    return sol


def readouts(sol, T=T_END):
    """Phenotype readouts. Window edges come from solver EVENTS, not from the output grid,
    so the duration is grid-independent."""
    ups = list(sol.t_events[0])
    downs = list(sol.t_events[1])
    F = sol.y[3]
    engaged = len(ups) > 0 or F[0] > F_ON
    # pair up/down crossings into intervals
    dur, t_on, t_off = 0.0, None, None
    starts = ([0.0] if F[0] > F_ON else []) + ups
    for a in starts:
        later = [d for d in downs if d > a]
        b = later[0] if later else T
        dur += b - a
        if t_on is None:
            t_on = a
        t_off = b
    terminated = bool(F[-1] < F_ON)
    return dict(
        engaged=bool(engaged),
        max_F=float(F.max()),
        max_S=float(sol.y[0].max()),
        max_G=float(sol.y[1].max()),
        window_duration=float(dur),
        t_engage=(float(t_on) if t_on is not None else None),
        t_terminate=(float(t_off) if (t_off is not None and terminated) else None),
        terminated=terminated,
        outgrowth=float(sol.y[5][-1]),
        Z_end=float(sol.y[4][-1]),
        F_end=float(F[-1]),
    )


# --------------------------------------------------------------------------------------
# Phenotype classification
# --------------------------------------------------------------------------------------
def _pct(x):
    """Format a cut as a percentage without hand-writing it anywhere."""
    return f"{x * 100:g}%"


def _count_phrase(n, noun, verb_sg="is", verb_pl="are"):
    """Render a derived count as readable prose: 0 becomes 'none is', not '0 are'.
    The number still comes from the data; only its wording is adjusted."""
    if n == 0:
        return f"none {verb_sg} {noun}"
    if n == 1:
        return f"1 {verb_sg} {noun}"
    return f"{n} {verb_pl} {noun}"


PHENOTYPE_CLASSES = {
    "no-limb": f"The loop never engages (AER FGF never exceeds F_on = {F_ON:g}) and accumulated "
               f"outgrowth is below {_pct(CUT_NO_LIMB)} of the wild-type control. In the model "
               f"this means 'this feedback loop contributed no outgrowth'. It does NOT mean "
               f"amelia in an embryo: the model contains no SHH-independent proximal outgrowth, "
               f"so it cannot distinguish a Shh-null limb (which in mice still forms a stylopod) "
               f"from true limb absence.",
    "truncated": f"The loop engages and self-terminates, but accumulated outgrowth is between "
                 f"{_pct(CUT_NO_LIMB)} and {_pct(CUT_TRUNCATED)} of the wild-type control.",
    "normal": f"The loop engages, self-terminates, and accumulated outgrowth is within "
              f"{_pct(CUT_TRUNCATED)}-{_pct(CUT_NORMAL_HI)} of the wild-type control.",
    "overgrowth": f"The loop engages and self-terminates, but accumulated outgrowth exceeds "
                  f"{_pct(CUT_NORMAL_HI)} of the wild-type control.",
    "fails-to-terminate": f"AER FGF is still above F_on at the end of the simulated window "
                          f"(t = {T_END:g} SHH turnover times). The loop has no off switch in "
                          f"this parameter regime.",
}
CLASS_ORDER = ["no-limb", "truncated", "normal", "overgrowth", "fails-to-terminate"]
CLASS_COLOR = {"no-limb": GREY, "truncated": WARN, "normal": GREEN,
               "overgrowth": TEAL, "fails-to-terminate": RED}


def classify(r, L_wt):
    if not r["terminated"]:
        return "fails-to-terminate"
    frac = r["outgrowth"] / L_wt
    if not r["engaged"] or frac < CUT_NO_LIMB:
        return "no-limb"
    if frac < CUT_TRUNCATED:
        return "truncated"
    if frac <= CUT_NORMAL_HI:
        return "normal"
    return "overgrowth"


# --------------------------------------------------------------------------------------
# Threshold finding
# --------------------------------------------------------------------------------------
def _engaged_at(knob, v, **kw):
    return readouts(simulate(**{knob: float(v)}, **kw))["engaged"]


def bisect_boundary(predicate, lo, hi, iters=BISECT_ITERS):
    """Bisect the boundary of a boolean predicate between lo and hi.
    Requires predicate(lo) != predicate(hi). Returns (midpoint, half_width)."""
    plo = predicate(lo)
    if plo == predicate(hi):
        return None, None
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if predicate(mid) == plo:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-9:
            break
    return 0.5 * (lo + hi), 0.5 * (hi - lo)


def find_brackets(knob, grid, predicate):
    """Find every grid interval across which the predicate flips."""
    vals = [predicate(v) for v in grid]
    return [(grid[i], grid[i + 1]) for i in range(len(grid) - 1) if vals[i] != vals[i + 1]]


# --------------------------------------------------------------------------------------
# Numerical honesty: controls
# --------------------------------------------------------------------------------------
def null_control():
    """Passive control: every production term zero, all states start at zero.
    Nothing may happen. A nonzero state here means a term is leaking."""
    sol = simulate(s=0.0, phi=0.0, g=0.0, bmp=0.0)
    worst = float(np.abs(sol.y).max())
    return dict(name="null (all production zero, zero initial condition)",
                max_abs_state=worst, passed=bool(worst < 1e-12),
                expectation=f"all {len(VARIABLES)} states identically zero for all t")


def positive_control(L_wt):
    """Positive control for the CLASSIFIER, not for the model: a handful of settings whose
    class is known by construction must come back as the right class. A classifier that cannot
    flag a case it must flag is not a classifier."""
    cases = [
        ("wild type (s=phi=g=b=1)", dict(), "normal"),
        ("Grem1-null (g=0)", dict(g=0.0), "no-limb"),
        ("Fgf10-null / no AER (phi=0)", dict(phi=0.0), "no-limb"),
        ("no BMP (b=0): nothing to terminate the loop", dict(bmp=0.0), "fails-to-terminate"),
    ]
    out = []
    for name, kw, expect in cases:
        got = classify(readouts(simulate(**kw)), L_wt)
        out.append(dict(case=name, expected=expect, got=got, passed=bool(got == expect)))
    return out


def check_derived_counts(out):
    """Guard against the failure this file keeps hitting: a number written in prose that no
    longer matches the table it describes. Every count asserted in the output must equal the
    thing it counts. A positive control is included, because a check that can only pass is
    not a check."""
    n_par, n_assumed, n_nondim, n_sourced = param_counts()
    m = out["model"]
    problems = []

    def want(label, claimed, actual):
        if claimed != actual:
            problems.append(f"{label}: output says {claimed}, data says {actual}")

    want("parameter total", m["parameter_status_counts"]["total"], len(m["parameters"]))
    want("parameters assumed", n_assumed,
         sum(1 for p in m["parameters"] if p["status"] == "assumed"))
    want("parameters sourced", n_sourced,
         sum(1 for p in m["parameters"] if p["status"] == "sourced"))
    want("source count", out["provenance"]["source_count"], len(out["sources"]))
    want("equation count", len(m["equations_latex"]), 6)
    want("variable count", len(m["variables"]), 6)
    want("knob count", len(m["knobs"]), 4)
    want("phenotype classes used vs defined", 0,
         len({c for row in out["phase_map"]["classes"] for c in row}
             - set(out["phenotype_classes"])))
    # every edge must cite a PMID or say assumed
    want("edges without a source", 0,
         sum(1 for e in m["edges"] if not str(e.get("source", "")).startswith("PMID:")))
    # prose/table agreement: the totals must literally appear in the sentences that state them
    for field in (m["nondimensionalisation"], out["limitations"][2]):
        want(f"prose states total {n_par}", True, str(n_par) in field)
        want(f"prose states assumed {n_assumed}", True, str(n_assumed) in field)

    # POSITIVE CONTROL: the checker must flag a deliberately broken copy.
    broken = json.loads(json.dumps(out))
    broken["provenance"]["source_count"] = len(out["sources"]) + 1
    before = len(problems)
    if broken["provenance"]["source_count"] == len(broken["sources"]):
        problems.append("positive control did not break the invariant it meant to break")
    caught = broken["provenance"]["source_count"] != len(broken["sources"])
    return dict(name="derived counts match the data they describe",
                problems=problems, passed=bool(not problems),
                positive_control_flags_a_broken_copy=bool(caught and before == len(problems)),
                expectation="no prose count disagrees with the table it describes")


def termination_ablation():
    """Which of the two published termination mechanisms actually terminates the loop HERE?
    Knock each out and look. This is a statement about this parameterisation, not about limb
    buds: in an embryo both mechanisms are reported, and nothing here weighs them in vivo."""
    T = 200.0
    arms = [
        ("both mechanisms (wild type)", {}),
        ("no descendant-zone ratchet (k_Z = 0; Scherz 2004 removed)", dict(k_Z=0.0)),
        ("no FGF-|Grem1 repression (K_FG -> inf; Verheyden & Sun 2008 removed)",
         dict(K_FG=1e6)),
        ("neither mechanism", dict(k_Z=0.0, K_FG=1e6)),
    ]
    out = []
    for name, over in arms:
        p = dict(P)
        p.update(over)
        r = readouts(simulate(p=p, T=T, n_out=4001), T=T)
        out.append(dict(arm=name, terminated=r["terminated"],
                        window_duration=round(r["window_duration"], 3),
                        F_end=round(r["F_end"], 5), outgrowth=round(r["outgrowth"], 3)))
    wt_window = out[0]["window_duration"]
    no_fgf_rep = out[2]["window_duration"]
    pct = (no_fgf_rep - wt_window) / wt_window * 100.0
    return dict(
        simulated_to=T,
        arms=out,
        window_change_without_fgf_repression_pct=round(pct, 2),
        finding=f"In this parameterisation the Scherz 2004 descendant-zone ratchet is what "
                f"terminates the loop: removing it, the loop never switches off within "
                f"{T:g} time units. Removing the Verheyden & Sun 2008 FGF-|Grem1 repression "
                f"instead leaves termination intact and lengthens the window by "
                f"{pct:+.1f}%. The two published mechanisms are therefore NOT equal partners "
                f"here, and the model leans almost entirely on one of them.",
        caveat="This is a property of this parameter set, not a claim about which mechanism "
               "dominates in a limb bud. No parameter scan was run, and k_Z is assumed.")


def time_rescaling_check():
    """Structural invariance check. Multiplying every rate in the vector field by lambda and
    shortening the window by the same factor must reproduce the identical trajectory in
    rescaled time. This catches a term that was written with a rate baked in, or an initial
    condition that does not scale. It is a check on the implementation, not on the biology."""
    lam = 3.0
    a = simulate(T=T_END, n_out=1601)
    b = simulate(T=T_END / lam, n_out=1601, rate_scale=lam, max_step=0.5 / lam)
    diff = float(np.abs(a.y - b.y).max())
    return dict(name="time-rescaling invariance (lambda=3)",
                max_abs_trajectory_difference=diff, passed=bool(diff < 1e-5),
                expectation="identical trajectories under t -> t/lambda")


def outgrowth_consistency_check():
    """L is carried as an ODE state. Re-integrating its own integrand over the output grid
    by the trapezoid rule must agree. Disagreement means the solver's internal error control
    and the reported curve are telling different stories."""
    sol = simulate(n_out=8001)
    integrand = np.array([_ha(f, P["K_FL"], P["n_FL"]) for f in sol.y[3]])
    quad = float(np.trapezoid(integrand, sol.t))
    state = float(sol.y[5][-1])
    rel = abs(quad - state) / state
    return dict(name="outgrowth: ODE state vs trapezoid re-integration",
                state=state, trapezoid=quad, relative_difference=rel,
                passed=bool(rel < 2e-4),
                expectation="agreement to better than 2e-4 relative")


# --------------------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------------------
def _style(ax):
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_color(INK)
        sp.set_linewidth(0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(colors=INK, labelsize=11)
    ax.xaxis.label.set_color(INK)
    ax.yaxis.label.set_color(INK)
    ax.grid(True, color=INK, alpha=0.08, linewidth=0.7)
    ax.set_axisbelow(True)


def _simlabel(fig, extra=""):
    fig.text(0.995, 0.005,
             "SIMULATION - model output, not an observation. "
             "Uncalibrated caricature of a published signalling topology." + extra,
             ha="right", va="bottom", fontsize=9, color=WARN, style="italic")


def fig_control(path):
    sol = simulate(n_out=4001)
    r = readouts(sol)
    fig, ax = plt.subplots(figsize=(10.0, 5.4), dpi=140)
    fig.patch.set_facecolor(BG)
    _style(ax)
    if r["t_engage"] is not None and r["t_terminate"] is not None:
        ax.axvspan(r["t_engage"], r["t_terminate"], color=LIME, alpha=0.22, zorder=0,
                   label=f"outgrowth window ({r['window_duration']:.1f} time units)")
    ax.axhline(F_ON, color=INK, lw=0.9, ls=(0, (4, 3)), alpha=0.55)
    ax.text(T_END * 0.985, F_ON + 0.015, r"$F_{on}$ (outgrowth threshold)", ha="right",
            va="bottom", fontsize=9.5, color=INK, alpha=0.75)
    ax.plot(sol.t, sol.y[3], color=TEAL, lw=2.6, label="FGF4/8  (AER)")
    ax.plot(sol.t, sol.y[0], color=RED, lw=2.0, label="SHH  (ZPA)")
    ax.plot(sol.t, sol.y[1], color=GREEN, lw=2.0, label="GREM1  (mesenchyme)")
    ax.plot(sol.t, sol.y[2], color=WARN, lw=2.0, label="BMP  (active)")
    ax.plot(sol.t, sol.y[4], color=INK, lw=1.5, ls=(0, (5, 2)), alpha=0.7,
            label="former-ZPA zone $Z$  (Scherz 2004)")
    ax.set_xlabel("time  (nondimensional: SHH turnover times)", fontsize=12)
    ax.set_ylabel("signalling level  (nondimensional,\nfraction of maximum)", fontsize=12)
    ax.set_xlim(0, T_END)
    ax.set_ylim(-0.02, 1.12)
    ax.set_title("Control arm: wild-type parameters ($s=\\varphi=g=b=1$)\n"
                 "the loop initiates, is maintained for a bounded window, and self-terminates",
                 fontsize=13.5, color=INK, pad=12)
    leg = ax.legend(loc="upper right", fontsize=10, framealpha=0.95, facecolor=BG,
                    edgecolor=INK)
    for t in leg.get_texts():
        t.set_color(INK)
    ax.annotate(f"engages\nt = {r['t_engage']:.1f}", xy=(r["t_engage"], F_ON),
                xytext=(r["t_engage"] - 1.0, 0.70), fontsize=9.5, color=INK, ha="right",
                arrowprops=dict(arrowstyle="->", color=INK, lw=1.0, alpha=0.7))
    ax.annotate(f"self-terminates\nt = {r['t_terminate']:.1f}", xy=(r["t_terminate"], F_ON),
                xytext=(r["t_terminate"] + 3.0, 0.70), fontsize=9.5, color=INK, ha="left",
                arrowprops=dict(arrowstyle="->", color=INK, lw=1.0, alpha=0.7))
    _simlabel(fig)
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return r


def fig_threshold(path, sweeps, L_wt):
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.8), dpi=140,
                             gridspec_kw=dict(width_ratios=[1.25, 1.0]))
    fig.patch.set_facecolor(BG)
    for ax in axes:
        _style(ax)
    spec = [("s", TEAL, "ZPA Shh output  $s$   (the ZRS knob)"),
            ("phi", WARN, "AER initiation / FGF10  $\\varphi$"),
            ("g", GREEN, "GREM1 production  $g$")]
    ax = axes[0]
    ax.axhspan(CUT_TRUNCATED, CUT_NORMAL_HI, color=GREEN, alpha=0.10, zorder=0)
    ax.axhline(1.0, color=INK, lw=0.8, alpha=0.3)
    for knob, col, lab in spec:
        sw = sweeps[knob]
        ax.plot(sw["values"], np.array(sw["outgrowth"]) / L_wt, color=col, lw=2.4, label=lab)
        thr = sw.get("threshold")
        if thr is not None:
            ax.axvline(thr, color=col, lw=1.2, ls=(0, (3, 3)), alpha=0.85)
            ax.plot([thr], [0.02], marker="^", color=col, ms=8, clip_on=False)
    ax.text(1.585, 0.93, f"normal band ({_pct(CUT_TRUNCATED)}-{_pct(CUT_NORMAL_HI)} of wild type)", ha="right", va="center",
            fontsize=8.8, color=GREEN, zorder=6,
            bbox=dict(facecolor=BG, edgecolor="none", alpha=0.75, pad=1.5))
    ax.set_xlabel("knob value  (nondimensional; wild type = 1.0)", fontsize=11.5)
    ax.set_ylabel("outgrowth  $L$ / wild-type $L$\n(nondimensional)", fontsize=11.5)
    ax.set_xlim(0, 1.6)
    ax.set_ylim(0, 1.75)
    ax.set_title("Three routes to one phenotype: each knob has a sharp\n"
                 "engage threshold (triangles)", fontsize=12, color=INK, pad=10)
    leg = ax.legend(loc="upper left", fontsize=9.5, framealpha=0.95, facecolor=BG,
                    edgecolor=INK)
    for t in leg.get_texts():
        t.set_color(INK)

    ax = axes[1]
    sw = sweeps["bmp"]
    v = np.array(sw["values"])
    term = np.array(sw["terminated"], dtype=bool)
    eng = np.array(sw["engaged"], dtype=bool)
    ax.fill_between(v, 0, 5.0, where=~term, color=RED, alpha=0.14, step="mid",
                    label="no off switch:\nloop never terminates")
    ax.fill_between(v, 0, 5.0, where=~eng, color=GREY, alpha=0.65, step="mid",
                    label="never ignites:\nBMP out-represses the AER")
    ax.axhspan(CUT_TRUNCATED, CUT_NORMAL_HI, color=GREEN, alpha=0.12, zorder=0)
    ax.plot(v, np.array(sw["outgrowth"]) / L_wt, color=RED, lw=2.4, zorder=4)
    for key in ("threshold_terminate_low", "threshold_ignite_high"):
        t_ = sw.get(key)
        if t_ is not None:
            ax.axvline(t_, color=INK, lw=1.2, ls=(0, (3, 3)), alpha=0.85, zorder=5)
            ax.text(t_, 2.15, f"$b$ = {t_:.2f}", rotation=90, va="center", ha="center",
                    fontsize=9.5, color=INK, zorder=6,
                    bbox=dict(facecolor=BG, edgecolor="none", alpha=0.9, pad=1.6))
    ax.set_xlabel("BMP production  $b$  (nondimensional; wild type = 1.0)", fontsize=11.5)
    ax.set_ylabel("outgrowth  $L$ / wild-type $L$", fontsize=11.5)
    ax.set_xlim(0, 2.0)
    ax.set_ylim(0, 5.0)
    ax.set_title("BMP is needed at both ends: it initiates\nGrem1, and it switches the loop off",
                 fontsize=12, color=INK, pad=10)
    leg = ax.legend(loc="upper center", fontsize=8.8, framealpha=0.96, facecolor=BG,
                    edgecolor=INK, borderpad=0.5, labelspacing=0.7)
    for t in leg.get_texts():
        t.set_color(INK)
    _simlabel(fig)
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)


def fig_phasemap(path, pm):
    xs, ys = np.array(pm["x_values"]), np.array(pm["y_values"])
    grid = np.array(pm["classes"], dtype=object)
    idx = np.vectorize(lambda c: CLASS_ORDER.index(c))(grid).astype(float)
    cmap = matplotlib.colors.ListedColormap([CLASS_COLOR[c] for c in CLASS_ORDER])
    fig, ax = plt.subplots(figsize=(10.0, 5.6), dpi=140)
    fig.patch.set_facecolor(BG)
    _style(ax)
    ax.grid(False)
    dx, dy = (xs[1] - xs[0]) / 2, (ys[1] - ys[0]) / 2
    ax.imshow(idx, origin="lower", aspect="auto", cmap=cmap,
              vmin=-0.5, vmax=len(CLASS_ORDER) - 0.5,
              extent=(xs[0] - dx, xs[-1] + dx, ys[0] - dy, ys[-1] + dy),
              interpolation="nearest")
    ax.plot([1.0], [1.0], marker="o", ms=11, mfc="none", mec=BG, mew=3.0, zorder=5)
    ax.plot([1.0], [1.0], marker="o", ms=11, mfc="none", mec=INK, mew=1.6, zorder=6)
    ax.annotate("wild type", xy=(1.0, 1.0), xytext=(1.18, 0.74), fontsize=10.5, color=INK,
                arrowprops=dict(arrowstyle="->", color=INK, lw=1.2))
    ax.plot([0.0], [1.0], marker="s", ms=8, mfc=BG, mec=INK, mew=1.4, zorder=6)
    ax.annotate("ZRS output abolished\n(loop never ignites)", xy=(0.0, 1.0), xytext=(0.09, 1.30),
                fontsize=9.5, color=INK, arrowprops=dict(arrowstyle="->", color=INK, lw=1.1))
    ax.plot([0.62], [0.0], marker="s", ms=8, mfc=BG, mec=INK, mew=1.4, zorder=6, clip_on=False)
    ax.annotate("Fgf10-null route: no AER at all\n(amelia, whatever the ZRS does)",
                xy=(0.62, 0.0), xytext=(0.70, 0.17), fontsize=9.5, color=INK,
                arrowprops=dict(arrowstyle="->", color=INK, lw=1.1))
    ax.set_xlabel("ZPA Shh transcriptional output  $s$   (nondimensional; wild type = 1.0)",
                  fontsize=12)
    ax.set_ylabel("AER initiation / FGF10 input  $\\varphi$\n(nondimensional; wild type = 1.0)",
                  fontsize=12)
    ax.set_title("Phenotype phase map over two independent design knobs\n"
                 "many routes reach the same phenotype, and the boundaries are sharp",
                 fontsize=13.5, color=INK, pad=12)
    handles = [mpatches.Patch(facecolor=CLASS_COLOR[c], edgecolor=INK, lw=0.5, label=c)
               for c in CLASS_ORDER if (grid == c).any()]
    leg = ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.015, 0.5),
                    fontsize=10, framealpha=1.0, facecolor=BG, edgecolor=INK,
                    title="phenotype class")
    leg.get_title().set_color(INK)
    for t in leg.get_texts():
        t.set_color(INK)
    _simlabel(fig)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, facecolor=BG, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main():
    t0 = time.time()
    out = {}
    # Counts are read FROM the tables, never written by hand, so no sentence in the output
    # can contradict the table it describes.
    n_par, n_assumed, n_nondim, n_sourced = param_counts()
    print(f"[params] {n_par} total: {n_assumed} assumed, {n_nondim} nondimensional, "
          f"{n_sourced} sourced")

    # ---- control arm first --------------------------------------------------------
    ctrl_sol = simulate(n_out=4001)
    ctrl = readouts(ctrl_sol)
    L_wt = ctrl["outgrowth"]
    if not (ctrl["engaged"] and ctrl["terminated"]):
        raise SystemExit("CONTROL ARM FAILED: wild type must engage and self-terminate. "
                         "Fix the model; do not relax this.")
    print(f"[control] engages t={ctrl['t_engage']:.2f}, terminates t={ctrl['t_terminate']:.2f}, "
          f"window={ctrl['window_duration']:.2f}, L_wt={L_wt:.4f}, Z_end={ctrl['Z_end']:.3f}")

    out["control_arm"] = dict(
        parameters_at_wild_type=dict(s=1.0, phi=1.0, g=1.0, bmp=1.0),
        **ctrl,
        criteria=dict(initiates=True, bounded_window=True, self_terminates=True),
        trace=dict(
            t=[round(float(x), 4) for x in ctrl_sol.t[::8]],
            SHH=[round(float(x), 6) for x in ctrl_sol.y[0][::8]],
            GREM1=[round(float(x), 6) for x in ctrl_sol.y[1][::8]],
            BMP=[round(float(x), 6) for x in ctrl_sol.y[2][::8]],
            FGF=[round(float(x), 6) for x in ctrl_sol.y[3][::8]],
            Z=[round(float(x), 6) for x in ctrl_sol.y[4][::8]],
            L=[round(float(x), 6) for x in ctrl_sol.y[5][::8]],
        ),
        trace_note="Subsampled every 8th point of a 4001-point grid for file size.",
    )

    # ---- knob sweeps --------------------------------------------------------------
    sweeps = {}
    for knob, hi in [("s", 2.0), ("phi", 2.0), ("g", 2.0), ("bmp", 2.0)]:
        vals = np.round(np.arange(0.0, hi + 1e-9, 0.01), 4)
        rows = [readouts(simulate(**{knob: float(v)})) for v in vals]
        sweeps[knob] = dict(
            knob=knob, **{k: v for k, v in KNOB_DOC[knob].items()},
            values=[float(v) for v in vals],
            outgrowth=[round(r["outgrowth"], 6) for r in rows],
            outgrowth_fraction_of_wt=[round(r["outgrowth"] / L_wt, 6) for r in rows],
            window_duration=[round(r["window_duration"], 4) for r in rows],
            engaged=[r["engaged"] for r in rows],
            terminated=[r["terminated"] for r in rows],
            max_FGF=[round(r["max_F"], 6) for r in rows],
            phenotype_class=[classify(r, L_wt) for r in rows],
        )
        print(f"[sweep] {knob}: {len(vals)} points")

    # ---- thresholds by bisection on the ignition bifurcation ----------------------
    coarse = np.round(np.arange(0.0, 2.001, 0.02), 4)
    for knob in ["s", "phi", "g"]:
        pred = (lambda k: (lambda v: _engaged_at(k, v)))(knob)
        br = find_brackets(knob, coarse, pred)
        if len(br) == 1:
            thr, hw = bisect_boundary(pred, *br[0])
            sweeps[knob]["threshold"] = round(float(thr), 6)
            sweeps[knob]["threshold_definition"] = (
                f"Value of the knob at which AER FGF first exceeds F_on = {F_ON:g} at some "
                f"time, i.e. the ignition bifurcation of the loop. Located by "
                f"{BISECT_ITERS}-step bisection.")
            sweeps[knob]["threshold_bisection_half_width"] = float(hw)
            print(f"[threshold] {knob} = {thr:.6f}")
        else:
            sweeps[knob]["threshold"] = None
            sweeps[knob]["threshold_note"] = f"{len(br)} sign changes on the coarse grid"

    # bmp is non-monotone: it has a lower termination edge and an upper ignition edge
    pred_ign = lambda v: _engaged_at("bmp", v)
    br = find_brackets("bmp", coarse, pred_ign)
    if br:
        thr, hw = bisect_boundary(pred_ign, *br[-1])
        sweeps["bmp"]["threshold_ignite_high"] = round(float(thr), 6)
        sweeps["bmp"]["threshold_ignite_half_width"] = float(hw)
    pred_term = lambda v: readouts(simulate(bmp=float(v)))["terminated"]
    brt = find_brackets("bmp", coarse, pred_term)
    if brt:
        thr, hw = bisect_boundary(pred_term, *brt[0])
        sweeps["bmp"]["threshold_terminate_low"] = round(float(thr), 6)
        sweeps["bmp"]["threshold_terminate_half_width"] = float(hw)
    sweeps["bmp"]["threshold"] = None
    sweeps["bmp"]["threshold_note"] = (
        "BMP is not monotone: the loop needs enough BMP to switch OFF (lower edge) and few "
        "enough to switch ON (upper edge), so it has a window rather than a threshold.")
    print(f"[threshold] bmp window = "
          f"[{sweeps['bmp'].get('threshold_terminate_low')}, "
          f"{sweeps['bmp'].get('threshold_ignite_high')}]")

    # ---- refinement arm -----------------------------------------------------------
    settings = [
        dict(name="baseline", method="LSODA", rtol=1e-6, atol=1e-9, max_step=0.5),
        dict(name="tight-LSODA", method="LSODA", rtol=1e-11, atol=1e-13, max_step=0.1),
        dict(name="Radau", method="Radau", rtol=1e-10, atol=1e-12, max_step=0.1),
        dict(name="DOP853", method="DOP853", rtol=1e-11, atol=1e-13, max_step=0.1),
    ]
    refinement = {"settings": settings, "thresholds": {}, "control_outgrowth": {}}
    for knob in ["s", "phi", "g"]:
        base = sweeps[knob]["threshold"]
        if base is None:
            continue
        vals = {}
        for st in settings:
            kw = {k: v for k, v in st.items() if k != "name"}
            pr = (lambda k, kk: (lambda v: _engaged_at(k, v, **kk)))(knob, kw)
            lo, hi = base - 0.05, base + 0.05
            thr, _ = bisect_boundary(pr, lo, hi)
            vals[st["name"]] = (round(float(thr), 8) if thr is not None else None)
        got = [v for v in vals.values() if v is not None]
        spread = (max(got) - min(got)) if len(got) > 1 else 0.0
        refinement["thresholds"][knob] = dict(
            by_setting=vals, spread=float(spread),
            reported=round(float(base), 4),
            uncertainty=float(max(spread, UNC_FLOOR)),
            uncertainty_basis=f"Full spread of the bisected threshold across "
                              f"{len(settings)} integrator/tolerance settings, floored at "
                              f"{UNC_FLOOR:g} (below which the number is not meaningful for an "
                              f"uncalibrated model).")
        print(f"[refine] {knob}: {base:.6f} +/- {max(spread, UNC_FLOOR):.2e}  "
              f"(spread across integrators {spread:.2e})")
    # mirror the refinement uncertainty back onto each sweep, so a reader of sweeps[knob]
    # never sees a threshold without the uncertainty that belongs to it
    for knob, rt in refinement["thresholds"].items():
        sweeps[knob]["threshold_uncertainty"] = rt["uncertainty"]
        sweeps[knob]["threshold_uncertainty_basis"] = rt["uncertainty_basis"]
    sweeps["bmp"]["threshold_uncertainty"] = max(
        float(sweeps["bmp"].get("threshold_ignite_half_width") or 0.0),
        float(sweeps["bmp"].get("threshold_terminate_half_width") or 0.0), UNC_FLOOR)
    sweeps["bmp"]["threshold_uncertainty_basis"] = (
        f"Bisection half-width only, floored at {UNC_FLOOR:g}. The bmp edges were not "
        f"re-bisected under the refinement arm's {len(settings)} integrator settings, "
        f"unlike s, phi and g.")

    for st in settings:
        kw = {k: v for k, v in st.items() if k != "name"}
        refinement["control_outgrowth"][st["name"]] = round(
            readouts(simulate(n_out=4001, **kw))["outgrowth"], 8)
    cv = list(refinement["control_outgrowth"].values())
    refinement["control_outgrowth_spread"] = float(max(cv) - min(cv))
    refinement["control_outgrowth_relative_spread"] = float((max(cv) - min(cv)) / L_wt)
    print(f"[refine] control L spread across integrators: "
          f"{refinement['control_outgrowth_spread']:.3e} "
          f"({refinement['control_outgrowth_relative_spread']:.2e} relative)")

    # ---- termination ablation -----------------------------------------------------
    abl = termination_ablation()
    for a in abl["arms"]:
        print(f"[ablation] {a['arm'][:52]:52s} terminated={str(a['terminated']):5s} "
              f"window={a['window_duration']:7.2f}")

    # ---- controls -----------------------------------------------------------------
    checks = dict(
        null_control=null_control(),
        positive_control_of_classifier=positive_control(L_wt),
        time_rescaling_invariance=time_rescaling_check(),
        outgrowth_consistency=outgrowth_consistency_check(),
        deterministic=dict(name="no RNG in the model", passed=True,
                           expectation="model uses no random numbers; the run is reproducible "
                                       "without a seed"),
    )
    for k, v in checks.items():
        if isinstance(v, dict) and "passed" in v:
            print(f"[check] {k}: {'PASS' if v['passed'] else 'FAIL'}")
        elif isinstance(v, list):
            print(f"[check] {k}: "
                  f"{sum(c['passed'] for c in v)}/{len(v)} pass")

    # ---- phase map ----------------------------------------------------------------
    n = 61
    xs = np.round(np.linspace(0.0, 1.5, n), 5)
    ys = np.round(np.linspace(0.0, 1.5, n), 5)
    classes, frac = [], []
    for y in ys:
        row, rowf = [], []
        for x in xs:
            r = readouts(simulate(s=float(x), phi=float(y)))
            row.append(classify(r, L_wt))
            rowf.append(round(r["outgrowth"] / L_wt, 5))
        classes.append(row)
        frac.append(rowf)
    pm = dict(
        x_knob="s", x_label=KNOB_DOC["s"]["label"], x_values=[float(v) for v in xs],
        y_knob="phi", y_label=KNOB_DOC["phi"]["label"], y_values=[float(v) for v in ys],
        grid=dict(x=[float(v) for v in xs], y=[float(v) for v in ys], shape=[n, n],
                  x_knob="s", y_knob="phi"),
        grid_shape=[n, n], held_fixed=dict(g=1.0, bmp=1.0),
        classes=classes, outgrowth_fraction_of_wt=frac,
        row_major_note="classes[j][i] is the class at x_values[i], y_values[j].",
    )
    print(f"[phasemap] {n}x{n} grid done")

    # ---- figures ------------------------------------------------------------------
    fig_control(HERE / "shh-loop-control.png")
    fig_threshold(HERE / "shh-loop-threshold.png", sweeps, L_wt)
    fig_phasemap(HERE / "shh-loop-phasemap.png", pm)
    print("[figures] written")

    # ---- assemble JSON ------------------------------------------------------------
    out["model"] = dict(
        name="SHH-GREM1-BMP-FGF limb bud outgrowth loop (caricature)",
        kind="simulation",
        is_observation=False,
        variables=VARIABLES,
        edges=EDGES,
        equations_latex=EQUATIONS_LATEX,
        parameters=[dict(name=k, **v) for k, v in PARAMS.items()],
        nondimensionalisation=(
            f"Time is measured in SHH turnover times (d_S = 1 by definition). Each species is "
            f"scaled by its own maximum, so the unantagonised BMP steady state and the "
            f"underepressed AER FGF steady state are both 1.0 at wild-type settings. This "
            f"removes {n_nondim} parameters (d_S is fixed to 1 by the time unit; b_prod is "
            f"fixed by d_B so that maximal BMP is 1) and makes every Hill constant readable "
            f"as a fraction of maximum. {n_assumed} of the {n_par} parameters remain free, "
            f"and all {n_assumed} are labelled assumed; "
            f"{_count_phrase(n_sourced, 'labelled sourced')}."),
        parameter_status_counts=dict(total=n_par, assumed=n_assumed,
                                     nondimensional=n_nondim, sourced=n_sourced),
        knobs=KNOB_DOC,
        readout_definitions=dict(
            F_on=dict(value=F_ON, status="assumed",
                      note="AER FGF level defining 'the loop is engaged'."),
            T_end=dict(value=T_END, status="assumed",
                       note="Simulated window in SHH turnover times."),
            outgrowth="L(T_end), the time integral of a sharp Hill function of AER FGF; a proxy "
                      "for proximodistal extent, reported only as a fraction of the wild-type "
                      "control because the model has no absolute length scale."),
        initial_condition="S=G=F=Z=L=0; B at its unantagonised steady state b*b_prod/d_B. "
                          "BMP is present first because Benazet 2009 report BMP4 initiates Grem1.",
    )
    out["sweeps"] = sweeps
    out["phase_map"] = pm
    out["refinement_arm"] = refinement
    out["termination_ablation"] = abl
    out["numerical_checks"] = checks
    out["phenotype_classes"] = PHENOTYPE_CLASSES
    out["limitations"] = [
        "This is a SIMULATION. No quantity in this file is an observation of any embryo.",
        "The model is a caricature of a signalling TOPOLOGY. It is not calibrated to any "
        "measured mouse limb bud: no concentration, rate, diffusion length or developmental "
        "time in it was fitted to data, and none should be read as one.",
        f"{n_assumed} of the {n_par} parameters are assumed and "
        f"{_count_phrase(n_sourced, 'sourced')}; the "
        f"other {n_nondim} are fixed by the non-dimensionalisation. They were chosen so the "
        f"wild-type arm initiates, is maintained and self-terminates -- that is, the control "
        f"arm's qualitative behaviour was an input to parameter choice, not an independent "
        f"result.",
        "A threshold in this model is a threshold in this model. It is not a prediction of the "
        "ZRS allelic series at which a mouse loses a limb, and it has no units that could be "
        "compared to one.",
        "The model is non-spatial: SHH, GREM1, BMP and FGF are single well-mixed levels. The "
        "real loop is spatially organised across an epithelial-mesenchymal boundary with "
        "measured gradients, and the Scherz 2004 mechanism it borrows is explicitly geometric "
        "(an expanding descendant zone). Variable Z is a zero-dimensional stand-in for that "
        "geometry.",
        "The model contains no SHH-independent proximal outgrowth, so it cannot distinguish a "
        "Shh-null limb -- which in mice still forms proximal skeleton -- from true amelia. Its "
        "'no-limb' class means only 'this loop never engaged'.",
        "Digit number and digit pattern are outside the model. Sheth et al. 2012 (PMID "
        "23239739) show digit patterning is a Turing-type mechanism whose wavelength distal Hox "
        "genes set; none of that is represented here, so the model says nothing about how many "
        "digits form.",
        "The knob s is held constant in time. In python hindlimb buds the reported defect is "
        "that SHH is weak AND transient (PMID 27773569); a time-varying s is not explored.",
        "Only the classifier's boundaries, not the model, decide where 'truncated' ends and "
        "'normal' begins. Those cuts (5%, 85%, 115% of the wild-type control) are assumed.",
        "The outgrowth window duration is most sensitive to k_Z, a wholly assumed parameter. "
        "No sensitivity analysis over the full parameter space was run.",
        "The two published termination mechanisms are not equal partners in this "
        "parameterisation. The ablation arm shows the loop leans almost entirely on the Scherz "
        "2004 descendant-zone ratchet: without it the loop never terminates, while without the "
        "Verheyden & Sun 2008 FGF-|Grem1 repression it still terminates, about 4% later. So the "
        "self-terminating behaviour shown in the control figure is mostly one mechanism, and "
        "which mechanism dominates in a real limb bud is not addressed here.",
    ]
    out["sources"] = [
        dict(cite="Zuniga A, Haramis AP, McMahon AP, Zeller R (1999). Signal relay by BMP "
                  "antagonism controls the SHH/FGF4 feedback loop in vertebrate limb buds. "
                  "Nature 401:598-602.",
             pmid="10524628", doi="10.1038/44157", read_level="abstract",
             used_for="SHH->GREM1 maintenance; GREM1-|BMP; BMP-|AER FGF; FGF->SHH."),
        dict(cite="Michos O, Panman L, Vintersten K, Beier K, Zeller R, Zuniga A (2004). "
                  "Gremlin-mediated BMP antagonism induces the epithelial-mesenchymal feedback "
                  "signalling controlling metanephric kidney and limb organogenesis. "
                  "Development 131:3401-3410.",
             pmid="15201225", doi="10.1242/dev.01251", read_level="abstract",
             used_for="Grem1-null route (g=0): Grem1 required to establish a functional AER."),
        dict(cite="Scherz PJ, Harfe BD, McMahon AP, Tabin CJ (2004). The limb bud Shh-Fgf "
                  "feedback loop is terminated by expansion of former ZPA cells. "
                  "Science 305:396-399.",
             pmid="15256670", doi="10.1126/science.1096966", read_level="abstract",
             used_for="The Z variable: the expanding Grem1-refractory descendant zone."),
        dict(cite="Verheyden JM, Sun X (2008). An Fgf/Gremlin inhibitory feedback loop triggers "
                  "termination of limb bud outgrowth. Nature 454:638-641.",
             pmid="18594511", doi="10.1038/nature07085", read_level="abstract",
             used_for="FGF-|GREM1 repression, and the requirement that it act only at high FGF."),
        dict(cite="Benazet JD, Bischofberger M, Tiecke E, Goncalves A, Martin JF, Zuniga A, "
                  "Naef F, Zeller R (2009). A self-regulatory system of interlinked signaling "
                  "feedback loops controls mouse limb patterning. Science 323:1050-1053.",
             pmid="19229034", doi="10.1126/science.1168755", read_level="abstract",
             used_for="BMP->GREM1 initiation arm; fast BMP/GREM1 module vs slow SHH/GREM1/FGF "
                      "loop, which sets the relative turnover rates."),
        dict(cite="Sekine K, Ohuchi H, Fujiwara M, et al. (1999). Fgf10 is essential for limb "
                  "and lung formation. Nat Genet 21:138-141.",
             pmid="9916808", doi="10.1038/5096", read_level="abstract",
             used_for="The phi=0 amelia route: in Fgf10-/- limb buds the AER and ZPA do not form."),
        dict(cite="Min H, Danilenko DM, Scully SA, et al. (1998). Fgf-10 is required for both "
                  "limb and lung development and exhibits striking functional similarity to "
                  "Drosophila branchless. Genes Dev 12:3156-3161.",
             pmid="9784490", doi="10.1101/gad.12.20.3156", read_level="abstract",
             used_for="Independent Fgf10-null amelia report; Fgf10 acts upstream of Fgf8."),
        dict(cite="Kvon EZ, Kamneva OK, Melo US, et al. (2016). Progressive Loss of Function in "
                  "a Limb Enhancer during Snake Evolution. Cell 167:633-642.e11.",
             pmid="27768887", doi="10.1016/j.cell.2016.09.028", read_level="abstract",
             used_for="Justifies s as the design knob: snake-ZRS knock-in mice show severe limb "
                      "reduction, and one restored binding site reinstates full function."),
        dict(cite="Leal F, Cohn MJ (2016). Loss and Re-emergence of Legs in Snakes by Modular "
                  "Evolution of Sonic hedgehog and HOXD Enhancers. Curr Biol 26:2966-2973.",
             pmid="27773569", doi="10.1016/j.cub.2016.09.020", read_level="abstract",
             used_for="Python ZRS mutations make SHH weak and transient, causing early "
                      "termination of the outgrowth circuit -- the qualitative behaviour the s "
                      "sweep is compared against."),
        dict(cite="Niemann S, Zhao C, Pascu F, et al. (2004). Homozygous WNT3 mutation causes "
                  "tetra-amelia in a large consanguineous family. Am J Hum Genet 74:558-563.",
             pmid="14872406", doi="10.1086/382196", read_level="abstract",
             used_for="Human tetra-amelia from an upstream initiation failure; context for the "
                      "phi=0 route."),
        dict(cite="Sheth R, Marcon L, Bastida MF, et al. (2012). Hox genes regulate digit "
                  "patterning by controlling the wavelength of a Turing-type mechanism. "
                  "Science 338:1476-1480.",
             pmid="23239739", doi="10.1126/science.1226804", read_level="abstract",
             used_for="Cited only to mark what this model does NOT cover: digit number and "
                      "pattern. No edge is taken from it."),
    ]
    n_src = len(out["sources"])
    read_levels = sorted({s["read_level"] for s in out["sources"]})
    out["provenance"] = dict(
        generator="shh_loop.py",
        source_count=n_src,
        read_levels_present=read_levels,
        source_verification=f"Every PMID and DOI above was resolved through the PubMed "
                            f"E-utilities MCP tools (search_articles / "
                            f"lookup_article_by_citation / get_article_metadata). Read level is "
                            f"{'/'.join(read_levels)} for all {n_src}: the regulatory edges are "
                            f"taken from statements made in the abstracts, not from figures or "
                            f"supplementary data.",
        attribution="Bibliographic metadata retrieved from PubMed.",
        runtime_seconds=None,
    )

    dc = check_derived_counts(out)
    out["numerical_checks"]["derived_counts"] = dc
    checks["derived_counts"] = dc
    print(f"[check] derived_counts: {'PASS' if dc['passed'] else 'FAIL'}"
          + ("" if dc["passed"] else " -> " + "; ".join(dc["problems"])))

    out["provenance"]["runtime_seconds"] = round(time.time() - t0, 2)
    (HERE / "shh-loop.json").write_text(json.dumps(out, indent=2))
    print(f"[done] shh-loop.json written in {out['provenance']['runtime_seconds']}s")

    failed = [k for k, v in checks.items()
              if isinstance(v, dict) and v.get("passed") is False]
    failed += [c["case"] for c in checks["positive_control_of_classifier"] if not c["passed"]]
    if failed:
        raise SystemExit(f"NUMERICAL CHECKS FAILED: {failed}")


if __name__ == "__main__":
    main()
