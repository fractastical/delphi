#!/usr/bin/env python3
"""Life-cycle wording for a flea, a fly and a blister beetle on Animal Diversity Web."""
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
UA = {"User-Agent": "delphisci-claim-test/aristotle-ga01-16"}


class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"):
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
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{2,}", "\n", text)


def fetch(url):
    DATA.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", url)[-120:]
    dest = DATA / name
    final = url
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                final = r.geturl()
                dest.write_bytes(r.read())
        except Exception as exc:
            return {"url": url, "error": str(exc), "text": "", "final_url": url}
        time.sleep(0.3)
    raw = dest.read_bytes()
    return {
        "url": url,
        "final_url": final if dest.stat().st_size else url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "text": html_to_text(raw),
        "error": None,
    }


def has_phrase(text, phrase):
    return phrase.lower() in text.lower()


def is_account(page):
    if page.get("error") or "/classification/" in (page.get("final_url") or ""):
        return False
    low = page["text"].lower()
    return len(low) > 4000 and ("reproduction" in low or "life cycle" in low or "development" in low)


def code_kind(text, rules):
    low = text.lower()
    eggs = [p for p in rules["egg_phrases"] if has_phrase(low, p)]
    meta = [p for p in rules["metamorphosis_phrases"] if has_phrase(low, p)]
    stages = all(re.search(r"\b" + w + r"\b", low) for w in rules["stage_words"])
    spontaneous = [p for p in rules["spontaneous_phrases"] if has_phrase(low, p)]
    parental = bool(eggs) and (bool(meta) or stages)
    return {
        "parental": parental and not spontaneous,
        "spontaneous": bool(spontaneous) and not parental,
        "conflict": parental and bool(spontaneous),
        "egg_phrases": eggs,
        "metamorphosis_phrases": meta,
        "four_stages": stages,
        "spontaneous_phrases": spontaneous,
    }


def main():
    result = json.loads(RESULT.read_text())
    rules = result["rules"]
    files = []
    coded = {}
    for kind, urls in rules["kinds"].items():
        chosen = None
        attempts = []
        for url in urls:
            page = fetch(url)
            attempts.append({"url": url, "final_url": page.get("final_url"), "error": page.get("error"),
                             "byte_size": page.get("byte_size"), "account": is_account(page)})
            if page.get("sha256"):
                files.append({k: page[k] for k in ("url", "final_url", "retrieved_at", "byte_size", "sha256")})
            if is_account(page):
                chosen = page
                break
        if not chosen:
            coded[kind] = {"status": "no-account", "attempts": attempts}
            continue
        coded[kind] = {"status": "coded", "url": chosen["final_url"], "attempts": attempts, **code_kind(chosen["text"], rules)}
    parental_kinds = [k for k, v in coded.items() if v.get("parental")]
    spontaneous_kinds = [k for k, v in coded.items() if v.get("spontaneous")]
    conflict_kinds = [k for k, v in coded.items() if v.get("conflict")]
    if conflict_kinds and not parental_kinds and not spontaneous_kinds:
        verdict, reason, conf = "inconclusive", "other", rules["confidence_inconclusive"]
    elif parental_kinds and spontaneous_kinds:
        verdict, reason, conf = "mixed", None, rules["confidence_mixed"]
    elif parental_kinds:
        verdict, reason = "refutes", None
        conf = rules["confidence_refutes_two"] if "flea" in parental_kinds and "fly" in parental_kinds else rules["confidence_refutes_one"]
    elif len(spontaneous_kinds) >= 2:
        verdict, reason, conf = "supports", None, rules["confidence_supports"]
    else:
        verdict, reason, conf = "inconclusive", "data-unavailable", rules["confidence_inconclusive"]
    measured = {
        "value": len(parental_kinds),
        "unit": "named kinds whose account states a parental egg-to-adult cycle",
        "n": sum(1 for v in coded.values() if v.get("status") == "coded"),
        "extra": {
            "parental_kinds": parental_kinds,
            "spontaneous_kinds": spontaneous_kinds,
            "conflict_kinds": conflict_kinds,
            "kinds": coded,
        },
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
    result["measured"] = measured
    result["method"] = (
        "Fetched Animal Diversity Web accounts in the preregistered order, skipped classification stubs, "
        "and coded egg-laying, metamorphosis or the four life stages, and spontaneous-generation phrases."
    )
    result["results_summary"] = [
        f"Coded kinds: {measured['n']}. Parental: {parental_kinds}. Spontaneous: {spontaneous_kinds}.",
        f"Verdict {verdict}.",
    ]
    result["datasets"] = [{
        "id": "animal-diversity-web-life-cycles",
        "name": "Animal Diversity Web species accounts",
        "landing_url": "https://animaldiversity.org/",
        "doi": None,
        "version": None,
        "license": None,
        "files": files,
        "role": "life-cycle prose for a flea, a fly and a blister beetle",
    }]
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, parental_kinds, spontaneous_kinds)


if __name__ == "__main__":
    main()
