"""Check the pre-fixed 15-item attestation sample against the cited sources. Bounded, read-only, public URLs only, no credentials.

Fetch order per source (declared before the run):
  1. Europe PMC full-text XML  https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML   (open-access subset only)
  2. if that is unavailable, the Europe PMC record (title and abstract) as metadata
  3. if the public page itself answers 403, the r.jina.ai reader proxy for that PUBLIC URL (no key, no cookies)
Each item gets exactly one status:
  verified          the quote is present in retrieved FULL TEXT (after the normalisation below)
  quote_not_found   FULL TEXT was retrieved and the quote is not in it  (a mismatch candidate; the closest passage is recorded)
  source_only       the identifier resolved (title/abstract/metadata retrieved) but no full text, so the quote could not be checked
  access_failure    nothing usable was retrieved
Normalisation (the only one): Unicode NFKC, lower case, typographic quotes/dashes folded, whitespace collapsed; second pass keeps
letters and digits only. A quote that matches only after the second pass is reported as such. Nothing is fuzzy-matched into "verified".
The script stores digests and short excerpts, never whole documents. It does not judge whether a quote supports the curator's question.
"""
import difflib
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).parent
SAMPLE = json.loads((HERE / "attestation-sample-15.json").read_text())
CACHE = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / ".cache"
CACHE.mkdir(parents=True, exist_ok=True)
UA = "delphi-frontier-attestation-check/1 (public-read; contact via repo)"
TIMEOUT = 30
MAX_BYTES = 6_000_000


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(MAX_BYTES + 1)
            return r.status, body[:MAX_BYTES], len(body) > MAX_BYTES
    except urllib.error.HTTPError as e:
        return e.code, b"", False
    except Exception as e:  # noqa: BLE001 - recorded as a failure, never raised
        return f"error:{type(e).__name__}", b"", False


FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-", " ": " "})


def norm(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s).translate(FOLD).lower()).strip()


def alnum(s):
    return re.sub(r"[^0-9a-z]+", "", norm(s))


def xml_text_and_sections(xml_bytes):
    root = ET.fromstring(xml_bytes)
    def txt(e):
        return "".join(e.itertext())
    sections = []
    def walk(e, trail):
        for c in e:
            if c.tag == "sec":
                t = c.find("title")
                title = txt(t) if t is not None else ""
                sections.append((trail + [title], txt(c)))
                walk(c, trail + [title])
            elif c.tag == "abstract":
                sections.append((["abstract"], txt(c)))
            else:
                walk(c, trail)
    walk(root, [])
    return txt(root), sections


def closest(quote, text):
    q = norm(quote).split()
    t = norm(text).split()
    n = len(q)
    if not t or not n:
        return 0.0, ""
    best, at = 0.0, 0
    step = max(1, n // 4)
    for i in range(0, max(1, len(t) - n + 1), step):
        r = difflib.SequenceMatcher(None, q, t[i:i + n], autojunk=False).quick_ratio()
        if r > best:
            best, at = r, i
    # refine around the best coarse window with the real ratio
    best2, at2 = 0.0, at
    for i in range(max(0, at - 2 * step), min(len(t) - n + 1, at + 2 * step) + 1):
        r = difflib.SequenceMatcher(None, q, t[i:i + n], autojunk=False).ratio()
        if r > best2:
            best2, at2 = r, i
    return round(best2, 3), " ".join(t[max(0, at2 - 5): at2 + n + 5])[:400]


def check(item):
    out = {"slug": item["slug"], "index": item["index"], "stratum": item["stratum"], "stance": item["stance"], "kind": item["kind"],
           "source": item["source"], "locator": item["locator"], "tries": []}
    text, sections, access = "", [], "none"
    if item["pmcid"]:
        pm = item["pmcid"]
        st, body, cut = get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pm}/fullTextXML")
        out["tries"].append({"route": "europepmc_fulltext_xml", "http": st, "bytes": len(body), "sha256": sha256(body).hexdigest() if body else None})
        if st == 200 and body:
            try:
                text, sections = xml_text_and_sections(body)
                access = "full_text"
                _r = ET.fromstring(body)
                _y = _r.find(".//pub-date/year")
                _t = _r.find(".//article-title")
                out["article_year"] = "".join(_y.itertext()) if _y is not None else None
                out["article_title"] = ("".join(_t.itertext()) if _t is not None else None)
                (CACHE / f"{pm}.xml").write_bytes(body)
            except ET.ParseError:
                out["tries"][-1]["parse"] = "failed"
        if access != "full_text":
            time.sleep(1)
            st, body, _ = get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PMCID:{pm}&format=json&resultType=core")
            out["tries"].append({"route": "europepmc_record", "http": st, "bytes": len(body), "sha256": sha256(body).hexdigest() if body else None})
            if st == 200 and body:
                try:
                    hits = json.loads(body)["resultList"]["result"]
                except Exception:  # noqa: BLE001
                    hits = []
                if hits:
                    out["resolved_title"] = hits[0].get("title")
                    text = (hits[0].get("title") or "") + " " + (hits[0].get("abstractText") or "")
                    access = "metadata_abstract"
                    out["europepmc_is_open_access"] = hits[0].get("isOpenAccess")
        if access != "full_text":  # public page via the reader proxy, only for the 403/unavailable case
            time.sleep(1)
            url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pm}/"
            st, body, _ = get("https://r.jina.ai/" + url)
            out["tries"].append({"route": "jina_reader_of_public_pmc_page", "http": st, "bytes": len(body), "sha256": sha256(body).hexdigest() if body else None})
            if st == 200 and len(body) > 2000:
                text, sections, access = body.decode("utf-8", "replace"), [], "full_text_via_jina"
    else:
        url = item["url"]
        st, body, _ = get(url)
        out["tries"].append({"route": "direct", "http": st, "bytes": len(body), "sha256": sha256(body).hexdigest() if body else None})
        if st == 200 and body:
            text, access = re.sub(r"<[^>]+>", " ", body.decode("utf-8", "replace")), "full_text"
        else:
            time.sleep(1)
            st, body, _ = get("https://r.jina.ai/" + url)
            out["tries"].append({"route": "jina_reader_of_public_url", "http": st, "bytes": len(body), "sha256": sha256(body).hexdigest() if body else None})
            if st == 200 and len(body) > 500:
                text, access = body.decode("utf-8", "replace"), "full_text_via_jina"
    out["access"] = access
    quote = item["quote"]
    if access in ("full_text", "full_text_via_jina"):
        nq, nt = norm(quote), norm(text)
        pos = nt.find(nq)
        how = "normalised_exact" if pos >= 0 else None
        if pos < 0 and alnum(quote) and alnum(quote) in alnum(text):
            how = "letters_and_digits_only"
        if how:
            out.update(status="verified", match=how)
            if sections:
                hits = [trail for trail, body_ in sections if nq in norm(body_) or alnum(quote) in alnum(body_)]
                loc = alnum(item["locator"])
                out["sections_containing_quote"] = [" > ".join(t for t in trail if t)[:200] for trail in hits][:4]
                out["locator_match"] = bool(any(loc and (loc in alnum(" ".join(trail)) or alnum(" ".join(trail)) in loc) for trail in hits))
            else:
                last = alnum(item["locator"].split(">")[-1])
                out["locator_match"] = ("last_heading_segment_present_in_page_text" if last and last in alnum(text)
                                        else "not_found_in_page_text") + " (no section structure; the quote position was not tied to the heading)"
            if pos >= 0:
                out["context_excerpt"] = nt[max(0, pos - 150): pos + len(nq) + 150]
        else:
            ratio, excerpt = closest(quote, text)
            out.update(status="quote_not_found", best_window_ratio=ratio, closest_excerpt=excerpt)
    elif access == "metadata_abstract":
        nq = norm(quote)
        out.update(status="source_only", note="title/abstract retrieved, full text not; quote not checkable"
                   + ("; quote IS present in the retrieved abstract" if nq in norm(text) else ""))
    else:
        out.update(status="access_failure")
    return out


results = []
for it in SAMPLE["items"]:
    results.append(check(it))
    time.sleep(1.5)
counts = {}
for r in results:
    counts[r["status"]] = counts.get(r["status"], 0) + 1
doc = {"sample_sha256": sha256((HERE / "attestation-sample-15.json").read_bytes()).hexdigest(), "run_note": "second run after a locator-comparison fix (separator); see README-attestation-check-15.md",
       "n": len(results), "status_counts": counts, "results": results}
(HERE / "attestation-check-15.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
print(json.dumps(counts))
for r in results:
    print(r["stratum"], r["slug"], r["source"][-30:], r["status"], r.get("access"), r.get("match", ""), r.get("locator_match", ""), r.get("best_window_ratio", ""))
