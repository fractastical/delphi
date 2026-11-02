#!/usr/bin/env python3
"""Arm number and sucker rows for six cephalopods, from FAO, ADW and SeaLifeBase."""
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
UA = {"User-Agent": "delphisci-claim-test/aristotle-ha04-01"}


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


def file_meta(url, dest, raw):
    return {
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def download(url, dest):
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=180) as r:
            dest.write_bytes(r.read())
        time.sleep(0.2)
    raw = dest.read_bytes()
    return raw, file_meta(url, dest, raw)


def subject_clause(sentence):
    s = sentence.strip()
    m = re.match(r"(?i)^(unlike|whereas|compared with|compared to)\b[^,]{0,120},\s*(.*)$", s)
    if m and m.group(2).strip():
        return m.group(2)
    parts = re.split(r"(?i)\b(?:unlike|whereas|compared with|compared to|in contrast to|rather than)\b", s, maxsplit=1)
    return parts[0]


def phrase_in(text, phrase):
    if " " in phrase or "-" in phrase:
        return phrase.lower() in text.lower()
    return re.search(r"\b" + re.escape(phrase) + r"\b", text, re.I) is not None


def code_arms(text):
    found = set()
    for sentence in re.split(r"[\n.!;]+", text):
        subject = subject_clause(sentence)
        low = subject.lower()
        if re.search(r"\b(?:eight|8)\s+arms?\b", low) or re.search(r"\barms?\s*[:\-]?\s*(?:eight|8)\b", low):
            found.add(8)
        if re.search(r"\b(?:ten|10)\s+arms?\b", low) or re.search(r"\barms?\s*[:\-]?\s*(?:ten|10)\b", low):
            found.add(10)
    if len(found) == 1:
        return found.pop()
    if len(found) > 1:
        return "conflict"
    return None


def code_rows(text, rules):
    found = set()
    evidence = []
    for sentence in re.split(r"[\n.!;]+", text):
        subject = subject_clause(sentence)
        one = any(phrase_in(subject, p) for p in rules["one_row_phrases"])
        two = any(phrase_in(subject, p) for p in rules["two_row_phrases"])
        if one and not two:
            found.add(1)
            evidence.append(subject.strip()[:240])
        elif two and not one:
            found.add(2)
            evidence.append(subject.strip()[:240])
        elif one and two:
            found.add("conflict")
    if "conflict" in found or len(found) > 1:
        return "conflict", evidence[:3]
    if len(found) == 1:
        return found.pop(), evidence[:3]
    return None, []


def windows(text, aliases):
    low = text.lower()
    coded_at = 0
    out = []
    for alias in aliases:
        start = 0
        a = alias.lower()
        hits = 0
        while hits < 40:
            i = low.find(a, start)
            if i < 0:
                break
            hits += 1
            chunk = text[max(0, i - 180):i + 3200]
            out.append(chunk)
            start = i + len(a)
            if len(out) >= 50:
                return out
    return out


def merge(values):
    clean = [v for v in values if v not in (None, "conflict")]
    if any(v == "conflict" for v in values) and len(set(clean)) != 1:
        return "conflict"
    uniq = set(clean)
    if len(uniq) == 1:
        return uniq.pop()
    if len(uniq) > 1:
        return "conflict"
    return None


def load_pdf(key, spec):
    from pypdf import PdfReader
    dest = DATA / f"{key}.pdf"
    raw, meta = download(spec["url"], dest)
    reader = PdfReader(dest)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text = "\n".join(pages)
    low = text.lower()
    ok = all(token in low for token in spec["must_contain"]) and len(text) > 5000
    return text if ok else "", meta | {"accepted": ok, "chars": len(text)}


def load_html(url):
    dest = DATA / (re.sub(r"[^A-Za-z0-9._-]+", "_", url)[-80:])
    try:
        raw, meta = download(url, dest)
    except Exception as exc:
        return "", {"download_url": url, "error": str(exc), "accepted": False}
    if b"/classification/" in raw[:500] or b"classification" in raw[:200]:
        # final pages saved after redirect still contain the classification path in links;
        # reject only very short accounts below.
        pass
    text = html_to_text(raw)
    accepted = len(text) > 2500 and "/classification/" not in url
    # A redirect target is not visible in the saved bytes. Reject stubs by length.
    if len(text) < 2500:
        accepted = False
    return (text if accepted else ""), meta | {"accepted": accepted, "chars": len(text)}


def main():
    result = json.loads(RESULT.read_text())
    rules = result["rules"]
    files = []
    pdf_text = {}
    for key, spec in rules["sources"].items():
        try:
            text, meta = load_pdf(key, spec)
        except Exception as exc:
            text, meta = "", {"download_url": spec["url"], "error": str(exc), "accepted": False}
        pdf_text[key] = text
        files.append(meta)
    coded = []
    for sp in rules["species"]:
        chunks = []
        sources_used = []
        for key in sp["pdf"]:
            if pdf_text.get(key):
                chunks.extend(windows(pdf_text[key], sp["aliases"]))
                sources_used.append(key)
        for slot in ("adw", "slb"):
            url = sp.get(slot)
            if not url:
                continue
            text, meta = load_html(url)
            files.append(meta)
            if text:
                chunks.extend(windows(text, sp["aliases"]))
                sources_used.append(slot)
        arm_vals = []
        row_vals = []
        evidence = []
        kept = 0
        for chunk in chunks:
            arms = code_arms(chunk)
            rows, ev = code_rows(chunk, rules)
            if arms is None and rows is None:
                continue
            arm_vals.append(arms)
            row_vals.append(rows)
            evidence.extend(ev)
            kept += 1
            if kept >= 12:
                break
        coded.append({
            "name": sp["name"],
            "group": sp["group"],
            "sources": sources_used,
            "windows_coded": kept,
            "arms": merge(arm_vals),
            "sucker_rows": merge(row_vals),
            "evidence": evidence[:4],
        })
    def arms_of(row):
        return row["arms"]
    def rows_of(row):
        return row["sucker_rows"]
    bad_arms = [r["name"] for r in coded if isinstance(arms_of(r), int) and arms_of(r) != 8]
    row_exceptions = [r for r in coded if rows_of(r) not in (None, "conflict", 2)]
    non_octopus_exc = [r["name"] for r in row_exceptions if r["group"] != "octopus"]
    eledone = [r for r in coded if r["name"].startswith("Eledone")]
    both_eledone_coded = all(r["sucker_rows"] not in (None, "conflict") and r["arms"] not in (None, "conflict") for r in eledone)
    sucker_coded = [r for r in coded if r["sucker_rows"] in (1, 2)]
    no_exception = both_eledone_coded and sucker_coded and all(r["sucker_rows"] == 2 for r in sucker_coded)
    vulgaris = next(r for r in coded if r["name"] == "Octopus vulgaris")
    cuttle = [r for r in coded if r["group"] == "cuttlefish" and r["arms"] == 8 and r["sucker_rows"] in (1, 2)]
    squid = [r for r in coded if r["group"] == "squid" and r["arms"] == 8 and r["sucker_rows"] in (1, 2)]
    exactly_one = (
        vulgaris["arms"] == 8 and vulgaris["sucker_rows"] == 2
        and both_eledone_coded
        and len(cuttle) >= 1 and len(squid) >= 1
        and not bad_arms
        and len(row_exceptions) == 1
        and row_exceptions[0]["group"] == "octopus"
        and all(r["arms"] in (8, None) for r in coded)
        and all(r["arms"] != "conflict" and r["sucker_rows"] != "conflict" for r in coded)
    )
    if bad_arms:
        verdict, reason, conf = "refutes", None, rules["confidence_bad_arms"]
    elif len(row_exceptions) >= 2:
        verdict, reason, conf = "refutes", None, rules["confidence_two_exceptions"]
    elif non_octopus_exc:
        verdict, reason, conf = "refutes", None, rules["confidence_non_octopus_exception"]
    elif no_exception:
        verdict, reason, conf = "refutes", None, rules["confidence_no_exception"]
    elif exactly_one:
        verdict, reason, conf = "supports", None, rules["confidence_supports"]
    else:
        missing = [r["name"] for r in coded if r["arms"] in (None, "conflict") or r["sucker_rows"] in (None, "conflict")]
        verdict, reason, conf = "inconclusive", "data-unavailable" if len(missing) >= 4 else "underpowered", rules["confidence_inconclusive"]
    measured = {
        "value": len(row_exceptions),
        "unit": "coded species whose sucker-row count is not 2",
        "n": sum(1 for r in coded if r["arms"] in (8, 10) or r["sucker_rows"] in (1, 2)),
        "extra": {"species": coded, "bad_arms": bad_arms, "row_exceptions": [r["name"] for r in row_exceptions]},
    }
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2, ensure_ascii=False) + "\n")
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = conf
    result["data_kind"] = "biological" if measured["n"] else "none"
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    # Compact the species block in result.json; full evidence stays in derived.
    compact = [{k: r[k] for k in ("name", "group", "arms", "sucker_rows", "windows_coded", "sources")} for r in coded]
    result["measured"] = {
        "value": measured["value"],
        "unit": measured["unit"],
        "n": measured["n"],
        "extra": {"species": compact, "bad_arms": bad_arms, "row_exceptions": [r["name"] for r in row_exceptions]},
    }
    result["method"] = (
        "Downloaded the two FAO catalogue PDFs and the pre-registered HTML summaries, "
        "kept a PDF only if its text contained the preregistered title tokens, "
        "coded arm number and sucker-row phrases in windows around each binomial, "
        "and applied the pass and fail rules."
    )
    result["results_summary"] = [
        f"{r['name']}: arms {r['arms']}, sucker rows {r['sucker_rows']}" for r in coded
    ] + [f"Verdict {verdict}."]
    result["datasets"] = [
        {
            "id": "fao-cephalopods-catalogue",
            "name": "FAO Cephalopods of the World, volumes 2 and 3",
            "landing_url": "https://www.fao.org/4/i3489e/i3489e.pdf",
            "doi": None,
            "version": None,
            "license": None,
            "files": [f for f in files if str(f.get("download_url", "")).endswith(".pdf") or "i3489e" in str(f.get("download_url", "")) or "i1920e" in str(f.get("download_url", ""))],
            "role": "arm and sucker-row wording in species accounts",
        },
        {
            "id": "adw-and-sealifebase",
            "name": "Animal Diversity Web and SeaLifeBase species pages",
            "landing_url": "https://www.sealifebase.se/",
            "doi": None,
            "version": None,
            "license": None,
            "files": [f for f in files if "animaldiversity" in str(f.get("download_url", "")) or "sealifebase" in str(f.get("download_url", ""))],
            "role": "the same wording where a catalogue window was empty",
        },
    ]
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict)
    for r in coded:
        print(f"  {r['name']}: arms={r['arms']} rows={r['sucker_rows']} windows={r['windows_coded']}")


if __name__ == "__main__":
    main()
