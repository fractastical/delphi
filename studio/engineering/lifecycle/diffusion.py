"""Steady-state oxygen diffusion with constant consumption: sphere and slab profiles.

Grimes et al. 2014 (J R Soc Interface 11:20131124; doi:10.1098/rsif.2013.1124,
PMC3899881) state the steady spherical diffusion equation and diffusion-limit
radius in displayed equations 2.2 and 2.6. We retrieved and read the equation
images because their MathML/XML contains image placeholders. Equation 2.6 is
written in partial pressure as r_l = sqrt(6 D p_o/(a Omega)); substituting the
paper's C_o = p_o/Omega yields sqrt(6 D C_o/a). Thus the spherical limit
coefficient 6 is explicitly in the paper, while this code's profile is the
closed form for constant a under the stated boundary conditions.

The slab profile and coefficient 2 are a one-dimensional analogue derived
here from D C'' = a with a no-flux center and supplied outer face; they are not
an equation attributed to Grimes. The paper's C is oxygen volume per unit
tissue mass, and a is oxygen consumption per unit tissue mass per time, so the
ratio C_o/a has time units. Grimes' DLD1 human colorectal tumour data and
parameters are source context only; they are not portable to another tissue.

Primary source: https://doi.org/10.1098/rsif.2013.1124

Units (SI): D m^2/s; C0 is the boundary oxygen-gas volume per tissue mass (m^3/kg), and a is oxygen-gas-volume consumption per tissue mass per second (m^3 kg^-1 s^-1). The ratio C0/a is seconds. If inputs are instead expressed per tissue volume, convert C0 and a consistently; that conversion is not performed here.
"""

from __future__ import annotations

import math


def sphere_limit_radius(D: float, c0_over_a: float) -> float:
    """r_l such that C(0) = 0 with C(r) = C0 - (a / 6D) (r_o^2 - r^2):  r_l = sqrt(6 D C0 / a)."""
    return math.sqrt(6.0 * D * c0_over_a)


def c0_over_a_from_sphere_limit(D: float, r_l: float) -> float:
    """Invert the sphere form: the C0/a (seconds) that makes a sphere of radius r_l just reach zero at its centre."""
    return r_l * r_l / (6.0 * D)


def slab_limit_thickness(D: float, c0_over_a: float) -> float:
    """One-sided supply: C(x) = C0 - (a / 2D) (L^2 - x^2) with the no-flux face at x=0; C(0)=0 at L = sqrt(2 D C0 / a)."""
    return math.sqrt(2.0 * D * c0_over_a)


def slab_max_total_thickness(D: float, c0_over_a: float) -> float:
    """Supplied from both faces, the no-flux plane is the mid-plane, so the total thickness is twice the one-sided limit."""
    return 2.0 * slab_limit_thickness(D, c0_over_a)


def sphere_profile(r: float, r_o: float, D: float, c0: float, a: float) -> float:
    return c0 - (a / (6.0 * D)) * (r_o ** 2 - r ** 2)


def slab_profile(x: float, L: float, D: float, c0: float, a: float) -> float:
    return c0 - (a / (2.0 * D)) * (L ** 2 - x ** 2)
