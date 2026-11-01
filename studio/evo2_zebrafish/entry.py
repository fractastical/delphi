"""Protocol 7 entry (one H100): Evo 2 7B setup (free-space aware), a CORRECTED sequence-control check, then the bioservices zebrafish candidate-generation job UNMODIFIED
(pinned copy of experiments/bioservices/... at work/frontier-bioservices 85077072b72934ebede462e81ef0041ce4298314). Writes after every stage; telemetry sampled.
Output: $COPS_OUT/{entry.json, zebrafish/{candidates,controls,scores,manifest}.json, control_check.json, telemetry_*, SHA256SUMS.json}"""
import hashlib, json, math, os, platform, random, shutil, subprocess, sys, time, collections
T0 = time.time()
OUT = os.environ.get("COPS_OUT", ".")
REV = "bda0089f92582d5baabf0f22d9fc85f3588f6b58"; LFS = "c66645929dc1b9c631f5be656da8726f38946315dc9167000a615dd626fcecf4"
INPUT_SHA = "41104d95770918fb422cdd56ecad9b584f280848da7fbeebdd0c24575d6f8a58"
BUDGET_JOB = int(os.environ.get("ZF_BUDGET_S", "420"))
PIN = "evo2_zebrafish/pinned"; JOBDIR = f"{PIN}/experiments/bioservices/zebrafish_evo2_regulatory_candidates"
sha = lambda b: hashlib.sha256(b).hexdigest()
if os.environ.get("PREFLIGHT"):
    assert sha(open(f"{JOBDIR}/input_set.json", "rb").read()) == INPUT_SHA, "input set hash mismatch"
    sys.path.insert(0, PIN)
    from experiments.bioservices.sequence_controls import dinucleotide_shuffle, gc_matched_random  # noqa: F401
    assert os.path.exists("inputs/evo2_ecoli_NC_000913.3_c364500-362455.fa")
    print("preflight ok: input_set hash, sequence_controls import, fasta present"); sys.exit(0)
R = {"stages": {}, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def save():
    json.dump(R, open(os.path.join(OUT, "entry.json"), "w"), indent=1, default=str)


def run(cmd, timeout):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)[-800:]


def stage(name, f):
    t = time.time()
    try:
        r = f(); R["stages"][name] = {"status": "ok", "seconds": round(time.time() - t, 1), **(r or {})}
    except Exception as e:
        R["stages"][name] = {"status": "error", "seconds": round(time.time() - t, 1), "error": repr(e)[:500]}
    save(); print("stage", name, R["stages"][name]["status"], flush=True)
    return R["stages"][name]["status"] == "ok"


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
from frontier_compute.telemetry import Telemetry
tel = Telemetry(OUT, max_s=1800); tel.__enter__()


def env():
    import torch
    pl = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True).stdout
    return {"python": platform.python_version(), "torch": torch.__version__, "gpu": subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip(),
            "pip_subset": [l for l in pl.splitlines() if any(k in l.lower() for k in ("torch", "flash", "transformer", "vtx", "evo2"))]}


def install():
    steps = []
    for cmd in ([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "evo2", "vtx"], [sys.executable, "-m", "pip", "install", "-q", "biopython", "huggingface_hub"]):
        rc, tail = run(cmd, 900); steps.append({"cmd": " ".join(cmd[3:]), "rc": rc, "tail": tail[-200:]})
    for _ in range(8):
        p = subprocess.run([sys.executable, "-c", "import evo2"], capture_output=True, text=True)
        if p.returncode == 0:
            steps.append({"import_evo2": "ok"}); break
        mod = p.stderr.split("No module named")[1].split("'")[1].split(".")[0] if "No module named" in p.stderr else None
        steps.append({"import_evo2": "fail", "missing": mod, "err": p.stderr[-200:]})
        if not mod:
            break
        run([sys.executable, "-m", "pip", "install", "-q", mod], 600)
    return {"steps": steps}


def weights():
    from huggingface_hub import hf_hub_download
    table, best = {}, None
    for c in ("/root/.cache", "/tmp", "/work", "/mnt"):
        if os.path.isdir(c):
            fr = shutil.disk_usage(c).free / 1e9; table[c] = round(fr, 1)
            if fr >= 22 and best is None:
                best = c
    R["disk_free_gb_by_dir"] = table
    if best is None:
        raise RuntimeError("no directory with >= 22 GB free")
    cache = os.path.join(best, "hf_evo2"); os.makedirs(cache, exist_ok=True); os.environ["HF_HOME"] = cache
    p = hf_hub_download("arcinstitute/evo2_7b", "evo2_7b.pt", revision=REV, cache_dir=cache)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 24), b""):
            h.update(ch)
    return {"bytes": os.path.getsize(p), "sha256": h.hexdigest(), "matches_pinned_lfs_oid": h.hexdigest() == LFS}


def control_check():
    """CORRECTED controls: ONE RNG object for the random sequences (the earlier smoke test built a new Random(3) per character and produced poly-C). Frozen expectations
    (PROTOCOL7): iid random NLL >= ln4 - 0.05; natural < both shuffles and < both iid sequences; the poly-C homopolymer is scored only to document the old artifact."""
    import numpy as np, torch
    from evo2 import Evo2
    fa = "inputs/evo2_ecoli_NC_000913.3_c364500-362455.fa"
    nat = "".join(l.strip() for l in open(fa) if not l.startswith(">")).upper()
    seqs = {"natural": nat}
    for k, sd in (("mono_shuffle_1", 1), ("mono_shuffle_2", 2)):
        a = list(nat); random.Random(sd).shuffle(a); seqs[k] = "".join(a)
    for k, sd in (("iid_random_seed3", 3), ("iid_random_seed4", 4)):
        rg = random.Random(sd); seqs[k] = "".join(rg.choice("ACGT") for _ in range(len(nat)))     # single RNG object
    seqs["poly_C_homopolymer_artifact_doc"] = "C" * len(nat)
    m = Evo2("evo2_7b")
    res = {}
    for k, s in seqs.items():
        ids = torch.tensor(m.tokenizer.tokenize(s), dtype=torch.int).unsqueeze(0).to("cuda:0")
        with torch.no_grad():
            out, _ = m(ids)
        lp = torch.log_softmax(out[0].float()[:, :-1, :], dim=-1)
        ll = lp.gather(-1, ids[:, 1:].long().unsqueeze(-1)).squeeze(-1)[0]
        res[k] = {"mean_nll_nats_per_nt": float(-ll.mean()), "distinct_bases": sorted(set(s)), "seq_sha256": sha(s.encode()), "finite": bool(torch.isfinite(out[0]).all())}
    n = res["natural"]["mean_nll_nats_per_nt"]
    ver = {"iid_ge_ln4_minus_0.05": all(res[k]["mean_nll_nats_per_nt"] >= math.log(4) - 0.05 for k in ("iid_random_seed3", "iid_random_seed4")),
           "natural_below_shuffles_and_iid": all(n < res[k]["mean_nll_nats_per_nt"] for k in ("mono_shuffle_1", "mono_shuffle_2", "iid_random_seed3", "iid_random_seed4")),
           "iid_sequences_use_all_four_bases": all(len(res[k]["distinct_bases"]) == 4 for k in ("iid_random_seed3", "iid_random_seed4"))}
    json.dump({"scores": res, "verdicts": ver}, open(os.path.join(OUT, "control_check.json"), "w"), indent=1)
    del m; torch.cuda.empty_cache()
    return {"verdicts": ver, "natural_nll": n}


def zebrafish():
    outd = os.path.join(OUT, "zebrafish"); os.makedirs(outd, exist_ok=True)
    env_ = dict(os.environ, PYTHONPATH=PIN)
    cmd = [sys.executable, f"{JOBDIR}/gpu_job.py", "--input-set", f"{JOBDIR}/input_set.json", "--out-dir", outd, "--model", "evo2_7b", "--budget-seconds", str(BUDGET_JOB)]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env_, timeout=BUDGET_JOB * 1.6 + 120)
    open(os.path.join(OUT, "zebrafish_stdout.txt"), "w").write((p.stdout + p.stderr)[-6000:])
    info = {"rc": p.returncode, "files": sorted(os.listdir(outd))}
    try:
        cand = json.load(open(os.path.join(outd, "candidates.json"))); ctrl = json.load(open(os.path.join(outd, "controls.json"))); sc = json.load(open(os.path.join(outd, "scores.json")))
        info.update(n_candidates=len(cand), n_controls=len(ctrl), n_scored=len(sc))
        di = lambda s: collections.Counter(zip(s, s[1:]))
        by = {c["sha256"]: c["sequence"] for c in cand}
        ex = [(di(k["sequence"]) == di(by[k["of"]])) for k in ctrl if k["kind"] == "dinucleotide_shuffle" and k["of"] in by]
        info["dinucleotide_shuffle_exact_count_preserved"] = {"n": len(ex), "exact": sum(ex)}
        g = collections.defaultdict(list)
        for s in sc:
            g[s["kind"]].append(s["evo2_mean_logprob"])
        info["mean_logprob_by_kind"] = {k: {"n": len(v), "mean": round(sum(v) / len(v), 4)} for k, v in g.items()}
    except Exception as e:
        info["readback_error"] = repr(e)[:200]
    return info


ok = stage("env", env)
ok = stage("install", install) and ok
ok_w = stage("weights", weights) if R["stages"]["install"]["status"] == "ok" else False
ok_c = stage("control_check", control_check) if ok_w else False
if ok_w:
    stage("zebrafish", zebrafish)
tel.__exit__(None, None, None)
files = sorted(os.path.join(d, f) for d, _, fs in os.walk(OUT) for f in fs)
json.dump({os.path.relpath(f, OUT): {"sha256": sha(open(f, "rb").read()), "bytes": os.path.getsize(f)} for f in files if not f.endswith("SHA256SUMS.json")}, open(os.path.join(OUT, "SHA256SUMS.json"), "w"), indent=1)
R["total_wall_s"] = round(time.time() - T0, 1); save()
print("DONE", json.dumps({k: v["status"] for k, v in R["stages"].items()}), flush=True)
