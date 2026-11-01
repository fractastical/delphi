"""Shared loading, subset selection and coverage for the Kir2.1 evaluation.

Everything here is fixed by ``protocol.json``. The subset rule in particular
reads only variant *names*, so this module never touches a measured value while
deciding what to score.
"""

from __future__ import annotations

import hashlib
import json
import os

from connectors.bioservices import proteingym, uniprot

HERE = os.path.dirname(os.path.abspath(__file__))
PROTOCOL_PATH = os.path.join(HERE, "protocol.json")


def load_protocol() -> dict:
    with open(PROTOCOL_PATH) as fh:
        return json.load(fh)


def subset_key(salt: str, mutant: str) -> str:
    return hashlib.sha256(f"{salt}|{mutant}".encode()).hexdigest()


def select_subset(matched: list[str], salt: str, size: int) -> list[str]:
    """Deterministic hashed sample of variant names, independent of any value."""
    ordered = sorted(matched, key=lambda m: (subset_key(salt, m), m))
    return ordered[:size]


def load_assays(protocol: dict, data_dir: str) -> tuple[proteingym.Assay, proteingym.Assay, list[dict]]:
    """Load both assays and run the six reference checks of PROTOCOL.md §3.

    Returns the two assays and a list of check records. Checks 1-4 are enforced
    inside :func:`connectors.bioservices.proteingym.load_assay`, which raises; a
    record is emitted here saying so, because a check that passes silently and a
    check that never ran look identical in a report.
    """
    archive, archive_receipt = proteingym.fetch_archive(data_dir)
    checks: list[dict] = []

    surface = proteingym.load_assay(archive, protocol["data"]["assays"]["surface"]["id"])
    function = proteingym.load_assay(archive, protocol["data"]["assays"]["function"]["id"])
    checks.append({
        "check": "1-4 per-assay internal consistency",
        "detail": "uniform lengths; mutated position holds the mutant; non-mutated positions agree; "
                  "declared wild-type agrees with the reconstruction",
        "passed": True,
        "note": "enforced by load_assay, which raises ReferenceMismatch on any violation",
    })

    for name, assay in (("surface", surface), ("function", function)):
        expected = protocol["data"]["assays"][name]["sha256"]
        checks.append({
            "check": f"{name} member sha256 matches the frozen protocol",
            "expected": expected,
            "observed": assay.source_sha256,
            "passed": assay.source_sha256 == expected,
        })
        checks.append({
            "check": f"{name} row count matches the frozen protocol",
            "expected": protocol["data"]["assays"][name]["rows"],
            "observed": assay.n_rows,
            "passed": assay.n_rows == protocol["data"]["assays"][name]["rows"],
        })

    same_ref = surface.reference_sequence == function.reference_sequence
    checks.append({
        "check": "5 both assays reconstruct to the same reference",
        "passed": same_ref,
    })

    header, up_seq, up_receipt = uniprot.fetch_sequence(protocol["reference"]["accession"])
    comparison = uniprot.compare(surface.reference_sequence, up_seq)
    checks.append({
        "check": f"6 reference equals UniProtKB {protocol['reference']['accession']}",
        "passed": bool(comparison["identical"]),
        "detail": comparison,
        "uniprot_header": header,
    })
    checks.append({
        "check": "reference sha256 matches the frozen protocol",
        "expected": protocol["reference"]["sha256"],
        "observed": comparison["reference_sha256"],
        "passed": comparison["reference_sha256"] == protocol["reference"]["sha256"],
    })

    receipts = [archive_receipt.to_dict(), up_receipt.to_dict()]
    return surface, function, checks + [{"receipts": receipts}]


def orientation_check(assay: proteingym.Assay, archive: str) -> dict:
    """Confirm DMS_score is oriented so that higher means more wild-type-like.

    ProteinGym also ships ``DMS_score_bin``. If the mean score of the 1-bin is
    not above the mean of the 0-bin, the orientation assumption is wrong and a
    sign error would masquerade as a finding. This reads only the assay's own
    internal consistency, not the comparison under test.
    """
    import csv, io, zipfile

    with zipfile.ZipFile(archive) as zf:
        member = proteingym._member_name(archive, assay.assay_id)
        rows = list(csv.DictReader(io.StringIO(zf.read(member).decode("utf-8"))))
    hi = [float(r["DMS_score"]) for r in rows if r.get("DMS_score_bin") == "1"]
    lo = [float(r["DMS_score"]) for r in rows if r.get("DMS_score_bin") == "0"]
    if not hi or not lo:
        return {"assay": assay.assay_id, "passed": False, "reason": "DMS_score_bin absent or single-valued"}
    mean_hi, mean_lo = sum(hi) / len(hi), sum(lo) / len(lo)
    return {
        "assay": assay.assay_id,
        "n_bin1": len(hi), "n_bin0": len(lo),
        "mean_bin1": mean_hi, "mean_bin0": mean_lo,
        "passed": mean_hi > mean_lo,
        "interpretation": "higher DMS_score means more wild-type-like" if mean_hi > mean_lo
                          else "orientation is NOT as assumed; stop",
    }


def coverage(subset: list[str], matched: list[str], surface, function) -> dict:
    """How the 256-variant subset sits inside the 6,789-variant matched set."""
    import statistics

    def composition(keys, attr):
        out: dict[str, int] = {}
        for k in keys:
            out[getattr(surface.variants[k], attr)] = out.get(getattr(surface.variants[k], attr), 0) + 1
        return dict(sorted(out.items()))

    def dist(keys, assay):
        vals = [assay.variants[k].dms_score for k in keys]
        vals_sorted = sorted(vals)
        q = lambda f: vals_sorted[min(len(vals_sorted) - 1, int(f * len(vals_sorted)))]
        return {
            "n": len(vals), "mean": statistics.fmean(vals),
            "sd": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
            "min": vals_sorted[0], "q25": q(0.25), "median": q(0.50), "q75": q(0.75), "max": vals_sorted[-1],
        }

    sub_pos = sorted({surface.variants[k].position for k in subset})
    all_pos = sorted({surface.variants[k].position for k in matched})
    return {
        "subset_size": len(subset),
        "matched_size": len(matched),
        "subset_distinct_positions": len(sub_pos),
        "matched_distinct_positions": len(all_pos),
        "position_coverage_fraction": round(len(sub_pos) / len(all_pos), 4),
        "subset_position_range": [sub_pos[0], sub_pos[-1]],
        "matched_position_range": [all_pos[0], all_pos[-1]],
        "subset_wt_composition": composition(subset, "wt_aa"),
        "subset_mut_composition": composition(subset, "mut_aa"),
        "matched_wt_distinct": len({surface.variants[k].wt_aa for k in matched}),
        "subset_wt_distinct": len({surface.variants[k].wt_aa for k in subset}),
        "subset_mut_distinct": len({surface.variants[k].mut_aa for k in subset}),
        "score_distribution": {
            "surface_subset": dist(subset, surface), "surface_matched": dist(matched, surface),
            "function_subset": dist(subset, function), "function_matched": dist(matched, function),
        },
    }
