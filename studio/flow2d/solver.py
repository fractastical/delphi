"""2-D incompressible Navier-Stokes on the doubly periodic box [0,2pi)^2, vorticity form, pseudo-spectral (2/3 dealiasing), integrating-factor RK4, torch float64.
  w_t + (U0 + u).grad w = nu lap w,   lap psi = -w,   u = (psi_y, -psi_x)  (U0 = (U0x,U0y) optional uniform mean flow, Galilean).
All output is SIMULATED (declared equations). Same code on CPU and GPU."""
import math
import torch


class NS2D:
    def __init__(self, N, nu, dt, device="cpu", U0=(0.0, 0.0), dealias=True, adv_scale=1.0, nu_scale=1.0, dtype=torch.float64):
        self.N, self.nu, self.dt, self.dev, self.dtype = N, nu * nu_scale, dt, device, dtype
        self.U0, self.adv = U0, adv_scale
        k = torch.fft.fftfreq(N, d=1.0 / N).to(dtype)
        self.kx = k[:, None].to(device)           # axis 0 = x
        self.ky = k[None, :].to(device)
        self.k2 = self.kx ** 2 + self.ky ** 2
        self.k2i = torch.where(self.k2 > 0, 1.0 / self.k2, torch.zeros_like(self.k2))
        kmax = N // 3
        self.mask = ((self.kx.abs() <= kmax) & (self.ky.abs() <= kmax)).to(dtype) if dealias else torch.ones_like(self.k2)
        L = -self.nu * self.k2
        self.E, self.E2 = torch.exp(L * dt), torch.exp(L * dt / 2)

    def vel(self, wh):
        ph = wh * self.k2i
        return torch.fft.ifft2(1j * self.ky * ph).real, torch.fft.ifft2(-1j * self.kx * ph).real     # u = psi_y, v = -psi_x

    def f(self, wh):
        u, v = self.vel(wh)
        wx = torch.fft.ifft2(1j * self.kx * wh).real
        wy = torch.fft.ifft2(1j * self.ky * wh).real
        nl = (self.U0[0] + u) * wx + (self.U0[1] + v) * wy
        return -self.adv * torch.fft.fft2(nl) * self.mask

    def step(self, wh):
        dt, E, E2 = self.dt, self.E, self.E2
        k1 = self.f(wh)
        k2 = self.f(E2 * (wh + 0.5 * dt * k1))
        k3 = self.f(E2 * wh + 0.5 * dt * k2)
        k4 = self.f(E * wh + dt * E2 * k3)
        return E * wh + dt / 6.0 * (E * k1 + 2.0 * E2 * (k2 + k3) + k4)

    def to_hat(self, w):
        return torch.fft.fft2(w) * self.mask

    def diag(self, wh):
        """energy, enstrophy (box averages), max|u|, max|div u| (spectral, ~0)"""
        N2 = float(self.N) ** 4
        ph = wh * self.k2i
        E = 0.5 * float((self.k2 * ph.abs() ** 2).sum() / N2)       # 1/2 <|u|^2> = 1/2 sum k^2 |psi_hat|^2 / N^4
        Z = 0.5 * float((wh.abs() ** 2).sum() / N2)
        u, v = self.vel(wh)
        div = torch.fft.ifft2(1j * self.kx * torch.fft.fft2(u) + 1j * self.ky * torch.fft.fft2(v)).real
        return {"E": E, "Z": Z, "umax": float(torch.sqrt(u * u + v * v).max()), "divmax": float(div.abs().max())}

    def grid(self):
        x = torch.arange(self.N, dtype=self.dtype, device=self.dev) * (2 * math.pi / self.N)
        return torch.meshgrid(x, x, indexing="ij")


def tg_exact(X, Y, t, nu, U0):
    """Taylor-Green vorticity advected by a uniform mean flow: w = 2 sin(x-U0x t) sin(y-U0y t) exp(-2 nu t). Exact NS solution (nonlinear term vanishes)."""
    return 2.0 * torch.sin(X - U0[0] * t) * torch.sin(Y - U0[1] * t) * math.exp(-2.0 * nu * t)


def shear_layer_w0(X, Y, rho=30.0, delta=0.05):
    """Bell-Colella-Glaz style doubly periodic shear layer (thin layers at y=pi/2 and 3pi/2) with a sinusoidal v perturbation; returns vorticity w = v_x - u_y."""
    # u = tanh(rho (y - pi/2)) for y<=pi ; tanh(rho (3pi/2 - y)) for y>pi ; v = delta sin(x)
    sech2 = lambda z: 1.0 / torch.cosh(z) ** 2
    uy = torch.where(Y <= math.pi, rho * sech2(rho * (Y - math.pi / 2)), -rho * sech2(rho * (1.5 * math.pi - Y)))
    vx = delta * torch.cos(X)
    return vx - uy


def rand_w0(N, seed=7, kmax=5):
    g = torch.Generator().manual_seed(seed)
    w = torch.zeros(N, N, dtype=torch.float64)
    X = torch.arange(N, dtype=torch.float64) * 2 * math.pi / N
    for kx in range(-kmax, kmax + 1):
        for ky in range(0, kmax + 1):
            if kx == 0 and ky == 0:
                continue
            a, b = torch.randn(2, generator=g, dtype=torch.float64)
            w += (a * torch.cos(kx * X[:, None] + ky * X[None, :]) + b * torch.sin(kx * X[:, None] + ky * X[None, :])) / (1 + kx * kx + ky * ky)
    return w


