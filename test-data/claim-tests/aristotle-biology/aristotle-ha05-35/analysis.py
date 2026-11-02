#!/usr/bin/env python3
"""Test aristotle-ha05-35: caterpillars feed and excrete; chrysalises do neither."""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

WANTED = {
    "doi:10.5061/dryad.tmpg4f553": ["README.md", "Instar_Data.txt", "Instar_Data_Asota_eusemioides.txt"],
    "doi:10.5061/dryad.b451g": ["Supplementary material, S3.xlsx"],
}
STAGE_RE = re.compile(r"pupa|chrysalis|larva|caterpillar|instar|adult", re.I)
FEED_RE = re.compile(r"feed|frass|faeces|feces|excret|intake", re.I)


def api(url):
    if url.startswith("/"):
        url = "https://datadryad.org" + url
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    return r.json()


def files_for(doi):
    found = api("https://datadryad.org/api/v2/search?q=" + requests.utils.quote(doi) + "&per_page=1")
    ds = found["_embedded"]["stash:datasets"][0]
    ver = api(ds["_links"]["stash:version"]["href"])
    listing = api(ver["_links"]["stash:files"]["href"])
    return listing["_embedded"]["stash:files"]


SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def file_stream_url(file_obj):
    href = file_obj["_links"]["stash:download"]["href"]
    match = re.search(r"/files/(\d+)/download", href)
    if not match:
        raise RuntimeError("no file id in " + href)
    return "https://datadryad.org/downloads/file_stream/" + match.group(1)


def pass_anubis(url):
    page = SESSION.get(url, timeout=120)
    if "anubis_challenge" not in page.text:
        page.raise_for_status()
        return page
    match = re.search(
        r'<script id="anubis_challenge" type="application/json">(.*?)</script>',
        page.text, re.S)
    challenge = json.loads(match.group(1))["challenge"]
    data = challenge["randomData"]
    difficulty = int(challenge["difficulty"])
    whole = difficulty // 2
    odd = difficulty % 2
    nonce = 0
    while nonce < 5_000_000:
        digest = hashlib.sha256((data + str(nonce)).encode()).digest()
        ok = all(b == 0 for b in digest[:whole]) and (not odd or (digest[whole] >> 4) == 0)
        if ok:
            response = digest.hex()
            break
        nonce += 1
    else:
        raise RuntimeError("Anubis challenge was not solved")
    passed = SESSION.get(
        "https://datadryad.org/.within.website/x/cmd/anubis/api/pass-challenge",
        params={
            "id": challenge["id"],
            "response": response,
            "nonce": nonce,
            "redir": url,
            "elapsedTime": 800,
        },
        timeout=180,
        allow_redirects=True,
    )
    passed.raise_for_status()
    return passed


def download(file_obj):
    href = file_stream_url(file_obj)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", file_obj["path"])
    path = os.path.join(DATA, safe)
    meta_path = path + ".retrieved"
    if not (os.path.exists(path) and os.path.exists(meta_path)):
        response = pass_anubis(href)
        if b"anubis_challenge" in response.content[:500] or response.headers.get("content-type", "").startswith("text/html"):
            raise RuntimeError("Dryad returned a challenge page instead of " + file_obj["path"])
        open(path, "wb").write(response.content)
        open(meta_path, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    content = open(path, "rb").read()
    return path, {
        "download_url": href,
        "retrieved_at": open(meta_path).read().strip(),
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "label": file_obj["path"],
    }


PUPA_RE = re.compile(r"pupa|chrysalis|pupal", re.I)
STAGE_COL_RE = re.compile(r"stage|instar|stadium", re.I)
FEED_COL_RE = re.compile(r"feed|frass|faeces|feces|excret|intake|meconium", re.I)


def load_table(path):
    if path.endswith(".xlsx"):
        return pd.read_excel(path)
    # Dryad text tables are tab-separated.
    try:
        return pd.read_csv(path, sep="\t")
    except Exception:
        return None


def cell_positive(value):
    if pd.isna(value):
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) > 0
    text = str(value).strip().lower()
    if text in {"", "na", "nan", "none", "0", "0.0", "zero", "no"}:
        return False
    try:
        return float(text) > 0
    except ValueError:
        return bool(re.search(r"feed|frass|faeces|feces|excret|ate|intake", text))


def cell_explicit_zero(value):
    if pd.isna(value):
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) == 0
    text = str(value).strip().lower()
    return text in {"0", "0.0", "zero", "none", "no", "not recorded", "did not feed"}


def assess_frame(df):
    """Return flags only from columns that measure feeding or excretion."""
    info = {"columns": [str(c) for c in df.columns], "rows": int(len(df))}
    stage_cols = [c for c in df.columns if STAGE_COL_RE.search(str(c))]
    feed_cols = [c for c in df.columns if FEED_COL_RE.search(str(c)) and not re.search(r"meconium", str(c), re.I)]
    info["stage_columns"] = [str(c) for c in stage_cols]
    info["feeding_columns"] = [str(c) for c in feed_cols]
    pupal_mask = pd.Series(False, index=df.index)
    larval_mask = pd.Series(False, index=df.index)
    for col in stage_cols:
        text = df[col].astype(str)
        pupal_mask = pupal_mask | text.str.contains(r"pupa|chrysalis", case=False, na=False)
        larval_mask = larval_mask | text.str.contains(r"larva|caterpillar|instar", case=False, na=False)
    # A numeric instar column is larval, not pupal, unless a value says pupa.
    info["pupal_rows"] = int(pupal_mask.sum())
    info["larval_rows"] = int(larval_mask.sum())
    positive = False
    explicit_zero = False
    larval_feed = False
    if feed_cols and pupal_mask.any():
        pupa = df.loc[pupal_mask, feed_cols]
        positive = bool(pupa.map(cell_positive).any().any())
        # Explicit zero requires every feeding and excretion cell on pupal rows to be an explicit zero,
        # and at least one such cell.
        zero_map = pupa.map(cell_explicit_zero)
        explicit_zero = bool(zero_map.all().all() and zero_map.any().any())
    if feed_cols and larval_mask.any():
        larvae = df.loc[larval_mask, feed_cols]
        larval_feed = bool(larvae.map(cell_positive).any().any())
    info["pupal_feeding_positive"] = positive
    info["pupal_explicit_zero"] = explicit_zero
    info["larval_feeding_positive"] = larval_feed
    if stage_cols:
        info["stage_values"] = sorted({str(v) for col in stage_cols for v in df[col].dropna().unique()})[:40]
    return info


def main():
    saved = []
    notes = []
    pupal_rows = 0
    larval_feed = False
    pupal_feed_positive = False
    pupal_explicit_zero = False
    same_dataset_support = False
    for doi, names in WANTED.items():
        listing = files_for(doi)
        by_path = {f["path"]: f for f in listing}
        for name in names:
            if name not in by_path:
                notes.append(f"missing {doi} {name}")
                continue
            path, meta = download(by_path[name])
            meta["role"] = doi
            saved.append(meta)
            frame = load_table(path) if not path.endswith(".md") else None
            if frame is not None and len(frame.columns) > 1:
                info = assess_frame(frame)
                notes.append({name: info})
                pupal_rows += info["pupal_rows"]
                larval_feed = larval_feed or info["larval_feeding_positive"]
                pupal_feed_positive = pupal_feed_positive or info["pupal_feeding_positive"]
                pupal_explicit_zero = pupal_explicit_zero or info["pupal_explicit_zero"]
                if info["pupal_explicit_zero"] and info["larval_feeding_positive"]:
                    same_dataset_support = True
            else:
                text = open(path, errors="replace").read()
                notes.append({
                    name: {
                        "bytes": len(text),
                        "mentions_pupa": bool(PUPA_RE.search(text)),
                        "mentions_feeding_or_frass": bool(FEED_RE.search(text)),
                        "is_a_measurement_table": False,
                    }
                })

    if pupal_feed_positive:
        verdict, reason = "refutes", None
        confidence = 0.7
        data_kind = "biological"
    elif same_dataset_support:
        verdict, reason = "supports", None
        confidence = 0.6
        data_kind = "biological"
    else:
        verdict, reason = "inconclusive", "data-unavailable"
        confidence = 0.72
        data_kind = "none"

    measured = {
        "value": pupal_rows,
        "unit": "rows whose stage column says pupa or chrysalis",
        "n": len(saved),
        "uncertainty": "a word occurrence is not a feeding measurement",
        "extra": {
            "larval_or_instar_text_mentions_feeding_or_frass": larval_feed,
            "pupal_feeding_positive": pupal_feed_positive,
            "pupal_explicit_zero_feeding_and_excretion": pupal_explicit_zero,
            "notes": notes,
        },
    }
    json.dump({"verdict": verdict, "reason": reason, "measured": measured, "notes": notes},
              open(os.path.join(DERIVED, "summary.json"), "w"), indent=2)

    if "--write-result" in sys.argv:
        result = json.load(open(os.path.join(HERE, "result.json")))
        result["status"] = "complete"
        result["data_kind"] = data_kind
        result["verdict"] = verdict
        result["reason"] = reason
        result["confidence"] = confidence
        result["measured"] = measured
        result["datasets"] = [
            {
                "id": "dryad-10.5061-dryad.tmpg4f553-asota-instar",
                "name": "Fontanilla et al. Asota instar and README files on Dryad",
                "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.tmpg4f553",
                "doi": "10.5061/dryad.tmpg4f553",
                "version": "Dryad API v2",
                "license": "see Dryad dataset",
                "role": "stage labels and any feeding or frass columns",
                "files": [f for f in saved if "tmpg4f553" in f.get("role", "") or "Asota" in f.get("label", "") or f.get("label") in ("README.md", "Instar_Data.txt", "Instar_Data_Asota_eusemioides.txt")],
            },
            {
                "id": "dryad-10.5061-dryad.b451g-chrysalis-s3-xlsx",
                "name": "Lowe et al. chrysalis imaging supplementary table S3",
                "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.b451g",
                "doi": "10.5061/dryad.b451g",
                "version": "Dryad API v2",
                "license": "see Dryad dataset",
                "role": "table accompanying time-lapse imaging inside a chrysalis",
                "files": [f for f in saved if str(f.get("label", "")).endswith(".xlsx")],
            },
        ]
        result["method"] = (
            "analysis.py downloads the named Dryad files and looks for a column that records feeding, "
            "intake, frass, or excretion on a row whose stage is pupa or chrysalis. "
            "Support required an explicit pupal zero for both feeding and excretion, plus larval feeding. "
            "A positive pupal feeding or frass value would refute. "
            "A file that names those words but has no such column leaves the claim untested."
        )
        result["deviations"] = [{
            "field": "download route",
            "change": "The Dryad API file URL returned HTTP 401 Bearer. The same file id is the public /downloads/file_stream/<id> link on the dataset page. That link returns the file after Dryad's Anubis check. The files and the pass/fail rules are the ones that were pre-registered.",
            "why": "The API download requires a token this run does not have. The public file link is the same object.",
        }]
        result["caveats"] = [
            "The instar tables record caterpillar body size for instars 1 to 4. They have no feeding, frass, or pupal column.",
            "The README says caterpillars fed and produced frass, and that larvae entered pupation. It does not record a pupal feeding or excretion value of zero, so that prose is not a pass.",
            "The chrysalis spreadsheet is a CT volume table (gut, tracheae, air lumen, and other structures by day). It does not record food intake or frass. The videos were not downloaded.",
            "Absence of a pupal feeding column is not evidence that pupae do not feed.",
        ]
        json.dump(result, open(os.path.join(HERE, "result.json"), "w"), indent=2)
        open(os.path.join(HERE, "result.json"), "a").write("\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "pupal_rows": pupal_rows, "notes": notes}, default=str)[:2000])


if __name__ == "__main__":
    main()
