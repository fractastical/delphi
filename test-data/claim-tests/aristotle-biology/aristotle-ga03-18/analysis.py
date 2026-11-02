#!/usr/bin/env python3
"""Code bee, wasp and butterfly accounts for a larva-to-pupa transition,
and count iNaturalist research-grade pupa observations.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/aristotle-ga03-18"

ACCOUNTS = [
    ("adw-apis-mellifera", "Apis mellifera", "https://animaldiversity.org/accounts/Apis_mellifera/"),
    ("adw-vespula-maculifrons", "Vespula maculifrons", "https://animaldiversity.org/accounts/Vespula_maculifrons/"),
    ("adw-danaus-plexippus", "Danaus plexippus", "https://animaldiversity.org/accounts/Danaus_plexippus/"),
]
LARVA = re.compile(r"\b(larvae|larva|caterpillars?|grubs?|grub-like)\b", re.I)
# pupa/pupate and their morphological forms (pupal, pupation), plus chrysalis and cocoon
PUPA = re.compile(r"\b(pupae|pupa|pupal|pupation|chrysalis|chrysalises|cocoons?)\b", re.I)
TRANSITION = re.compile(
    r"\b(become|becomes|pupate|pupates|pupation|enter the pupal|molt|molts|moult|transform|transforms|develops into|emerge|emerges)\b",
    re.I,
)
# A denial has to be about this animal. The ADW glossary defines "incomplete metamorphosis"
# for grasshoppers in the same sentence as "complete metamorphosis" for butterflies; that
# glossary sentence is not a denial for the account's species.
DENY = re.compile(r"no pupal stage|without a pupa|hemimetabolous", re.I)
GLOSSARY = re.compile(r"incomplete metamorphosis.{0,200}complete metamorphosis|complete metamorphosis.{0,200}incomplete metamorphosis", re.I)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/html"})
    return urllib.request.urlopen(req, timeout=60).read()


def html_to_text(raw):
    html = raw.decode("utf-8", "replace")
    html = re.sub(r"(?is)<script\b.*?</script>", " ", html)
    html = re.sub(r"(?is)<style\b.*?</style>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]


def larval_clause(text):
    m = re.search(r"\b(?:yellow jackets|the larva|larvae|larva|grub-like)\b", text, re.I)
    return text[m.start():] if m else text[-240:]


def life_stage_ids(terms_json):
    data = json.loads(terms_json)
    term_id = value_id = None
    for term in data.get("results", []):
        if str(term.get("label", "")).lower() == "life stage":
            term_id = term.get("id")
            for value in term.get("values", []):
                if str(value.get("label", "")).lower() == "pupa":
                    value_id = value.get("id")
    return term_id, value_id


def observation_count(taxon, term_id, value_id):
    qs = urllib.parse.urlencode({
        "taxon_name": taxon,
        "quality_grade": "research",
        "term_id": term_id,
        "term_value_id": value_id,
        "per_page": 1,
    })
    raw = get("https://api.inaturalist.org/v1/observations?" + qs)
    payload = json.loads(raw)
    return payload.get("total_results"), raw


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    datasets = []
    coded = []
    for did, taxon, url in ACCOUNTS:
        try:
            raw = get(url)
            err = None
        except Exception as exc:
            raw = b""
            err = str(exc)
        (DATA / (did + ".html")).write_bytes(raw)
        text = html_to_text(raw) if raw else ""
        sents = sentences(text)
        transition_sents = [s for s in sents if LARVA.search(s) and PUPA.search(s) and TRANSITION.search(s)]
        deny_sents = [s for s in sents if DENY.search(s) and not GLOSSARY.search(s)]
        # A pupal sentence that fails the same-sentence rule is recorded and not scored.
        adjacent = []
        if not transition_sents:
            for i, s in enumerate(sents):
                if not (PUPA.search(s) or re.search(r"\bpupates?\b", s, re.I)):
                    continue
                window = " ".join(sents[max(0, i - 2):i])
                if LARVA.search(window):
                    adjacent.append(larval_clause(window) + " || " + s)
        coded.append({
            "id": did,
            "taxon": taxon,
            "fetched": bool(raw) and err is None,
            "error": err,
            "transition": bool(transition_sents) and not deny_sents,
            "denied": bool(deny_sents),
            "transition_sentences": transition_sents[:6],
            "deny_sentences": deny_sents[:4],
            "adjacent_not_scored": adjacent[:3],
        })
        datasets.append({
            "id": did,
            "name": f"Animal Diversity Web account of {taxon}",
            "landing_url": url,
            "doi": None,
            "version": now[:10],
            "license": "Animal Diversity Web; coded, not redistributed",
            "files": [{
                "download_url": url,
                "retrieved_at": now,
                "byte_size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest() if raw else None,
            }],
            "role": "life-history account of larva and pupa",
        })

    terms_raw = b""
    term_id = value_id = None
    counts = {}
    try:
        terms_raw = get("https://api.inaturalist.org/v1/controlled_terms")
        (DATA / "controlled_terms.json").write_bytes(terms_raw)
        term_id, value_id = life_stage_ids(terms_raw)
        if term_id is not None and value_id is not None:
            for _, taxon, _ in ACCOUNTS:
                count, raw_obs = observation_count(taxon, term_id, value_id)
                counts[taxon] = count
                (DATA / ("inat-" + taxon.replace(" ", "-") + ".json")).write_bytes(raw_obs)
    except Exception as exc:
        counts["error"] = str(exc)
    datasets.append({
        "id": "inaturalist-life-stage-pupa",
        "name": "iNaturalist research-grade observations annotated Life Stage = Pupa",
        "landing_url": "https://www.inaturalist.org/",
        "doi": None,
        "version": now[:10],
        "license": "iNaturalist observation data, CC-BY-NC or as marked on each observation; only the count was used",
        "files": [{
            "download_url": "https://api.inaturalist.org/v1/controlled_terms",
            "retrieved_at": now,
            "byte_size": len(terms_raw),
            "sha256": hashlib.sha256(terms_raw).hexdigest() if terms_raw else None,
        }],
        "role": f"pupa observation counts; term_id={term_id} value_id={value_id}",
    })
    (DERIVED / "coding.json").write_text(json.dumps({"accounts": coded, "pupa_counts": counts, "term_id": term_id, "value_id": value_id}, indent=2) + "\n")

    fetched = [c for c in coded if c["fetched"]]
    denied = [c for c in coded if c["denied"]]
    transitioned = [c for c in coded if c["transition"]]
    count_vals = [counts.get(taxon) for _, taxon, _ in ACCOUNTS]
    counts_ok = all(isinstance(v, int) and v >= 30 for v in count_vals)
    if not fetched:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.3
    elif denied:
        verdict, reason, confidence = "refutes", None, 0.7
    elif len(transitioned) == 3 and counts_ok:
        verdict, reason, confidence = "supports", None, 0.7
    elif len(transitioned) == 3 and not counts_ok:
        verdict, reason, confidence = "mixed", None, 0.55
    elif 0 < len(transitioned) < 3:
        verdict, reason, confidence = "mixed", None, 0.5
    elif term_id is None:
        verdict, reason, confidence = "inconclusive", "not-operationalizable", 0.35
    else:
        verdict, reason, confidence = "inconclusive", "not-operationalizable", 0.4

    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological" if fetched else "none",
        "method": "Downloaded the three Animal Diversity Web accounts and coded sentences that contain a larval term, a pupal term, and a transition verb. Resolved the iNaturalist Life Stage vocabulary and counted research-grade observations annotated Pupa for each taxon. Support required all three accounts and at least 30 pupa observations each.",
        "measured": {
            "value": len(transitioned),
            "unit": "accounts, of three, with a larva-to-pupa sentence",
            "n": 3,
            "uncertainty": "one species account per named group; observation counts are annotations, not timed immobility",
            "extra": {
                "pupa_observation_counts": {taxon: counts.get(taxon) for _, taxon, _ in ACCOUNTS},
                "term_id": term_id,
                "pupa_value_id": value_id,
                "denied": [c["taxon"] for c in denied],
            },
        },
        "datasets": datasets,
        "results_summary": [
            f"{c['taxon']}: transition={c['transition']} denied={c['denied']}" for c in coded
        ] + [s for c in coded for s in c.get("transition_sentences", [])] + [
            "not scored (larva and pupa are in adjacent sentences): " + s
            for c in coded for s in c.get("adjacent_not_scored", [])
        ] + [f"iNaturalist pupa counts: { {taxon: counts.get(taxon) for _, taxon, _ in ACCOUNTS} }"],
    })
    if reason:
        result["reason"] = reason
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, reason, counts)


if __name__ == "__main__":
    main()
