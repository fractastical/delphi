#!/usr/bin/env python3
"""Horns, upper incisors, stomach chambers and cud-chewing in twelve ungulate accounts."""
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
UA = {"User-Agent": "delphisci-claim-test/aristotle-ha02-24"}


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
    text = unescape("".join(parser.parts))
    return re.sub(r"[ \t]+", " ", text)


def fetch(url):
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / (re.sub(r"[^A-Za-z0-9._-]+", "_", url)[-100:])
    final = url
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                final = r.geturl()
                dest.write_bytes(r.read())
        except Exception as exc:
            return {"url": url, "error": str(exc), "text": "", "final_url": url}
        time.sleep(0.25)
    raw = dest.read_bytes()
    text = html_to_text(raw)
    account = "/classification/" not in final and len(text) > 4000
    return {
        "url": url,
        "final_url": final,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "text": text if account else "",
        "account": account,
        "error": None,
    }


def subject_clause(sentence, split_re):
    s = sentence.strip()
    m = re.match(r"(?i)^(unlike|whereas|compared with|compared to)\b[^,]{0,120},\s*(.*)$", s)
    if m and m.group(2).strip():
        return m.group(2)
    return split_re.split(s, maxsplit=1)[0]


def phrase_in(text, phrase):
    if " " in phrase or "-" in phrase:
        return phrase.lower() in text.lower()
    return re.search(r"\b" + re.escape(phrase) + r"\b", text, re.I) is not None


def code_trait(text, spec, split_re):
    found = []
    evidence = []
    for bit in re.split(r"[\n.!;]+", text):
        subject = subject_clause(bit, split_re).strip()
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
            evidence.append({"label": hits[0], "sentence": subject[:240]})
        elif spec["mode"] == "exclusive" and len(hits) == 1:
            found.append(hits[0])
            evidence.append({"label": hits[0], "sentence": subject[:240]})
        elif spec["mode"] == "exclusive" and len(hits) > 1:
            found.append("conflict")
    labels = set(found)
    if not labels:
        return None, []
    if len(labels) == 1:
        return labels.pop(), evidence[:3]
    return "conflict", evidence[:3]


def combine(species_label, family_label):
    if species_label in (None, "conflict") and family_label in (None, "conflict"):
        return species_label or family_label, "none" if species_label is None else "conflict"
    if species_label not in (None, "conflict"):
        if family_label not in (None, "conflict", species_label):
            return "conflict", "species-family-disagree"
        return species_label, "species"
    return family_label, "family"


def antecedent(row):
    return row["horns"] in ("paired", "single") and row["upper_incisors"] == "absent"


def complete(row):
    return all(row[k] not in (None, "conflict") for k in ("horns", "upper_incisors", "chambers", "ruminates"))


def main():
    result = json.loads(RESULT.read_text())
    rules = result["rules"]
    split_re = re.compile(rules["contrast_split"])
    files = []
    pages = {}
    for family in rules["families"]:
        url = f"https://animaldiversity.org/accounts/{family}/"
        page = fetch(url)
        pages[family] = page
        if page.get("sha256"):
            files.append({k: page[k] for k in ("url", "final_url", "retrieved_at", "byte_size", "sha256")})
    rows = []
    for sp in rules["species"]:
        url = "https://animaldiversity.org/accounts/" + sp["name"].replace(" ", "_") + "/"
        page = fetch(url)
        if page.get("sha256"):
            files.append({k: page[k] for k in ("url", "final_url", "retrieved_at", "byte_size", "sha256")})
        family_page = pages.get(sp["family"], {})
        coded = {"name": sp["name"], "family": sp["family"], "sources": {}}
        for trait, spec in rules["traits"].items():
            s_label, s_ev = code_trait(page.get("text") or "", spec, split_re)
            f_label, f_ev = code_trait(family_page.get("text") or "", spec, split_re)
            label, source = combine(s_label, f_label)
            coded[trait] = label
            coded["sources"][trait] = {"value": label, "from": source, "evidence": (s_ev or f_ev)[:2]}
        rows.append(coded)
    counter = []
    matches = []
    for row in rows:
        if not complete(row):
            continue
        ant = antecedent(row)
        match = ant and row["chambers"] == "4" and row["ruminates"] == "yes"
        if match:
            matches.append(row["name"])
        if ant and (row["chambers"] != "4" or row["ruminates"] != "yes"):
            counter.append({"name": row["name"], "kind": "conditional"})
        if row["ruminates"] == "yes" and not (ant and row["chambers"] == "4"):
            counter.append({"name": row["name"], "kind": "identity"})
    families_matched = {next(s["family"] for s in rules["species"] if s["name"] == n) for n in matches}
    camel_complete = any(complete(r) and r["family"] == "Camelidae" for r in rows)
    negative = any(complete(r) and not antecedent(r) and r["ruminates"] == "no" for r in rows)
    bovid = "Bovidae" in families_matched
    cervid = "Cervidae" in families_matched
    if counter:
        verdict, reason, conf = "refutes", None, rules["confidence_refutes"]
    elif len(matches) >= rules["min_matches"] and bovid and cervid and camel_complete and negative:
        verdict, reason, conf = "supports", None, rules["confidence_supports"]
    elif not any(r.get("account") for r in pages.values()):
        verdict, reason, conf = "inconclusive", "data-unavailable", rules["confidence_inconclusive"]
    else:
        verdict, reason, conf = "inconclusive", "underpowered", rules["confidence_inconclusive"]
    measured = {
        "value": len(matches),
        "unit": "fully coded species that are horned, lack upper incisors, have four chambers and chew the cud",
        "n": sum(1 for r in rows if complete(r)),
        "extra": {
            "matches": matches,
            "counterexamples": counter,
            "camelid_complete": camel_complete,
            "negative_control": negative,
            "species": [{k: r[k] for k in ("name", "family", "horns", "upper_incisors", "chambers", "ruminates")} for r in rows],
        },
    }
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({"rows": rows, "measured": measured}, indent=2, ensure_ascii=False) + "\n")
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = conf
    result["data_kind"] = "biological" if measured["n"] else "none"
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["measured"] = measured
    result["method"] = (
        "Fetched the pre-registered Animal Diversity Web species and family accounts, "
        "coded four traits from phrases in the subject clause of each sentence, "
        "filled a species gap from its family only when the family stated the trait, "
        "and applied the counterexample and minimum-set rules."
    )
    result["results_summary"] = [
        f"{r['name']}: horns {r['horns']}, incisors {r['upper_incisors']}, chambers {r['chambers']}, ruminates {r['ruminates']}"
        for r in rows
    ] + [f"Matches {matches}. Counterexamples {counter}. Verdict {verdict}."]
    result["datasets"] = [{
        "id": "animal-diversity-web-ungulate-accounts",
        "name": "Animal Diversity Web ungulate species and family accounts",
        "landing_url": "https://animaldiversity.org/",
        "doi": None,
        "version": None,
        "license": None,
        "files": files,
        "role": "wording of horns, incisors, stomach chambers and rumination",
    }]
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, "matches", matches, "counter", counter)


if __name__ == "__main__":
    main()
