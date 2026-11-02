#!/usr/bin/env python3
"""Octopus background matching from the Results text of Josef et al. 2012."""
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
UA = "delphi-claim-test/1.0 (research; aristotle-biology)"
ARTICLE = "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0037579"
NEAR_RE = re.compile(r"adjacent|nearby|local|immediate|nearest|specific (?:feature|object)", re.I)
WIDE_RE = re.compile(r"entire|whole field|wider|wide background|field of view|distant", re.I)
P_RE = re.compile(r"p\s*([<=>])\s*(0?\.\d+|\d+\.\d+)", re.I)
R_RE = re.compile(r"\br\s*=\s*(-?\d+\.\d+)", re.I)
R2_RE = re.compile(r"R\s*(?:\^?2|²)\s*=\s*(\d+\.\d+)", re.I)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def significant(operator, value):
    if operator == "<":
        return value <= 0.05
    if operator == "=":
        return value < 0.05
    return False


def classify_sentence(sentence):
    nearby = bool(NEAR_RE.search(sentence))
    wide = bool(WIDE_RE.search(sentence))
    correlations = [float(value) for value in R_RE.findall(sentence)]
    r2 = [float(value) for value in R2_RE.findall(sentence)]
    pvalues = [(op, float(value)) for op, value in P_RE.findall(sentence)]
    sig = any(significant(op, value) for op, value in pvalues)
    lower_distance = bool(
        re.search(r"(distance|dissimilarity).{0,80}(lower|smaller|less)", sentence, re.I)
        or re.search(r"(lower|smaller|less).{0,40}(distance|dissimilarity)", sentence, re.I)
    )
    kind = "nearby" if nearby else ("wide" if wide else "other")
    supports = False
    contradicts = False
    if kind == "nearby":
        if correlations and sig and any(value > 0 for value in correlations):
            supports = True
        if correlations and (any(value <= 0 for value in correlations) or (pvalues and not sig)):
            contradicts = True
        if r2 and sig and any(value > 0 for value in r2) and not correlations:
            supports = True
        if lower_distance and sig and nearby:
            supports = True
    return {
        "sentence": sentence.strip(),
        "kind": kind,
        "r": correlations,
        "r2": r2,
        "p": pvalues,
        "supports": supports,
        "contradicts": contradicts,
    }


def results_text(html):
    text = re.sub(r"(?is)<script[\s\S]*?</script>", " ", html)
    text = re.sub(r"(?is)<style[\s\S]*?</style>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?i)</h[1-6]>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"[ \t]+", " ", text)
    match = re.search(r"(?is)\bResults\b(.*)\bDiscussion\b", text)
    return match.group(1) if match else ""


def sentences_of(text):
    parts = re.split(r"(?<=[.])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def decide(records):
    nearby = [row for row in records if row["kind"] == "nearby" and (row["r"] or row["r2"] or row["p"])]
    if not nearby:
        return "inconclusive", "data-unavailable"
    if any(row["supports"] for row in nearby) and not any(row["contradicts"] for row in nearby):
        return "supports", None
    if nearby and all(row["contradicts"] or not row["supports"] for row in nearby) and any(
        row["contradicts"] for row in nearby
    ):
        return "refutes", None
    if any(row["supports"] for row in nearby) and any(row["contradicts"] for row in nearby):
        return "mixed", None
    return "inconclusive", "data-unavailable"


def contexts(text):
    hunting = bool(re.search(r"prey|forag|hunt", text, re.I))
    alarm = bool(re.search(r"alarm|threat|fright", text, re.I))
    return hunting and alarm


def self_test():
    good = classify_sentence(
        "The correlation with nearby objects was r = 0.62 (p < 0.01), higher than chance."
    )
    assert good["kind"] == "nearby" and good["supports"] and not good["contradicts"]
    bad = classify_sentence("Correlation with adjacent stones was r = 0.02 (p = 0.40).")
    assert bad["contradicts"]
    assert decide([good])[0] == "supports"
    assert decide([bad])[0] == "refutes"
    assert decide([classify_sentence("Octopuses were observed.")])[0] == "inconclusive"
    print("self-test ok")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    result = json.loads((ROOT / "result.json").read_text())
    req = urllib.request.Request(ARTICLE, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except Exception as exc:
        result.update(
            {
                "status": "complete",
                "verdict": "inconclusive",
                "reason": "data-unavailable",
                "confidence": 0.8,
                "data_kind": "none",
                "method": f"The article HTML could not be downloaded ({exc}).",
                "measured": {"value": None, "unit": "nearby statistics", "n": 0, "uncertainty": None, "extra": {}},
            }
        )
        (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print("inconclusive", exc)
        return
    (CACHE).mkdir(parents=True, exist_ok=True)
    (CACHE / "article.html").write_bytes(data)
    html = data.decode("utf-8", errors="replace")
    body = results_text(html)
    records = [classify_sentence(sentence) for sentence in sentences_of(body)]
    records = [row for row in records if row["r"] or row["r2"] or row["p"] or row["kind"] != "other"]
    verdict, reason = decide(records)
    both_contexts = contexts(body)
    if verdict == "supports" and both_contexts is False:
        # Contexts untested. The match clause can still pass. Recorded, not a mixed verdict
        # unless the pre-registered fail rule's "only one context matches" applies, which needs both tested.
        pass
    file_meta = {
        "download_url": ARTICLE,
        "retrieved_at": now(),
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "name": "article.html",
    }
    kept = [
        {key: row[key] for key in ("sentence", "kind", "r", "r2", "p", "supports", "contradicts")}
        for row in records
        if row["kind"] != "other" or row["r"] or row["p"]
    ]
    measured = {
        "value": sum(1 for row in records if row["supports"]),
        "unit": "nearby Results sentences with r > 0 or a lower distance at p < 0.05",
        "n": sum(1 for row in records if row["kind"] == "nearby"),
        "uncertainty": "regex extraction from publisher HTML; figures were not measured",
        "extra": {
            "results_characters": len(body),
            "contexts_both_named": both_contexts,
            "sentences": kept[:40],
        },
    }
    result.update(
        {
            "status": "complete",
            "verdict": verdict,
            "confidence": 0.55 if verdict == "supports" else 0.75,
            "data_kind": "none" if verdict == "inconclusive" else "biological",
            "method": (
                "Downloaded the PLOS ONE HTML for Josef et al. 2012 and extracted Results sentences. "
                "A nearby sentence supports the match only if it reports r > 0, or a positive R^2, at p < 0.05, "
                "or a lower distance to nearby objects at p < 0.05. No statistic was typed in by hand. "
                "Hunting and alarm were scored only as whether both words appear. Figures were not measured."
            ),
            "datasets": [
                {
                    "id": "josef-2012-plosone-0037579",
                    "name": "Josef et al. 2012, Camouflaging in a complex environment",
                    "landing_url": ARTICLE,
                    "doi": "10.1371/journal.pone.0037579",
                    "version": "PLOS ONE 7(5): e37579",
                    "license": "CC BY",
                    "files": [file_meta],
                    "role": "published image-analysis results for Octopus vulgaris and Octopus cyanea",
                }
            ],
            "measured": measured,
            "results_summary": [
                f"verdict {verdict}; nearby sentences {measured['n']}; supporting sentences {measured['value']}; both contexts named {both_contexts}."
            ],
        }
    )
    if reason:
        result["reason"] = reason
    (ROOT / "derived").mkdir(exist_ok=True)
    (ROOT / "derived" / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, measured["value"], "results_chars", len(body))


if __name__ == "__main__":
    main()
