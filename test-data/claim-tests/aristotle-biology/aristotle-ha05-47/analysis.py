#!/usr/bin/env python3
"""Test aristotle-ha05-47 against the Zimin et al. squamate reproductive-mode table.

The published file is a RAR5 archive. Extraction uses `unar` when it is on
PATH (The Unarchiver), which reads RAR5. Python's standard library does not.
"""

import hashlib
import json
import shutil
import ssl
import subprocess
import tempfile
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

URL = "https://zenodo.org/records/7144760/files/Appendix_S1.rar?download=1"
HERE = Path(__file__).resolve().parent
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "DelphiClaimTest/1.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
        data = resp.read()
        retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return data, retrieved


def col_index(ref):
    col = ""
    for ch in ref:
        if ch.isalpha():
            col += ch
        else:
            break
    n = 0
    for ch in col:
        n = n * 26 + ord(ch.upper()) - 64
    return n - 1


def load_sheet_rows(xlsx_path):
    with zipfile.ZipFile(xlsx_path) as zf:
        shared = []
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    rows = {}
    for cell in sheet.iter(f"{NS}c"):
        ref = cell.attrib.get("r")
        if not ref:
            continue
        ci = col_index(ref)
        ri = int("".join(ch for ch in ref if ch.isdigit()))
        kind = cell.attrib.get("t")
        vnode = cell.find(f"{NS}v")
        if kind == "s" and vnode is not None and vnode.text is not None:
            val = shared[int(vnode.text)]
        elif vnode is not None and vnode.text is not None:
            val = vnode.text
        else:
            val = ""
        rows.setdefault(ri, {})[ci] = val
    header = [rows[1].get(i, "") for i in range(max(rows[1]) + 1)]
    out = []
    for ri in range(2, max(rows) + 1):
        raw = rows.get(ri, {})
        out.append({header[i]: raw.get(i, "") for i in range(len(header))})
    return out


def proportion(flags):
    if not flags:
        return None
    return sum(flags) / len(flags)


def main():
    unar = shutil.which("unar")
    if not unar:
        raise SystemExit("unar is required to extract the RAR5 archive")
    data, retrieved = fetch(URL)
    with tempfile.TemporaryDirectory() as tmp:
        rar_path = Path(tmp) / "Appendix_S1.rar"
        rar_path.write_bytes(data)
        subprocess.run(
            [unar, "-q", "-f", "-o", tmp, str(rar_path), "species_level_data.xlsx"],
            check=True,
            capture_output=True,
        )
        xlsx = next(Path(tmp).rglob("species_level_data.xlsx"))
        xlsx_bytes = xlsx.read_bytes()
        rows = load_sheet_rows(xlsx)

    snakes = [r for r in rows if (r.get("what") or "").strip().lower() == "snake"]

    def mode_of(row):
        raw = (row.get("reproduction") or "").strip()
        if raw == "0":
            return "oviparous"
        if raw == "1":
            return "viviparous"
        if raw == "2":
            return "mixed"
        return "missing"

    def is_observed(row):
        return (row.get("source.reproductive.mode") or "").strip().lower() == "not imputed"

    def tally(subset):
        vipera = []
        other = []
        for row in subset:
            species = (row.get("Species.Aug2020") or "").strip()
            genus = species.split()[0] if species else ""
            mode = mode_of(row)
            if mode == "missing":
                continue
            target = vipera if genus == "Vipera" else other
            target.append(mode)
        return vipera, other

    # Primary counts use snakes whose reproductive mode was not phylogenetically
    # imputed. An imputed code is a prediction, not a record of that species.
    # Mixed (code 2) stays in the denominator and counts as neither mode.
    vipera_modes, other_modes = tally([r for r in snakes if is_observed(r)])
    vipera_live = proportion([m == "viviparous" for m in vipera_modes])
    other_egg = proportion([m == "oviparous" for m in other_modes])
    n_vipera = len(vipera_modes)
    n_other = len(other_modes)
    all_v, all_o = tally(snakes)
    all_live = proportion([m == "viviparous" for m in all_v])
    all_egg = proportion([m == "oviparous" for m in all_o])
    imputed = sum(1 for r in snakes if mode_of(r) != "missing" and not is_observed(r))

    # Litter size and parturition duration are not columns of this table.
    columns = set(rows[0].keys()) if rows else set()
    litter_columns = [c for c in columns if "litter" in c.lower() or "clutch" in c.lower() or "fecund" in c.lower()]

    if n_vipera < 3 or n_other < 50:
        verdict, reason = "inconclusive", "underpowered"
    elif vipera_live is not None and vipera_live < 0.50:
        verdict, reason = "refutes", None
    elif (
        vipera_live is not None
        and vipera_live >= 0.80
        and other_egg is not None
        and other_egg >= 0.80
    ):
        verdict, reason = "supports", None
    elif vipera_live is not None and vipera_live >= 0.80 and other_egg is not None and other_egg < 0.80:
        verdict, reason = "mixed", None
    else:
        verdict, reason = "mixed", None

    family_counts = Counter(
        (r.get("family") or "")
        for r in snakes
        if is_observed(r)
        and mode_of(r) == "viviparous"
        and (r.get("Species.Aug2020") or "").split()[:1] != ["Vipera"]
    )

    measured = {
        "value": vipera_live,
        "unit": "proportion of genus Vipera species that are viviparous",
        "n": n_vipera,
        "uncertainty": None,
        "extra": {
            "vipera_viviparous_proportion": vipera_live,
            "n_vipera_scored": n_vipera,
            "vipera_mode_counts": dict(Counter(vipera_modes)),
            "other_snakes_oviparous_proportion": other_egg,
            "n_other_snakes_scored": n_other,
            "other_snake_mode_counts": dict(Counter(other_modes)),
            "imputed_snake_rows_excluded": imputed,
            "all_rows_including_imputed_vipera_viviparous_proportion": all_live,
            "all_rows_including_imputed_n_vipera": len(all_v),
            "all_rows_including_imputed_other_snakes_oviparous_proportion": all_egg,
            "all_rows_including_imputed_n_other": len(all_o),
            "litter_columns": litter_columns,
            "litter_size": "untested",
            "parturition_duration": "untested",
            "births_one_at_a_time": "untested",
            "viviparous_other_snake_families_top": family_counts.most_common(8),
            "verdict_from_criteria": verdict,
            "reason": reason,
        },
    }
    out = {
        "retrieved_at": retrieved,
        "archive_byte_size": len(data),
        "archive_sha256": hashlib.sha256(data).hexdigest(),
        "xlsx_byte_size": len(xlsx_bytes),
        "xlsx_sha256": hashlib.sha256(xlsx_bytes).hexdigest(),
        "n_rows": len(rows),
        "n_snakes": len(snakes),
        "measured": measured,
    }
    derived = HERE / "derived"
    derived.mkdir(exist_ok=True)
    (derived / "measured.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
