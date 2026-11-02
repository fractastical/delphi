#!/usr/bin/env python3
"""Measure reproductive mode of testaceans in SeaLifeBase slb/v26.06.

Implements the thresholds in result.json. Those thresholds are not changed here.
Downloads stay in the system temp directory and are not written into the repo.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
BASE = "https://data.source.coop/cboettig/fishbase/slb/v26.06/parquet/"
TABLES = {
    "species": "species.parquet",
    "species_hierarchy": "species_hierarchy.parquet",
    "reproduc": "reproduc.parquet",
    "larvae": "larvae.parquet",
}
CACHE = Path("/tmp/delphi-claim-tests/sealifebase-slb-v26.06")
UA = {"User-Agent": "Mozilla/5.0 DelphiClaimTest/1.0 (aristotle-ga03-27)"}

CLASSES = {
    "bivalvia",
    "gastropoda",
    "polyplacophora",
    "scaphopoda",
    "monoplacophora",
    "thecostraca",
    "cirripedia",
    "hexanauplia",
}
BARNACLE_ORDERS = (
    "cirripedia",
    "sessilia",
    "pedunculata",
    "balanomorpha",
    "lepadomorpha",
    "thoracica",
    "kentrogonida",
    "rhizocephala",
)
FOULING_GENERA = {
    "mytilus",
    "crassostrea",
    "ostrea",
    "magallana",
    "balanus",
    "amphibalanus",
    "semibalanus",
    "chthamalus",
    "crepidula",
    "dreissena",
    "perna",
    "saccostrea",
}
MODE_NEEDLES = ("repro", "fertil", "spawn", "larva", "egg", "guild")
MODE_BLOCK = ("ref", "author", "date", "remark")
SPONTANEOUS_RE = re.compile(r"spontaneous|abiogenesis|putref|from mud", re.I)
LETTER_RE = re.compile(r"[A-Za-z]")


def fetch(name: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    url = BASE + TABLES[name]
    path = CACHE / TABLES[name]
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as response, path.open("wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    data = path.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": retrieved_at,
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "path": str(path),
    }


def is_mode_column(name: str) -> bool:
    low = name.lower()
    return any(n in low for n in MODE_NEEDLES) and not any(b in low for b in MODE_BLOCK)


def class_key(value: object) -> str:
    text = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
    return text.strip().lower()


def in_named_class(class_name: str) -> bool:
    if class_name.startswith("cephalopoda"):
        return False
    for allowed in CLASSES:
        if class_name == allowed or class_name.startswith(allowed + " ") or class_name.startswith(allowed + "-") or class_name.startswith(allowed + "("):
            return True
    return False


def in_scope(class_name: str, order_name: str) -> bool:
    if class_name.startswith("cephalopoda"):
        return False
    if in_named_class(class_name):
        return True
    return any(token in order_name for token in BARNACLE_ORDERS)


def mode_text(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [c for c in frame.columns if is_mode_column(c)]
    if "SpecCode" not in frame.columns or not columns:
        return pd.DataFrame(columns=["SpecCode", "text"])
    pieces = []
    for column in columns:
        part = frame[["SpecCode", column]].dropna()
        part[column] = part[column].astype(str).str.strip()
        part = part[part[column].map(lambda s: bool(LETTER_RE.search(s)) and s.lower() not in {"nan", "none", "<na>"})]
        part = part.rename(columns={column: "text"})
        part["column"] = column
        pieces.append(part)
    if not pieces:
        return pd.DataFrame(columns=["SpecCode", "text"])
    long = pd.concat(pieces, ignore_index=True)
    grouped = (
        long.groupby("SpecCode")["text"]
        .apply(lambda s: " | ".join(sorted(set(s))))
        .reset_index()
    )
    return grouped


def main() -> None:
    files = {name: fetch(name) for name in TABLES}
    species = pd.read_parquet(files["species"]["path"], columns=["SpecCode", "Genus", "Species", "FamCode"])
    hierarchy = pd.read_parquet(
        files["species_hierarchy"]["path"],
        columns=["FamCode", "Family", "Order", "Class", "Phylum"],
    )
    hierarchy = hierarchy.drop_duplicates(subset=["FamCode"])
    reproduc = pd.read_parquet(files["reproduc"]["path"])
    larvae = pd.read_parquet(files["larvae"]["path"])

    taxa = species.merge(hierarchy, on="FamCode", how="left")
    taxa["class_key"] = taxa["Class"].map(class_key)
    taxa["order_key"] = taxa["Order"].map(class_key)
    taxa["in_scope"] = [
        in_scope(c, o) for c, o in zip(taxa["class_key"], taxa["order_key"])
    ]
    scope = taxa.loc[taxa["in_scope"], ["SpecCode", "Genus", "Species", "Family", "Order", "Class", "Phylum"]].copy()

    repro_text = mode_text(reproduc).rename(columns={"text": "repro_text"})
    larva_text = mode_text(larvae).rename(columns={"text": "larva_text"})
    scored = scope.merge(repro_text, on="SpecCode", how="left").merge(larva_text, on="SpecCode", how="left")
    scored["repro_text"] = scored["repro_text"].fillna("")
    scored["larva_text"] = scored["larva_text"].fillna("")
    scored["text"] = (scored["repro_text"] + " | " + scored["larva_text"]).str.strip(" |")
    scored = scored[scored["text"].str.len() > 0].copy()
    scored["spontaneous"] = scored["text"].map(lambda s: bool(SPONTANEOUS_RE.search(s)))
    scored["parental"] = ~scored["spontaneous"]

    n_in_scope = int(len(scope))
    n_scored = int(len(scored))
    n_parental = int(scored["parental"].sum())
    n_spontaneous = int(scored["spontaneous"].sum())
    share = (n_parental / n_scored) if n_scored else None

    if n_scored < 30:
        verdict = "inconclusive"
        reason = "underpowered"
    elif share <= 0.05:
        verdict = "supports"
        reason = None
    elif share >= 0.50:
        verdict = "refutes"
        reason = None
    else:
        verdict = "mixed"
        reason = None

    by_class = (
        scope.groupby(["Phylum", "Class"], dropna=False)
        .size()
        .rename("n_in_scope")
        .reset_index()
        .merge(
            scored.groupby(["Phylum", "Class"], dropna=False)
            .agg(n_scored=("SpecCode", "size"), n_parental=("parental", "sum"), n_spontaneous=("spontaneous", "sum"))
            .reset_index(),
            on=["Phylum", "Class"],
            how="left",
        )
        .fillna({"n_scored": 0, "n_parental": 0, "n_spontaneous": 0})
    )
    for column in ("n_scored", "n_parental", "n_spontaneous"):
        by_class[column] = by_class[column].astype(int)
    by_class = by_class.sort_values(["n_in_scope", "Class"], ascending=[False, True])

    fouling = scope[scope["Genus"].fillna("").str.lower().isin(FOULING_GENERA)].merge(
        scored[["SpecCode", "parental", "spontaneous", "text"]],
        on="SpecCode",
        how="left",
    )
    fouling["status"] = "unscored"
    fouling.loc[fouling["parental"] == True, "status"] = "parental"  # noqa: E712
    fouling.loc[fouling["spontaneous"] == True, "status"] = "spontaneous"  # noqa: E712

    in_scope_ids = set(scope["SpecCode"])
    value_counts = []
    for label, frame in (("reproduc", reproduc), ("larvae", larvae)):
        in_scope_rows = frame[frame["SpecCode"].isin(in_scope_ids)].copy()
        for column in [c for c in in_scope_rows.columns if is_mode_column(c)]:
            part = in_scope_rows[["SpecCode", column]].dropna()
            part[column] = part[column].astype(str).str.strip()
            part = part[part[column].map(lambda s: bool(LETTER_RE.search(s)))]
            if part.empty:
                continue
            grouped = part.groupby(column).agg(n_rows_in_scope=(column, "size"), n_species_in_scope=("SpecCode", "nunique"))
            for value, row in grouped.iterrows():
                value_counts.append({
                    "table": label,
                    "column": column,
                    "value": value,
                    "n_rows_in_scope": int(row["n_rows_in_scope"]),
                    "n_species_in_scope": int(row["n_species_in_scope"]),
                })

    derived = HERE / "derived"
    derived.mkdir(exist_ok=True)
    by_class.to_csv(derived / "by_class.csv", index=False)
    fouling.sort_values(["Genus", "Species"]).to_csv(derived / "fouling.csv", index=False)
    pd.DataFrame(value_counts).to_csv(derived / "mode_values.csv", index=False)

    repro_only = int((scored["repro_text"].str.len() > 0).sum())
    larva_only_mask = (scored["larva_text"].str.len() > 0) & (scored["repro_text"].str.len() == 0)
    larva_only = int(larva_only_mask.sum())
    larva_only_names = [
        f"{g} {s}"
        for g, s in scored.loc[larva_only_mask, ["Genus", "Species"]].itertuples(index=False)
    ]
    not_gastropod = scored["Class"].map(class_key) != "gastropoda"
    shell_less = {
        "nudibranchia",
        "sacoglossa",
        "cephalaspidea",
        "anaspidea",
        "aplysiida",
        "gymnosomata",
        "pleurobranchida",
        "pleurobranchomorpha",
        "acochlidiacea",
        "rhodopemorpha",
        "runcinida",
        "umbraculida",
    }
    shelled_mask = ~scored["Order"].map(class_key).isin(shell_less)
    fouling_scored = fouling[fouling["status"] != "unscored"]

    def species_with_value(frame: pd.DataFrame, column: str, value: str) -> int:
        if column not in frame.columns:
            return 0
        hit = frame[["SpecCode", column]].dropna()
        hit = hit[hit["SpecCode"].isin(in_scope_ids)]
        hit[column] = hit[column].astype(str).str.strip()
        return int(hit.loc[hit[column] == value, "SpecCode"].nunique())
    measured = {
        "value": None if share is None else round(share, 6),
        "unit": "share of scored testacean species with a parental reproductive mode",
        "n": n_scored,
        "uncertainty": None,
        "extra": {
            "n_in_scope": n_in_scope,
            "n_parental": n_parental,
            "n_spontaneous": n_spontaneous,
            "share_parental": None if share is None else round(share, 6),
            "n_scored_with_reproduc_text": repro_only,
            "n_scored_larvae_only": larva_only,
            "n_fouling_species_in_scope": int(len(fouling)),
            "n_fouling_scored": int(len(fouling_scored)),
            "n_fouling_parental": int((fouling_scored["status"] == "parental").sum()) if len(fouling_scored) else 0,
            "n_scored_excluding_gastropoda": int(not_gastropod.sum()),
            "n_parental_excluding_gastropoda": int(scored.loc[not_gastropod, "parental"].sum()),
            "n_scored_excluding_shell_less_orders": int(shelled_mask.sum()),
            "n_parental_excluding_shell_less_orders": int(scored.loc[shelled_mask, "parental"].sum()),
            "n_in_scope_repromode_dioecism": species_with_value(reproduc, "ReproMode", "dioecism"),
            "n_in_scope_repromode_protandry": species_with_value(reproduc, "ReproMode", "protandry"),
            "n_in_scope_repromode_protogyny": species_with_value(reproduc, "ReproMode", "protogyny"),
            "n_in_scope_repromode_hermaphroditism": species_with_value(reproduc, "ReproMode", "true hermaphroditism"),
            "n_in_scope_repromode_parthenogenesis": species_with_value(reproduc, "ReproMode", "parthenogenesis"),
            "n_in_scope_repromode_binary_fission": species_with_value(reproduc, "ReproMode", "binary fission"),
            "n_in_scope_fertilization_external": species_with_value(reproduc, "Fertilization", "external"),
            "n_in_scope_fertilization_internal": species_with_value(reproduc, "Fertilization", "internal (oviduct)"),
            "larva_only_names": larva_only_names,
            "verdict_from_criteria": verdict,
            "reason": reason,
        },
    }
    payload = {"files": files, "measured": measured, "verdict": verdict, "reason": reason}
    public = json.loads(json.dumps(payload))
    for item in public["files"].values():
        item.pop("path", None)
    (derived / "measured.json").write_text(json.dumps(public, indent=2) + "\n")
    print(json.dumps(public, indent=2))


if __name__ == "__main__":
    main()
