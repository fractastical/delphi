"""Download the CRAN source package popgenr 0.2 (CC0) into data/ (git-ignored), extract data/fly.RData (Buri 1956 bw75
allele counts, 19 generations x 107 replicates) and convert it to derived/buri1956_fly.csv with Rscript.

Records URL, retrieval time, byte size and SHA-256 in data/manifest.json. The derived CSV (< 10 KB) is committed so that
analysis.py runs without R; re-running this script regenerates it from the pinned tarball.
Run: python fetch.py   (needs `requests`; Rscript on PATH for the conversion step)
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
URL = "https://cran.r-project.org/src/contrib/popgenr_0.2.tar.gz"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(DERIVED, exist_ok=True)
    mpath = os.path.join(DATA, "manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    out = os.path.join(DATA, "popgenr_0.2.tar.gz")
    if not (os.path.exists(out) and "popgenr" in manifest):
        retrieved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        r = requests.get(URL, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=120)
        r.raise_for_status()
        with open(out, "wb") as f:
            f.write(r.content)
        manifest["popgenr"] = {"download_url": URL, "retrieved_at": retrieved, "byte_size": os.path.getsize(out), "sha256": sha256(out)}
        json.dump(manifest, open(mpath, "w"), indent=1)
    # Extract only the data file we need (member path is popgenr/data/fly.RData in the CRAN tarball).
    with tarfile.open(out, "r:gz") as tf:
        members = [m for m in tf.getmembers() if m.name.lower().endswith("data/fly.rdata")]
        if not members:
            raise SystemExit("fly.RData not found in tarball: " + ", ".join(m.name for m in tf.getmembers()))
        src = tf.extractfile(members[0]).read()
    rdata = os.path.join(DATA, "fly.RData")
    with open(rdata, "wb") as f:
        f.write(src)
    manifest["fly_rdata_in_tarball"] = {"member": members[0].name, "byte_size": len(src), "sha256": hashlib.sha256(src).hexdigest()}
    json.dump(manifest, open(mpath, "w"), indent=1)
    # Convert with R: write the matrix as CSV with generation as the first column.
    rscript = shutil.which("Rscript")
    if rscript is None:
        print("Rscript not found; derived/buri1956_fly.csv not regenerated", file=sys.stderr)
    else:
        code = (
            "e <- new.env(); load(commandArgs(TRUE)[1], envir=e); x <- get(ls(e)[1], envir=e); "
            "m <- as.matrix(x); d <- data.frame(generation=seq_len(nrow(m)), m); "
            "colnames(d) <- c('generation', paste0('rep', seq_len(ncol(m)))); "
            "write.csv(d, commandArgs(TRUE)[2], row.names=FALSE)"
        )
        subprocess.run([rscript, "-e", code, rdata, os.path.join(DERIVED, "buri1956_fly.csv")], check=True)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
