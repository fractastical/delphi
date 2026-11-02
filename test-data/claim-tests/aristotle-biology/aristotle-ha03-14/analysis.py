#!/usr/bin/env python3
"""Test aristotle-ha03-14 against two open PMC reviews.

Re-run from this directory: python3 analysis.py
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

HEADGEAR_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC3151718/"
CAST_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC1571559/"
TYPES = ["antler", "bovid horn", "ossicone", "pronghorn"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def fetch(url):
    r = requests.get(url, timeout=120, headers={"User-Agent": "DelphiClaimTest/1.0"})
    r.raise_for_status()
    return r.content, r.headers.get("content-type", ""), r.url


def strip_html(html):
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def cell_text(cell):
    cell = re.sub(r"<[^>]+>", " ", cell)
    return re.sub(r"\s+", " ", cell).strip()


def parse_table(html):
    tables = re.findall(r"<table[\s\S]*?</table>", html, flags=re.I)
    if not tables:
        return []
    rows = []
    for tr in re.findall(r"<tr[\s\S]*?</tr>", tables[0], flags=re.I):
        cells = [cell_text(c) for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", tr, flags=re.I)]
        if cells:
            rows.append(cells)
    return rows


def row_by_label(rows, label):
    for cells in rows:
        if cells and cells[0].strip().lower() == label:
            return cells
    return None


def flag(cell):
    return cell.strip() in {"+", "(+)"}


def meta(html):
    def grab(name):
        m = re.search(rf'<meta[^>]+name="{name}"[^>]+content="([^"]+)"', html, re.I)
        if not m:
            m = re.search(rf'<meta[^>]+content="([^"]+)"[^>]+name="{name}"', html, re.I)
        return m.group(1) if m else None
    title = re.search(r"<title>([^<]+)</title>", html, re.I)
    doi = grab("citation_doi")
    lic = None
    for pat in (r"creative commons[^<.]{0,60}", r"CC BY(?:-NC)?(?:-ND|-SA)?(?: \d\.\d)?"):
        m = re.search(pat, html, re.I)
        if m:
            lic = re.sub(r"\s+", " ", m.group(0))
            break
    return {
        "title": re.sub(r"\s+", " ", title.group(1)).strip() if title else None,
        "doi": doi,
        "license": lic or "not stated as a Creative Commons grant in the retrieved HTML",
    }


def main():
    head_b, head_ct, head_final = fetch(HEADGEAR_URL)
    cast_b, cast_ct, cast_final = fetch(CAST_URL)
    open(os.path.join(DATA, "pmc3151718.html"), "wb").write(head_b)
    open(os.path.join(DATA, "pmc1571559.html"), "wb").write(cast_b)
    head_html = head_b.decode("utf-8", "replace")
    cast_html = cast_b.decode("utf-8", "replace")
    head_info = meta(head_html)
    cast_info = meta(cast_html)
    rows = parse_table(head_html)
    wanted = {
        "keratin sheath": row_by_label(rows, "keratin sheath"),
        "of bone": row_by_label(rows, "of bone"),
        "of sheath": row_by_label(rows, "of sheath"),
        "of bone tissue": row_by_label(rows, "of bone tissue"),
        "of integument": row_by_label(rows, "of integument"),
        "of keratin sheath": row_by_label(rows, "of keratin sheath"),
    }
    coded = []
    can_code = all(wanted[k] and len(wanted[k]) >= 5 for k in wanted)
    if can_code:
        for i, name in enumerate(TYPES, start=1):
            sheath = flag(wanted["keratin sheath"][i])
            bone_branch = flag(wanted["of bone"][i])
            sheath_branch = flag(wanted["of sheath"][i])
            regen_bone = flag(wanted["of bone tissue"][i])
            regen_integument = flag(wanted["of integument"][i])
            regen_sheath = flag(wanted["of keratin sheath"][i])
            # Solid throughout: the appendage is bone, not a keratin sheath over a core.
            solid = wanted["keratin sheath"][i].strip() in {"−", "-", "–"}
            branched = bone_branch or sheath_branch
            shed = regen_bone or regen_integument or regen_sheath
            coded.append({
                "type": name,
                "keratin_sheath": wanted["keratin sheath"][i],
                "bone_branching": wanted["of bone"][i],
                "sheath_branching": wanted["of sheath"][i],
                "regeneration_bone": wanted["of bone tissue"][i],
                "regeneration_integument": wanted["of integument"][i],
                "regeneration_keratin_sheath": wanted["of keratin sheath"][i],
                "solid_throughout": solid,
                "branched": branched,
                "solid_and_branched": solid and branched,
                "shed_or_annually_replaced": shed,
                "sheath_present_flag": sheath,
            })
    clause1 = None
    clause2 = None
    if coded:
        both = [c["type"] for c in coded if c["solid_and_branched"]]
        shed = [c["type"] for c in coded if c["shed_or_annually_replaced"]]
        clause1 = both == ["antler"]
        clause2 = shed == ["antler"]

    cast_text = strip_html(cast_html)
    sentences = re.split(r"(?<=[.])\s+", cast_text)
    castrat = [s for s in sentences if re.search(r"castrat", s, re.I)]
    fail_complete = any(re.search(r"velvet|do not fully minerali[sz]e|not fully minerali[sz]e|remain in velvet|aberrant", s, re.I) for s in castrat)
    ordinary = any(re.search(r"ordinary annual|normal annual (?:cycle|schedule)|cast and regrow hardened", s, re.I) for s in castrat)
    clause3 = True if (castrat and fail_complete and not ordinary) else (False if ordinary else None)

    if clause1 is False or clause2 is False or clause3 is False:
        verdict, reason = "refutes", None
    elif clause1 is None or clause2 is None or (clause1 and clause2 and clause3 is None):
        verdict, reason = "inconclusive", "data-unavailable"
    elif clause1 and clause2 and clause3:
        verdict, reason = "supports", None
    else:
        verdict, reason = "inconclusive", "other"

    confidence = 0.84 if can_code and castrat else 0.45
    measured = {
        "value": sum(1 for flag_ in (clause1, clause2, clause3) if flag_ is True),
        "unit": "clauses coded as passing (solid-and-branched unique to antler; shedding unique to antler; castration stops the normal hardened cycle)",
        "n": 4,
        "uncertainty": "Table 1 cells coded + versus minus; castration from sentences containing castrat",
        "extra": {
            "types": coded,
            "clause_solid_and_branched_only_antler": clause1,
            "clause_shedding_only_antler": clause2,
            "clause_castration_stops_normal_hardened_cycle": clause3,
            "castration_sentences": castrat[:20],
            "castration_fail_to_complete_phrase": fail_complete,
            "castration_ordinary_schedule_phrase": ordinary,
            "table_rows_found": {k: bool(v) for k, v in wanted.items()},
            "verdict_by_rule": verdict,
        },
    }
    result = json.load(open(os.path.join(HERE, "result.json")))
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["confidence"] = confidence
    result["datasets"] = [
        {
            "id": "pmc3151718-ruminant-headgear",
            "name": head_info["title"],
            "landing_url": HEADGEAR_URL,
            "doi": head_info["doi"],
            "version": "PMC3151718",
            "license": head_info["license"],
            "files": [{"download_url": HEADGEAR_URL, "retrieved_at": now(), "byte_size": len(head_b), "sha256": sha256(head_b), "content_type": head_ct, "final_url": head_final}],
            "role": "comparative table of extant ruminant headgear",
        },
        {
            "id": "pmc1571559-deer-antlers",
            "name": cast_info["title"],
            "landing_url": CAST_URL,
            "doi": cast_info["doi"],
            "version": "PMC1571559",
            "license": cast_info["license"],
            "files": [{"download_url": CAST_URL, "retrieved_at": now(), "byte_size": len(cast_b), "sha256": sha256(cast_b), "content_type": cast_ct, "final_url": cast_final}],
            "role": "castration and the antler cycle",
        },
    ]
    result["method"] = (
        "Table 1 of the headgear review was read from the PMC HTML. "
        "Solid-throughout means the keratin-sheath cell is minus. Branched means bone or sheath branching is plus. "
        "Shed or annually replaced means regeneration of bone, integument, or the keratin sheath is plus. "
        "Castration sentences are those containing 'castrat' in the antler review. "
        "A failed clause refutes the conjunction."
    )
    result["measured"] = measured
    result["caveats"] = [
        "An annually replaced keratin sheath counts as shedding, which is the pre-registered reading. The pronghorn sheath is that case.",
        "Stag and deer are read as cervids, the antler column, not as one species.",
        "The castration clause uses the sentences in PMC1571559. It does not add a second experiment.",
    ]
    with open(os.path.join(HERE, "result.json"), "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    summary = {k: measured["extra"][k] for k in (
        "clause_solid_and_branched_only_antler", "clause_shedding_only_antler", "clause_castration_stops_normal_hardened_cycle"
    )}
    print(json.dumps({"verdict": verdict, "reason": reason, **summary, "types": coded}, indent=2))


if __name__ == "__main__":
    main()
