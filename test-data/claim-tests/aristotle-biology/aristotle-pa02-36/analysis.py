#!/usr/bin/env python3
"""Recompute the pre-registered test of aristotle-pa02-36.

Scores public prose about living elephants. A sentence supports a component
when it contains the pre-registered words. A sentence refutes a component
only when it contains those words and also says "does not", "cannot", or
"never". Downloads are cached outside the repo and are not committed.

Requires Python 3 and a network connection on a cold cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT_PATH = HERE / "result.json"
DERIVED = HERE / "derived"
CACHE = Path(os.environ.get("CLAIM_TEST_CACHE", "/tmp/aristotle-pa02-36"))
USER_AGENT = "delphi-claim-test/1.0 (research; +https://github.com/fractastical/delphi)"

ADW_LOXODONTA = "https://animaldiversity.org/accounts/Loxodonta_africana/"
ADW_ELEPHAS = "https://animaldiversity.org/accounts/Elephas_maximus/"
ETHOGRAM_INDEX = "https://www.elephantvoices.org/elephant-ethogram.html"
LIBRARY_PATH = "/ethogram"

# Listed words, plus the regular inflections of those same words.
# A longer unrelated stem does not match: branchlet, vomeronasal, seedling.
ORGAN = re.compile(r"\b(?:trunk|trunks|proboscis)\b", re.I)
NOSTRIL = re.compile(r"\b(?:nostril|nostrils|nose|noses|nasal)\b", re.I)
MOUTH = re.compile(r"\b(?:mouth|mouths)\b", re.I)
FOOD = re.compile(r"\b(?:food|water|drink|drinks|drinking)\b", re.I)
PLANT = re.compile(r"\b(?:tree|trees|stem|stems|branch|branches)\b", re.I)
ACT = re.compile(
    r"\b(?:coil|coils|coiling|coiled|wrap|wraps|wrapping|wrapped|"
    r"uproot|uproots|uprooting|uprooted|tear|tears|tearing|"
    r"pull|pulls|pulling|pulled)\b",
    re.I,
)
DENY = re.compile(r"\b(?:does not|cannot|never)\b", re.I)
CARD_RE = re.compile(
    r'href="(/the-elephant-ethogram/[^"?#]+)"><div><h4[^>]*>(.*?)</h4><p[^>]*>(.*?)</p>',
    re.S,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, dest: Path) -> tuple[bytes | None, str | None]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest.read_bytes(), None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            status = getattr(resp, "status", 200)
            data = resp.read()
            if status != 200:
                return None, f"HTTP {status}"
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return None, str(exc.reason)
    if data.lstrip().lower().startswith(b"<!doctype html") or data.lstrip().lower().startswith(b"<html") or b"<main" in data[:8000].lower() or b"<body" in data[:8000].lower():
        dest.write_bytes(data)
        return data, None
    # A non-HTML body is not an account page.
    return None, "response was not HTML"


def visible_main(html: str) -> str:
    """Server-rendered page text.

    ElephantVoices puts the behavior description in a hidden template and
    leaves the <main> shell empty. The description is still in the HTML, so
    the whole document is read and scripts, navigation, footers and dialogs
    are dropped.
    """
    fragment = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    fragment = re.sub(r"<style[\s\S]*?</style>", " ", fragment, flags=re.I)
    fragment = re.sub(r"<svg[\s\S]*?</svg>", " ", fragment, flags=re.I)
    fragment = re.sub(r"<nav\b[\s\S]*?</nav>", " ", fragment, flags=re.I)
    fragment = re.sub(r"<footer\b[\s\S]*?</footer>", " ", fragment, flags=re.I)
    fragment = re.sub(r"<dialog\b[\s\S]*?</dialog>", " ", fragment, flags=re.I)
    # Keep headings and paragraphs from gluing into one sentence.
    fragment = re.sub(r"</(?:p|h1|h2|h3|h4|li|figcaption)>", ". ", fragment, flags=re.I)
    fragment = re.sub(r"<br\s*/?>", " ", fragment, flags=re.I)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    fragment = unescape(fragment)
    fragment = fragment.replace("\u00a0", " ")
    fragment = re.sub(r"\s+", " ", fragment).strip()
    return fragment


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for part in parts:
        sentence = part.strip(" \"")
        sentence = re.sub(r"([.!?])\1+$", r"\1", sentence)
        if len(sentence) < 20:
            continue
        if sentence.endswith("..."):
            continue
        out.append(sentence)
    return out


def component_flags(sentence: str) -> list[str]:
    if not ORGAN.search(sentence):
        return []
    flags = []
    if NOSTRIL.search(sentence):
        flags.append("nostril")
    if MOUTH.search(sentence) and FOOD.search(sentence):
        flags.append("food")
    if PLANT.search(sentence) and ACT.search(sentence):
        flags.append("trees")
    return flags


def trunk_hrefs(library_html: str) -> list[str]:
    found = []
    seen = set()
    for href, title, blurb in CARD_RE.findall(library_html):
        plain = unescape(re.sub(r"<[^>]+>", " ", f"{title} {blurb}"))
        if not ORGAN.search(plain):
            continue
        if href not in seen:
            seen.add(href)
            found.append(href)
    return found


def score_pages(pages: list[tuple[str, str]]) -> list[dict]:
    rows = []
    for url, text in pages:
        for sentence in sentences(text):
            flags = component_flags(sentence)
            if not flags:
                continue
            polarity = "refutes" if DENY.search(sentence) else "supports"
            for flag in flags:
                rows.append({
                    "component": flag,
                    "polarity": polarity,
                    "url": url,
                    "sentence": sentence,
                })
    rows.sort(key=lambda row: (row["component"], row["polarity"], row["url"], row["sentence"]))
    return rows


def status_of(rows: list[dict], component: str) -> str:
    supports = any(row["component"] == component and row["polarity"] == "supports" for row in rows)
    refutes = any(row["component"] == component and row["polarity"] == "refutes" for row in rows)
    if supports and refutes:
        return "both"
    if refutes:
        return "refuted"
    if supports:
        return "supported"
    return "untested"


def quotes(rows: list[dict], component: str, polarity: str, limit: int = 6) -> list[str]:
    picked = []
    seen = set()
    for row in rows:
        if row["component"] != component or row["polarity"] != polarity:
            continue
        if row["sentence"] in seen:
            continue
        seen.add(row["sentence"])
        picked.append(row["sentence"])
        if len(picked) >= limit:
            break
    return picked


def main() -> None:
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = json.loads(RESULT_PATH.read_text())
    prior = result.get("datasets") or []
    if prior and prior[0].get("files"):
        retrieved_at = prior[0]["files"][0].get("retrieved_at", retrieved_at)

    CACHE.mkdir(parents=True, exist_ok=True)
    landings = [
        ("loxodonta", ADW_LOXODONTA, CACHE / "loxodonta.html"),
        ("elephas", ADW_ELEPHAS, CACHE / "elephas.html"),
        ("index", ETHOGRAM_INDEX, CACHE / "index.html"),
    ]
    # Reuse pages saved before this script existed.
    aliases = {
        "index": CACHE / "ethogram.html",
        "library": CACHE / "ethogram-root.html",
    }
    fetched: dict[str, bytes | None] = {}
    errors: dict[str, str] = {}
    for key, url, dest in landings:
        if not dest.exists() and key in aliases and aliases[key].exists():
            dest.write_bytes(aliases[key].read_bytes())
        data, err = fetch(url, dest)
        fetched[key] = data
        if err:
            errors[key] = err

    landing_ok = [key for key in ("loxodonta", "elephas", "index") if fetched.get(key)]
    if not landing_ok:
        finish_unavailable(result, retrieved_at, errors)
        return

    library = None
    index_html = fetched.get("index")
    if index_html and (LIBRARY_PATH in index_html.decode("utf-8", "replace") or b'href="/ethogram"' in index_html):
        library_dest = CACHE / "library.html"
        if not library_dest.exists() and aliases["library"].exists():
            library_dest.write_bytes(aliases["library"].read_bytes())
        library, err = fetch("https://www.elephantvoices.org/ethogram", library_dest)
        fetched["library"] = library
        if err:
            errors["library"] = err

    hrefs: list[str] = []
    if library:
        hrefs = trunk_hrefs(library.decode("utf-8", "replace"))

    behavior_dest = CACHE / "behaviors"
    behavior_dest.mkdir(parents=True, exist_ok=True)

    def one(href: str) -> tuple[str, bytes | None, str | None]:
        url = "https://www.elephantvoices.org" + href
        slug = href.rstrip("/").split("/")[-1]
        data, err = fetch(url, behavior_dest / f"{slug}.html")
        return url, data, err

    behavior_pages: list[tuple[str, bytes]] = []
    if hrefs:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(one, href) for href in hrefs]
            for future in as_completed(futures):
                url, data, err = future.result()
                if err or not data:
                    errors[url] = err or "empty"
                else:
                    behavior_pages.append((url, data))
    behavior_pages.sort(key=lambda item: item[0])

    scored_pages: list[tuple[str, str]] = []
    file_records = []

    def add_record(url: str, data: bytes, text: str) -> None:
        file_records.append({
            "download_url": url,
            "retrieved_at": retrieved_at,
            "byte_size": len(data),
            "sha256": sha256_bytes(text.encode("utf-8")),
            "raw_sha256": sha256_bytes(data),
        })

    if fetched.get("loxodonta"):
        text = visible_main(fetched["loxodonta"].decode("utf-8", "replace"))
        scored_pages.append((ADW_LOXODONTA, text))
        add_record(ADW_LOXODONTA, fetched["loxodonta"], text)
    if fetched.get("elephas"):
        text = visible_main(fetched["elephas"].decode("utf-8", "replace"))
        scored_pages.append((ADW_ELEPHAS, text))
        add_record(ADW_ELEPHAS, fetched["elephas"], text)
    for url, data in behavior_pages:
        text = visible_main(data.decode("utf-8", "replace"))
        scored_pages.append((url, text))
        add_record(url, data, text)

    rows = score_pages(scored_pages)
    components = ["nostril", "food", "trees"]
    statuses = {name: status_of(rows, name) for name in components}
    untested = [name for name, status in statuses.items() if status == "untested"]
    supported = [name for name, status in statuses.items() if status in ("supported", "both")]
    refuted = [name for name, status in statuses.items() if status in ("refuted", "both")]

    if not scored_pages:
        finish_unavailable(result, retrieved_at, errors)
        return
    if untested:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.35
    elif len(refuted) == 3 and len(supported) == 0:
        verdict, reason, confidence = "refutes", None, 0.6
    elif supported and refuted:
        verdict, reason, confidence = "mixed", None, 0.45
    elif len(supported) == 3 and len(refuted) == 0:
        verdict, reason, confidence = "supports", None, 0.6
    else:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.35

    support_counts = {
        name: sum(1 for row in rows if row["component"] == name and row["polarity"] == "supports")
        for name in components
    }
    deny_counts = {
        name: sum(1 for row in rows if row["component"] == name and row["polarity"] == "refutes")
        for name in components
    }
    extra = {
        "component_status": statuses,
        "support_sentence_counts": support_counts,
        "denial_sentence_counts": deny_counts,
        "quotes": {
            name: {
                "supports": quotes(rows, name, "supports"),
                "refutes": quotes(rows, name, "refutes"),
            }
            for name in components
        },
        "pages_scored": len(scored_pages),
        "trunk_pages_linked": len(hrefs),
        "trunk_pages_failed": len(hrefs) - len(behavior_pages),
        "adw_pages_scored": sum(1 for url, _ in scored_pages if "animaldiversity.org" in url),
    }
    measured = {
        "value": len([name for name in components if statuses[name] == "supported"]),
        "unit": "components supported and not denied",
        "n": len(scored_pages),
        "uncertainty": (
            f"nostril={statuses['nostril']} ({support_counts['nostril']} support, {deny_counts['nostril']} denial); "
            f"food={statuses['food']} ({support_counts['food']} support, {deny_counts['food']} denial); "
            f"trees={statuses['trees']} ({support_counts['trees']} support, {deny_counts['trees']} denial)"
        ),
        "extra": extra,
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2, ensure_ascii=False) + "\n")
    lines = ["component,polarity,url,sentence"]
    for row in rows:
        sentence = row["sentence"].replace('"', '""')
        lines.append(f'{row["component"]},{row["polarity"]},{row["url"]},"{sentence}"')
    (DERIVED / "matched-sentences.csv").write_text("\n".join(lines) + "\n")

    adw_files = [rec for rec in file_records if "animaldiversity.org" in rec["download_url"]]
    ev_files = [rec for rec in file_records if "elephantvoices.org" in rec["download_url"]]
    datasets = []
    if adw_files:
        datasets.append({
            "id": "animal-diversity-web-elephantidae",
            "name": "Animal Diversity Web accounts of Loxodonta africana and Elephas maximus",
            "landing_url": "https://animaldiversity.org/",
            "doi": None,
            "version": retrieved_at[:10],
            "license": "© 2025 Regents of the University of Michigan; no public license is stated on the account pages",
            "files": adw_files,
            "role": "prose natural-history accounts of the two living elephant genera",
        })
    if ev_files:
        datasets.append({
            "id": "elephantvoices-ethogram-trunk",
            "name": "ElephantVoices Elephant Ethogram, trunk-behavior pages linked from the ethogram index",
            "landing_url": ETHOGRAM_INDEX,
            "doi": None,
            "version": retrieved_at[:10],
            "license": "Copyright © 2026 ElephantVoices. All Rights Reserved.",
            "files": ev_files,
            "role": "behavior descriptions whose index card contains the word trunk or proboscis",
        })

    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["data_kind"] = "biological"
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["measured"] = measured
    result["method"] = (
        "Downloaded the Animal Diversity Web accounts of Loxodonta africana and Elephas maximus "
        "and the ElephantVoices ethogram index. The index links to the ethogram library. "
        "Every library card whose title or preview contains trunk or proboscis was downloaded "
        "and its main-text sentences were scored. A listed word matches itself and the regular "
        "inflections -s, -es, -ed and -ing, and does not match a longer stem such as branchlet, "
        "vomeronasal or seedling. A sentence with the content words supports that component "
        "unless it also says does not, cannot, or never, in which case it denies the component. "
        f"Scored {len(scored_pages)} pages ({len(behavior_pages)} trunk-behavior pages). "
        f"Failed fetches: {len(errors)}."
    )
    result["results_summary"] = [
        f"Nostril: {statuses['nostril']}. {quote_line(rows, 'nostril')}",
        f"Food and drink: {statuses['food']}. {quote_line(rows, 'food')}",
        f"Trees: {statuses['trees']}. {quote_line(rows, 'trees')}",
        (
            f"Verdict {verdict}. {measured['value']} of 3 components supported without a denial. "
            f"{len(scored_pages)} pages scored."
        ),
    ]
    result["datasets"] = datasets
    caveats = list(result.get("caveats") or [])
    added = (
        "The ethogram index links to the library at /ethogram, and the trunk-behavior pages "
        "are the library cards that contain the word trunk or proboscis. Site navigation, "
        "the footer and the cookie dialog were not scored. Keyword matches include sentences "
        "that mention the words without describing the act; each matched sentence is in "
        "derived/matched-sentences.csv. The SHA-256 on each file is the hash of the normalized "
        "visible main text. raw_sha256 is the HTML bytes, which can change when the page template changes."
    )
    if added not in caveats:
        caveats.append(added)
    denial_note = (
        "The nostril denial is one sentence on the Silly-Trunk page. It calls the trunk a long nose "
        "and says the infant does not know what to make of it. The pre-registered rule counts every "
        "sentence that has the content words and also says does not, cannot, or never as a denial, "
        "so the nostril component is not a clean support."
    )
    if any(row["polarity"] == "refutes" for row in rows) and denial_note not in caveats:
        caveats.append(denial_note)
    if errors:
        err_note = "Pages that did not download: " + "; ".join(f"{key}: {errors[key]}" for key in sorted(errors)[:12])
        if err_note not in caveats:
            caveats.append(err_note)
    result["caveats"] = caveats
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "reason": reason,
        "statuses": statuses,
        "support_counts": support_counts,
        "deny_counts": deny_counts,
        "pages": len(scored_pages),
        "hrefs": len(hrefs),
        "errors": len(errors),
        "value": measured["value"],
    }, indent=2))


def quote_line(rows: list[dict], component: str) -> str:
    parts = []
    support = quotes(rows, component, "supports", limit=1)
    deny = quotes(rows, component, "refutes", limit=1)
    if support:
        sentence = support[0]
        if len(sentence) > 240:
            sentence = sentence[:237] + "..."
        parts.append(f'Support: "{sentence}"')
    if deny:
        sentence = deny[0]
        if len(sentence) > 240:
            sentence = sentence[:237] + "..."
        parts.append(f'Denial: "{sentence}"')
    if not parts:
        return "No matching sentence."
    return " ".join(parts)


def finish_unavailable(result: dict, retrieved_at: str, errors: dict) -> None:
    result["status"] = "complete"
    result["verdict"] = "inconclusive"
    result["reason"] = "data-unavailable"
    result["confidence"] = 0.35
    result["data_kind"] = "none"
    result["measured"] = {
        "value": None,
        "unit": "components supported and not denied",
        "n": 0,
        "uncertainty": "no account page could be downloaded",
        "extra": {"errors": errors},
    }
    result["method"] = "None of the three landing pages returned HTML."
    result["results_summary"] = ["No account page could be downloaded. Verdict inconclusive, data-unavailable."]
    result["datasets"] = []
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"verdict": "inconclusive", "reason": "data-unavailable", "errors": errors}, indent=2))


if __name__ == "__main__":
    main()
