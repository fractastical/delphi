"""SECONDARY evaluation registered in AMENDMENT_1.md (not part of the frozen packet). Loads the RETURNED frozen checkpoint (no training, no tuning), regenerates the held-out
ensemble with the frozen rd_ddpm.evaluate unchanged (same seeds), adds the exact empirical W1, SAVES the full generated ensemble, and checks that the regenerated frozen metrics
reproduce the returned evaluation.json. Output JSON is strict (allow_nan=False; non-finite values become {"status": "nonfinite"}).
    python3 secondary_eval.py --ckpt checkpoint.pt --primary evaluation.json --out outdir [--smoke]"""
import argparse, json, math, os, sys
import numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rd_ddpm as R
from exact_w1 import exact_w1

def strict(o):
    if isinstance(o, float) and not math.isfinite(o): return {"status": "nonfinite", "token": str(o)}
    if isinstance(o, dict): return {k: strict(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [strict(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)) and getattr(o, "shape", None) == (): return strict(o.item())
    return o

def build_ev(dev, table, smoke):
    sm = R.CFG["smoke"]; taus = sm["save_tau"] if smoke else R.S["save_tau"]
    tr = R.build_split("train", dev, table, ids=list(range(*sm["train_ids"])), seed_idx=[0], save_tau=taus) if smoke else R.build_split("train", dev, table, save_tau=taus)
    c, f, sid, _ = R.flatten(tr, taus)
    return {"train_params": c[:, :4], "train_fields": f, "train_setting": sid, "train_tau": c[:, 4], "spc": sm["samples_per_condition"] if smoke else R.CFG["eval"]["samples_per_condition"]}, taus

def marginals_exact(net, mean, std, sch, table, dev, taus):
    gen = torch.Generator(device=dev); gen.manual_seed(321); out = {}
    for name in ("test_param", "test_seed"):
        d = R.build_split(name, dev, table, save_tau=taus); c, f, _, _ = R.flatten(d, taus); g = []
        for i in range(0, len(c), 2048):
            x, _ = R.sample(net, torch.tensor(R.cscale(c[i:i + 2048]), device=dev), sch, gen); g.append(x.cpu().numpy() * std + mean)
        g = np.concatenate(g); out[name] = {}
        for tau in taus:
            m = c[:, 4] == tau; ag, as_ = g[m][:, 0].std(-1), f[m][:, 0].std(-1); fin = np.isfinite(ag)
            out[name][str(tau)] = {"n": int(m.sum()), "n_generated_finite": int(fin.sum()), "amp_marginal_w1_exact_rel": (exact_w1(ag[fin], as_) / as_.mean()) if fin.any() else None}
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ckpt", required=True); ap.add_argument("--primary"); ap.add_argument("--out", required=True); ap.add_argument("--smoke", action="store_true"); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True); dev = "cuda" if torch.cuda.is_available() else "cpu"; table = R.settings_table()
    ck = torch.load(a.ckpt, map_location=dev, weights_only=False); net = R.Net().to(dev); net.load_state_dict(ck["ema"]); net.eval(); mean, std = ck["mean"], ck["std"]; sch = R.schedule(R.CFG["model"]["T_diffusion"], dev)
    ev, taus = build_ev(dev, table, a.smoke); orig = R.ens_metrics
    def patched(gen, sol, D):
        r = orig(gen, sol, D); fin = np.isfinite(gen).all((1, 2)); r["amp_w1_exact_rel"] = float(exact_w1(gen[fin][:, 0].std(-1), sol[:, 0].std(-1)) / sol[:, 0].std(-1).mean()) if fin.any() else None; return r
    R.ens_metrics = patched
    res, E, G, rows, taus_, fields, failed, ids = R.evaluate(net, mean, std, sch, table, dev, a.out, ev, a.smoke); R.ens_metrics = orig
    np.savez_compressed(os.path.join(a.out, "generated_ensemble_full.npz"), generated=G.astype(np.float32), solver=fields.astype(np.float32), solver_failed=failed, setting_ids=np.array(ids), taus=np.array(taus_))
    out = {"schema": "frontier.rd-ddpm.secondary/1", "role": "SECONDARY exact-W1 audit of the frozen checkpoint; the frozen primary results are unchanged", "smoke": a.smoke, "device": dev, "ckpt_sha256": R.sha_file(a.ckpt),
           "code_sha256": R.sha_file(R.__file__), "secondary_code_sha256": R.sha_file(os.path.abspath(__file__)), "ensemble": res, "marginals_exact": "skipped in smoke" if a.smoke else marginals_exact(net, mean, std, sch, table, dev, taus)}
    if a.primary:
        prim = json.loads(open(a.primary).read(), parse_constant=lambda c: float("nan")); pc = {(r["setting_id"], r["tau"]): r for r in prim["ensemble_eval"]["per_condition"] if "ddpm" in r}; diffs = []
        for r in res["per_condition"]:
            p = pc.get((r.get("setting_id"), r.get("tau")))
            if p and "ddpm" in r: diffs.append(max(abs(r["ddpm"]["amp_w1_rel"] - p["ddpm"]["amp_w1_rel"]), abs(r["ddpm"]["mode_tv"] - p["ddpm"]["mode_tv"])))
        out["reproduction_of_frozen_metrics"] = {"n_compared": len(diffs), "max_abs_diff_amp_w1_rel_or_mode_tv": max(diffs) if diffs else None, "note": "generation is stochastic on GPU; a nonzero difference is reported, not corrected"}
    ok = [r for r in res["per_condition"] if "ddpm" in r]
    GATE = 1e-3                                           # registered in AMENDMENT_3.md before any trained result: solver median std(u) at or above this counts as "patterned"; numerical audit saw mode flips only at std <= 1.2e-12
    nT = len(taus_); amp = {}
    for si in range(fields.shape[0]):
        for ti in range(nT):
            okr = ~failed[si]; amp[(si, ti)] = float(np.median(fields[si][okr][:, ti, 0].std(-1))) if okr.any() else None
    strata = {"patterned": [], "near_uniform": []}
    for k, r in enumerate(res["per_condition"]):
        a_ = amp[(k // nT, k % nT)]
        if "ddpm" in r and a_ is not None: strata["patterned" if a_ >= GATE else "near_uniform"].append(r)
    out["stratified_by_solver_amplitude"] = {"gate_std_u": GATE, "note": "SECONDARY stratification; dominant mode of a near-uniform field is numerically arbitrary, so mode metrics are only interpretable in the patterned stratum",
        **{name: {"n_conditions": len(rows), **{mth: {mt: (float(np.median([x[mth][mt] for x in rows])) if rows else None) for mt in ("mode_tv", "amp_w1_rel", "amp_w1_exact_rel")} for mth in ("ddpm", "ddpm_shuffled_condition", "nearest1_pooled", "nearest5_pooled", "nearest10_pooled")}} for name, rows in strata.items()}}
    out["precision_flags_at_runtime"] = {"cudnn_allow_tf32": torch.backends.cudnn.allow_tf32, "matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32, "float32_matmul_precision": torch.get_float32_matmul_precision(), "note": "must equal the policy used by the primary run; this tool sets nothing itself"}
    for mth in ("ddpm", "ddpm_shuffled_condition", "nearest1_pooled", "nearest5_pooled", "nearest10_pooled"):
        v = [r[mth]["amp_w1_exact_rel"] for r in ok if r[mth].get("amp_w1_exact_rel") is not None]; out.setdefault("median_amp_w1_exact_rel", {})[mth] = (float(np.median(v)) if v else None); out.setdefault("n_conditions_with_value", {})[mth] = len(v)
    open(os.path.join(a.out, "secondary_evaluation.json"), "w").write(json.dumps(strict(out), indent=1, sort_keys=True, allow_nan=False, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(json.dumps({"ok": True, "median_amp_w1_exact_rel": out["median_amp_w1_exact_rel"]}))

if __name__ == "__main__": main()
