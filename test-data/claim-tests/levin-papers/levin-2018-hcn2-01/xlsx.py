"""Minimal multi-sheet .xlsx reader (standard library only): {sheet name: rows}."""
import re
import xml.etree.ElementTree as ET
import zipfile

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _rows(z, member, shared):
    rows = []
    for row_el in ET.parse(z.open(member)).getroot().iter(NS + "row"):
        row = {}
        for c in row_el.iter(NS + "c"):
            v, t = c.find(NS + "v"), c.get("t")
            if t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(NS + "t"))
            elif v is None:
                continue
            elif t == "s":
                val = shared[int(v.text)]
            else:
                val = v.text
            row[_col(c.get("r"))] = val
        rows.append([row.get(i) for i in range(max(row) + 1)] if row else [])
    return rows


def read_workbook(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.parse(z.open("xl/sharedStrings.xml")).getroot().iter(NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
        rels = {r.get("Id"): r.get("Target") for r in ET.parse(z.open("xl/_rels/workbook.xml.rels")).getroot().iter(PKG + "Relationship")}
        out = {}
        for s in ET.parse(z.open("xl/workbook.xml")).getroot().iter(NS + "sheet"):
            target = rels[s.get(REL + "id")].lstrip("/")
            member = target if target.startswith("xl/") else "xl/" + target
            out[s.get("name")] = _rows(z, member, shared)
        return out
