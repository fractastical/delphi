"""Auditable D2Q9 BGK lattice-Boltzmann solver with Guo forcing, mid-way bounce-back on a solid mask, momentum-exchange force and open boundaries.
torch float64; runs on CPU or CUDA unchanged. Lattice units (dx = dt = 1, c_s^2 = 1/3, nu = (tau - 1/2)/3, p = rho/3). Evidence kind: simulated."""
from __future__ import annotations

import math

import torch

CX = [0, 1, 0, -1, 0, 1, -1, -1, 1]
CY = [0, 0, 1, 0, -1, 1, 1, -1, -1]
W = [4 / 9] + [1 / 9] * 4 + [1 / 36] * 4
OPP = [0, 3, 4, 1, 2, 7, 8, 5, 6]


class LBM:
    def __init__(self, nx, ny, tau, solid=None, force=(0.0, 0.0), device="cpu"):
        if tau <= 0.5:
            raise ValueError("tau must exceed 1/2")
        self.nx, self.ny, self.tau, self.dev = nx, ny, tau, torch.device(device)
        self.nu = (tau - 0.5) / 3.0
        d = dict(dtype=torch.float64, device=self.dev)
        self.cx = torch.tensor(CX, **d)[:, None, None]
        self.cy = torch.tensor(CY, **d)[:, None, None]
        self.w = torch.tensor(W, **d)[:, None, None]
        self.solid = torch.zeros(nx, ny, dtype=torch.bool, device=self.dev) if solid is None else solid.to(self.dev)
        self.fluid = ~self.solid
        self.force = force
        self.f = None
        self.open = None
        # link masks: incoming population i at x comes from a solid node at x - c_i  (bounce-back); outgoing link: fluid x, solid x + c_i
        self.bb = []
        self.out = []
        for i in range(9):
            sh = (CX[i], CY[i])
            self.bb.append(torch.roll(self.solid, shifts=sh, dims=(0, 1)) & self.fluid)
            self.out.append(torch.roll(self.solid, shifts=(-CX[i], -CY[i]), dims=(0, 1)) & self.fluid)

    def feq(self, rho, ux, uy):
        cu = self.cx * ux + self.cy * uy
        return self.w * rho * (1 + 3 * cu + 4.5 * cu * cu - 1.5 * (ux * ux + uy * uy))

    def init(self, rho=1.0, ux=0.0, uy=0.0):
        r = torch.full((self.nx, self.ny), rho, dtype=torch.float64, device=self.dev)
        u = torch.full_like(r, ux) if not torch.is_tensor(ux) else ux.to(self.dev)
        v = torch.full_like(r, uy) if not torch.is_tensor(uy) else uy.to(self.dev)
        self.f = self.feq(r, u, v)

    def macro(self):
        rho = self.f.sum(0)
        ux = ((self.f * self.cx).sum(0) + 0.5 * self.force[0]) / rho
        uy = ((self.f * self.cy).sum(0) + 0.5 * self.force[1]) / rho
        return rho, ux, uy

    def set_open(self, U, rho0=1.0):
        """Equilibrium inflow at left/top/bottom columns/rows (rho0, U, 0), zero-gradient outflow at the last column."""
        self.open = (U, rho0)

    def step(self, want_force=False):
        rho, ux, uy = self.macro()
        feq = self.feq(rho, ux, uy)
        om = 1.0 / self.tau
        post = self.f - om * (self.f - feq)
        if self.force != (0.0, 0.0):
            Fx, Fy = self.force
            cu = self.cx * ux + self.cy * uy
            post = post + (1 - 0.5 * om) * self.w * (3 * ((self.cx - ux) * Fx + (self.cy - uy) * Fy) + 9 * cu * (self.cx * Fx + self.cy * Fy))
        new = torch.empty_like(post)
        for i in range(9):
            new[i] = torch.roll(post[i], shifts=(CX[i], CY[i]), dims=(0, 1))
        fx = fy = None
        for i in range(9):
            new[i] = torch.where(self.bb[i], post[OPP[i]], new[i])
        if want_force:
            fx = fy = 0.0
            for i in range(1, 9):
                m = self.out[i]
                s = (post[i] * m).sum()
                fx = fx + 2 * CX[i] * s
                fy = fy + 2 * CY[i] * s
        if self.open is not None:
            U, rho0 = self.open
            eq = self.feq(torch.tensor(rho0, dtype=torch.float64, device=self.dev), torch.tensor(U, dtype=torch.float64, device=self.dev), torch.tensor(0.0, dtype=torch.float64, device=self.dev))
            eq = eq.reshape(9, 1, 1)
            new[:, 0, :] = eq[:, 0, :].expand(9, self.ny)
            new[:, :, 0] = eq[:, :, 0].expand(9, self.nx)
            new[:, :, -1] = eq[:, :, 0].expand(9, self.nx)
            new[:, -1, :] = new[:, -2, :]
        if self.solid.any():
            new = torch.where(self.solid[None], self.w.expand(9, self.nx, self.ny), new)     # solid nodes held at rest equilibrium (rho = 1)
        self.f = new
        return (fx, fy) if want_force else None

    def total_mass(self):
        return float((self.f * self.fluid).sum())
