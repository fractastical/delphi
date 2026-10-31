"""Volume-penalized (Brinkman) immersed boundary on top of the periodic spectral NS solver: a rigid body = mask chi (1 inside) with u_s = 0, uniform mean flow U0, optional body force G.
Splitting per step: IFRK4 for advection+viscosity (flow2d.solver.NS2D), then pointwise: U += dt G (1-chi); U <- U / (1 + dt chi/eta) (implicit penalization, first order in dt), then the vorticity is
re-derived from the modified velocity (spectral curl, 2/3 dealiased), which also removes the divergent part. Drag = integral of (chi/eta) U over the box (force of the fluid on the body).
Evidence kind: simulated. Penalization error scales like sqrt(eta nu) plus the mask resolution; it is NOT a body-fitted solver."""
import math
import torch
from .solver import NS2D


class NS2DPen(NS2D):
    def __init__(self, N, nu, dt, chi, eta=1e-3, G=(0.0, 0.0), dynamic_mean=False, **kw):
        super().__init__(N, nu, dt, **kw)
        self.dynamic_mean = dynamic_mean      # True: the domain-mean velocity U0 evolves with the net forcing and penalization (momentum balance); False: U0 is prescribed
        self.chi, self.eta, self.G = chi.to(self.dev), eta, G
        self.fac = 1.0 / (1.0 + dt * self.chi / eta)
        self.dA = (2 * math.pi / N) ** 2
        self.last_force = (0.0, 0.0)

    def step(self, wh):
        wh = super().step(wh)
        u, v = self.vel(wh)
        U = u + self.U0[0] + self.dt * self.G[0] * (1 - self.chi)
        V = v + self.U0[1] + self.dt * self.G[1] * (1 - self.chi)
        U, V = U * self.fac, V * self.fac
        self.last_force = (float((self.chi / self.eta * U).sum() * self.dA), float((self.chi / self.eta * V).sum() * self.dA))
        if self.dynamic_mean:
            self.U0 = (float(U.mean()), float(V.mean()))
        Uh, Vh = torch.fft.fft2(U - self.U0[0]), torch.fft.fft2(V - self.U0[1])
        return (1j * self.kx * Vh - 1j * self.ky * Uh) * self.mask         # w = v_x - u_y

    def mask_of(self, kind, **p):
        raise NotImplementedError


def _ramp(sdist, w):
    """compact-support smooth indicator: 1 for sdist <= -w/2, 0 for sdist >= +w/2, cubic smoothstep between (sdist = signed distance, negative inside the body).
    Compact support matters: a tanh tail leaves chi/eta >> 1 well inside the nominal fluid region when eta is small, which shifts the effective wall inward."""
    t = torch.clamp(0.5 - sdist / w, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def disk_mask(N, cx, cy, radius, smooth=2.0, dtype=torch.float64):
    """indicator of a disk, transition width smooth*dx, compact support (periodic distance)."""
    x = torch.arange(N, dtype=dtype) * (2 * math.pi / N)
    dx = 2 * math.pi / N
    X, Y = torch.meshgrid(x, x, indexing="ij")
    def d(a, c):
        r = (a - c + math.pi) % (2 * math.pi) - math.pi
        return r
    r = torch.sqrt(d(X, cx) ** 2 + d(Y, cy) ** 2)
    return _ramp(r - radius, smooth * dx)


def channel_mask(N, h, dtype=torch.float64, smooth=2.0):
    """walls for |y - pi| > h (fluid slab of half-width h centred at y = pi), compact-support transition of width smooth*dx."""
    y = torch.arange(N, dtype=dtype) * (2 * math.pi / N)
    dx = 2 * math.pi / N
    s = _ramp(h - torch.abs(y - math.pi), smooth * dx)
    return s[None, :].expand(N, N).contiguous()
