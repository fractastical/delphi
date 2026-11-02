#!/usr/bin/env python3
"""Score whether the octopus hectocotylus is described as only an attachment organ."""
import datetime as dt
import hashlib
import html
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/1.0 (aristotle-ga01-15; research)"
PAGES = [
    ("adw-octopus-vulgaris", "Animal Diversity Web account of Octopus vulgaris",
     "https://animaldiversity.org/accounts/Octopus_vulgaris/"),
    ("wikipedia-hectocotylus", "Wikipedia article Hectocotylus",
     "https://en.wikipedia.org/wiki/Hectocotylus"),
]
GEN = re.compile(r"sperm groove|transfers sperm|transfer of spermatophores", re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read(), getattr(resp, "status", 200)


def to_text(raw):
    page = raw.decode("utf-8", "replace")
    page = re.sub(r"(?is)<(script|style)\b.*?>.*?</\1>", " ", page)
    page = re.sub(r"(?is)<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(page)).strip()


def generative_windows(text):
    hits = []
    for m in re.finditer(r"hectocotyl\w*", text, re.I):
        w = text[max(0, m.start() - 200): m.end() + 200]
        if re.search(r"sperm|spermatophore|fertil", w, re.I):
            hits.append(w)
    for m in GEN.finditer(text):
        hits.append(text[max(0, m.start() - 80): m.end() + 80])
    return hits


def attachment_only_windows(text):
    hits = []
    for m in re.finditer(r"arm|hectocotyl\w*", text, re.I):
        w = text[max(0, m.start() - 120): m.end() + 120]
        if re.search(r"attachment|holding|holdfast", w, re.I) and re.search(r"only|not an organ|no role|not used", w, re.I):
            hits.append(w)
    return hits


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    datasets = []
    scores = []
    for pid, name, url in PAGES:
        raw, status = fetch(url)
        (DATA / f"{pid}.html").write_bytes(raw)
        text = to_text(raw)
        gen = generative_windows(text)
        att = attachment_only_windows(text)
        mentioned = bool(re.search(r"hectocotyl|spermatophore|attachment", text, re.I))
        if gen:
            label = "generative"
        elif att:
            label = "attachment-only"
        else:
            label = "silent"
        scores.append({
            "id": pid,
            "http_status": status,
            "chars": len(text),
            "label": label,
            "mentioned": mentioned,
            "n_generative_windows": len(gen),
            "n_attachment_windows": len(att),
            "generative_snippet": gen[0][:400] if gen else "",
            "attachment_snippet": att[0][:400] if att else "",
        })
        datasets.append({
            "id": pid, "name": name, "landing_url": url, "doi": None, "version": None, "license": None,
            "files": [{"download_url": url, "retrieved_at": now, "byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}],
            "role": "prose account of the arm used in octopus mating",
        })
    labels = {s["id"]: s["label"] for s in scores}
    mentioned_any = any(s["mentioned"] for s in scores)
    if not mentioned_any or any(s["http_status"] != 200 for s in scores) and not mentioned_any:
        verdict, reason = "inconclusive", "data-unavailable"
    elif any(s["label"] == "generative" for s in scores) and any(s["label"] == "attachment-only" for s in scores):
        verdict, reason = "mixed", None
    elif any(s["label"] == "generative" for s in scores):
        verdict, reason = "refutes", None
    elif any(s["label"] == "attachment-only" for s in scores) and all(s["label"] != "generative" for s in scores):
        verdict, reason = "supports", None
    else:
        verdict, reason = "inconclusive", "data-unavailable"
    # Pass requires at least one attachment-only AND neither generative.
    # A generative hit with no attachment-only page is a refutation, which the branch above covers.
    n_gen = sum(s["n_generative_windows"] for s in scores)
    measured = {
        "value": n_gen,
        "unit": "character windows linking the hectocotylus to sperm or spermatophores",
        "n": len(scores),
        "uncertainty": None,
        "extra": {"pages": scores},
    }
    sources = {s["id"] for s in scores if s["label"] == "generative"}
    if verdict == "refutes" and sources == {"wikipedia-hectocotylus"}:
        confidence = 0.62
    elif verdict == "refutes":
        confidence = 0.84
    elif verdict == "supports":
        confidence = 0.6
    else:
        confidence = 0.45
    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "data_kind": "biological",
        "datasets": datasets,
        "measured": measured,
        "verdict": verdict,
        "confidence": confidence,
        "method": (
            "Fetched the two pre-registered pages, stripped HTML, and applied the generative and "
            "attachment-only windows from pass_criterion. "
            + ", ".join(f"{k}={v}" for k, v in labels.items())
            + "."
        ),
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["results_summary"] = [
        f"{s['id']}: {s['label']} ({s['n_generative_windows']} generative windows)." for s in scores
    ]
    (DERIVED / "measured.json").write_text(json.dumps({"measured": measured, "verdict": verdict}, indent=2) + "\n")
    (HERE / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, labels, "confidence", confidence)


if __name__ == "__main__":
    main()
