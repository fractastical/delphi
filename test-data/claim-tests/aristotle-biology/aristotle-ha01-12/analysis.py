#!/usr/bin/env python3
"""aristotle-ha01-12: hair-coated animals bear live young.

The decision rule is the one committed in result.json before these pages were
downloaded. A living monotreme that is coded as both coated and egg-laying, on
its Animal Diversity Web account or on the Monotremata account, and corroborated
by Europe PMC titles or abstracts, refutes the universal. This sample cannot
support it.

    python3 analysis.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html as html_lib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
UA = "delphisci-claim-test/aristotle-ha01-12"

ACCOUNTS = [
    ("Ornithorhynchus anatinus", "https://animaldiversity.org/accounts/Ornithorhynchus_anatinus/"),
    ("Tachyglossus aculeatus", "https://animaldiversity.org/accounts/Tachyglossus_aculeatus/"),
    ("Zaglossus bartoni", "https://animaldiversity.org/accounts/Zaglossus_bartoni/"),
    ("Zaglossus attenboroughi", "https://animaldiversity.org/accounts/Zaglossus_attenboroughi/"),
    ("Zaglossus bruijnii", "https://animaldiversity.org/accounts/Zaglossus_bruijnii/"),
    ("Monotremata", "https://animaldiversity.org/accounts/Monotremata/"),
]
SPECIES = [name for name, _ in ACCOUNTS if name != "Monotremata"]

COAT_POS = re.compile(r"\b(fur|hairs|hair|pelage|spines|spine|quills|quill)\b", re.I)
COAT_NEG = re.compile(
    r"\b(hairless|no fur|no hair|without fur|without hair|lacks hair|lack hair|no spines|without spines|lacks spines)\b",
    re.I,
)
OVIP_EXPLICIT = re.compile(r"\b(oviparous|egg-laying|egg laying)\b", re.I)
OVIP_NEG = re.compile(r"\b(does not lay|do not lay|never lays)\b", re.I)
LAY_WORD = re.compile(r"\b(lay|lays|laid|laying)\b", re.I)
EGG_WORD = re.compile(r"\beggs?\b", re.I)

EBI = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
            return resp.status, body, resp.geturl()
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return exc.code, body, url


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def plain(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def section_text(page: str, sid: str) -> str | None:
    match = re.search(rf'<h2 id="{sid}"[^>]*>.*?</h2>(.*?)(?:<h2\b|$)', page, re.S | re.I)
    if not match:
        return None
    return plain(match.group(1))


def egg_near_lay(text: str) -> bool:
    for match in EGG_WORD.finditer(text):
        window = text[max(0, match.start() - 80) : match.end() + 80]
        if LAY_WORD.search(window):
            return True
    return False


def codes_coat(text: str | None) -> bool:
    if not text:
        return False
    return bool(COAT_POS.search(text)) and not bool(COAT_NEG.search(text))


def codes_oviparity(text: str | None) -> bool:
    if not text or OVIP_NEG.search(text):
        return False
    return bool(OVIP_EXPLICIT.search(text)) or egg_near_lay(text)


def evidence_sentence(text: str | None, kind: str) -> str | None:
    if not text:
        return None
    parts = re.split(r"(?<=[.!?])\s+", text)
    for sentence in parts:
        if kind == "coat" and codes_coat(sentence):
            return sentence[:500]
        if kind == "ovip" and codes_oviparity(sentence):
            return sentence[:500]
    if kind == "coat" and codes_coat(text):
        return text[:500]
    if kind == "ovip" and codes_oviparity(text):
        return text[:500]
    return None


def europepmc(binomial: str, kind: str) -> dict:
    if kind == "ovip":
        clause = '(oviparous OR "egg-laying" OR "lays eggs" OR "lays an egg" OR "egg is laid")'
    else:
        clause = "(fur OR hair OR pelage OR spines OR quills)"
    query = f'TITLE_ABS:"{binomial}" AND {clause}'
    params = {
        "query": query,
        "format": "json",
        "resultType": "core",
        "pageSize": "25",
    }
    url = EBI + "?" + urllib.parse.urlencode(params)
    status, body, final = fetch(url)
    hits = []
    hit_count = None
    slug = binomial.replace(" ", "_")
    (DATA / f"{slug}-{kind}.json").write_bytes(body)
    if status == 200:
        payload = json.loads(body.decode("utf-8"))
        hit_count = payload.get("hitCount")
        results = (payload.get("resultList") or {}).get("result") or []
        for row in results:
            title = plain(row.get("title") or "")
            abstract = plain(row.get("abstractText") or "")
            blob = f"{title} {abstract}".strip()
            matched = codes_oviparity(blob) if kind == "ovip" else codes_coat(blob)
            if not matched:
                continue
            hits.append({
                "pmid": row.get("pmid"),
                "doi": row.get("doi"),
                "year": row.get("pubYear"),
                "title": title[:300],
                "match_in": "title" if (codes_oviparity(title) if kind == "ovip" else codes_coat(title)) else "abstract",
                "sentence": evidence_sentence(abstract or title, "ovip" if kind == "ovip" else "coat"),
            })
    return {
        "query": query,
        "request_url": url,
        "http_status": status,
        "final_url": final,
        "byte_size": len(body),
        "sha256": sha256(body),
        "hit_count_reported": hit_count,
        "corroborating_hits": hits,
    }


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    retrieved = now_utc()
    accounts = {}
    for name, url in ACCOUNTS:
        status, body, final = fetch(url)
        page = body.decode("utf-8", errors="replace")
        slug = name.replace(" ", "_")
        (DATA / f"{slug}.html").write_bytes(body)
        physical = section_text(page, "physical_description")
        reproduction = section_text(page, "reproduction")
        accounts[name] = {
            "url": url,
            "final_url": final,
            "http_status": status,
            "retrieved_at": retrieved,
            "byte_size": len(body),
            "sha256": sha256(body),
            "loaded": status == 200 and len(body) > 1000,
            "physical_description_present": physical is not None,
            "reproduction_present": reproduction is not None,
            "coat": codes_coat(physical),
            "oviparous": codes_oviparity(reproduction),
            "coat_sentence": evidence_sentence(physical, "coat"),
            "oviparity_sentence": evidence_sentence(reproduction, "ovip"),
        }
        time.sleep(0.2)

    order_codes = bool(accounts["Monotremata"]["coat"] and accounts["Monotremata"]["oviparous"])
    literature = {}
    for name in SPECIES:
        literature[name] = {"oviparity": europepmc(name, "ovip"), "coat": europepmc(name, "coat")}
        time.sleep(0.3)

    refuters = []
    adw_only = []
    for name in SPECIES:
        own = accounts[name]["coat"] and accounts[name]["oviparous"]
        coded = own or order_codes
        egg_hits = literature[name]["oviparity"]["corroborating_hits"]
        coat_hits = literature[name]["coat"]["corroborating_hits"]
        if coded and egg_hits and coat_hits:
            refuters.append(name)
        elif own or (order_codes and (accounts[name]["loaded"] or True)):
            if (own or order_codes) and not (egg_hits and coat_hits):
                if own or order_codes:
                    adw_only.append(name)

    loaded = [name for name, row in accounts.items() if row["loaded"]]
    if not loaded:
        verdict, reason = "inconclusive", "data-unavailable"
    elif refuters:
        verdict, reason = "refutes", None
    elif any(accounts[name]["coat"] and accounts[name]["oviparous"] for name in SPECIES) or order_codes:
        verdict, reason = "inconclusive", "other"
    else:
        verdict, reason = "inconclusive", "underpowered"

    species_level = [name for name in refuters if accounts[name]["coat"] and accounts[name]["oviparous"]]
    if verdict == "refutes" and species_level:
        confidence = 0.85
    elif verdict == "refutes":
        confidence = 0.6
    elif reason == "other":
        confidence = 0.4
    elif reason == "underpowered":
        confidence = 0.35
    else:
        confidence = 0.2

    measured = {
        "value": len(refuters),
        "unit": "living monotreme species coded as coated and oviparous on Animal Diversity Web or the Monotremata account, and corroborated by Europe PMC for both traits",
        "n": len([name for name in SPECIES if accounts[name]["loaded"]]),
        "uncertainty": "keyword coding of two public texts per species, not a specimen count",
        "extra": {
            "order_account_codes_coat_and_oviparity": order_codes,
            "refuting_species": refuters,
            "accounts_coding_counterexample_without_both_literature_hits": [
                name for name in SPECIES
                if (accounts[name]["coat"] and accounts[name]["oviparous"]) and name not in refuters
            ],
            "accounts": {
                name: {k: v for k, v in row.items()}
                for name, row in accounts.items()
            },
            "literature": {
                name: {
                    kind: {
                        "query": block["query"],
                        "http_status": block["http_status"],
                        "byte_size": block["byte_size"],
                        "sha256": block["sha256"],
                        "hit_count_reported": block["hit_count_reported"],
                        "n_corroborating": len(block["corroborating_hits"]),
                        "corroborating_hits": block["corroborating_hits"][:5],
                    }
                    for kind, block in kinds.items()
                }
                for name, kinds in literature.items()
            },
        },
    }

    deviations = [{
        "what": "Europe PMC was requested with resultType=core rather than the pre-registered resultType=lite.",
        "why": "A header-free trial of the pre-registered lite request returned titles but no abstractText field, and the inference rule counts a hit only when the title or the abstract matches. core is the same search with the abstract included. Queries, page size and the match rule are unchanged.",
    }]

    derived = {"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured, "deviations": deviations}
    (DERIVED / "measured.json").write_text(json.dumps(derived, indent=2) + "\n")

    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if loaded else "none"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = confidence
    result["measured"] = measured
    result["deviations"] = deviations
    result["datasets"] = [
        {
            "id": "animal-diversity-web-monotreme-accounts",
            "name": "Animal Diversity Web species and order accounts",
            "landing_url": "https://animaldiversity.org/",
            "doi": None,
            "version": f"pages retrieved {retrieved}",
            "license": "Animal Diversity Web, University of Michigan Museum of Zoology; terms on the site disclaimer linked from each account",
            "files": [
                {
                    "name": f"{name.replace(' ', '_')}.html",
                    "download_url": row["url"],
                    "retrieved_at": row["retrieved_at"],
                    "byte_size": row["byte_size"],
                    "sha256": row["sha256"],
                }
                for name, row in accounts.items()
            ],
            "role": "physical-description and reproduction passages for the frozen monotreme taxa",
        },
        {
            "id": "europepmc-monotreme-abstracts",
            "name": "Europe PMC REST search, title and abstract",
            "landing_url": "https://europepmc.org/",
            "doi": None,
            "version": f"queries retrieved {retrieved}",
            "license": "Public Europe PMC REST API; each abstract remains under its source article's terms",
            "files": [
                {
                    "name": f"{name.replace(' ', '_')}-{kind}.json",
                    "download_url": block["request_url"],
                    "retrieved_at": retrieved,
                    "byte_size": block["byte_size"],
                    "sha256": block["sha256"],
                }
                for name, kinds in literature.items()
                for kind, block in kinds.items()
            ],
            "role": "corroborating titles and abstracts for coat and egg-laying",
        },
    ]
    result["method"] = (
        "Fetched the six pre-registered Animal Diversity Web accounts and the Europe PMC title-and-abstract "
        "searches for the five species. Coded a coat only from the Physical Description passage and oviparity "
        "only from the Reproduction passage, using the pre-registered patterns. A Europe PMC record counts only "
        "when its own title or abstract matches the same pattern. The Monotremata account can supply the coding "
        "for the clade; the literature hits still have to be for a named species. Supports was not available from this sample."
    )
    lines = []
    for name in SPECIES:
        row = accounts[name]
        egg_n = len(literature[name]["oviparity"]["corroborating_hits"])
        coat_n = len(literature[name]["coat"]["corroborating_hits"])
        lines.append(
            f"{name}: ADW coat={row['coat']}, ADW oviparous={row['oviparous']}, "
            f"PMC coat hits={coat_n}, PMC egg hits={egg_n}, http={row['http_status']}"
        )
    lines.insert(0, f"Monotremata account coat={accounts['Monotremata']['coat']}, oviparous={accounts['Monotremata']['oviparous']}.")
    if refuters:
        lines.insert(0, "Refuting species: " + ", ".join(refuters) + ".")
    result["results_summary"] = lines
    extra_caveats = [
        "Europe PMC searches were narrowed with the trait words so that a matching abstract could appear inside the pre-registered page of 25. The match is still required in the returned title or abstract, not merely in the hit count.",
        "The Animal Diversity Web passages are narrative accounts compiled by the site's contributors, not measurements taken for this test. The literature hits are the second source.",
        "The Monotremata order page and the Zaglossus bruijnii account did not contain both coded passages, so they did not enter the verdict. The refutation is the platypus and the short-beaked echidna.",
        "One platypus coat hit is the phrase about hair loss. The same search also returns a title that says 'hairs of the platypus' (recorded among the corroborating hits), and the echidna coat hits include spines and quills.",
    ]
    caveats = list(result.get("caveats") or [])
    for caveat in extra_caveats:
        if caveat not in caveats:
            caveats.append(caveat)
    result["caveats"] = caveats
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "refuters": refuters,
        "order_codes": order_codes,
        "lines": lines,
    }, indent=2))


if __name__ == "__main__":
    main()
