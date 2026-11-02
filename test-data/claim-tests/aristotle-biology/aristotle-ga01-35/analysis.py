#!/usr/bin/env python3
"""Test aristotle-ga01-35 against FishBase reproduction modes.

Thresholds are locked to result.json. The script downloads the snapshot,
counts species, and writes measured, verdict, and derived/measured.json.
It does not edit the pre-registered criteria.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DERIVED = HERE / "derived" / "measured.json"

REPRODUC_URL = "https://data.source.coop/cboettig/fishbase/fb/v26.06/parquet/reproduc.parquet"
SPECIES_URL = "https://data.source.coop/cboettig/fishbase/fb/v26.06/parquet/species.parquet"

EXPECTED_THRESHOLDS = {
    "min_classified_species": 100,
    "refute_min_nonseparate_species": 10,
    "high_confidence_min_nonseparate_species": 50,
    "documented_vocabulary_min_fraction": 0.9,
    "other_species_confidence_cap_fraction": 0.1,
}

DOCUMENTED = {
    "dioecism",
    "protandry",
    "protogyny",
    "true hermaphroditism",
    "parthenogenesis",
}

LOCKED = [
    "claim_id",
    "claim_iri",
    "project",
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "thresholds",
    "test_contract",
    "interpretation",
    "preregistered_at",
    "created",
    "agent",
]


def fetch(url: str, dest: Path) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "delphi-claim-test/aristotle-ga01-35"})
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    h = hashlib.sha256()
    nbytes = 0
    with urllib.request.urlopen(req, timeout=180) as resp, dest.open("wb") as out:
        final = resp.geturl()
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            h.update(chunk)
            nbytes += len(chunk)
    return {
        "download_url": url,
        "final_url": final,
        "retrieved_at": retrieved,
        "byte_size": nbytes,
        "sha256": h.hexdigest(),
    }


def norm(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def classify(value: str):
    v = norm(value)
    if not v:
        return None
    if any(s in v for s in ("protand", "protogyn", "hermaphrod", "parthenogen")):
        return "nonseparate"
    if v.startswith("dioec") or v in {"gonochorism", "gonochoristic", "dioecism", "dioecious"}:
        return "separate"
    return "other"


def pick_column(names, *preds):
    for pred in preds:
        for name in names:
            if pred(name):
                return name
    return None


def load_result():
    result = json.loads(RESULT.read_text())
    if result.get("thresholds") != EXPECTED_THRESHOLDS:
        sys.exit("thresholds in result.json do not match the locked constants in analysis.py")
    return result


def main() -> None:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        sys.exit("pyarrow is required to read the FishBase parquet snapshot")

    result = load_result()
    locked = {k: result.get(k) for k in LOCKED}
    original_caveats = list(result.get("caveats") or [])

    with tempfile.TemporaryDirectory(prefix="aristotle-ga01-35-") as tmp:
        tmp = Path(tmp)
        repro_path = tmp / "reproduc.parquet"
        species_path = tmp / "species.parquet"
        repro_meta = fetch(REPRODUC_URL, repro_path)
        species_meta = None
        species_error = None
        try:
            species_meta = fetch(SPECIES_URL, species_path)
        except Exception as exc:  # names are not required for the verdict
            species_error = str(exc)

        table = pq.read_table(repro_path)
        names = list(table.column_names)
        spec_col = pick_column(
            names,
            lambda n: n == "SpecCode",
            lambda n: n.lower() == "speccode",
        )
        mode_col = pick_column(
            names,
            lambda n: n == "Mode",
            lambda n: n.lower() == "mode",
            lambda n: "mode" in n.lower() and "model" not in n.lower(),
        )
        if spec_col is None or mode_col is None:
            finish(
                result,
                locked,
                original_caveats,
                repro_meta,
                species_meta,
                verdict="inconclusive",
                reason="data-unavailable",
                confidence=0.35,
                measured=empty_measured(),
                summary=[
                    "SpecCode or Mode could not be identified.",
                    "Columns seen: " + ", ".join(names),
                ],
                extra={"columns": names, "species_table_error": species_error},
                deviations=[],
            )
            return

        cols = table.select([spec_col, mode_col]).to_pydict()
        codes = cols[spec_col]
        modes = cols[mode_col]
        by_species = {}
        value_counts = {}
        alphabetic = 0
        nonblank_values = 0
        for code, mode in zip(codes, modes):
            if code is None or str(code).strip() == "":
                continue
            key = str(code).strip()
            label = classify(mode)
            raw = norm(mode)
            if raw:
                nonblank_values += 1
                value_counts[raw] = value_counts.get(raw, 0) + 1
                if any(c.isalpha() for c in raw):
                    alphabetic += 1
            if label is None:
                continue
            by_species.setdefault(key, set()).add(label)

        if alphabetic == 0:
            finish(
                result,
                locked,
                original_caveats,
                repro_meta,
                species_meta,
                verdict="inconclusive",
                reason="data-unavailable",
                confidence=0.35,
                measured=empty_measured(),
                summary=["The Mode column has no alphabetic values, so the documented text vocabulary was not applied."],
                extra={"mode_column": mode_col, "spec_column": spec_col, "columns": names},
                deviations=[
                    {
                        "date": "2026-11-01",
                        "change": "none to the thresholds",
                        "note": "Mode column was not the documented text vocabulary.",
                    }
                ],
            )
            return

        nonseparate = []
        separate_n = 0
        other_n = 0
        for key, labels in by_species.items():
            if "nonseparate" in labels:
                nonseparate.append(key)
            elif "separate" in labels:
                separate_n += 1
            elif "other" in labels:
                other_n += 1
        h = len(nonseparate)
        n_classified = h + separate_n
        species_with_mode = h + separate_n + other_n
        documented_n = sum(value_counts.get(v, 0) for v in DOCUMENTED)
        vocab_fraction = (documented_n / nonblank_values) if nonblank_values else 0.0
        other_fraction = (other_n / species_with_mode) if species_with_mode else 0.0

        names_by_code = {}
        if species_meta is not None:
            st = pq.read_table(species_path)
            s_names = list(st.column_names)
            s_spec = pick_column(s_names, lambda n: n == "SpecCode", lambda n: n.lower() == "speccode")
            genus = pick_column(s_names, lambda n: n == "Genus", lambda n: n.lower() == "genus")
            species = pick_column(s_names, lambda n: n == "Species", lambda n: n.lower() == "species")
            if s_spec and genus and species:
                sd = st.select([s_spec, genus, species]).to_pydict()
                for code, g, s in zip(sd[s_spec], sd[genus], sd[species]):
                    if code is None:
                        continue
                    binomial = " ".join(p for p in (norm_keep(g), norm_keep(s)) if p)
                    if binomial:
                        names_by_code.setdefault(str(code).strip(), binomial)

        # Mode breakdown among non-separate species, from the raw strings.
        nonsep_modes = {}
        code_set = set(nonseparate)
        for code, mode in zip(codes, modes):
            if code is None or str(code).strip() not in code_set:
                continue
            label = classify(mode)
            if label == "nonseparate":
                raw = norm(mode)
                nonsep_modes[raw] = nonsep_modes.get(raw, 0) + 1

        examples = []
        for code in nonseparate:
            if len(examples) >= 15:
                break
            examples.append({"spec_code": code, "name": names_by_code.get(code)})

        th = EXPECTED_THRESHOLDS
        if n_classified < th["min_classified_species"] or h == 0:
            verdict, reason = "inconclusive", "underpowered"
            confidence = 0.35
        elif h >= th["refute_min_nonseparate_species"]:
            verdict, reason = "refutes", None
            if other_fraction > th["other_species_confidence_cap_fraction"]:
                confidence = 0.55
            elif h >= th["high_confidence_min_nonseparate_species"] and vocab_fraction >= th["documented_vocabulary_min_fraction"]:
                confidence = 0.80
            else:
                confidence = 0.65
        elif 1 <= h <= 9:
            verdict, reason = "mixed", None
            confidence = 0.45
        else:
            verdict, reason = "inconclusive", "other"
            confidence = 0.35

        measured = {
            "value": h,
            "unit": "fish species with a non-separate reproductive mode",
            "n": n_classified,
            "uncertainty": None,
            "extra": {
                "separate_species": separate_n,
                "other_species": other_n,
                "nonblank_mode_values": nonblank_values,
                "documented_vocabulary_fraction": round(vocab_fraction, 6),
                "other_species_fraction": round(other_fraction, 6),
                "mode_value_counts": dict(sorted(value_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
                "nonseparate_mode_row_counts": nonsep_modes,
                "example_nonseparate_species": examples,
                "mode_column": mode_col,
                "spec_column": spec_col,
                "species_names_joined": species_meta is not None and bool(names_by_code),
                "species_table_error": species_error,
            },
        }
        summary = [
            f"Classified species (separate or non-separate): {n_classified}. Non-separate: {h}. Separate: {separate_n}. Other: {other_n}.",
            f"Non-blank mode values in the documented five-word vocabulary: {documented_n} of {nonblank_values} ({vocab_fraction:.4f}).",
            "Mode value counts: " + ", ".join(f"{k}={v}" for k, v in sorted(value_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:12]) + ".",
        ]
        deviations = []
        if mode_col != "Mode":
            deviations.append(
                {
                    "date": "2026-11-01",
                    "change": "column name only",
                    "note": (
                        f"The snapshot has no column named Mode. The pre-registered fallback "
                        f"(a name containing mode and not model) selected {mode_col}. "
                        "Thresholds were not changed."
                    ),
                }
            )
        finish(
            result,
            locked,
            original_caveats,
            repro_meta,
            species_meta,
            verdict=verdict,
            reason=reason,
            confidence=confidence,
            measured=measured,
            summary=summary,
            extra=None,
            deviations=deviations,
        )


def norm_keep(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def empty_measured():
    return {
        "value": None,
        "unit": "fish species with a non-separate reproductive mode",
        "n": 0,
        "uncertainty": None,
        "extra": {},
    }


def finish(result, locked, original_caveats, repro_meta, species_meta, verdict, reason, confidence, measured, summary, extra, deviations):
    if extra:
        measured = dict(measured)
        measured["extra"] = {**measured.get("extra", {}), **extra}
    files = [
        {
            "name": "reproduc.parquet",
            "download_url": repro_meta["download_url"],
            "final_url": repro_meta["final_url"],
            "retrieved_at": repro_meta["retrieved_at"],
            "byte_size": repro_meta["byte_size"],
            "sha256": repro_meta["sha256"],
        }
    ]
    if species_meta is not None:
        files.append(
            {
                "name": "species.parquet",
                "download_url": species_meta["download_url"],
                "final_url": species_meta["final_url"],
                "retrieved_at": species_meta["retrieved_at"],
                "byte_size": species_meta["byte_size"],
                "sha256": species_meta["sha256"],
                "role_note": "Joined for binomials of example species only. Not used in the count and not committed (over 1 MB).",
            }
        )
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "fishbase-reproduc-v26.06",
            "name": "FishBase reproduction table, parquet snapshot fb/v26.06",
            "landing_url": "https://source.coop/cboettig/fishbase",
            "doi": None,
            "version": "fb/v26.06",
            "license": "CC-BY-NC (FishBase.org Team, as stated on the Source Cooperative dataset card)",
            "files": files,
            "role": "reproductive mode of fishes, counted as distinct SpecCode",
        }
    ]
    result["measured"] = measured
    result["method"] = (
        "Downloaded the pinned FishBase v26.06 reproduc parquet, hashed it, and classified each "
        "SpecCode from its Mode strings using the pre-registered substring rules. "
        "Distinct species, not rows, were counted. The species parquet was joined only to name "
        "examples and was not used in the verdict. The decision rule in fail_criterion was applied unchanged."
    )
    result["results_summary"] = summary
    result["caveats"] = original_caveats
    if deviations:
        result["deviations"] = deviations
    for key, value in locked.items():
        if result.get(key) != value:
            sys.exit(f"locked field changed: {key}")
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    DERIVED.write_text(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured, "results_summary": summary}, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "value": measured.get("value"), "n": measured.get("n")}, indent=2))


if __name__ == "__main__":
    main()
