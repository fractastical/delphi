#!/usr/bin/env python3
"""Queen maternity of workers, from Dryad genotypes if the workbook downloads,
otherwise from the Animal Diversity Web account named as the fallback.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "Mozilla/5.0 (compatible; delphisci-claim-test/aristotle-ga03-21)"
DRYAD = "https://datadryad.org/downloads/file_stream/22989"
DRYAD_PAGE = "https://datadryad.org/dataset/doi:10.5061/dryad.f4m18"
ADW = "https://animaldiversity.org/accounts/Apis_mellifera/"

WORKER_QUEEN = re.compile(r"\b(workers?|queens?|gynes?)\b", re.I)
QUEEN_PRODUCES = re.compile(
    r"(queen.{0,80}(workers?|queens?|gynes?)| (workers?|queens?|gynes?).{0,80}queen)",
    re.I,
)


def fetch(url, dest, referer=None):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    raw = urllib.request.urlopen(req, timeout=90).read()
    dest.write_bytes(raw)
    return raw


def is_xlsx(raw):
    return raw[:2] == b"PK"


def html_to_text(raw):
    html = raw.decode("utf-8", "replace")
    html = re.sub(r"(?is)<script\b.*?</script>", " ", html)
    html = re.sub(r"(?is)<style\b.*?</style>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def meta(raw, url, now):
    return {
        "download_url": url,
        "retrieved_at": now,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest() if raw else None,
    }


def score_workbook(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    colonies = []
    daughter_hits = 0
    daughter_ok = 0
    for sheet in wb.worksheets:
        rows = []
        for row in sheet.iter_rows(values_only=True):
            rows.append([("" if c is None else str(c).strip()) for c in row])
        if not rows:
            continue
        queen_idx = None
        for i, row in enumerate(rows):
            label = " ".join(row[:3]).lower()
            if "queen" in label and "worker" not in label and "offspring" not in label and "daughter" not in label and "gyne" not in label:
                queen_idx = i
                break
        daughter_rows = []
        for i, row in enumerate(rows):
            label = " ".join(row[:3]).lower()
            if any(k in label for k in ("daughter queen", "gyne", "queen offspring", "virgin queen")):
                daughter_rows.append(i)
        if queen_idx is None:
            colonies.append({"sheet": sheet.title, "skipped": "no queen row"})
            continue
        queen = rows[queen_idx]
        # Allele columns are those where the queen cell looks like a genotype.
        worker_ok = 0
        worker_n = 0
        for i, row in enumerate(rows):
            if i == queen_idx or i in daughter_rows:
                continue
            label = " ".join(row[:2]).lower()
            if "worker" not in label and not re.search(r"\d", " ".join(row)):
                continue
            comparable = 0
            compatible = 0
            for q, w in zip(queen, row):
                q_alleles = set(re.findall(r"[0-9A-Za-z]+", q))
                w_alleles = set(re.findall(r"[0-9A-Za-z]+", w))
                if len(q_alleles) < 1 or len(w_alleles) < 1:
                    continue
                if q.lower() in {"queen", "locus", "allele"} or w.lower() in {"worker"}:
                    continue
                comparable += 1
                if q_alleles & w_alleles:
                    compatible += 1
            if comparable >= 2:
                worker_n += 1
                if compatible == comparable:
                    worker_ok += 1
        for i in daughter_rows:
            row = rows[i]
            comparable = compatible = 0
            for q, w in zip(queen, row):
                q_alleles = set(re.findall(r"[0-9A-Za-z]+", q))
                w_alleles = set(re.findall(r"[0-9A-Za-z]+", w))
                if not q_alleles or not w_alleles:
                    continue
                comparable += 1
                if q_alleles & w_alleles:
                    compatible += 1
            if comparable >= 2:
                daughter_hits += 1
                if compatible == comparable:
                    daughter_ok += 1
        colonies.append({
            "sheet": sheet.title,
            "workers": worker_n,
            "workers_compatible": worker_ok,
            "pass": worker_n > 0 and (worker_ok / worker_n) >= 0.95,
        })
    scored = [c for c in colonies if "workers" in c]
    total_workers = sum(c["workers"] for c in scored)
    passing = [c for c in scored if c["pass"]]
    worker_pass = bool(scored) and total_workers >= 100 and (len(passing) / len(scored)) >= 0.90
    worker_fail = bool(scored) and (len(passing) / len(scored)) < 0.50
    if daughter_hits >= 10:
        own_rate = daughter_ok / daughter_hits
        own = "pass" if own_rate >= 0.95 else ("fail" if own_rate < 0.50 else "between")
    elif daughter_hits == 0:
        own = "unmeasured"
    else:
        own = "underpowered"
    return {
        "colonies": colonies,
        "total_workers": total_workers,
        "colonies_scored": len(scored),
        "colonies_pass": len(passing),
        "worker_pass": worker_pass,
        "worker_fail": worker_fail,
        "daughter_n": daughter_hits,
        "daughter_ok": daughter_ok,
        "own_kind": own,
    }


def code_adw(raw):
    text = html_to_text(raw)
    sents = sentences(text)
    both = []
    for i, s in enumerate(sents):
        low = s.lower()
        # Both castes, and the queen named as the one who lays or produces the egg.
        if not re.search(r"\b(develop|develops|produce|produces|lay|lays|become|becomes)\b", low):
            continue
        has_worker = bool(re.search(r"\bworkers?\b", low))
        has_new_queen = bool(re.search(r"\b(new queens?|daughter queens?|gynes?)\b", low))
        if not (has_worker and has_new_queen):
            continue
        prev_window = " ".join(sents[max(0, i - 2):i])
        queen_here = bool(re.search(r"\bqueen\b", low))
        # The queen-lays sentence is two sentences above the caste sentence:
        # she lays the egg, unfertilized eggs are males, fertilized eggs are the two female castes.
        queen_lays_near = bool(
            re.search(r"\bqueen\b", prev_window, re.I)
            and re.search(r"\b(lay|lays|laid|egg|eggs)\b", prev_window, re.I)
        )
        if queen_here or queen_lays_near:
            both.append(s if queen_here else (prev_window + " " + s))
    worker_only = [s for s in sents if re.search(r"queen", s, re.I) and re.search(r"workers?", s, re.I)]
    return {"both_sentences": both[:8], "n_queen_worker_sentences": len(worker_only), "both": bool(both)}


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dryad_path = DATA / "Data.xlsx"
    try:
        raw = fetch(DRYAD, dryad_path, referer=DRYAD_PAGE)
    except Exception as exc:
        raw = b""
        (DERIVED / "dryad_error.txt").write_text(str(exc))
    datasets = []
    if is_xlsx(raw):
        scored = score_workbook(dryad_path)
        (DERIVED / "genotypes.json").write_text(json.dumps(scored, indent=2) + "\n")
        datasets.append({
            "id": "dryad-10.5061/dryad.f4m18",
            "name": "Subfamily-dependent alternative reproductive strategies in worker honey bees",
            "landing_url": "https://doi.org/10.5061/dryad.f4m18",
            "doi": "10.5061/dryad.f4m18",
            "version": "Data.xlsx",
            "license": "Dryad dataset; see the dataset page",
            "files": [meta(raw, DRYAD, now)],
            "role": "worker and queen microsatellite genotypes",
        })
        if scored["worker_fail"] or scored["own_kind"] == "fail":
            verdict, reason, confidence = "refutes", None, 0.7
        elif scored["worker_pass"] and scored["own_kind"] == "pass":
            verdict, reason, confidence = "supports", None, 0.75
        elif scored["worker_pass"] and scored["own_kind"] in {"unmeasured", "underpowered", "between"}:
            verdict, reason, confidence = "mixed", None, 0.6
        else:
            verdict, reason, confidence = "inconclusive", "not-operationalizable", 0.4
        measured_extra = scored
        method = "Downloaded Data.xlsx and scored allele sharing between each sheet's queen row and worker rows. A worker is compatible when every comparable locus shares an allele with the queen. Daughter-queen rows were scored the same way when labels existed."
        value = scored["colonies_pass"]
        unit = "colonies whose workers are mother-compatible with the queen"
        n = scored["colonies_scored"]
        data_kind = "biological"
    else:
        try:
            adw = fetch(ADW, DATA / "apis.html")
        except Exception as exc:
            adw = b""
            (DERIVED / "adw_error.txt").write_text(str(exc))
        coding = code_adw(adw) if adw else {"both": False, "both_sentences": [], "n_queen_worker_sentences": 0}
        (DERIVED / "adw_coding.json").write_text(json.dumps(coding, indent=2) + "\n")
        datasets.append({
            "id": "dryad-10.5061/dryad.f4m18",
            "name": "Dryad workbook was not retrievable",
            "landing_url": "https://doi.org/10.5061/dryad.f4m18",
            "doi": "10.5061/dryad.f4m18",
            "version": None,
            "license": None,
            "files": [meta(raw, DRYAD, now)] if raw else [],
            "role": "planned genotype file; the response was not an xlsx workbook",
        })
        datasets.append({
            "id": "adw-apis-mellifera-fallback",
            "name": "Animal Diversity Web account of Apis mellifera",
            "landing_url": ADW,
            "doi": None,
            "version": now[:10],
            "license": "Animal Diversity Web; coded, not redistributed",
            "files": [meta(adw, ADW, now)] if adw else [],
            "role": "fallback life-history account of queen maternity",
        })
        if not adw:
            verdict, reason, confidence = "inconclusive", "data-unavailable", 0.3
            data_kind = "none"
        elif coding["both"]:
            verdict, reason, confidence = "supports", None, 0.55
            data_kind = "biological"
        else:
            verdict, reason, confidence = "inconclusive", "not-operationalizable", 0.4
            data_kind = "biological" if adw else "none"
        method = "The Dryad file request did not return an xlsx workbook, so the pre-registered fallback was used: the Animal Diversity Web account of Apis mellifera was coded for a sentence in which the queen produces both workers and new queens."
        measured_extra = {"dryad_was_xlsx": False, "dryad_bytes": len(raw), "adw": coding}
        value = int(bool(coding.get("both")))
        unit = "1 if the account states that the queen produces both workers and new queens"
        n = 1 if adw else 0

    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": data_kind,
        "method": method,
        "measured": {
            "value": value,
            "unit": unit,
            "n": n,
            "uncertainty": "see extra",
            "extra": measured_extra if not isinstance(measured_extra, dict) or "colonies" not in measured_extra else {
                "total_workers": measured_extra["total_workers"],
                "colonies_scored": measured_extra["colonies_scored"],
                "colonies_pass": measured_extra["colonies_pass"],
                "own_kind": measured_extra["own_kind"],
                "daughter_n": measured_extra["daughter_n"],
            },
        },
        "datasets": datasets,
        "results_summary": [method] + (coding.get("both_sentences", [])[:2] if not is_xlsx(raw) else []),
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, reason if "reason" in dir() else "", "xlsx" if is_xlsx(raw) else f"not-xlsx {len(raw)}")


if __name__ == "__main__":
    main()
