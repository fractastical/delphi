"""Evo 2 (7B) capability smoke test on ONE H100: install, load, score, controls. Not a scientific claim about any organism or variant.
Stages are logged with timings; partial results are written after every stage; a global wall budget stops later stages (recorded, not hidden).
Output: $COPS_OUT/evo2_smoke.json (+ logprobs npz). Source-linked facts: HF arcinstitute/evo2_7b (Apache-2.0, evo2_7b.pt 13,766,621,200 B, LFS sha256 c66645929dc1...),
GitHub ArcInstitute/evo2 (Apache-2.0)."""
import hashlib, json, math, os, platform, random, subprocess, sys, time
T0 = time.time()
OUT = os.environ.get("COPS_OUT", ".")
BUDGET = float(os.environ.get("EVO2_BUDGET_S", "3000"))
REV = "bda0089f92582d5baabf0f22d9fc85f3588f6b58"
LFS_SHA = "c66645929dc1b9c631f5be656da8726f38946315dc9167000a615dd626fcecf4"
R = {"stages": {}, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "budget_s": BUDGET}


def save():
    json.dump(R, open(os.path.join(OUT, "evo2_smoke.json"), "w"), indent=1, default=str)


def run(cmd, timeout):
    t = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)[-1500:], round(time.time() - t, 1)


def stage(name):
    def deco(f):
        def w(*a, **k):
            if time.time() - T0 > BUDGET:
                R["stages"][name] = {"status": "not_run_out_of_budget"}; save(); return None
            t = time.time()
            try:
                r = f(*a, **k)
                R["stages"][name] = {"status": "ok", "seconds": round(time.time() - t, 1), **(r or {})}
            except Exception as e:                       # recorded, never hidden
                R["stages"][name] = {"status": "error", "seconds": round(time.time() - t, 1), "error": repr(e)[:600]}
                print("STAGE ERROR", name, repr(e)[:300], flush=True)
            save(); print("stage", name, R["stages"][name].get("status"), flush=True)
            return R["stages"][name]
        return w
    return deco


@stage("env")
def env():
    import torch
    smi = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    pl = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True).stdout
    keep = [l for l in pl.splitlines() if any(k in l.lower() for k in ("torch", "flash", "transformer", "vtx", "evo2", "biopython", "huggingface", "numpy", "triton"))]
    df = subprocess.run(["df", "-h", "/root", "/tmp"], capture_output=True, text=True).stdout
    return {"python": platform.python_version(), "torch": torch.__version__, "cuda": torch.version.cuda, "gpu": smi, "pip_subset": keep, "df": df}


@stage("net")
def net():
    import urllib.request
    out = {}
    for u in ("https://huggingface.co/api/models/arcinstitute/evo2_7b", "https://pypi.org/pypi/evo2/json"):
        try:
            out[u] = urllib.request.urlopen(u, timeout=20).status
        except Exception as e:
            out[u] = repr(e)[:120]
    return out


@stage("install")
def install():
    steps = []
    rc, tail, sec = run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "evo2", "vtx"], 900)
    steps.append({"cmd": "pip install --no-deps evo2 vtx", "rc": rc, "tail": tail[-500:], "s": sec})
    rc, tail, sec = run([sys.executable, "-m", "pip", "install", "-q", "biopython", "huggingface_hub"], 600)
    steps.append({"cmd": "pip install biopython huggingface_hub", "rc": rc, "tail": tail[-500:], "s": sec})
    for k in range(8):                                   # resolve missing pure-python imports one at a time (never touches torch)
        p = subprocess.run([sys.executable, "-c", "import evo2"], capture_output=True, text=True)
        if p.returncode == 0:
            steps.append({"import_evo2": "ok"}); break
        err = p.stderr[-400:]
        mod = None
        if "No module named" in err:
            mod = err.split("No module named")[1].split("'")[1].split(".")[0]
        steps.append({"import_evo2": "fail", "err": err[-300:], "missing": mod})
        if not mod:
            break
        rc, tail, sec = run([sys.executable, "-m", "pip", "install", "-q", mod], 600)
        steps.append({"cmd": f"pip install {mod}", "rc": rc, "tail": tail[-300:], "s": sec})
    pl = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True).stdout
    return {"steps": steps, "pip_after": [l for l in pl.splitlines() if any(k in l.lower() for k in ("torch", "flash", "transformer", "vtx", "evo2"))]}


@stage("weights")
def weights():
    from huggingface_hub import hf_hub_download
    p = hf_hub_download("arcinstitute/evo2_7b", "evo2_7b.pt", revision=REV)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 24), b""):
            h.update(ch)
    return {"path": p, "bytes": os.path.getsize(p), "sha256": h.hexdigest(), "sha256_matches_hf_lfs_oid": h.hexdigest() == LFS_SHA, "revision": REV}


MODEL = {}


@stage("load")
def load():
    import torch
    from evo2 import Evo2
    t = time.time()
    m = Evo2("evo2_7b")
    MODEL["m"] = m
    return {"load_s": round(time.time() - t, 1), "gpu_mem_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2)}


def read_fasta(path):
    return "".join(l.strip() for l in open(path) if not l.startswith(">")).upper()


def logps(seq):
    import torch
    m = MODEL["m"]
    ids = torch.tensor(m.tokenizer.tokenize(seq), dtype=torch.int).unsqueeze(0).to("cuda:0")
    with torch.no_grad():
        out, _ = m(ids)
    lg = out[0].float()
    lp = torch.log_softmax(lg[:, :-1, :], dim=-1)
    tok = ids[:, 1:].long()
    ll = lp.gather(-1, tok.unsqueeze(-1)).squeeze(-1)[0]
    return ll.cpu().numpy(), tuple(lg.shape), bool(torch.isfinite(lg).all())


@stage("score")
def score():
    import numpy as np, torch
    fa = os.environ.get("EVO2_FASTA", "inputs/evo2_ecoli_NC_000913.3_c364500-362455.fa")
    nat = read_fasta(fa)
    R["input_fasta_sha256"] = hashlib.sha256(open(fa, "rb").read()).hexdigest()
    seqs = {"natural": nat}
    for k, seed in (("mono_shuffle_1", 1), ("mono_shuffle_2", 2)):
        a = list(nat); random.Random(seed).shuffle(a); seqs[k] = "".join(a)
    seqs["uniform_random_iid"] = "".join(random.Random(3).choice("ACGT") for _ in range(len(nat)))
    res, arrs = {}, {}
    for k, s in seqs.items():
        ll, shape, fin = logps(s)
        arrs[k] = ll
        res[k] = {"length": len(s), "mean_nll_nats_per_nt": float(-ll.mean()), "logits_shape": shape, "finite": fin, "seq_sha256": hashlib.sha256(s.encode()).hexdigest()}
    ll2, _, _ = logps(nat)
    det = float(np.abs(ll2 - arrs["natural"]).max())
    comp = {b: nat.count(b) / len(nat) for b in "ACGT"}
    order0 = -sum(p * math.log(p) for p in comp.values() if p > 0)
    np.savez_compressed(os.path.join(OUT, "evo2_logprobs.npz"), **arrs)
    t = time.time(); ll4, _, _ = logps(nat * 4); torch.cuda.synchronize(); tm = time.time() - t
    return {"scores": res, "determinism_max_abs_logprob_diff": det, "baseline_uniform_nll": math.log(4), "baseline_order0_nll_of_natural_composition": order0,
            "timing_8184nt_forward_s_incl_first_call_overhead": round(tm, 2),
            "A_natural_beats_uniform_baseline": res["natural"]["mean_nll_nats_per_nt"] < math.log(4),
            "A_natural_beats_order0_baseline": res["natural"]["mean_nll_nats_per_nt"] < order0,
            "A_natural_beats_all_controls": all(res["natural"]["mean_nll_nats_per_nt"] < res[k]["mean_nll_nats_per_nt"] for k in ("mono_shuffle_1", "mono_shuffle_2", "uniform_random_iid"))}


for f in (env, net, install, weights, load, score):
    f()
R["total_wall_s"] = round(time.time() - T0, 1)
save()
print("DONE", json.dumps({k: v.get("status") for k, v in R["stages"].items()}), flush=True)
