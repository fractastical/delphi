# Vendor the selected Levin papers as plain text from the Europe PMC open-access subset.
# Each paper becomes inputs/<key>.txt (one paragraph per line, "## " section headings,
# figures, tables and back matter dropped) and inputs/sources.json pins the JATS XML and
# the text by SHA-256. Every paper must be CC BY; the script refuses anything else.
#
#   python3 build/fetch.py            # fetch and (re)write inputs/
#   python3 build/fetch.py --check    # verify inputs/*.txt against sources.json
import hashlib, json, re, sys, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / "inputs"
API = "https://www.ebi.ac.uk/europepmc/webservices/rest"

# key: the paper's slug in claim ids (levin-<key>-NN). Chosen from Levin's CC BY papers in
# Europe PMC: his main theoretical statements plus empirical and computational papers whose
# claims are concrete enough to test.
PAPERS = [
    ("2015-place", "PMC4387527"),
    ("2015-girardia", "PMC4661923"),
    ("2014-tumor", "PMC4102810"),
    ("2018-hcn2", "PMC5843655"),
    ("2019-boundary", "PMC6923654"),
    ("2020-xenobots", "PMC6994979"),
    ("2022-tame", "PMC8988303"),
    ("2022-grn-learning", "PMC9820177"),
    ("2023-competency", "PMC9858125"),
    ("2023-goals", "PMC10102734"),
    ("2023-agential", "PMC10167196"),
    ("2023-glue", "PMC10770221"),
    ("2024-anthrobots", "PMC10811512"),
    ("2024-collective", "PMC10978875"),
    ("2024-memory", "PMC11203334"),
    ("2025-wisdom", "PMC11848127"),
]

SKIP = {"fig", "table-wrap", "supplementary-material", "fig-group", "table-wrap-group", "ref-list", "ack", "fn-group", "app-group", "glossary", "notes"}
BLOCK = {"p", "title", "list-item", "disp-quote", "def-item", "statement"}
MML = "{http://www.w3.org/1998/Math/MathML}"
# Back matter that some journals (Frontiers, MDPI) put inside <body>.
BACK_MATTER = re.compile(r"^(data (availability|accessibility)( statement)?|authors?[’']? contributions?|author disclaimer|conflicts? of interest( declaration)?|competing interests?|publisher[’']s note|acknowledge?ments?|glossary|funding( statement)?|references|associated data|abbreviations|(electronic )?supplementary (materials?|information|figures?)|supporting information|ethics( statement)?|institutional review board statement|informed consent statement|footnotes|contributor information|peer review|web-summary)$", re.I)


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "delphisci/levin-papers"}), timeout=60) as r:
        return r.read()


def inline(el):
    """Text of an element with formulas rendered as TeX (or [formula]) and whitespace collapsed."""
    out = []

    def walk(e):
        tag = e.tag.split("}")[-1] if isinstance(e.tag, str) else ""
        if tag in SKIP:
            out.append(" ")
            return
        if tag in ("inline-formula", "disp-formula"):
            tex = e.find(".//tex-math")
            math = e.find(f".//{MML}math")
            alt = (tex.text if tex is not None else None) or (math.get("alttext") if math is not None else None)
            out.append(f" ${alt.strip()}$ " if alt else " [formula] ")
        elif tag == "label" and e is not el:
            pass
        else:
            if e.text:
                out.append(e.text)
            for c in e:
                walk(c)
                if c.tail:
                    out.append(c.tail)
                    c.tail = None
            return
        if e.tail:
            out.append(e.tail)
            e.tail = None

    walk(el)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def blocks(el, depth, lines):
    """Walk body/abstract structure: sections give headings, paragraphs give one line each."""
    for c in el:
        tag = c.tag.split("}")[-1] if isinstance(c.tag, str) else ""
        if tag in SKIP:
            continue
        if tag == "sec":
            t = c.find("title")
            if t is not None and BACK_MATTER.match(inline(t)):
                continue
            if t is not None and inline(t):
                lines.append("#" * min(depth, 4) + " " + inline(t))
            blocks(c, depth + 1, lines)
        elif tag == "title":
            continue
        elif tag == "p":
            # Paragraphs can contain lists or quotes; split those out as their own lines.
            nested = [x for x in c if x.tag in ("list", "disp-quote")]
            for x in nested:
                c.remove(x)
            text = inline(c)
            if text:
                lines.append(text)
            for x in nested:
                blocks(x, depth, lines) if x.tag == "list" else lines.append(inline(x))
        elif tag == "list":
            for li in c.findall("list-item"):
                text = inline(li)
                if text:
                    lines.append("- " + text)
        elif tag in BLOCK or tag == "boxed-text":
            text = inline(c) if tag != "boxed-text" else None
            if text:
                lines.append(text)
            elif tag == "boxed-text":
                blocks(c, depth, lines)
        elif tag in ("disp-formula",):
            lines.append(inline(c))
        else:
            blocks(c, depth, lines)


def to_text(xml, meta):
    root = ET.fromstring(xml)
    art = root.find(".//article-meta")
    title = inline(art.find(".//article-title"))
    lines = [f"# {title}", "",
             f"{meta['authorString']}", f"{meta['journalInfo']['journal']['title']} ({meta['pubYear']}). doi:{meta.get('doi')}. {meta['pmcid']}.",
             f"License: {meta['license'].upper()}. Text from the Europe PMC open-access full text; figures, tables, references and back matter omitted.", ""]
    for ab in art.findall("abstract"):
        if ab.get("abstract-type") in ("graphical", "teaser", "toc"):
            continue
        lines.append("## " + (ab.get("abstract-type") or "Abstract").capitalize() if ab.get("abstract-type") else "## Abstract")
        blocks(ab, 3, lines)
    body = root.find(".//body")
    blocks(body, 2, lines)
    out = []
    for l in lines:
        if l.startswith("#") and out and out[-1] != "":
            out.append("")
        out.append(l)
        if l.startswith("#"):
            out.append("")
    text = "\n".join(re.sub(r"\n{3,}", "\n\n", "\n".join(out)).split("\n")).strip() + "\n"
    return re.sub(r"\n{3,}", "\n\n", text)


def check():
    src = json.loads((INPUTS / "sources.json").read_text())
    bad = [p["key"] for p in src["papers"] if hashlib.sha256((INPUTS / p["text_file"]).read_bytes()).hexdigest() != p["text_sha256"]]
    print("ok" if not bad else f"mismatch: {bad}")
    sys.exit(1 if bad else 0)


def main():
    if "--check" in sys.argv:
        check()
    INPUTS.mkdir(exist_ok=True)
    papers = []
    for key, pmcid in PAPERS:
        meta = json.loads(get(f"{API}/search?query=PMCID:{pmcid}&format=json&resultType=core"))["resultList"]["result"][0]
        if meta.get("license") != "cc by":
            raise SystemExit(f"{pmcid}: license {meta.get('license')!r} is not CC BY")
        xml_url = f"{API}/{pmcid}/fullTextXML"
        xml = get(xml_url)
        text = to_text(xml, meta)
        (INPUTS / f"{key}.txt").write_text(text)
        tb = text.encode()
        papers.append({
            "key": key, "pmcid": pmcid, "pmid": meta.get("pmid"), "doi": meta.get("doi"),
            "title": re.sub(r"<[^>]+>", "", meta["title"]).rstrip("."), "authors": meta["authorString"].rstrip("."),
            "journal": meta["journalInfo"]["journal"]["title"], "year": int(meta["pubYear"]), "license": "CC BY",
            "landing_url": f"https://europepmc.org/article/PMC/{pmcid}",
            "xml": {"download_url": xml_url, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "byte_size": len(xml), "sha256": hashlib.sha256(xml).hexdigest()},
            "text_file": f"{key}.txt", "text_lines": text.count("\n"), "text_sha256": hashlib.sha256(tb).hexdigest(),
        })
        print(f"{key:20} {pmcid:12} {len(tb):>7} bytes {text.count(chr(10)):>5} lines  {papers[-1]['title'][:70]}")
    (INPUTS / "sources.json").write_text(json.dumps({"source": "Europe PMC open-access full text (JATS XML)", "papers": papers}, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
