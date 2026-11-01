"""Download the COMADRE Animal Matrix Database (RData) into data/ (git-ignored) and export the metadata plus U and F
submatrices of every matrix to data/comadre.json with Rscript (the RData holds R lists, which Python cannot read directly).

Records URL, retrieval time, byte size and SHA-256 in data/manifest.json.
Run: python fetch.py   (needs `requests`; Rscript on PATH for the export step)
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
URL = "https://compadre-db.org/Data/ComadreDownload"

R_EXPORT = r"""
args <- commandArgs(TRUE)
e <- new.env(); load(args[1], envir = e)
db <- get(ls(e)[1], envir = e)
md <- db$metadata
keep <- c("MatrixID","SpeciesAccepted","SpeciesAuthor","Class","Order","Family","MatrixDimension","MatrixSplit",
          "MatrixComposite","MatrixTreatment","MatrixCaptivity","MatrixCriteriaAge","MatrixCriteriaSize",
          "MatrixCriteriaOntogeny","MatrixStartYear","MatrixEndYear","Authors","Journal","YearPublication","DOI_ISBN")
keep <- keep[keep %in% names(md)]
n <- nrow(md)
out <- vector("list", n)
for (i in seq_len(n)) {
  m <- db$mat[[i]]
  rec <- as.list(md[i, keep, drop = FALSE])
  rec$matU <- unname(as.matrix(m$matU)); rec$matF <- unname(as.matrix(m$matF))
  if (!is.null(m$matC)) rec$matC <- unname(as.matrix(m$matC))
  out[[i]] <- rec
}
con <- file(args[2], open = "w", encoding = "UTF-8")
writeLines(jsonlite::toJSON(list(version = as.list(db$version), n = n, matrices = out), auto_unbox = TRUE, na = "null", digits = NA), con)
close(con)
"""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(DATA, exist_ok=True)
    mpath = os.path.join(DATA, "manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    out = os.path.join(DATA, "COMADRE.RData")
    if not (os.path.exists(out) and "comadre" in manifest):
        retrieved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with requests.get(URL, headers={"User-Agent": "delphisci-claim-tests/1.0"}, timeout=600, stream=True) as r:
            r.raise_for_status()
            fname = None
            cd = r.headers.get("Content-Disposition", "")
            if "filename=" in cd:
                fname = cd.split("filename=", 1)[1].strip('"; ')
            with open(out, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        manifest["comadre"] = {"download_url": URL, "served_filename": fname, "retrieved_at": retrieved,
                               "byte_size": os.path.getsize(out), "sha256": sha256(out)}
        json.dump(manifest, open(mpath, "w"), indent=1)
    rscript = shutil.which("Rscript")
    if rscript is None:
        print("Rscript not found; data/comadre.json not regenerated", file=sys.stderr)
    else:
        script = os.path.join(DATA, "export.R")
        with open(script, "w", encoding="utf-8") as f:
            f.write(R_EXPORT)
        subprocess.run([rscript, script, out, os.path.join(DATA, "comadre.json")], check=True)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
