#!/usr/bin/env python3
"""Download every file used by analysis.py into ./data and write checksums to fetch_manifest.json.

Run: python3 fetch.py   (needs requests). Files over 1 MB stay in ./data (git-ignored); only the
manifest (URL, retrieval time, byte size, SHA-256) is committed.
Upstream files change rarely; if a SHA-256 differs from the committed manifest the script prints DRIFT
(it still keeps the new file; analysis results may then differ).
"""
import hashlib, json, os, sys, zipfile, datetime, requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)
MANIFEST = os.path.join(HERE, "fetch_manifest.json")

GH = "740b70189c77fc168be17bd6ade204c755bcb19b"  # n8upham/MamPhy_v1 HEAD at retrieval (2023-02-18 commit)
RAW = f"https://raw.githubusercontent.com/n8upham/MamPhy_v1/{GH}/_DATA/"
FILES = [
    ("pantheria", "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt", "PanTHERIA_1-0_WR05_Aug2008.txt"),
    ("anage", "https://genomics.senescence.info/species/dataset.zip", "anage_dataset.zip"),
    ("upham_mcc_nd", RAW + "MamPhy_fullPosterior_BDvr_Completed_5911sp_topoCons_NDexp_MCC_v2_target.tre", "upham_NDexp_MCC.tre"),
    ("upham_sample100_nd", RAW + "MamPhy_fullPosterior_BDvr_Completed_5911sp_topoCons_NDexp_v2_sample100_nexus.trees", "upham_NDexp_sample100.trees"),
    ("upham_mcc_fbd", RAW + "MamPhy_fullPosterior_BDvr_Completed_5911sp_topoCons_FBDasZhouEtAl_MCC_v2_target.tre", "upham_FBD_MCC.tre"),
    ("bininda_emonds_2007", RAW + "bininda-emonds-et-al2007_treeFile_Supp1.nex", "bininda_emonds_2007.nex"),
]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


old = {}
if os.path.exists(MANIFEST):
    old = {x["id"]: x for x in json.load(open(MANIFEST))["files"]}
out = []
for fid, url, name in FILES:
    path = os.path.join(DATA, name)
    r = requests.get(url, timeout=300, headers={"User-Agent": "delphisci-run/1.0"})
    r.raise_for_status()
    open(path, "wb").write(r.content)
    rec = {
        "id": fid, "download_url": url, "local_name": name,
        "retrieved_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": os.path.getsize(path), "sha256": sha(path),
    }
    if fid in old and old[fid]["sha256"] != rec["sha256"]:
        print("DRIFT", fid, old[fid]["sha256"], "->", rec["sha256"], file=sys.stderr)
    out.append(rec)
    print(fid, rec["byte_size"], rec["sha256"])
with zipfile.ZipFile(os.path.join(DATA, "anage_dataset.zip")) as z:
    z.extract("anage_data.txt", DATA)
json.dump({"upham_repo_commit": GH, "files": out}, open(MANIFEST, "w"), indent=1)
