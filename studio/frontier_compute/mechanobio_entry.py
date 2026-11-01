"""CPU-job entry for the mechanobiology sweep payload (code by the mechanobio worker, commit 0dbeb56a49c7208fc01f5e154936a5ea4a935585; not authored or altered here).
Pinned environment: python 3.12 container, numpy==2.4.4, scipy==1.17.1. Reads the injected source tarball (sha256 verified), runs the worker-reported command, hashes every output.
Return path: $COPS_OUT is returned through the job log with sha256 verification by the controller (no bucket, no credential). Size guard: if the compressed output would exceed
GUARD bytes the large files are not returned, SHA256SUMS still lists them, and a loud NOT_RETURNED file says so (the runner would otherwise drop everything)."""
import hashlib, io, json, os, subprocess, sys, tarfile, time
SRC = "inputs/mechanobio/source-0dbeb56a49c7208fc01f5e154936a5ea4a935585.tar.gz"
SRC_SHA = "9ede0679b785219093e3efc69d424d975042d7a4167594750a3222847e68dcce"
GUARD = int(os.environ.get("RETURN_GUARD_BYTES", "3500000"))
OUT = os.environ.get("COPS_OUT", ".")
sha = lambda b: hashlib.sha256(b).hexdigest()
raw = open(SRC, "rb").read()
assert sha(raw) == SRC_SHA, "source tarball hash mismatch"
if os.environ.get("PREFLIGHT"):
    names = tarfile.open(fileobj=io.BytesIO(raw)).getnames()
    assert "engineering/mechanobio/sweep.py" in names, names
    print("preflight ok: tarball hash and members", len(names)); sys.exit(0)
t0 = time.time()
rec = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "src_sha256": SRC_SHA, "python": sys.version.split()[0]}
r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "numpy==2.4.4", "scipy==1.17.1"], capture_output=True, text=True)
rec["pip_rc"] = r.returncode; rec["pip_tail"] = (r.stdout + r.stderr)[-400:]
print("pip rc", r.returncode, flush=True)
work = "/work/job/mechsrc"; os.makedirs(work, exist_ok=True)
tarfile.open(fileobj=io.BytesIO(raw)).extractall(work)
res = os.path.join(OUT, "results")
env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONPATH=work)
cmd = [sys.executable, "-m", "engineering.mechanobio.sweep", "--output", res, "--replicates", "32", "--grid", "7", "--workers", "2", "--duration", "30"]
rec["command"] = " ".join(cmd)
p = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True)
rec["rc"] = p.returncode; rec["stdout_tail"] = p.stdout[-600:]; rec["stderr_tail"] = p.stderr[-600:]; rec["wall_s"] = round(time.time() - t0, 1)
import numpy, scipy
rec["numpy"], rec["scipy"] = numpy.__version__, scipy.__version__
files = sorted(os.path.join(d, f) for d, _, fs in os.walk(res) for f in fs) if os.path.isdir(res) else []
sums = {os.path.relpath(f, OUT): (sha(open(f, "rb").read()), os.path.getsize(f)) for f in files}
est = sum(os.path.getsize(f) for f in files)
if est > GUARD * 3:            # conservative: JSON compresses well, but do not gamble the whole result on it
    big = sorted(files, key=os.path.getsize, reverse=True)
    dropped = []
    while est > GUARD * 3 and big:
        f = big.pop(0); est -= os.path.getsize(f); dropped.append(os.path.relpath(f, OUT)); os.remove(f)
    open(os.path.join(OUT, "NOT_RETURNED.txt"), "w").write("size guard: not returned (hashes in SHA256SUMS.json): " + ", ".join(dropped) + "\n")
    rec["not_returned"] = dropped
with open(os.path.join(OUT, "SHA256SUMS.json"), "w") as fh:
    json.dump({k: {"sha256": v[0], "bytes": v[1]} for k, v in sums.items()}, fh, indent=1)
json.dump(rec, open(os.path.join(OUT, "run_record.json"), "w"), indent=1)
print("done rc", p.returncode, "files", len(files), "wall", rec["wall_s"], flush=True)
sys.exit(p.returncode)
