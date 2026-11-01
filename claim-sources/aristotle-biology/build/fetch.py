# Vendor Aristotle's three main biological works, in the Oxford translations (1910-1912), as
# plain text. Each work becomes inputs/<key>.txt: one paragraph per line, "## Book N" and
# "### Part N" headings. inputs/sources.json pins every downloaded file by SHA-256 (and each
# Wikisource page by revision id) and each text file by SHA-256.
#
# Sources: History of Animals (Thompson) and Parts of Animals (Ogle) from the MIT Internet Classics
# Archive; Generation of Animals (Platt) from English Wikisource, which the MIT archive lacks.
# Wikisource's copies of the other two were imported from the MIT files and are cut short at a
# stray "<A" in History VIII-IX and Parts II-IV, so they are not used. The translations are in the
# public domain; the script refuses a text that still holds markup or does not reach its last book.
#
#   python3 build/fetch.py            # fetch and (re)write inputs/
#   python3 build/fetch.py --check    # verify inputs/*.txt against sources.json
import hashlib, json, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / "inputs"
WIKISOURCE = "https://en.wikisource.org/w/api.php"
UA = {"User-Agent": "delphisci/aristotle-biology (https://github.com/fractastical/delphisci)"}
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
OXFORD = "The Works of Aristotle Translated into English, ed. J. A. Smith and W. D. Ross, Oxford: Clarendon Press"

# key: the work's slug in claim ids (aristotle-<key>NN-MM, NN the book).
WORKS = [
    {"key": "ha", "title": "The History of Animals", "latin": "Historia Animalium", "books": 9,
     "translator": "D'Arcy Wentworth Thompson", "translation_year": 1910, "oxford_volume": "IV",
     "wikidata": "Q1620799", "mit": "http://classics.mit.edu/Aristotle/history_anim.mb.txt"},
    {"key": "pa", "title": "On the Parts of Animals", "latin": "De Partibus Animalium", "books": 4,
     "translator": "William Ogle", "translation_year": 1912, "oxford_volume": "V",
     "wikidata": "Q1180725", "mit": "http://classics.mit.edu/Aristotle/parts_animals.mb.txt"},
    {"key": "ga", "title": "On the Generation of Animals", "latin": "De Generatione Animalium", "books": 5,
     "translator": "Arthur Platt", "translation_year": 1912, "oxford_volume": "V",
     "wikidata": "Q1180637", "wikisource": "On the Generation of Animals"},
]
PD = re.compile(r"\{\{\s*(PD-old|PD/US|PD-US|translation license)", re.I)


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def stamp(url, data):
    return {"download_url": url, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def mit_books(raw):
    """MIT text: hard-wrapped, paragraphs separated by blank lines, 'BOOK N' and 'Part N' lines."""
    body = raw.split("-" * 70, 1)[1].rsplit("THE END", 1)[0]
    books, cur, para = [], None, []

    def flush():
        if para:
            cur[1].append(("p", " ".join(para)))
            para.clear()

    for line in body.split("\n"):
        s = re.sub(r"\s+", " ", line).strip()
        if re.fullmatch(r"-{10,}", s):
            flush()
        elif m := re.fullmatch(r"BOOK ([IVX]+)", s):
            flush()
            cur = (ROMAN.index(m.group(1)) + 1, [])
            books.append(cur)
        elif re.fullmatch(r"Part \d+", s):
            flush()
            cur[1].append(("h", s))
        elif not s:
            flush()
        else:
            para.append(s)
    flush()
    return books


def wikisource_page(title):
    q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "ids|timestamp|content", "rvslots": "main",
                                "titles": title, "format": "json", "formatversion": 2})
    p = json.loads(get(f"{WIKISOURCE}?{q}"))["query"]["pages"][0]
    if "missing" in p:
        raise SystemExit(f"missing Wikisource page: {title}")
    rev = p["revisions"][0]
    return p["title"], rev["revid"], rev["timestamp"], rev["slots"]["main"]["content"]


def wikisource_lines(wikitext):
    s = wikitext
    prev = None
    while prev != s:
        prev, s = s, re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"\[\[[a-z]{2,3}:[^\]]*\]\]", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    out = []
    for raw in s.split("\n"):
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        h = re.fullmatch(r"=+\s*(.*?)\s*=+", line) or re.fullmatch(r"(Part \d+)", line)
        out.append(("h", h.group(1)) if h else ("p", line))
    return out


def to_text(w, books):
    lines = [f"# Aristotle, {w['title']} ({w['latin']})", "",
             f"Translated by {w['translator']} ({w['translation_year']}), {OXFORD}, vol. {w['oxford_volume']}.",
             "Plain text, one paragraph per line; see sources.json for where it was taken from.", ""]
    for n, items in books:
        lines += [f"## Book {ROMAN[n - 1]}", ""]
        for kind, t in items:
            lines += (["", f"### {t}", ""] if kind == "h" else [t])
        lines.append("")
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"
    if re.search(r"<[A-Za-z/]|\{\{|\}\}|\[\[", text):
        raise SystemExit(f"{w['key']}: markup left in the text")
    if [n for n, _ in books] != list(range(1, w["books"] + 1)):
        raise SystemExit(f"{w['key']}: expected books 1-{w['books']}, got {[n for n, _ in books]}")
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
    works = []
    for w in WORKS:
        entry = {"key": w["key"], "title": w["title"], "latin": w["latin"], "author": "Aristotle",
                 "translator": w["translator"], "translation_year": w["translation_year"],
                 "edition": f"{OXFORD}, vol. {w['oxford_volume']} ({w['translation_year']})",
                 "wikidata": f"http://www.wikidata.org/entity/{w['wikidata']}"}
        if "mit" in w:
            raw = get(w["mit"])
            books = mit_books(raw.decode("utf-8"))
            entry |= {"source": "MIT Internet Classics Archive", "landing_url": w["mit"].replace(".mb.txt", ".html"),
                      "license": "Translation in the public domain (published 1910-1912); the archive claims copyright only in its web presentation.",
                      "files": [stamp(w["mit"], raw)]}
        else:
            base = w["wikisource"]
            _, index_rev, _, index = wikisource_page(base)
            if not PD.search(index):
                raise SystemExit(f"{base}: no public-domain licence template on the index page")
            books, files = [], []
            for n in range(1, w["books"] + 1):
                title, revid, ts, text = wikisource_page(f"{base}/Book {ROMAN[n - 1]}")
                books.append((n, wikisource_lines(text)))
                url = f"https://en.wikisource.org/w/index.php?title={urllib.parse.quote(title.replace(' ', '_'))}&oldid={revid}&action=raw"
                files.append({**stamp(url, text.encode()), "revid": revid, "rev_timestamp": ts})
            entry |= {"source": "English Wikisource", "landing_url": f"https://en.wikisource.org/wiki/{urllib.parse.quote(base.replace(' ', '_'))}",
                      "index_revid": index_rev,
                      "license": "Public domain (Wikisource: original PD-old; translation PD in the US, published before 1930).",
                      "files": files}
        text = to_text(w, books)
        (INPUTS / f"{w['key']}.txt").write_text(text)
        tb = text.encode()
        entry |= {"text_file": f"{w['key']}.txt", "text_lines": text.count("\n"), "text_sha256": hashlib.sha256(tb).hexdigest()}
        works.append(entry)
        print(f"{w['key']}  {len(tb):>7} bytes {text.count(chr(10)):>5} lines {len(text.split()):>7} words  {w['title']} ({w['translator']}, {entry['source']})")
    (INPUTS / "sources.json").write_text(json.dumps({"works": works}, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
