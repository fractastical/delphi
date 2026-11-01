"""Summarise Daane et al. 2021 Data S1A (per-specimen beloniform fin lengths) into fin/SL ratios.

    python -m engineering.geometry.daane_s1 <mmc2.xlsx> [--out artifacts/print/sources/daane2021-S1A-summary.json]

The spreadsheet is the article's supplement (Elsevier CDN, `1-s2.0-S0960982221011908-mmc2.xlsx`); it is not
redistributed here.  Ratios are recomputed from the raw lengths because the sheet's own ratio column has at
least one corrupt cell (specimen 1, pelvic/SL = 2.4e-16 where 6.9 / 23 = 0.30).  'NA' cells are skipped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

SOURCE = {
    "citation": "Daane, J. M. et al. (2021). Modulation of bioelectric cues in the evolution of flying fishes. "
                "Curr. Biol. 31(22): 5052-5061.e8. doi:10.1016/j.cub.2021.08.054",
    "pmc": "PMC9172250",
    "supplement_url": "https://ars.els-cdn.com/content/image/1-s2.0-S0960982221011908-mmc2.xlsx",
    "sheet": "A - fin measurement",
    "text_locator": "Results, 'To understand the changes in fin allometry ... we measured fin length as a function of "
                    "body size (standard length)' (Figure 1B; Data S1A); STAR Methods: specimens in the Harvard MCZ",
    "license": "Crossref lists the Elsevier open-access user license for the version of record from 2022-11-22; "
               "the spreadsheet is not redistributed, only this derived summary",
    "read_level": "full-text (article via r.jina.ai of PMC; supplement downloaded and parsed)",
    "not_in_data": "Cypselurus is not among the measured species; Cheilopogon furcatus is the measured four-wing genus",
}


def _num(x):
    return x if isinstance(x, (int, float)) else None


def summarise(xlsx: Path) -> dict:
    import openpyxl
    raw = xlsx.read_bytes()
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    rows = list(wb[SOURCE["sheet"]].iter_rows(values_only=True))
    header, data = rows[0], [r for r in rows[1:] if r and _num(r[4])]
    groups, species = defaultdict(list), defaultdict(list)
    sheet_ratio_mismatch = []
    for r in data:
        n, sp, grp, _cat, sl, pec, pel = r[:7]
        sl, pec, pel = _num(sl), _num(pec), _num(pel)
        groups[grp].append((sl, pec, pel))
        species[(grp, sp)].append((sl, pec, pel))
        if pel is not None and _num(r[8]) is not None and abs(r[8] - pel / sl) > 1e-6:
            sheet_ratio_mismatch.append({"specimen": n, "species": sp, "sheet_pelvic_over_sl": r[8],
                                         "recomputed": pel / sl})

    def stats(v):
        pr = [p / s for s, p, _ in v if p is not None]
        vr = [q / s for s, _, q in v if q is not None]
        return {"n": len(v), "sl_cm_range": [min(x[0] for x in v), max(x[0] for x in v)],
                "pectoral_over_sl": {"n": len(pr), "median": st.median(pr), "min": min(pr), "max": max(pr)},
                "pelvic_over_sl": {"n": len(vr), "median": st.median(vr), "min": min(vr), "max": max(vr)} if vr else None}
    return {"schema": "frontier.print.source_summary/1", "source": SOURCE,
            "xlsx_sha256": hashlib.sha256(raw).hexdigest(), "xlsx_bytes": len(raw), "header": list(header[:9]),
            "specimens": len(data), "sheet_ratio_mismatches": sheet_ratio_mismatch,
            "groups": {g: stats(v) for g, v in sorted(groups.items())},
            "species": {f"{g} | {s}": stats(v) for (g, s), v in sorted(species.items())}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--out", default="artifacts/print/sources/daane2021-S1A-summary.json")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summarise(Path(a.xlsx)), indent=2, sort_keys=True) + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
