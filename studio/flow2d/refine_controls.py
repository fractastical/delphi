"""Protocol 5 CPU controls (<=2 threads). Paired-step criterion with EQUAL end times (dt = T/n exactly): theory-conformant on a resolved case, tiny on the demo's flow at small N,
and the two mutations that matter are caught: (M1) unequal end times, the defect of the Protocol 4 check; (M2) a partner run with changed physics (nu x 1.1).
Usage: python3 flow2d/refine_controls.py OUT.json"""
import json, math, os, sys, time
import torch
torch.set_num_threads(2)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flow2d.solver import NS2D, shear_layer_w0

BOUND = 1e-4


def run(N, nu, n, dt, rho, nu_scale=1.0):
    s = NS2D(N, nu, dt, nu_scale=nu_scale)
    X, Y = s.grid()
    wh = s.to_hat(shear_layer_w0(X, Y, rho=rho))
    umax = 0.0
    for k in range(n):
        wh = s.step(wh)
        if k % 10 == 0:
            umax = max(umax, s.diag(wh)["umax"])
    return wh, umax


def rel(a, b):
    A, B = torch.fft.ifft2(a).real, torch.fft.ifft2(b).real
    return float(torch.linalg.norm(A - B) / torch.linalg.norm(B))


def main(out):
    R, t0 = {}, time.time()
    T = 2.0
    # resolved: N=128, rho=4, nu=1e-3; dt = T/n with n = 200, 400, 800 (dt = 0.01, 0.005, 0.0025)
    N, nu, rho = 128, 1e-3, 4.0
    w = {n: run(N, nu, n, T / n, rho) for n in (200, 400, 800)}
    e1, e2 = rel(w[200][0], w[400][0]), rel(w[400][0], w[800][0])
    R["resolved_N128_rho4_equalT"] = {"cfl_max_at_dt0.01": w[200][1] * 0.01 / (2 * math.pi / N), "rel_L2_dt_vs_dt/2": e1, "rel_L2_dt/2_vs_dt/4": e2, "ratio": e1 / e2,
                                      "pass_paired_le_1e-4": e1 <= BOUND, "pass_ratio_ge_8": e1 / e2 >= 8}
    # the demo's flow (rho=30, nu=1e-4) at small N with equal end time: n=1000, 2000 (dt = 2e-3, 1e-3)
    a, b = run(128, 1e-4, 1000, 2e-3, 30.0)[0], run(128, 1e-4, 2000, 1e-3, 30.0)[0]
    R["demo_flow_N128_equalT"] = {"rel_L2_dt_vs_dt/2": rel(a, b), "pass_le_1e-4": rel(a, b) <= BOUND}
    # M1: unequal end times as in the Protocol 4 check: 833 steps of 2.4e-3 (T=1.9992) vs 1667 steps of 1.2e-3 (T=2.0004)
    c, d = run(128, 1e-4, 833, 2.4e-3, 30.0)[0], run(128, 1e-4, 1667, 1.2e-3, 30.0)[0]
    R["M1_unequal_end_times"] = {"rel_L2": rel(c, d), "caught_by_criterion": rel(c, d) > BOUND, "note": "reproduces the magnitude of the Protocol 4 dt-halving 'failure' (2.83e-3 at N=512): it is an end-time mismatch of 1.2e-3, not a time-scheme error"}
    # M2: partner with changed physics
    e = run(128, 1e-4, 2000, 1e-3, 30.0, nu_scale=1.1)[0]
    R["M2_partner_viscosity_x1.1"] = {"rel_L2": rel(a, e), "caught_by_criterion": rel(a, e) > BOUND}
    R["gate"] = {"resolved_paired": R["resolved_N128_rho4_equalT"]["pass_paired_le_1e-4"], "resolved_ratio": R["resolved_N128_rho4_equalT"]["pass_ratio_ge_8"],
                 "demo_flow_paired": R["demo_flow_N128_equalT"]["pass_le_1e-4"], "M1_caught": R["M1_unequal_end_times"]["caught_by_criterion"], "M2_caught": R["M2_partner_viscosity_x1.1"]["caught_by_criterion"]}
    R["gate"]["ALL"] = all(R["gate"].values())
    R["cpu_wall_s"] = round(time.time() - t0, 1)
    json.dump(R, open(out, "w"), indent=1, allow_nan=False)
    print(json.dumps(R, indent=1))


main(sys.argv[1])
