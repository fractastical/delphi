#!/usr/bin/env python3
"""Horned versus cloven-hoofed and solid-hoofed mammals, family accounts plus the MDD checklist."""
import csv
import datetime as dt
import hashlib
import json
import re
import time
import urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/aristotle-ha02-03"}


class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(raw):
    parser = Extractor()
    parser.feed(raw.decode("utf-8", "replace"))
    return re.sub(r"[ \t]+", " ", unescape("".join(parser.parts)))


def download(url, dest):
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r:
            dest.write_bytes(r.read())
        time.sleep(0.2)
    raw = dest.read_bytes()
    return raw, {
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "md5": hashlib.md5(raw).hexdigest(),
    }


def subject_clause(sentence):
    s = sentence.strip()
    m = re.match(r"(?i)^(unlike|whereas|compared with|compared to)\b[^,]{0,120},\s*(.*)$", s)
    if m and m.group(2).strip():
        return m.group(2)
    return re.split(r"(?i)\b(?:unlike|whereas|compared with|compared to|in contrast to|rather than)\b", s, maxsplit=1)[0]


def phrase_in(text, phrase):
    if " " in phrase or "-" in phrase:
        return phrase.lower() in text.lower()
    return re.search(r"\b" + re.escape(phrase) + r"\b", text, re.I) is not None


def code_trait(text, spec):
    found = []
    evidence = []
    for bit in re.split(r"[\n.!;]+", text):
        subject = subject_clause(bit).strip()
        if len(subject) < 12:
            continue
        hits = []
        for label, phrases in spec["labels"]:
            if any(phrase_in(subject, p) for p in phrases):
                hits.append(label)
                if spec["mode"] == "priority":
                    break
        if spec["mode"] == "priority" and hits:
            found.append(hits[0])
            evidence.append(subject[:220])
        elif spec["mode"] == "exclusive" and len(hits) == 1:
            found.append(hits[0])
            evidence.append(subject[:220])
        elif spec["mode"] == "exclusive" and len(hits) > 1:
            found.append("conflict")
    labels = set(found)
    if len(labels) == 1:
        return labels.pop(), evidence[:2]
    if len(labels) > 1:
        return "conflict", evidence[:2]
    return None, []


def main():
    result = json.loads(RESULT.read_text())
    rules = result["rules"]
    exp = result["expected_files"][0]
    raw, meta = download(exp["download_url"], DATA / exp["name"])
    checksum_ok = meta["md5"] == exp["md5"] and meta["byte_size"] == exp["byte_size"]
    files = [meta]
    family_code = {}
    for family in rules["families"]:
        url = f"https://animaldiversity.org/accounts/{family}/"
        page_raw, page_meta = download(url, DATA / f"{family}.html")
        files.append(page_meta)
        text = html_to_text(page_raw)
        account = len(text) > 4000 and b"classification" not in page_raw[:80]
        hoof, hoof_ev = code_trait(text if account or len(text) > 4000 else "", rules["hoof"])
        horns, horn_ev = code_trait(text if len(text) > 4000 else "", rules["horns"])
        family_code[family] = {"hoof": hoof, "horns": horns, "hoof_evidence": hoof_ev, "horn_evidence": horn_ev, "chars": len(text)}
    extinct_values = {}
    counts = {f: {"extant": 0, "extinct": 0, "other": 0} for f in rules["families"]}
    total_rows = 0
    with (DATA / exp["name"]).open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            family = (row.get("family") or "").strip()
            flag = (row.get("extinct") or "").strip()
            extinct_values[flag] = extinct_values.get(flag, 0) + 1
            if family not in counts:
                continue
            if flag == rules["extant_code"]:
                counts[family]["extant"] += 1
            elif flag == rules["extinct_code"]:
                counts[family]["extinct"] += 1
            else:
                counts[family]["other"] += 1
    bad_flags = sum(n for flag, n in extinct_values.items() if flag not in (rules["extant_code"], rules["extinct_code"]))
    unrecognized = bad_flags / total_rows if total_rows else 1
    horned = []
    for family, code in family_code.items():
        if code["horns"] in ("paired", "single"):
            horned.append(family)
    n_horned = sum(counts[f]["extant"] for f in horned)
    n_cloven = sum(counts[f]["extant"] for f in horned if family_code[f]["hoof"] == "cloven")
    proportion = (n_cloven / n_horned) if n_horned else None
    solid_horned = [f for f, c in family_code.items() if c["hoof"] == "solid" and c["horns"] in ("paired", "single")]
    equidae = family_code.get("Equidae", {})
    universal_ok = equidae.get("hoof") == "solid" and equidae.get("horns") == "absent" and not solid_horned
    missing = [f for f in rules["decisive_families"] if family_code[f]["hoof"] in (None, "conflict") or family_code[f]["horns"] in (None, "conflict")]
    if not checksum_ok or unrecognized > rules["unrecognized_limit"]:
        verdict, reason, conf = "inconclusive", "data-unavailable", rules["confidence_inconclusive"]
    elif missing:
        verdict, reason, conf = "inconclusive", "underpowered", rules["confidence_inconclusive"]
    elif solid_horned or (proportion is not None and proportion <= rules["bare_majority_gt"]):
        verdict, reason, conf = "refutes", None, rules["confidence_refutes"]
    elif proportion is not None and proportion > rules["majority_gt"] and universal_ok:
        verdict, reason, conf = "supports", None, rules["confidence_supports"]
    elif proportion is not None and proportion > rules["bare_majority_gt"] and universal_ok:
        verdict, reason, conf = "mixed", None, rules["confidence_mixed"]
    else:
        verdict, reason, conf = "inconclusive", "underpowered", rules["confidence_inconclusive"]
    measured = {
        "value": None if proportion is None else round(proportion, 4),
        "unit": "share of extant species in horned panel families that are in cloven-hoofed families",
        "n": n_horned,
        "extra": {
            "checksum_ok": checksum_ok,
            "n_cloven_horned": n_cloven,
            "universal_ok": universal_ok,
            "solid_and_horned_families": solid_horned,
            "missing_decisive_families": missing,
            "extinct_value_counts": extinct_values,
            "family_counts": counts,
            "family_codes": {f: {"hoof": c["hoof"], "horns": c["horns"]} for f, c in family_code.items()},
        },
    }
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({"measured": measured, "evidence": family_code}, indent=2, ensure_ascii=False) + "\n")
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = conf
    result["data_kind"] = "biological" if checksum_ok and any(c["chars"] > 4000 for c in family_code.values()) else "none"
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["measured"] = measured
    result["method"] = (
        "Downloaded Mammal Diversity Database v1.13 and checked its md5 and size. "
        "Counted extant species (extinct flag 0) in eight families. "
        "Coded hoof and horns from each Animal Diversity Web family account with the preregistered phrases, "
        "dropping contrast clauses, and applied the 2/3 and solid-hoof rules."
    )
    result["results_summary"] = [
        f"{f}: hoof {c['hoof']}, horns {c['horns']}, extant {counts[f]['extant']}" for f, c in family_code.items()
    ] + [f"Proportion {proportion}. Universal {universal_ok}. Verdict {verdict}."]
    result["datasets"] = [
        {
            "id": "mdd-v1.13-zenodo-12738010",
            "name": "Mammal Diversity Database v1.13",
            "landing_url": exp["landing_url"],
            "doi": exp["doi"],
            "version": "1.13",
            "license": exp["license"],
            "files": [meta],
            "role": "extant species counts by family",
        },
        {
            "id": "animal-diversity-web-family-accounts",
            "name": "Animal Diversity Web family accounts",
            "landing_url": "https://animaldiversity.org/",
            "doi": None,
            "version": None,
            "license": None,
            "files": files[1:],
            "role": "family-level hoof and horn wording",
        },
    ]
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, proportion, "missing", missing, "solid_horned", solid_horned)


if __name__ == "__main__":
    main()
