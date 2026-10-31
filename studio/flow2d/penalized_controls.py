"""CPU analytic control for the penalized-boundary solver: steady Poiseuille flow between penalized walls (exact parabola), grid refinement, and mutations. <= 2 threads.
Usage: python3 flow2d/penalized_controls.py OUT.json"""
import json, math, os, sys, time
import torch
torch.set_num_threads(2)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flow2d.penalized import NS2DPen, channel_mask

NU, H, UMAX = 0.05, 0.6, 1.0
G = 2 * NU * UMAX / H ** 2                       # u(y) = G/(2 nu) (h^2 - (y-pi)^2), centreline UMAX


def run(N, eta=1e-4, T=30.0, dt=0.01, nu_scale=1.0, G_scale=1.0, wall=True):
    chi = channel_mask(N, H) if wall else torch.zeros(N, N, dtype=torch.float64)
    s = NS2DPen(N, NU * nu_scale, dt, chi, eta=eta, G=(G * G_scale, 0.0), dealias=True, dynamic_mean=True)
    wh = torch.zeros(N, N, dtype=torch.complex128)
    for _ in range(int(round(T / dt))):
        wh = s.step(wh)
    u, _ = s.vel(wh)
    return u[0] + s.U0[0], s


def err(N, **kw):
    u, s = run(N, **kw)
    y = torch.arange(N, dtype=torch.float64) * (2 * math.pi / N)
    exact = G / (2 * NU) * (H ** 2 - (y - math.pi) ** 2)
    fluid = (torch.abs(y - math.pi) < 0.8 * H)             # compare in the fluid core, away from the mask transition
    e = float(torch.linalg.norm((u - exact)[fluid]) / torch.linalg.norm(exact[fluid]))
    return e, float(u[fluid].max()), float(exact.max())


def main(out):
    R, t0 = {}, time.time()
    errs = {}
    for N in (64, 128, 256):
        e, um, ex = err(N)
        errs[N] = {"rel_L2_error_core": e, "centreline_numeric": um, "centreline_exact": ex}
    ks = list(errs)
    R["poiseuille_refinement"] = {"nu": NU, "h": H, "eta": 1e-4, "errors": errs, "observed_order_64_to_128": math.log2(errs[64]["rel_L2_error_core"] / errs[128]["rel_L2_error_core"]),
                                  "observed_order_128_to_256": math.log2(errs[128]["rel_L2_error_core"] / errs[256]["rel_L2_error_core"])}
    e256 = errs[256]["rel_L2_error_core"]
    # mutations on the N=256 case: leaky walls (eta x 1e4), no walls, wrong viscosity, wrong forcing; each must exceed the tolerance
    TOL = 0.05
    mut = {"M1_leaky_wall_eta_x1e4": err(256, eta=1e0)[0], "M2_no_wall": err(256, wall=False)[0], "M3_viscosity_x1.2": err(256, nu_scale=1.2)[0], "M4_forcing_x1.2": err(256, G_scale=1.2)[0]}
    R["mutations_rel_L2"] = mut
    R["gate"] = {"core_error_le_5pct_N256": e256 <= TOL, "error_decreases_with_N": errs[256]["rel_L2_error_core"] < errs[128]["rel_L2_error_core"] < errs[64]["rel_L2_error_core"],
                 "observed_order_ge_0.8_128_to_256": R["poiseuille_refinement"]["observed_order_128_to_256"] >= 0.8, "all_mutations_exceed_tol": all(v > TOL for v in mut.values())}
    R["gate"]["ALL"] = all(R["gate"].values()); R["cpu_wall_s"] = round(time.time() - t0, 1)
    json.dump(R, open(out, "w"), indent=1, allow_nan=False); print(json.dumps(R, indent=1))


main(sys.argv[1])
