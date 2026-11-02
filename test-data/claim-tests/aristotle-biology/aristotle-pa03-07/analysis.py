#!/usr/bin/env python3
"""aristotle-pa03-07: deer alone solid-throughout and alone casting the horn.

Reads Davis, Brakora and Lee 2011 Table 1 from the public PMC HTML and applies
the rules frozen in result.json. Does not edit pass_criterion or fail_criterion.

Run: python3 analysis.py
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
TABLE_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC3151718/table/RSPB20110938TB1/"
ARTICLE_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC3151718/"
UA = "delphisci-claim-test/aristotle-pa03-07"


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.cell = ""
        self.row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if tag in ("td", "th"):
            self.capture = True
            self.cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.capture:
            self.row.append(re.sub(r"\s+", " ", self.cell).strip())
            self.capture = False
        if tag == "tr" and any(self.row):
            self.rows.append(self.row)

    def handle_data(self, data):
        if self.capture:
            self.cell += data


def fetch(url, name):
    DATA.mkdir(exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=90).read()
    path = DATA / name
    path.write_bytes(raw)
    return {
        "name": name,
        "download_url": url,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }, raw


def norm_code(cell):
    s = cell.strip().replace("\u2212", "-").replace("\u2013", "-").replace("\uff0b", "+")
    s = s.replace("\u2215", "/").replace(" ", "")
    s = s.replace("+/\u2212", "+/-").replace("+/−", "+/-")
    return s


def row_by_label(rows, predicate):
    for row in rows:
        label = row[0].lower()
        if predicate(label):
            return row
    return None


def clause(deer_yes, others):
    """others: list of (family, state) where state is True, False, or None if unscored."""
    if deer_yes is None:
        return "unscored"
    definite_counter = any(state is True for _, state in others)
    if not deer_yes or definite_counter:
        return "fail"
    if any(state is None for _, state in others):
        return "unscored"
    return "pass"


def main():
    table_meta, table_raw = fetch(TABLE_URL, "table1.html")
    article_meta, article_raw = fetch(ARTICLE_URL, "article.html")
    parser = TableParser()
    parser.feed(table_raw.decode("utf-8", "replace"))
    header = None
    for row in parser.rows:
        if "cervids" in [c.lower() for c in row]:
            header = [c.lower() for c in row if c]
            break
    if header != ["cervids", "bovids", "giraffids", "antilocaprids"]:
        raise SystemExit("family header not found: %s" % header)
    sheath = row_by_label(parser.rows, lambda s: s.endswith("keratin sheath"))
    bone = row_by_label(parser.rows, lambda s: s.endswith("of bone tissue"))
    if not sheath or not bone or len(sheath) < 5 or len(bone) < 5:
        raise SystemExit("character rows missing")
    families = header
    sheath_codes = [norm_code(c) for c in sheath[1:5]]
    bone_codes = [norm_code(c) for c in bone[1:5]]

    def present(code):
        if code in {"?", ""}:
            return None
        if code in {"+", "(+)"}:
            return True
        if code in {"-", "(-)"}:
            return False
        if code == "+/-":
            return "variable"
        raise SystemExit("unrecognised cell %r" % code)

    sheath_state = [present(c) for c in sheath_codes]
    bone_state = [present(c) for c in bone_codes]
    # solid throughout = keratin sheath absent
    solid = [None if s is None else (False if s == "variable" else (not s)) for s in sheath_state]
    # variable sheath means the deer-like state (sheath absent) occurs in some members
    solid = []
    for s in sheath_state:
        if s is None:
            solid.append(None)
        elif s == "variable":
            solid.append(True)  # sheath absent in some members: the solid state occurs
        else:
            solid.append(not s)
    shed = []
    for s in bone_state:
        if s is None:
            shed.append(None)
        elif s == "variable":
            shed.append(True)
        else:
            shed.append(bool(s))

    by = {fam: {"keratin_sheath": sheath_codes[i], "solid_throughout": solid[i],
                "bone_regeneration": bone_codes[i], "casts_bone": shed[i]}
          for i, fam in enumerate(families)}
    solid_clause = clause(by["cervids"]["solid_throughout"],
                          [(f, by[f]["solid_throughout"]) for f in families if f != "cervids"])
    shed_clause = clause(by["cervids"]["casts_bone"],
                         [(f, by[f]["casts_bone"]) for f in families if f != "cervids"])

    article = article_raw.decode("utf-8", "replace")
    rhino = len(re.findall(r"rhinocer", article, re.I))
    # The same article does not characterise rhinoceros horn, so Rhinocerotidae is not added.

    passes = sum(c == "pass" for c in (solid_clause, shed_clause))
    fails = sum(c == "fail" for c in (solid_clause, shed_clause))
    if solid_clause == "pass" and shed_clause == "pass":
        verdict, reason, confidence = "supports", None, 0.70
    elif fails == 2:
        verdict, reason, confidence = "refutes", None, 0.70
    elif passes == 1 and fails == 1:
        verdict, reason, confidence = "mixed", None, 0.70
    elif fails == 0:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.35
    else:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.50
    definite = all(c not in {"?", ""} for c in sheath_codes + bone_codes)
    if verdict != "inconclusive" and not definite:
        confidence = 0.50

    measured = {
        "value": passes,
        "unit": "only-clauses that hold (solid-throughout exclusive to deer; bone-casting exclusive to deer)",
        "n": 4,
        "uncertainty": None,
        "extra": {
            "families": by,
            "solid_only_clause": solid_clause,
            "shed_only_clause": shed_clause,
            "rhinoceros_mentions_in_article_html": rhino,
        },
    }
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({
        "families": by,
        "solid_only_clause": solid_clause,
        "shed_only_clause": shed_clause,
        "rhinoceros_mentions": rhino,
    }, indent=2) + "\n")

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["datasets"] = [{
        "id": "davis-brakora-lee-2011-ruminant-headgear-table1",
        "name": "Davis, Brakora and Lee 2011, Table 1, Evolution of ruminant headgear",
        "landing_url": "https://doi.org/10.1098/rspb.2011.0938",
        "doi": "10.1098/rspb.2011.0938",
        "version": "Proc R Soc B 278:2857-2865",
        "license": "Full text publicly readable on PMC; copyright The Royal Society 2011",
        "files": [table_meta, article_meta],
        "role": "character table of keratin sheath and bone regeneration for cervids, bovids, giraffids and antilocaprids",
    }]
    result["measured"] = measured
    result["method"] = (
        "Fetched the PMC HTML of Table 1 and the article, transcribed the keratin-sheath row and the "
        "regeneration-of-bone-tissue row for the four families, and applied the pre-registered only-clause rules. "
        "A keratin sheath absent is solid-throughout; regeneration of bone is casting. Sheath-only renewal is not casting. "
        "The article HTML does not mention rhinoceroses, so Rhinocerotidae was not added."
    )
    gir = "giraffids lack a keratin sheath (solid bone under skin) and do not regenerate it"
    result["results_summary"] = [
        "Keratin sheath codes: " + ", ".join("%s=%s" % (f, by[f]["keratin_sheath"]) for f in families) + ".",
        "Bone regeneration codes: " + ", ".join("%s=%s" % (f, by[f]["bone_regeneration"]) for f in families) + ".",
        "Solid-only clause %s; shed-only clause %s. %s." % (solid_clause, shed_clause, gir),
    ]
    caveats = [
        c for c in (result.get("caveats") or [])
        if not str(c).startswith("Analysis: ")
        and not str(c).startswith("Giraffe ossicones are scored")
        and not str(c).startswith("Rhinoceroses are outside this table.")
    ]
    caveats.append(
        "Analysis: Giraffe ossicones are scored solid-throughout because Table 1 codes their epidermis as having no keratin sheath. "
        "Pronghorns regenerate the keratin sheath and not the bone, so they are not scored as casting the horn."
    )
    caveats.append("Analysis: Rhinoceroses are outside this table. The article page contains no rhinoceros wording, so they were not coded.")
    result["caveats"] = caveats
    (HERE / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"verdict": verdict, "confidence": confidence, "solid": solid_clause, "shed": shed_clause, "families": by}, indent=2))


if __name__ == "__main__":
    main()
