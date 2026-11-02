#!/usr/bin/env python3
"""aristotle-pa04-23: tongue of the Nile crocodile versus other oviparous quadrupeds and snakes.

Re-run: python3 analysis.py
Downloads the Putterill & Soley 2004 PDF and Animal Diversity Web accounts into ./data
(gitignored). Writes derived/coded.json and fills result.json.
Criteria were committed in result.json before these files were read.
"""
import hashlib
import html
import json
import re
import warnings
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests

warnings.filterwarnings("ignore")
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphi-claim-tests/1.0 (aristotle-pa04-23)"}
PAPER_URL = "https://ojvr.org/index.php/ojvr/article/download/230/218"
PANEL = [
    ("Testudo graeca", "tortoise", "https://animaldiversity.org/accounts/Testudo_graeca/"),
    ("Emys orbicularis", "turtle", "https://animaldiversity.org/accounts/Emys_orbicularis/"),
    ("Lacerta viridis", "lizard", "https://animaldiversity.org/accounts/Lacerta_viridis/"),
    ("Podarcis muralis", "lizard", "https://animaldiversity.org/accounts/Podarcis_muralis/"),
    ("Chamaeleo chamaeleon", "lizard", "https://animaldiversity.org/accounts/Chamaeleo_chamaeleon/"),
    ("Natrix natrix", "snake", "https://animaldiversity.org/accounts/Natrix_natrix/"),
    ("Hierophis viridiflavus", "snake", "https://animaldiversity.org/accounts/Hierophis_viridiflavus/"),
]
DESCRIBE = re.compile(
    r"(the tongue (was|is|appeared|occupied|exhibited)|dorsal surface of the tongue|"
    r"surface of the tongue|tongue occupied|ventro-lateral aspect of the tongue)",
    re.I,
)
DENY = re.compile(
    r"\b(no tongue|without a tongue|lacks? a tongue|tongue is absent|only a space)\b",
    re.I,
)
# Negation must attach to the tongue. "not protrusible" does not deny that a tongue exists.
TONGUE_DENIAL = re.compile(
    r"\b(?:no|without|lack(?:s|ing)?|absent)\b(?:\s+\w+){0,4}\s+tongues?\b"
    r"|\btongues?\b(?:\s+\w+){0,3}\s+(?:is|are|was|were)\s+(?:not\s+present|absent|lacking)\b"
    r"|\bnot\b(?:\s+\w+){0,3}\s+tongues?\b",
    re.I,
)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest):
    DATA.mkdir(parents=True, exist_ok=True)
    meta_path = dest.with_suffix(dest.suffix + ".meta.json")
    if dest.exists() and dest.stat().st_size > 0 and meta_path.exists():
        return json.loads(meta_path.read_text()), dest.read_bytes()
    r = requests.get(url, timeout=120, headers=UA)
    r.raise_for_status()
    body = r.content
    meta = {
        "download_url": r.url,
        "requested_url": url,
        "retrieved_at": now(),
        "byte_size": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "content_type": r.headers.get("content-type", ""),
    }
    dest.write_bytes(body)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta, body


def html_text(raw):
    raw = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?>.*?</style>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</p>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    return re.sub(r"\n{2,}", "\n", raw)


def code_account(text):
    sentences = []
    for s in re.split(r"(?<=[.!?])\s+", text):
        if re.search(r"\btongues?\b", s, re.I):
            sentences.append({"sentence": s.strip()[:500], "denial": bool(TONGUE_DENIAL.search(s))})
    if not sentences:
        return "unscored", sentences
    den = any(s["denial"] for s in sentences)
    aff = any(not s["denial"] for s in sentences)
    if den and not aff:
        return "absent", sentences
    if aff and not den:
        return "present", sentences
    return "ambiguous", sentences


def code_paper(pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    m = re.search(r"\bRESULTS\b", text)
    if not m:
        return {"code": "unscored", "reason": "no RESULTS heading", "pages": len(reader.pages), "chars": len(text)}
    results = text[m.end():]
    mend = re.search(r"\b(DISCUSSION|REFERENCES|ACKNOWLEDGEMENTS)\b", results)
    if mend:
        results = results[: mend.start()]
    described = [mm.group(0) for mm in DESCRIBE.finditer(results)]
    denied = [mm.group(0) for mm in DENY.finditer(results)]
    specimens = [int(x) for x in re.findall(r"\b(\d+)\s+(?:adult\s+)?(?:specimens?|crocodiles|animals)\b", results, re.I)]
    if described and not denied:
        code = "present"
    elif denied and not described:
        code = "absent"
    elif described and denied:
        code = "ambiguous"
    else:
        code = "unscored"
    return {
        "code": code,
        "describe_hits": len(described),
        "deny_hits": len(denied),
        "describe_examples": described[:5],
        "deny_examples": denied[:5],
        "specimen_counts_mentioned": specimens,
        "results_chars": len(results),
        "pages": len(reader.pages),
        "tongue_mentions_in_paper": len(re.findall(r"\btongues?\b", text, re.I)),
    }


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    paper_meta, paper_bytes = fetch(PAPER_URL, DATA / "putterill-soley-2004.pdf")
    paper = code_paper(paper_bytes)
    panel = []
    files = [paper_meta]
    for name, group, url in PANEL:
        slug = name.replace(" ", "_")
        try:
            meta, body = fetch(url, DATA / f"adw-{slug}.html")
        except requests.HTTPError as e:
            panel.append({"species": name, "group": group, "url": url, "code": "unresolved", "error": str(e)})
            continue
        text = html_text(body.decode("utf-8", "replace"))
        # A challenge or empty shell is not an account.
        if "Physical Description" not in text and name.split()[-1] not in text:
            panel.append({"species": name, "group": group, "url": url, "final_url": meta["download_url"], "code": "unresolved"})
            files.append(meta)
            continue
        code, sentences = code_account(text)
        panel.append({
            "species": name, "group": group, "url": url, "final_url": meta["download_url"],
            "code": code, "tongue_sentences": sentences[:6],
        })
        files.append(meta)

    present = [p for p in panel if p["code"] == "present"]
    absent = [p for p in panel if p["code"] == "absent"]
    groups_present = {p["group"] for p in present}
    quadruped = any(p["group"] in {"tortoise", "turtle", "lizard"} for p in present)
    snake = any(p["group"] == "snake" for p in present)
    universal_ok = len(present) >= 4 and len(groups_present) >= 2 and quadruped and snake and not absent

    croc = paper["code"]
    reason = None
    if croc == "present":
        verdict, confidence = "refutes", 0.80
    elif croc == "ambiguous":
        verdict, confidence = "mixed", 0.45
    elif croc == "absent" and universal_ok:
        verdict, confidence = "supports", 0.55
    elif croc == "absent" and absent:
        verdict, confidence = "mixed", 0.45
    elif croc == "absent":
        verdict, confidence = "inconclusive", 0.60
        reason = "underpowered" if present else "data-unavailable"
    else:
        verdict, confidence = "inconclusive", 0.60
        reason = "data-unavailable"

    n_spec = paper.get("specimen_counts_mentioned") or []
    measured = {
        "value": 1 if croc == "present" else 0 if croc == "absent" else None,
        "unit": "Nile crocodile coded as having a tongue organ in the oral cavity (1) or not (0)",
        "n": max(n_spec) if n_spec else 1,
        "uncertainty": "one published gross-anatomy paper; specimen count is the largest integer the results attach to specimens, animals, or crocodiles",
        "extra": {
            "crocodile_code": croc,
            "describe_hits": paper.get("describe_hits"),
            "deny_hits": paper.get("deny_hits"),
            "specimen_counts_mentioned": n_spec,
            "panel_present": len(present),
            "panel_absent": len(absent),
            "panel_scored_groups": sorted(groups_present),
            "universal_clause_holds": universal_ok,
            "panel": [{k: p[k] for k in ("species", "group", "code")} for p in panel],
        },
    }
    derived = {"paper": paper, "panel": panel, "measured": measured, "verdict": verdict}
    (DERIVED / "coded.json").write_text(json.dumps(derived, indent=2) + "\n")

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["data_kind"] = "biological" if paper.get("pages") else "none"
    if reason:
        result["reason"] = reason
    result["datasets"] = [
        {
            "id": "putterill-soley-2004-nile-crocodile-tongue",
            "name": "Putterill and Soley 2004, General morphology of the oral cavity of the Nile crocodile, Crocodylus niloticus. II. The tongue",
            "landing_url": "https://doi.org/10.4102/ojvr.v71i4.230",
            "doi": "10.4102/ojvr.v71i4.230",
            "version": "Onderstepoort Journal of Veterinary Research 71(4)",
            "license": "open access (journal PDF retrieved without a login)",
            "files": [{k: paper_meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
            "role": "gross anatomy of the tongue in Crocodylus niloticus specimens",
        },
        {
            "id": "adw-oviparous-tetrapod-tongue-panel",
            "name": "Animal Diversity Web accounts for the pre-registered tortoise, turtle, lizard and snake panel",
            "landing_url": "https://animaldiversity.org/",
            "doi": None,
            "version": "pages retrieved " + now()[:10],
            "license": "Animal Diversity Web, University of Michigan Museum of Zoology",
            "files": [
                {k: f[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}
                for f in files if f is not paper_meta and "sha256" in f
            ],
            "role": "whether other oviparous quadrupeds and snakes are described as having a tongue",
        },
    ]
    result["method"] = (
        "Downloaded the open PDF of Putterill and Soley 2004, extracted the text, and coded only the RESULTS "
        "section (up to DISCUSSION) for a gross-anatomical description of a tongue versus a denial that a tongue "
        "is present. Fetched each pre-registered Animal Diversity Web account and coded sentences containing "
        "'tongue', treating a negation as a denial only when it attaches to the word tongue. The exception clause "
        "alone refutes the claim if the crocodile has a tongue organ, because the claim says that animal has only a space."
    )
    result["measured"] = measured
    if croc == "present":
        headline = "The Nile crocodile has a tongue organ in the mouth, so it is not the tongueless exception the claim describes."
    elif verdict == "supports":
        headline = "The coded sources describe no tongue in the Nile crocodile and a tongue in the other reptiles that were scored."
    elif verdict == "mixed":
        headline = "The crocodile coding and the other-reptile panel do not agree on a single reading of the claim."
    else:
        headline = "The sources that could be fetched do not say whether the Nile crocodile lacks a tongue."
    result["results_summary"] = [headline]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "confidence": confidence, "crocodile": croc, "panel_present": len(present)}, indent=2))


if __name__ == "__main__":
    main()
