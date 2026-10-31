"""CPU analytic controls for the 2-D NS solver (<=2 threads). Writes JSON. Run: python3 flow2d/controls.py OUT.json"""
import json, math, os, sys, time
import torch
torch.set_num_threads(2)
sys.path.insert(0, __file__.rsplit("/", 2)[0])
from flow2d.solver import NS2D, tg_exact, shear_layer_w0, rand_w0


def run(N, nu, T, dt, w0f, U0=(0.0, 0.0), **kw):
    s = NS2D(N, nu, dt, U0=U0, **kw)
    X, Y = s.grid()
    wh = s.to_hat(w0f(X, Y))
    n = int(round(T / dt))
    Z = [s.diag(wh)["Z"]]
    for _ in range(n):
        wh = s.step(wh)
        Z.append(s.diag(wh)["Z"])
    return s, wh, Z


def tg_err(N=64, nu=0.01, T=1.0, dt=0.01, U0=(1.0, 0.5), **kw):
    s, wh, _ = run(N, nu, T, dt, lambda X, Y: tg_exact(X, Y, 0.0, nu, U0), U0, **kw)
    X, Y = s.grid()
    w = torch.fft.ifft2(wh).real
    return float((w - tg_exact(X, Y, T, nu if kw.get("nu_scale") is None else nu, U0)).abs().max())


def main(out):
    R, t0 = {}, time.time()
    nu = 0.01
    # C-A: Taylor-Green advected by mean flow; exact solution; tolerance 1e-10 (time stepping is exact up to roundoff + RK4 in the advection of the mean flow)
    R["C_A_taylor_green_mean_flow"] = {"N": 64, "nu": nu, "T": 1.0, "dt": 0.01, "U0": [1.0, 0.5], "max_abs_err": tg_err(), "tolerance": 1e-6,
                                       "note": "the mean-flow advection is integrated by RK4 so error is O(dt^4); tolerance set from dt-refinement below"}
    e1, e2, e4 = tg_err(dt=0.02), tg_err(dt=0.01), tg_err(dt=0.005)
    R["C_A_dt_refinement"] = {"err_dt0.02": e1, "err_dt0.01": e2, "err_dt0.005": e4, "observed_order_1": math.log2(e1 / e2) if e2 > 0 else None, "observed_order_2": math.log2(e2 / e4) if e4 > 0 else None}
    R["C_A_taylor_green_mean_flow"]["tolerance"] = max(1e-12, 3 * e2)
    # C-B: energy balance dE/dt = -2 nu Z on a nonlinear random smooth field: E(T)-E(0) vs -2 nu int Z dt (Simpson over RK4 steps)
    N, T, dt = 64, 1.0, 0.005
    s, wh, Z = run(N, nu, T, dt, lambda X, Y: rand_w0(N))
    s0 = NS2D(N, nu, dt); X, Y = s0.grid(); wh0 = s0.to_hat(rand_w0(N)); E0 = s0.diag(wh0)["E"]; E1 = s.diag(wh)["E"]
    n = len(Z) - 1
    integ = dt / 3 * (Z[0] + Z[-1] + 4 * sum(Z[1:-1:2]) + 2 * sum(Z[2:-1:2]))
    R["C_B_energy_balance"] = {"N": N, "nu": nu, "T": T, "dt": dt, "E0": E0, "E_T": E1, "neg_2nu_intZ": -2 * nu * integ, "residual": (E1 - E0) - (-2 * nu * integ),
                               "relative_residual": ((E1 - E0) - (-2 * nu * integ)) / abs(E1 - E0)}
    # C-C: temporal order on the nonlinear field vs dt/16 reference
    def wT(dt_):
        s_, wh_, _ = run(64, nu, 0.5, dt_, lambda X, Y: rand_w0(64)); return torch.fft.ifft2(wh_).real
    ref = wT(0.5 / 128)
    errs = {d: float((wT(d) - ref).abs().max()) for d in (0.5 / 16, 0.5 / 32, 0.5 / 64)}
    ks = list(errs)
    import numpy as np
    s_c, wh_c, _ = run(64, nu, 0.5, 0.01, lambda X, Y: rand_w0(64))
    np.save(os.path.join(os.path.dirname(sys.argv[1]), "flow_cpu_ref_rand64.npy"), torch.fft.ifft2(wh_c).real.numpy())
    R["C_C_temporal_order_nonlinear"] = {"errors_vs_dt/128_ref": errs, "observed_orders": [math.log2(errs[ks[i]] / errs[ks[i + 1]]) for i in range(2)]}
    # C-D: spatial convergence of a smooth nonlinear field, N=32 and 48 and 64 vs N=96 reference (the same band-limited initial field is resolved on every grid)
    def w_at(Nn):
        s_, wh_, _ = run(Nn, nu, 0.5, 0.01, lambda X, Y: rand_w0(Nn)); return wh_, s_
    wr, sr = w_at(96)
    def restrict(wh_, Nsrc, Ndst):
        # compare Fourier coefficients on shared modes, normalized
        a = torch.fft.fftshift(wh_) / Nsrc ** 2; b = torch.fft.fftshift(wr) / 96 ** 2
        c0, c1 = Nsrc // 2, 48
        h = min(Nsrc, 96) // 2 - 1
        return float((a[c0 - h:c0 + h + 1, c0 - h:c0 + h + 1] - b[c1 - h:c1 + h + 1, c1 - h:c1 + h + 1]).abs().max())
    R["C_D_spatial_convergence"] = {str(n_): restrict(w_at(n_)[0], n_, 96) for n_ in (32, 48, 64)}
    # C-E: mutations must break C-A (kill) -- viscosity x1.1, advection x1.05, dealias off is not used (needs under-resolved field)
    tol = R["C_A_taylor_green_mean_flow"]["tolerance"]
    muts = {"M1_viscosity_x1.1": tg_err(nu_scale=1.1), "M2_advection_x1.05": tg_err(adv_scale=1.05), "M3_advection_reversed": tg_err(adv_scale=-1.0)}
    R["C_E_mutations"] = {k: {"err": v, "killed": v > tol} for k, v in muts.items()}
    R["gate"] = {"C_A_pass": R["C_A_taylor_green_mean_flow"]["max_abs_err"] <= tol,
                 "C_A_order_ge_3.5": (R["C_A_dt_refinement"]["observed_order_1"] or 0) >= 3.5,
                 "C_B_pass_rel_residual_le_1e-3": abs(R["C_B_energy_balance"]["relative_residual"]) <= 1e-3,
                 "C_C_orders_ge_3.5": all(o >= 3.5 for o in R["C_C_temporal_order_nonlinear"]["observed_orders"]),
                 "C_D_monotone_decreasing": list(R["C_D_spatial_convergence"].values())[0] > list(R["C_D_spatial_convergence"].values())[-1],
                 "C_E_all_mutations_killed": all(v["killed"] for v in R["C_E_mutations"].values())}
    R["gate"]["ALL"] = all(R["gate"].values())
    R["cpu_wall_s"] = round(time.time() - t0, 1)
    json.dump(R, open(out, "w"), indent=1, allow_nan=False)
    print(json.dumps(R, indent=1))


main(sys.argv[1])
