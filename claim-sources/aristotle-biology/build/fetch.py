# Vendor Aristotle's three main biological works, in the Oxford translations (1910-1912), as
# plain text from English Wikisource. Each work becomes inputs/<key>.txt: one paragraph per line,
# "## Book N" and "### Part N" headings, wiki markup removed. inputs/sources.json pins every
# Wikisource page by revision id and SHA-256, and the text files by SHA-256. Every page must
# carry a public-domain licence template; the script refuses anything else.
#
#   python3 build/fetch.py            # fetch and (re)write inputs/
#   python3 build/fetch.py --check    # verify inputs/*.txt against sources.json
import hashlib, json, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / "inputs"
API = "https://en.wikisource.org/w/api.php"
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]

# key: the work's slug in claim ids (aristotle-<key>NN-MM, NN the book).
WORKS = [
    {"key": "ha", "base": "History of Animals (Thompson)", "books": 9, "title": "The History of Animals",
     "latin": "Historia Animalium", "translator": "D'Arcy Wentworth Thompson", "translation_year": 1910,
     "wikidata": "Q1620799"},
    {"key": "pa", "base": "On the Parts of Animals", "books": 4, "title": "On the Parts of Animals",
     "latin": "De Partibus Animalium", "translator": "William Ogle", "translation_year": 1912,
     "wikidata": "Q1180725"},
    {"key": "ga", "base": "On the Generation of Animals", "books": 5, "title": "On the Generation of Animals",
     "latin": "De Generatione Animalium", "translator": "Arthur Platt", "translation_year": 1912,
     "wikidata": "Q1180637"},
]
PD = re.compile(r"\{\{\s*(PD-old|PD/US|PD-US|translation license)", re.I)


def get(params):
    url = f"{API}?{urllib.parse.urlencode({**params, 'format': 'json', 'formatversion': 2})}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "delphisci/aristotle-biology (https://github.com/fractastical/delphisci)"}), timeout=60) as r:
        return json.loads(r.read())


def page(title):
    p = get({"action": "query", "prop": "revisions", "rvprop": "ids|timestamp|content", "rvslots": "main", "titles": title})["query"]["pages"][0]
    if "missing" in p:
        raise SystemExit(f"missing Wikisource page: {title}")
    rev = p["revisions"][0]
    return {"title": p["title"], "revid": rev["revid"], "timestamp": rev["timestamp"], "wikitext": rev["slots"]["main"]["content"]}


def strip_templates(s):
    # Nested {{...}} removed innermost first.
    prev = None
    while prev != s:
        prev, s = s, re.sub(r"\{\{[^{}]*\}\}", "", s)
    return s


def to_lines(wikitext):
    s = strip_templates(wikitext)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"</?[a-z][^>]*>", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    out = []
    for raw in s.split("\n"):
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or re.fullmatch(r"\[\[?[a-z]{2}:.*", line):
            continue
        h = re.fullmatch(r"=+\s*(.*?)\s*=+", line)
        out.append(("h", h.group(1)) if h else ("p", line))
    return out


def to_text(work, books):
    lines = [f"# Aristotle, {work['title']} ({work['latin']})", "",
             f"Translated by {work['translator']} ({work['translation_year']}), The Works of Aristotle Translated into English, Oxford: Clarendon Press.",
             "Text from English Wikisource (public domain); wiki markup removed, one paragraph per line.", ""]
    for n, items in books:
        lines += [f"## Book {ROMAN[n - 1]}", ""]
        for kind, t in items:
            if kind == "h":
                lines += ["", f"### {t}", ""]
            else:
                lines.append(t)
        lines.append("")
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"
    return text


def check():
    src = json.loads((INPUTS / "sources.json").read_text())
    bad = [w["key"] for w in src["works"] if hashlib.sha256((INPUTS / w["text_file"]).read_bytes()).hexdigest() != w["text_sha256"]]
    print("ok" if not bad else f"mismatch: {bad}")
    sys.exit(1 if bad else 0)


def main():
    if "--check" in sys.argv:
        check()
    INPUTS.mkdir(exist_ok=True)
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    works = []
    for w in WORKS:
        index = page(w["base"])
        if not PD.search(index["wikitext"]):
            raise SystemExit(f"{w['base']}: no public-domain licence template on the index page")
        pages, books = [], []
        for n in range(1, w["books"] + 1):
            p = page(f"{w['base']}/Book {ROMAN[n - 1]}")
            items = to_lines(p["wikitext"])
            if not any(k == "p" for k, _ in items):
                raise SystemExit(f"{p['title']}: no text")
            books.append((n, items))
            wb = p["wikitext"].encode()
            pages.append({"book": ROMAN[n - 1], "title": p["title"], "revid": p["revid"], "rev_timestamp": p["timestamp"],
                          "url": f"https://en.wikisource.org/w/index.php?title={urllib.parse.quote(p['title'].replace(' ', '_'))}&oldid={p['revid']}",
                          "byte_size": len(wb), "sha256": hashlib.sha256(wb).hexdigest()})
        text = to_text(w, books)
        (INPUTS / f"{w['key']}.txt").write_text(text)
        tb = text.encode()
        works.append({
            "key": w["key"], "title": w["title"], "latin": w["latin"], "author": "Aristotle",
            "translator": w["translator"], "translation_year": w["translation_year"],
            "wikidata": f"http://www.wikidata.org/entity/{w['wikidata']}",
            "landing_url": f"https://en.wikisource.org/wiki/{urllib.parse.quote(w['base'].replace(' ', '_'))}",
            "index_revid": index["revid"], "license": "Public domain (Wikisource: original PD-old; translation PD in the US, published before 1930)",
            "retrieved_at": retrieved, "pages": pages,
            "text_file": f"{w['key']}.txt", "text_lines": text.count("\n"), "text_sha256": hashlib.sha256(tb).hexdigest(),
        })
        print(f"{w['key']}  {len(tb):>7} bytes {text.count(chr(10)):>5} lines  {w['title']} ({w['translator']})")
    (INPUTS / "sources.json").write_text(json.dumps({"source": "English Wikisource, Oxford translation (ed. J. A. Smith and W. D. Ross)", "works": works}, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
