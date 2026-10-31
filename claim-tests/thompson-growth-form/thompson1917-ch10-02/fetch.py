"""Download Pandita et al. (2013) and transcribe Tables 2-6 to derived/pandita2013_turritellidae.csv.

Needs `pdfplumber` (pip install pdfplumber) in addition to requests; analysis.py itself only needs the
committed CSV plus numpy/pandas. The PDF (0.5 MB) is kept in data/ (git-ignored).

Column layout per table (header rows are read from the PDF but the rendered header is garbled, so the
layout is fixed here from the published tables): spec, L(mm), Wang, Wsut, [Ww], [alpha], whorl number,
Wang:L, Wsut:L, Wsut:Wang. Table 5 has no alpha values, Table 6 has no Ww column. Rows with blank cells are
disambiguated as in the published tables: in Tables 2-4 a row with four values before the whorl number has
Ww present and alpha blank; a row with three values has both blank.
"""
import hashlib
import json
import os
import re
import time

import pdfplumber
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
URL = "https://www.scirp.org/pdf/ijg_2013062114170109.pdf"
SPECIES = {
    "Table 2.": ("Turritella sp. (MNT13)", True),
    "Table 3.": ("Turritella bantamensis (BOJ3)", True),
    "Table 4.": ("Turritella simplex (CLN01-A)", True),
    "Table 5.": ("Turritella djadjariensis (PsI01)", True),
    "Table 6.": ("Turritella javana (CJR02B)", False),  # no Ww column
}
NUM = re.compile(r"^-?\d+(\.\d+)?$")


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(DERIVED, exist_ok=True)
    pdf_path = os.path.join(DATA, "ijg_2013062114170109.pdf")
    if not os.path.exists(pdf_path):
        r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0 delphisci-claim-tests/1.0"}, timeout=120)
        r.raise_for_status()
        open(pdf_path, "wb").write(r.content)
        meta = {"download_url": URL, "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}
        json.dump(meta, open(os.path.join(DATA, "manifest.json"), "w"), indent=1)
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        current = None
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                for key, val in SPECIES.items():
                    if line.startswith(key):
                        current = (key, *val)
                if current is None:
                    continue
                toks = line.split()
                if len(toks) < 6 or not all(NUM.match(t) for t in toks[1:]):
                    continue
                spec, vals = toks[0], [float(t) for t in toks[1:]]
                ratios, n_whorls, lead = vals[-3:], vals[-4], vals[:-4]
                if not (3 <= len(lead) <= 5) or not re.search(r"[BY]$", spec):
                    continue
                L, wang, wsut = lead[:3]
                ww = alpha = None
                has_ww = current[2]
                if has_ww:
                    if len(lead) == 5:
                        ww, alpha = lead[3], lead[4]
                    elif len(lead) == 4:
                        ww = lead[3]
                else:
                    if len(lead) == 4:
                        alpha = lead[3]
                rows.append({"table": current[0].rstrip("."), "species": current[1], "specimen": spec, "L_mm": L,
                             "Wang_mm": wang, "Wsut_mm": wsut, "Ww_mm": ww, "alpha_deg": alpha, "whorl_number": n_whorls,
                             "Wang_L": ratios[0], "Wsut_L": ratios[1], "Wsut_Wang": ratios[2]})
    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(DERIVED, "pandita2013_turritellidae.csv"), index=False)
    print(df.to_string())
    print(len(df), "rows;", df["alpha_deg"].notna().sum(), "with apical angle")


if __name__ == "__main__":
    main()
