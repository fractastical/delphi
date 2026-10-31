"""Compact conditional DDPM surrogate for a 1-D two-channel Schnakenberg reaction-diffusion field (SIMULATED data from a real forward solver; not a fin, not measured).
Solver = batched torch port of engineering/simulation/rd_frames.py solver A (Strang splitting, exact DCT-II diffusion, RK4 reaction, dt 0.02, zero-flux), equivalence tested.
Subcommands: preflight (hashes/imports only, never trains) | control (gate) | run (dataset -> train -> freeze -> holdout eval) | smoke (tiny CPU/CUDA end-to-end on dev ids).
Everything is in model units; tau is dimensionless. No physics loss: conditioning does not guarantee the PDE holds, and the evaluation measures it instead."""
import argparse, copy, hashlib, json, math, os, platform, subprocess, sys, time
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
S = CFG["solver"]; N = S["N"]; DT = S["dt_tau"]
sha = lambda b: hashlib.sha256(b).hexdigest()
def sha_file(p): return sha(open(p, "rb").read())
def jdump(o, p): open(p, "w").write(json.dumps(o, indent=1, sort_keys=True, default=lambda x: x.item() if hasattr(x, "item") else str(x)))

# ------------------------------------------------------------------ solver
def dct_matrix(n, dtype=torch.float64, device="cpu"):
    k = torch.arange(n, dtype=torch.float64)[:, None]; m = torch.arange(n, dtype=torch.float64)[None, :]
    D = math.sqrt(2.0 / n) * torch.cos(math.pi * (2 * m + 1) * k / (2 * n)); D[0] *= 1 / math.sqrt(2.0)
    return D.to(dtype=dtype, device=device)

def ic_modal(seed, K, L, n, amp_u, amp_v):                  # same construction as rd_frames.ic_modal
    rng = np.random.default_rng(int(seed)); cu, cv = rng.standard_normal(K), rng.standard_normal(K)
    x = (np.arange(n) + 0.5) * L / n; M = np.cos(np.outer(x, np.arange(1, K + 1)) * math.pi / L)
    return [amp * (M @ c) / math.sqrt(0.5 * float(np.sum(c * c))) for c, amp in ((cu, amp_u), (cv, amp_v))]

def advance(u, v, a, b, d, L, n_steps, dt=DT, save_steps=(), D=None):
    """u, v: (B,N) float64 tensors; a,b,d,L: (B,) tensors. Strang splitting as rd_frames.run_cell. Returns u, v and saved list of (u,v) at save_steps."""
    dev = u.device; D = dct_matrix(u.shape[-1], device=dev) if D is None else D
    q = (torch.arange(u.shape[-1], dtype=torch.float64, device=dev)[None, :] * math.pi / L[:, None]) ** 2
    mu, mv = torch.exp(-q * dt / 2), torch.exp(-d[:, None] * q * dt / 2); a, b = a[:, None], b[:, None]
    dif = lambda x, m: ((x @ D.T) * m) @ D
    def react(u, v):
        w = u * u * v; return a - u + w, b - w
    saves, ss = [], set(int(s) for s in save_steps)
    for k in range(1, n_steps + 1):
        u, v = dif(u, mu), dif(v, mv)
        k1u, k1v = react(u, v); k2u, k2v = react(u + .5 * dt * k1u, v + .5 * dt * k1v)
        k3u, k3v = react(u + .5 * dt * k2u, v + .5 * dt * k2v); k4u, k4v = react(u + dt * k3u, v + dt * k3v)
        u = u + dt / 6 * (k1u + 2 * k2u + 2 * k3u + k4u); v = v + dt / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
        u, v = dif(u, mu), dif(v, mv)
        if k in ss: saves.append((u.clone(), v.clone()))
    return u, v, saves

def simulate(P, seeds, device="cpu", eps=None, K=None, save_tau=None, chunk=2048):
    """P: (B,4) numpy [a,b,d,L]; seeds: (B,) int. Returns fields (B,nT,2,N) float64 numpy and failed (B,) bool."""
    eps = S["eps"] if eps is None else eps; K = S["K_modes"] if K is None else K; save_tau = S["save_tau"] if save_tau is None else save_tau
    steps = [int(round(t / DT)) for t in save_tau]; out, fail = [], []
    for i in range(0, len(P), chunk):
        p, sd = P[i:i + chunk], seeds[i:i + chunk]; us, vs = [], []
        for (a, b, d, L), s in zip(p, sd):
            ust, vst = a + b, b / (a + b) ** 2; pu, pv = ic_modal(s, K, L, N, eps * abs(ust), eps * abs(vst)); us.append(ust + pu); vs.append(vst + pv)
        T = lambda x: torch.tensor(np.asarray(x), dtype=torch.float64, device=device)
        u, v = T(us), T(vs); _, _, sv = advance(u, v, T(p[:, 0]), T(p[:, 1]), T(p[:, 2]), T(p[:, 3]), steps[-1], save_steps=steps)
        f = torch.stack([torch.stack([x, y], 1) for x, y in sv], 1).cpu().numpy(); out.append(f)
    f = np.concatenate(out); bad = ~np.isfinite(f).all((1, 2, 3)) | (np.abs(np.nan_to_num(f, nan=1e9)).max((1, 2, 3)) > 1000)
    f[bad] = 0.0; return f, bad

def dominant_mode(u, D=None):                              # u: (...,N) numpy or torch; DCT-II mode index of the mean-removed field, index 0 excluded
    t = torch.as_tensor(u, dtype=torch.float64); D = dct_matrix(t.shape[-1]) if D is None else D
    c = ((t - t.mean(-1, keepdim=True)) @ D.T).abs(); c[..., 0] = 0; return c.argmax(-1).numpy()

# ------------------------------------------------------------------ data
def settings_table():
    r = np.random.default_rng(CFG["settings_rng_seed"]); pr = CFG["prior"]; n = CFG["n_settings"]
    return np.stack([r.uniform(*pr[k], size=n) for k in ("a", "b", "d", "L")], 1)

def split_seeds(spec):
    s = spec["seed_indices"]; return list(range(s[0], s[1] + 1)) if spec.get("note", "").startswith("seed_indices is an inclusive") else list(s)

def build_split(name, device, table, ids=None, seed_idx=None, save_tau=None, T_override=None):
    spec = CFG["splits"][name]; ids = list(range(*spec["setting_ids"])) if ids is None else ids; seed_idx = split_seeds(spec) if seed_idx is None else seed_idx
    sid = np.array([i for i in ids for _ in seed_idx]); sdx = np.array([j for _ in ids for j in seed_idx]); seeds = sid * 1000 + sdx
    t0 = time.time(); f, bad = simulate(table[sid], seeds, device=device, save_tau=save_tau); sec = time.time() - t0
    return {"setting_id": sid, "seed_index": sdx, "ic_seed": seeds, "params": table[sid], "fields": f.astype(np.float32), "failed": bad, "solver_seconds": sec, "device": device}

def flatten(d, taus):                                      # (runs, nT, 2, N) -> one row per (run, time) with its condition
    ok = ~d["failed"]; r, nt = np.nonzero(ok[:, None] & np.ones((1, len(taus)), bool))
    cond = np.concatenate([d["params"][r], np.asarray(taus, float)[nt][:, None]], 1)
    return cond.astype(np.float32), d["fields"][r, nt], d["setting_id"][r], d["ic_seed"][r]

def cscale(c):
    lo = np.array([CFG["prior"][k][0] for k in ("a", "b", "d", "L", "t")], np.float32); hi = np.array([CFG["prior"][k][1] for k in ("a", "b", "d", "L", "t")], np.float32)
    return 2 * (c - lo) / (hi - lo) - 1

# ------------------------------------------------------------------ model
def temb(t, dim=64):
    h = dim // 2; f = torch.exp(-math.log(10000) * torch.arange(h, device=t.device) / h); a = t[:, None].float() * f[None]; return torch.cat([a.sin(), a.cos()], 1)

class Blk(nn.Module):
    def __init__(s, i, o, e):
        super().__init__(); s.c1 = nn.Conv1d(i, o, 3, padding=1, padding_mode="replicate"); s.n1 = nn.GroupNorm(8, o); s.c2 = nn.Conv1d(o, o, 3, padding=1, padding_mode="replicate")
        s.n2 = nn.GroupNorm(8, o); s.e = nn.Linear(e, o); s.sk = nn.Conv1d(i, o, 1) if i != o else nn.Identity()
    def forward(s, x, e):
        h = F.silu(s.n1(s.c1(x))) + s.e(e)[:, :, None]; return F.silu(s.n2(s.c2(h))) + s.sk(x)

class Net(nn.Module):                                      # replicate padding == half-sample symmetric extension: zero-flux ends
    def __init__(s, c=64, e=128, ncond=5):
        super().__init__(); s.t = nn.Sequential(nn.Linear(64, e), nn.SiLU(), nn.Linear(e, e)); s.c = nn.Sequential(nn.Linear(ncond, e), nn.SiLU(), nn.Linear(e, e))
        s.e0 = Blk(2, c, e); s.d1 = nn.Conv1d(c, c, 3, 2, 1); s.e1 = Blk(c, 2 * c, e); s.d2 = nn.Conv1d(2 * c, 2 * c, 3, 2, 1); s.e2 = Blk(2 * c, 4 * c, e)
        s.m = Blk(4 * c, 4 * c, e); s.u1 = Blk(4 * c + 2 * c, 2 * c, e); s.u0 = Blk(2 * c + c, c, e); s.o = nn.Conv1d(c, 2, 1)
    def forward(s, x, t, c):
        e = s.t(temb(t)) + s.c(c); h0 = s.e0(x, e); h1 = s.e1(s.d1(h0), e); h = s.m(s.e2(s.d2(h1), e), e)
        h = s.u1(torch.cat([F.interpolate(h, scale_factor=2), h1], 1), e); h = s.u0(torch.cat([F.interpolate(h, scale_factor=2), h0], 1), e); return s.o(h)

def schedule(T, dev):
    s = 0.008; f = lambda t: math.cos((t / T + s) / (1 + s) * math.pi / 2) ** 2; ab = np.array([f(t) for t in range(T + 1)]); ab = ab / ab[0]
    beta = np.clip(1 - ab[1:] / ab[:-1], 0, 0.999); abar = np.cumprod(1 - beta)
    return [torch.tensor(x, dtype=torch.float32, device=dev) for x in (beta, 1 - beta, abar)]

@torch.no_grad()
def sample(net, cond, sch, gen, keep_every=0):
    beta, alpha, abar = sch; T = len(beta); x = torch.randn(cond.shape[0], 2, N, device=cond.device, generator=gen); traj = []
    for t in range(T - 1, -1, -1):
        eps = net(x, torch.full((x.shape[0],), t, device=x.device), cond)
        x = (x - beta[t] / (1 - abar[t]).sqrt() * eps) / alpha[t].sqrt()
        if t > 0: x = x + (beta[t] * (1 - abar[t - 1]) / (1 - abar[t])).sqrt() * torch.randn(x.shape, device=x.device, generator=gen)
        if keep_every and (t % keep_every == 0): traj.append(x.cpu().numpy())
    return x, traj

def gpu_telemetry():
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw", "--format=csv,noheader"], capture_output=True, text=True, timeout=20)
        return o.stdout.strip() if o.returncode == 0 else None
    except Exception:
        return None

def env_receipt(dev):
    r = {"python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__, "cuda_available": torch.cuda.is_available(), "cuda_version": torch.version.cuda,
         "device": dev, "cpu_count": os.cpu_count(), "torch_threads": torch.get_num_threads(), "gpu_telemetry": gpu_telemetry()}
    if torch.cuda.is_available(): r["gpu_name"] = torch.cuda.get_device_name(0); r["gpu_capability"] = torch.cuda.get_device_capability(0)
    return r

# ------------------------------------------------------------------ train
def train(cond, fields, tc, dev, out, log_extra=None):
    mean = fields.mean((0, 2), keepdims=True); std = fields.std((0, 2), keepdims=True)          # per-channel statistics from TRAINING rows only
    X = torch.tensor((fields - mean) / std, device=dev); C = torch.tensor(cscale(cond), device=dev); n = len(X)
    torch.manual_seed(tc["seed"]); net = Net().to(dev); ema = copy.deepcopy(net).eval(); sch = schedule(CFG["model"]["T_diffusion"], dev)
    opt = torch.optim.AdamW(net.parameters(), lr=tc["lr"], weight_decay=1e-4); log = []; t0 = time.time(); g = torch.Generator(device=dev); g.manual_seed(tc["seed"])
    for step in range(1, tc["steps"] + 1):
        lr = tc["lr_final"] + 0.5 * (tc["lr"] - tc["lr_final"]) * (1 + math.cos(math.pi * step / tc["steps"]))
        for pg in opt.param_groups: pg["lr"] = lr
        idx = torch.randint(0, n, (tc["batch"],), device=dev, generator=g); x0, c = X[idx], C[idx]
        t = torch.randint(0, len(sch[0]), (tc["batch"],), device=dev, generator=g); e = torch.randn(x0.shape, device=dev, generator=g); ab = sch[2][t][:, None, None]
        loss = F.mse_loss(net(ab.sqrt() * x0 + (1 - ab).sqrt() * e, t, c), e); opt.zero_grad(set_to_none=True); loss.backward()
        nn.utils.clip_grad_norm_(net.parameters(), tc["grad_clip"]); opt.step()
        with torch.no_grad():
            for pe, pn in zip(ema.parameters(), net.parameters()): pe.mul_(tc["ema"]).add_(pn, alpha=1 - tc["ema"])
        if step % tc["log_every"] == 0 or step == 1:
            rec = {"step": step, "loss": float(loss.detach()), "lr": lr, "elapsed_s": time.time() - t0}
            if dev == "cuda" and step % (tc["log_every"] * 10) == 0: rec["gpu"] = gpu_telemetry(); rec["cuda_mem_alloc_mb"] = torch.cuda.max_memory_allocated() / 2**20
            log.append(rec)
    train_s = time.time() - t0
    with open(os.path.join(out, "train_loss.jsonl"), "w") as f: f.write("\n".join(json.dumps(r) for r in log))
    ck = {"ema": ema.state_dict(), "mean": mean, "std": std, "config_sha256": sha_file(os.path.join(HERE, "config.json")), "steps": tc["steps"], "n_train_rows": n}
    torch.save(ck, os.path.join(out, "checkpoint.pt")); return ema, mean, std, sch, train_s, log

# ------------------------------------------------------------------ evaluation
def ens_metrics(gen, sol, D):                              # gen, sol: (S, 2, N) arrays for ONE condition; returns the preregistered distribution metrics
    fin = np.isfinite(gen).all((1, 2)); nonfinite = float((~fin).mean())
    if not fin.any(): return {"mode_tv": 1.0, "mode_agree_argmax": False, "amp_w1_rel": float("inf"), "amp_mean_rel_err": float("inf"), "nonfinite_frac": nonfinite, "negative_frac": float("nan")}
    gen = gen[fin]; mg, ms = dominant_mode(gen[:, 0], D), dominant_mode(sol[:, 0], D)
    pg, ps = np.bincount(mg, minlength=N) / len(mg), np.bincount(ms, minlength=N) / len(ms)
    ag, as_ = gen[:, 0].std(-1), sol[:, 0].std(-1); k = min(len(ag), len(as_))
    qs = (np.arange(k) + 0.5) / k
    return {"mode_tv": 0.5 * float(np.abs(pg - ps).sum()), "mode_agree_argmax": bool(pg.argmax() == ps.argmax()),
            "amp_w1_rel": float(np.abs(np.quantile(ag, qs) - np.quantile(as_, qs)).mean() / max(as_.mean(), 1e-12)), "amp_mean_rel_err": float(abs(ag.mean() - as_.mean()) / max(as_.mean(), 1e-12)),
            "nonfinite_frac": nonfinite, "negative_frac": float((np.nan_to_num(gen, nan=-1).min((1, 2)) < 0).mean())}

def rollout_drift(fields, P, dev, dtau):                   # relative change of u after a short solver continuation from the given (u,v); fields (B,2,N)
    T = lambda x: torch.tensor(np.asarray(x), dtype=torch.float64, device=dev); u, v = T(fields[:, 0]), T(fields[:, 1])
    u2, _, _ = advance(u, v, T(P[:, 0]), T(P[:, 1]), T(P[:, 2]), T(P[:, 3]), int(round(dtau / DT)))
    dev_u = (u - u.mean(-1, keepdim=True)).norm(dim=-1); return (((u2 - u).norm(dim=-1)) / (dev_u + 1e-12)).cpu().numpy()

def evaluate(net, mean, std, sch, table, dev, out, ev, smoke=False):
    D = dct_matrix(N); taus = S["save_tau"] if not smoke else CFG["smoke"]["save_tau"]; gen = torch.Generator(device=dev); gen.manual_seed(123); res = {}
    ids = list(range(*CFG["splits"]["ensemble"]["setting_ids"])) if not smoke else list(range(CFG["smoke"]["test_ids"][0], CFG["smoke"]["test_ids"][0] + 4))
    sidx = split_seeds(CFG["splits"]["ensemble"]) if not smoke else list(range(CFG["smoke"]["ensemble_seeds"]))
    E = build_split("ensemble", dev, table, ids=ids, seed_idx=sidx, save_tau=taus); res["ensemble_solver_seconds"] = E["solver_seconds"]; res["ensemble_failed_runs"] = int(E["failed"].sum())
    nS = len(sidx); fields = E["fields"].reshape(len(ids), nS, len(taus), 2, N); failed = E["failed"].reshape(len(ids), nS)
    Ptr, Ftr, trid = ev["train_params"], ev["train_fields"], ev["train_setting"]; uniq = np.unique(trid); up = table[uniq]
    nrm = lambda p: (p - np.array([[CFG["prior"][k][0] for k in "abdL"]])) / np.array([[CFG["prior"][k][1] - CFG["prior"][k][0] for k in "abdL"]])
    rng = np.random.default_rng(7); spc = ev["spc"]; cond_rows, solver_rows = [], []
    for si, sid in enumerate(ids):
        for ti, tau in enumerate(taus): cond_rows.append((si, ti, sid, tau))
    pc = np.array([[*table[sid], tau] for (_, _, sid, tau) in cond_rows], np.float32)
    shuf = rng.permutation(len(ids)); shuf_rows = np.array([[*table[ids[shuf[si]]], tau] for (si, _, _, tau) in cond_rows], np.float32)
    def gen_for(c):
        out_ = []
        for i in range(0, len(c), 512):
            cc = torch.tensor(cscale(np.repeat(c[i:i + 512], spc, 0)), device=dev); x, _ = sample(net, cc, sch, gen); out_.append(x.cpu().numpy())
        x = np.concatenate(out_).reshape(len(c), spc, 2, N); return x * std[None] + mean[None]
    t0 = time.time(); G = gen_for(pc); res["gen_seconds_main"] = time.time() - t0; Gs = gen_for(shuf_rows)
    per = []
    for k, (si, ti, sid, tau) in enumerate(cond_rows):
        ok = ~failed[si]; sol = fields[si][ok][:, ti]
        if len(sol) < 4: per.append({"setting_id": int(sid), "tau": tau, "skipped": "fewer than 4 non-failed solver runs"}); continue
        row = {"setting_id": int(sid), "tau": tau, "params": [float(x) for x in table[sid]], "n_solver": int(len(sol)), "ddpm": ens_metrics(G[k], sol, D), "ddpm_shuffled_condition": ens_metrics(Gs[k], sol, D)}
        m = ev["train_tau"] == tau; dist = np.abs(nrm(up) - nrm(table[sid][None])).sum(1); order = uniq[np.argsort(dist)]
        for kk in CFG["eval"]["baseline_nearest_k"]:
            sel = np.isin(trid, order[:kk]) & m; pool = Ftr[sel]
            row[f"nearest{kk}_pooled"] = ens_metrics(pool[rng.integers(0, len(pool), spc)], sol, D) if kk < 10 else {"mean_field_of_nearest10": ens_metrics(np.repeat(pool.mean(0, keepdims=True), spc, 0), sol, D)}["mean_field_of_nearest10"]
        per.append(row)
    res["per_condition"] = per; okp = [r for r in per if "ddpm" in r]
    methods = ["ddpm", "ddpm_shuffled_condition", "nearest1_pooled", "nearest5_pooled", "nearest10_pooled"]; names = {"nearest10_pooled": "conditional_mean_of_nearest10"}
    summ = {}
    for mth in methods:
        summ[names.get(mth, mth)] = {mt: float(np.median([r[mth][mt] for r in okp])) for mt in ("mode_tv", "amp_w1_rel", "amp_mean_rel_err", "negative_frac", "nonfinite_frac")}
        summ[names.get(mth, mth)]["mode_agree_argmax_rate"] = float(np.mean([r[mth]["mode_agree_argmax"] for r in okp]))
    wins = {}
    for mth in methods[1:]:
        wins[names.get(mth, mth)] = {mt: {"ddpm_lower": int(sum(r["ddpm"][mt] < r[mth][mt] for r in okp)), "tie": int(sum(r["ddpm"][mt] == r[mth][mt] for r in okp)), "ddpm_higher": int(sum(r["ddpm"][mt] > r[mth][mt] for r in okp)), "n": len(okp)} for mt in ("mode_tv", "amp_w1_rel")}
    res["summary_median_over_conditions"] = summ; res["paired_counts_ddpm_vs_baseline"] = wins; res["n_conditions"] = len(okp)
    res["by_tau_median"] = {str(tau): {mth: {mt: float(np.median([r[mth][mt] for r in okp if r["tau"] == tau])) for mt in ("mode_tv", "amp_w1_rel")} for mth in ("ddpm", "nearest1_pooled", "nearest5_pooled", "ddpm_shuffled_condition")} for tau in taus}
    # short solver rollout from generated vs solver states (nonsteady snapshots: drift is reported, not forced to zero)
    dr = []
    for k, (si, ti, sid, tau) in enumerate(cond_rows[:: max(1, len(cond_rows) // 24)]):
        kk = cond_rows.index((si, ti, sid, tau)); nr = min(8, spc, nS); P = np.repeat(table[sid][None], nr, 0); ok = ~failed[si]; sol = fields[si][ok][:nr, ti]
        if len(sol) < nr: continue
        dr.append({"setting_id": int(sid), "tau": tau, "drift_generated_median": float(np.median(np.where(np.isfinite(dg := rollout_drift(np.nan_to_num(G[kk][:nr], nan=0.0, posinf=1e6, neginf=-1e6), P, dev, CFG["eval"]["rollout_dtau"])) & np.isfinite(G[kk][:nr]).all((1, 2)), dg, np.inf))), "drift_solver_median": float(np.median(rollout_drift(sol, P, dev, CFG["eval"]["rollout_dtau"])))})
    res["rollout_drift"] = {"dtau": CFG["eval"]["rollout_dtau"], "rows": dr, "median_generated": float(np.median([r["drift_generated_median"] for r in dr])) if dr else None, "median_solver": float(np.median([r["drift_solver_median"] for r in dr])) if dr else None,
                            "note": "relative change of u over a short solver continuation; snapshots need not be steady"}
    # display examples (direct solver vs generated, same conditions) and a reverse-process trajectory
    sel = list(range(0, len(ids), max(1, len(ids) // CFG["eval"]["display_conditions"])))[:CFG["eval"]["display_conditions"]]
    ex = {"setting_ids": np.array([ids[i] for i in sel]), "taus": np.array(taus), "x": (np.arange(N) + 0.5), "params": table[[ids[i] for i in sel]]}
    nd = min(8, spc, nS); ex["solver"] = np.stack([fields[i][~failed[i]][:nd] for i in sel]); ex["generated"] = np.stack([G[cond_rows.index((i, ti, ids[i], taus[ti]))][:nd] for i in sel for ti in range(len(taus))]).reshape(len(sel), len(taus), nd, 2, N)
    cc = torch.tensor(cscale(np.repeat(pc[[cond_rows.index((sel[0], len(taus) - 1, ids[sel[0]], taus[-1]))]], 4, 0)), device=dev); _, tr = sample(net, cc, sch, gen, keep_every=10)
    ex["reverse_trajectory_normalized"] = np.stack(tr)
    np.savez_compressed(os.path.join(out, "examples.npz"), **ex)
    return res, E, G, cond_rows, taus, fields, failed, ids

def marginals(net, mean, std, sch, table, dev, taus, spc_seed=321):
    D = dct_matrix(N); gen = torch.Generator(device=dev); gen.manual_seed(spc_seed); out = {}
    for name in ("test_param", "test_seed"):
        d = build_split(name, dev, table, save_tau=taus); c, f, sid, _ = flatten(d, taus); o = {"n_rows": int(len(c)), "failed_runs": int(d["failed"].sum()), "n_runs": int(len(d["failed"])), "solver_seconds": d["solver_seconds"]}
        g = []
        for i in range(0, len(c), 2048):
            x, _ = sample(net, torch.tensor(cscale(c[i:i + 2048]), device=dev), sch, gen); g.append(x.cpu().numpy() * std + mean)
        g = np.concatenate(g); per = {}
        for tau in taus:
            m = c[:, 4] == tau; ag, as_ = g[m][:, 0].std(-1), f[m][:, 0].std(-1); k = min(len(ag), len(as_)); qs = (np.arange(k) + .5) / k
            pg = np.bincount(dominant_mode(g[m][:, 0], D), minlength=N) / m.sum(); ps = np.bincount(dominant_mode(f[m][:, 0], D), minlength=N) / m.sum()
            per[str(tau)] = {"n": int(m.sum()), "amp_marginal_w1_rel": float(np.abs(np.quantile(ag, qs) - np.quantile(as_, qs)).mean() / as_.mean()), "mode_marginal_tv": 0.5 * float(np.abs(pg - ps).sum()),
                             "gen_negative_frac": float((g[m].min((1, 2)) < 0).mean()), "solver_negative_frac": float((f[m].min((1, 2)) < 0).mean()), "gen_nonfinite_frac": float((~np.isfinite(g[m])).any((1, 2)).mean())}
        o["by_tau"] = per; out[name] = o
    return out

def timings(net, mean, std, sch, table, dev, ev_):
    nb = CFG["eval"]["timing_batch"] if not ev_ else 64; gen = torch.Generator(device=dev); gen.manual_seed(5); c = torch.tensor(cscale(np.repeat(np.array([[*table[1450], 200.0]], np.float32), nb, 0)), device=dev); res = {"batch": nb}
    def sync(): torch.cuda.synchronize() if dev == "cuda" else None
    for _ in range(CFG["eval"]["timing_warmup"]): sample(net, c[:min(nb, 64)], sch, gen); sync()
    ts = []
    for _ in range(CFG["eval"]["timing_repeats"]): sync(); t0 = time.time(); sample(net, c, sch, gen); sync(); ts.append(time.time() - t0)
    res["ddpm_sampling_seconds"] = ts; res["ddpm_seconds_per_field"] = float(np.median(ts) / nb)
    P = np.repeat(table[1450:1451], nb, 0); sd = np.arange(nb)
    sync(); t0 = time.time(); simulate(P, sd, device=dev, save_tau=[S["save_tau"][-1]] if not ev_ else [CFG["smoke"]["T_final_tau"]]); sync(); res["solver_same_device_seconds"] = time.time() - t0; res["solver_device"] = dev
    nc = min(nb, 64); t0 = time.time(); simulate(P[:nc], sd[:nc], device="cpu", save_tau=[S["save_tau"][-1]] if not ev_ else [CFG["smoke"]["T_final_tau"]]); res["solver_cpu_seconds_for_64"] = time.time() - t0; res["solver_cpu_runs"] = nc; res["cpu_threads"] = torch.get_num_threads()
    res["note"] = "solver time is for T=200 tau (smoke: shorter) from random ICs at one setting; DDPM time is 200 ancestral steps; different algorithms and devices; no speedup is claimed from these numbers alone"
    return res

# ------------------------------------------------------------------ gates
def cmd_preflight(a):
    man = json.load(open(os.path.join(HERE, "MANIFEST.json"))); bad = [f for f, h in man["sha256"].items() if sha_file(os.path.join(HERE, f)) != h]
    print(json.dumps({"preflight": "ok" if not bad else "HASH_MISMATCH", "mismatch": bad, "imports": {"torch": torch.__version__, "numpy": np.__version__}, "trains": False})); sys.exit(1 if bad else 0)

def cmd_control(a):
    dev = "cuda" if torch.cuda.is_available() else "cpu"; r = {"env": env_receipt(dev), "checks": {}}
    if dev != "cuda" and not a.allow_cpu: r["checks"]["cuda_present"] = {"ok": False}; jdump(r, os.path.join(a.out, "control.json")); print(json.dumps(r["checks"])); sys.exit(2)
    D = dct_matrix(N); r["checks"]["dct_orthonormal"] = {"ok": bool((D @ D.T - torch.eye(N, dtype=torch.float64)).abs().max() < 1e-12)}
    t = settings_table(); P = t[:4]; sd = np.arange(4); f0, bad0 = simulate(P, sd, "cpu", eps=0.0, save_tau=[5.0]); st = np.stack([P[:, 0] + P[:, 1], P[:, 1] / (P[:, 0] + P[:, 1]) ** 2], 1)
    r["checks"]["steady_state_preserved_eps0"] = {"ok": bool(np.abs(f0[:, 0] - st[:, :, None]).max() < 1e-9), "max_abs": float(np.abs(f0[:, 0] - st[:, :, None]).max())}
    fc, _ = simulate(P, sd, "cpu", save_tau=[10.0]); r["checks"]["solver_deterministic_cpu"] = {"ok": bool(np.array_equal(fc, simulate(P, sd, "cpu", save_tau=[10.0])[0]))}
    if dev == "cuda":
        fg, _ = simulate(P, sd, "cuda", save_tau=[10.0]); r["checks"]["solver_cpu_vs_cuda"] = {"ok": bool(np.abs(fg - fc).max() < 1e-6), "max_abs": float(np.abs(fg - fc).max()), "tolerance": 1e-6}
    torch.manual_seed(0); n1 = Net(); n2 = copy.deepcopy(n1); x = torch.randn(4, 2, N); c = torch.randn(4, 5); tt = torch.tensor([0, 50, 100, 199]); o1 = n1(x, tt, c)
    if dev == "cuda": o2 = n2.cuda()(x.cuda(), tt.cuda(), c.cuda()).cpu(); r["checks"]["net_cpu_vs_cuda"] = {"ok": bool((o1 - o2).abs().max() < 1e-3), "max_abs": float((o1 - o2).abs().max()), "tolerance": 1e-3}
    r["checks"]["net_params"] = {"ok": True, "n_params": int(sum(p.numel() for p in n1.parameters()))}
    sch = schedule(CFG["model"]["T_diffusion"], "cpu"); r["checks"]["schedule_abar_monotone"] = {"ok": bool((sch[2][1:] < sch[2][:-1]).all() and sch[2][-1] < 0.01)}
    r["ok"] = all(v["ok"] for v in r["checks"].values()); jdump(r, os.path.join(a.out, "control.json")); print(json.dumps({k: v["ok"] for k, v in r["checks"].items()})); sys.exit(0 if r["ok"] else 3)

def cmd_run(a, smoke=False):
    t_all = time.time(); dev = "cuda" if torch.cuda.is_available() else "cpu"; os.makedirs(a.out, exist_ok=True)
    if dev != "cuda" and not smoke and not a.allow_cpu: print("no CUDA: refusing the full run"); sys.exit(2)
    table = settings_table(); sm = CFG["smoke"]; tc = dict(CFG["train"]); R = {"env": env_receipt(dev), "smoke": smoke}
    taus = sm["save_tau"] if smoke else S["save_tau"]
    if smoke:
        assert sm["train_ids"][0] >= CFG["splits"]["dev"]["setting_ids"][0] and sm["test_ids"][1] <= CFG["splits"]["dev"]["setting_ids"][1]; tc.update(steps=sm["steps"], batch=sm["batch"], log_every=25)
        tr = build_split("train", dev, table, ids=list(range(*sm["train_ids"])), seed_idx=[0], save_tau=taus)
    else: tr = build_split("train", dev, table, save_tau=taus)
    c, f, sid, ics = flatten(tr, taus)
    R["dataset"] = {"train": {"runs": int(len(tr["failed"])), "failed_runs": int(tr["failed"].sum()), "failed_setting_ids": sorted(set(int(i) for i in tr["setting_id"][tr["failed"]]))[:200], "rows": int(len(c)), "solver_seconds": tr["solver_seconds"],
                  "fields_sha256": sha(f.tobytes()), "setting_ids_sha256": sha(np.unique(sid).tobytes()), "n_settings": int(len(np.unique(sid)))}, "settings_table_sha256": sha(table.tobytes()), "config_sha256": sha_file(os.path.join(HERE, "config.json")), "code_sha256": sha_file(os.path.abspath(__file__))}
    if smoke: R["smoke_note"] = "tiny dev-range control; numbers are not results"
    ema, mean, std, sch, train_s, log = train(c, f, tc, dev, a.out); R["train"] = {"seconds": train_s, "steps": tc["steps"], "final_loss": log[-1]["loss"], "first_loss": log[0]["loss"], "mean_last_10_logged": float(np.mean([x["loss"] for x in log[-10:]])),
                  "checkpoint_sha256": sha_file(os.path.join(a.out, "checkpoint.pt")), "frozen_before_holdout_generation": True, "cuda_max_mem_mb": (torch.cuda.max_memory_allocated() / 2**20 if dev == "cuda" else None), "gpu_after": gpu_telemetry()}
    ema.eval(); ev = {"train_params": c[:, :4], "train_fields": f, "train_setting": sid, "train_tau": c[:, 4], "spc": (sm["samples_per_condition"] if smoke else CFG["eval"]["samples_per_condition"])}
    res, E, G, rows, taus_, fields, failed, ids = evaluate(ema, mean, std, sch, table, dev, a.out, ev, smoke); R["ensemble_eval"] = res
    R["held_out_marginals"] = marginals(ema, mean, std, sch, table, dev, taus) if not smoke else "skipped in smoke"
    R["timings"] = timings(ema, mean, std, sch, table, dev, smoke); R["total_seconds"] = time.time() - t_all
    R["costs_separate"] = {"train_data_solver_seconds": tr["solver_seconds"], "train_seconds": train_s, "ensemble_solver_seconds": res["ensemble_solver_seconds"]}
    jdump(R, os.path.join(a.out, "evaluation.json")); print(json.dumps({"ok": True, "total_seconds": R["total_seconds"], "median_mode_tv": res["summary_median_over_conditions"]["ddpm"]["mode_tv"]}))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["preflight", "control", "run", "smoke"]); ap.add_argument("--out", default="out"); ap.add_argument("--allow-cpu", action="store_true"); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.cmd == "preflight" or os.environ.get("PREFLIGHT") == "1": cmd_preflight(a)
    {"control": cmd_control, "run": cmd_run, "smoke": lambda x: cmd_run(x, smoke=True)}[a.cmd](a)

if __name__ == "__main__": main()
