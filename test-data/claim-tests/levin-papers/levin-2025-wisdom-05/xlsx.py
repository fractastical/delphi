"""Minimal reader for the first worksheet of an .xlsx file (standard library only)."""
import re
import xml.etree.ElementTree as ET
import zipfile

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _col(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_rows(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.parse(z.open("xl/sharedStrings.xml")).getroot().iter(NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
        rows = []
        for _, el in ET.iterparse(z.open("xl/worksheets/sheet1.xml")):
            if el.tag != NS + "row":
                continue
            row = {}
            for c in el.iter(NS + "c"):
                v = c.find(NS + "v")
                t = c.get("t")
                if t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(NS + "t"))
                elif v is None:
                    continue
                elif t == "s":
                    val = shared[int(v.text)]
                else:
                    val = v.text
                row[_col(c.get("r"))] = val
            width = max(row) + 1 if row else 0
            rows.append([row.get(i) for i in range(width)])
            el.clear()
        return rows
