#!/usr/bin/env python3
"""thompson1917-ch11-16: coaxial growth lines need a plan-view coordinate table.

The verdict rule was committed in result.json before this script retrieved anything.
It counts admissible coordinate tables. Adult dimensions, single outlines, shell
sections and login-gated scans are not admissible. If the count is zero, the
verdict is inconclusive with reason data-unavailable.

Run: python3 analysis.py
Uses only the Python standard library.
"""

import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DERIVED = HERE / "derived"

# Landing pages checked for a plan-view growth-line coordinate table.
# admissibility is fixed by the test contract, not by numbers inside the files.
CANDIDATES = [
    {
        "id": "morphosource-shell-media",
        "url": "https://www.morphosource.org/",
        "admissible": False,
        "why": "Media download requires a login. A landing page is not a coordinate table.",
    },
    {
        "id": "de-winter-2017-oyster-section-zenodo-1045192",
        "url": "https://zenodo.org/records/1045192",
        "admissible": False,
        "why": "The deposit is a longitudinal cross-section of one Magallana gigas shell, not plan-view growth lines of a valve.",
    },
    {
        "id": "pangaea-neubauer-2013-venerid-outlines-810112",
        "url": "https://doi.pangaea.de/10.1594/PANGAEA.810112",
        "admissible": False,
        "why": "One adult outline per venerid valve. A single curve cannot separate coaxial from concentric lines.",
    },
    {
        "id": "vihtakari-sclero-shellspots",
        "url": "https://rdrr.io/cran/sclero/man/shellspots.html",
        "admissible": False,
        "why": "The documented object is growth lines on a bivalve shell section, one specimen, not a plan-view family.",
    },
    {
        "id": "shackleton-scallop-landmarks-dryad-j4n09",
        "url": "https://datadryad.org/dataset/doi:10.5061/dryad.j4n09",
        "admissible": False,
        "why": "Adult scallop landmark coordinates, not successive growth lines.",
    },
    {
        "id": "taylor-el-dornajo-shell-measurements",
        "url": "https://www.cadb.pitt.edu/taylor/shellmeasurements.html",
        "admissible": False,
        "why": "Archaeological length and height of valves. Linear dimensions are not a family of growth lines.",
    },
]


def probe(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; delphisci-claim-test/1.0)"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            # Read a short prefix so the status is real, and do not parse measurements.
            response.read(800)
            return {
                "http_status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "final_url": response.geturl(),
            }
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code, "content_type": exc.headers.get("Content-Type") if exc.headers else None, "final_url": url, "error": str(exc)}
    except Exception as exc:
        return {"http_status": None, "error": f"{type(exc).__name__}: {exc}", "final_url": url}


def main():
    checked = []
    for candidate in CANDIDATES:
        row = dict(candidate)
        row["probe"] = probe(candidate["url"])
        row["probed_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        checked.append(row)
    n_admissible = sum(1 for row in checked if row["admissible"])
    reached = sum(1 for row in checked if row["probe"].get("http_status") and 200 <= row["probe"]["http_status"] < 400)
    verdict = "inconclusive"
    reason = "data-unavailable"
    # The contract allows a supports/refutes verdict only when n_admissible tables
    # supply at least 8 valves. None of the registered candidates is admissible.
    if n_admissible > 0:
        raise RuntimeError("an admissible table appeared; the geometric fit is not implemented because none was registered")
    measured = {
        "value": n_admissible,
        "unit": "admissible plan-view growth-line coordinate tables",
        "n": 0,
        "uncertainty": None,
        "extra": {
            "candidates_checked": len(checked),
            "landing_pages_reached": reached,
            "valves_measured": 0,
            "candidates": [
                {
                    "id": row["id"],
                    "url": row["url"],
                    "admissible": row["admissible"],
                    "why": row["why"],
                    "http_status": row["probe"].get("http_status"),
                    "final_url": row["probe"].get("final_url"),
                }
                for row in checked
            ],
        },
    }
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({"measured": measured, "verdict": verdict, "reason": reason}, indent=2) + "\n")

    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    frozen_keys = ("hypothesis", "pass_criterion", "fail_criterion", "planned_datasets", "test_contract", "interpretation")
    frozen = {k: result.get(k) for k in frozen_keys}
    result["status"] = "complete"
    result["verdict"] = verdict
    result["reason"] = reason
    result["data_kind"] = "none"
    result["confidence"] = 0.8
    result["measured"] = measured
    result["datasets"] = [
        {
            "id": row["id"],
            "name": row["id"],
            "landing_url": row["url"],
            "doi": None,
            "version": None,
            "license": None,
            "files": [],
            "role": "checked and not used: " + row["why"],
        }
        for row in checked
    ]
    result["method"] = (
        "Requested each pre-registered landing page and recorded the HTTP status. "
        "No coordinate file was parsed. Admissibility follows the test contract: a plan-view "
        "table of at least three growth lines per valve, already published as coordinates. "
        "Every candidate fails that constraint, so the valve count is zero and the verdict is "
        "inconclusive with reason data-unavailable."
    )
    result["results_summary"] = [
        f"{reached} of {len(checked)} landing pages responded; {n_admissible} admissible coordinate tables.",
        "No plan-view growth-line coordinates were retrieved, so coaxial and concentric models were not fit.",
    ]
    for key, value in frozen.items():
        if result.get(key) != value:
            raise RuntimeError(f"refusing to alter pre-registered field {key}")
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "n_admissible": n_admissible, "reached": reached}, indent=2))


if __name__ == "__main__":
    main()
