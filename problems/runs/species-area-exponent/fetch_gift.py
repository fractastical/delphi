#!/usr/bin/env python3
"""Fetch the GIFT data pre-registered in PREREG.md and write derived/gift_richness.csv.

Raw responses go to data/ (git-ignored). derived/gift_manifest.csv.gz records, per file,
URL, retrieval time (UTC), byte size and SHA-256. Re-running reuses files already in data/
(manifest keeps the original retrieval time) and re-derives everything else.
"""
import concurrent.futures as cf
import csv, gzip, hashlib, json, os, sys, time, datetime as dt
import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DER = os.path.join(HERE, "derived")
API = "https://gift.uni-goettingen.de/api/"
SEED = 20261101
os.makedirs(os.path.join(DATA, "lists"), exist_ok=True)
os.makedirs(DER, exist_ok=True)
MAN_PATH = os.path.join(DER, "gift_manifest.csv.gz")

manifest = {}
if os.path.exists(MAN_PATH):
    with gzip.open(MAN_PATH, "rt") as f:
        for r in csv.DictReader(f):
            manifest[r["path"]] = r

sess = requests.Session()


def fetch(url, path, tries=5):
    full = os.path.join(DATA, path)
    if os.path.exists(full) and path in manifest:
        return full
    for k in range(tries):
        try:
            r = sess.get(url, timeout=180)
            if r.status_code == 200 and r.content[:1] in (b"[", b"{"):
                json.loads(r.content)  # must parse
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "wb") as f:
                    f.write(r.content)
                manifest[path] = dict(
                    path=path, url=url,
                    retrieved_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    byte_size=len(r.content), sha256=hashlib.sha256(r.content).hexdigest())
                return full
        except Exception as e:  # noqa
            err = e
        time.sleep(2 + 3 * k)
    raise RuntimeError(f"failed {url}")


def save_manifest():
    with gzip.open(MAN_PATH, "wt") as f:
        w = csv.DictWriter(f, fieldnames=["path", "url", "retrieved_at", "byte_size", "sha256"])
        w.writeheader()
        for k in sorted(manifest):
            w.writerow(manifest[k])


lists_p = fetch(API + "extended/index.php?query=lists", "lists.json")
geo_p = fetch(API + "index.php?query=geoentities", "geoentities.json")
lists = pd.DataFrame(json.load(open(lists_p)))
geo = pd.DataFrame(json.load(open(geo_p)))
print("lists", lists.shape, "geoentities", geo.shape)

# ---- frozen selection (PREREG.md) ----
sel = lists[(lists.taxon_ID == 2) & lists.type.isin(["Flora", "Checklist"])
            & lists.subset.isin(["all", "native", "native and naturalized"])
            & (lists.native_indicated == 1) & (lists.restricted == 0) & (lists.suit_geo == 1)]
sel = sel.merge(geo[["entity_ID", "area", "longitude", "latitude", "distance_to_mainland"]],
                on="entity_ID", how="left")
sel = sel[sel.area.notna() & (sel.area > 0)]
isl = sel[sel.entity_class == "Island"]
mainland = sel[(sel.entity_class == "Mainland")
               & sel.entity_type.isin(["Political Unit", "Botanical Country", "Landscape/Region"])]
rng = np.random.default_rng(SEED)
ment = np.sort(mainland.entity_ID.unique())
if len(ment) > 400:
    ment = np.sort(rng.choice(ment, 400, replace=False))
mainland = mainland[mainland.entity_ID.isin(ment)]
want = pd.concat([isl.assign(role="island"), mainland.assign(role="mainland")])
print("eligible lists: island", len(isl), "(entities", isl.entity_ID.nunique(), ") mainland", len(mainland),
      "(entities", mainland.entity_ID.nunique(), ")")


def get_list(lid):
    p = fetch(API + f"extended/index.php?query=checklists&listid={lid}", f"lists/{lid}.json")
    rows = json.load(open(p))
    ids = {r["work_ID"] for r in rows if r.get("native") == 1}
    return lid, len(ids), len(rows)


res = {}
ids = sorted(want.list_ID.unique())
t0 = time.time()
with cf.ThreadPoolExecutor(8) as ex:
    futs = [ex.submit(get_list, int(i)) for i in ids]
    for n, f in enumerate(cf.as_completed(futs)):
        lid, s, nrows = f.result()
        res[lid] = (s, nrows)
        if n % 100 == 0:
            print(n, len(ids), round(time.time() - t0), "s", flush=True)
            save_manifest()
save_manifest()

want["native_richness"] = want.list_ID.map(lambda i: res[int(i)][0])
want["n_rows"] = want.list_ID.map(lambda i: res[int(i)][1])
want = want[want.native_richness >= 1]
best = want.sort_values(["entity_ID", "native_richness"], ascending=[True, False]).drop_duplicates("entity_ID")
best = best[["role", "entity_ID", "geo_entity", "entity_class", "entity_type", "list_ID", "ref_ID", "type", "subset",
             "area", "longitude", "latitude", "distance_to_mainland", "native_richness"]]
best.to_csv(os.path.join(DER, "gift_richness.csv"), index=False)
print(best.groupby("role").size())
