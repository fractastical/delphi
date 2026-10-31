"""Steady-state oxygen diffusion with constant consumption: the diffusion limit for a sphere and a slab.

Grimes et al. 2014 (J R Soc Interface 11:20131124) state the model in words and typeset equations that are images in the open-access XML:
  (1) steady-state diffusion with consumption:  D * Laplacian(C) = a            (their eq. 2.2, spherical Laplacian; text not read, form from their stated setup)
  (2) boundary conditions as stated:  C = C_o at r = r_o;  C = 0 and dC/dr = 0 at r = r_n
  (3) the 'diffusion limit' r_l: the radius at which the centre pressure just reaches zero (their eq. 2.6; closed form not read from the typeset equation)
The closed forms below were DERIVED here from (1) and (2) with constant a, and verified by substitution in the tests. They are not a transcription of the paper.

Units (SI): D m^2/s; C0 the boundary oxygen amount per unit volume, a the consumption per unit volume, in the same amount unit, so C0/a is a time (s).
Only the ratio C0/a enters. Grimes's own a is in m^3(O2 gas) kg^-1 s^-1 and C0 in m^3 kg^-1; the ratio is the same.
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
