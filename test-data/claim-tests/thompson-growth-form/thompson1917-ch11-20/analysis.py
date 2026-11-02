#!/usr/bin/env python3
"""thompson1917-ch11-20: spherical septa need two radii from real straight cones.

The verdict rule was committed in result.json before this script retrieved anything.
It counts admissible tables of paired sectional radii. Models built to be minimal,
spacing angles, chamber volumes, and coiled-shell radii exposed before registration
do not count. If the count is zero, the verdict is inconclusive with reason
data-unavailable.

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

CANDIDATES = [
    {
        "id": "morphosource-cephalopod-ct",
        "url": "https://www.morphosource.org/",
        "admissible": False,
        "why": "Micro-CT download requires a login. A landing page is not a radius table.",
    },
    {
        "id": "lemanis-2016-peerj-septal-radii",
        "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5028744/",
        "admissible": False,
        "why": "Nautilus and Spirula are coiled shells, not straight cones with a perpendicular planar suture. A search snippet showed the radius table before registration, so it is excluded from the verdict and is not copied here.",
    },
    {
        "id": "lemanis-2020-figshare-minimum-curvature-models",
        "url": "https://doi.org/10.6084/m9.figshare.c.5141909",
        "admissible": False,
        "why": "Septal surfaces in that study were constructed as minimum-curvature surfaces. They cannot test whether real septa have that shape.",
    },
    {
        "id": "johnson-2021-dryad-printed-septa-pvmcvdnk6",
        "url": "https://datadryad.org/dataset/doi:10.5061/dryad.pvmcvdnk6",
        "admissible": False,
        "why": "The deposit is figures of 3D-printed theoretical septa, not radii measured on fossil septa.",
    },
    {
        "id": "hoffmann-kosmoceras-dryad-133nq",
        "url": "https://zenodo.org/records/5011159",
        "admissible": False,
        "why": "The readme lists conch diameters, expansion rates, septal spacing angles and chamber area and volume for one Kosmoceras. It does not list two radii of curvature.",
    },
    {
        "id": "ikuno-dryad-septal-spacing-bzkh189gp",
        "url": "https://datadryad.org/dataset/doi:10.5061/dryad.bzkh189gp",
        "admissible": False,
        "why": "Septal spacing is a rotational angle between septa, not a radius of curvature of the septal surface.",
    },
]


def probe(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; delphisci-claim-test/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            response.read(800)
            return {
                "http_status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "final_url": response.geturl(),
            }
    except urllib.error.HTTPError as exc:
        return {
            "http_status": exc.code,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "final_url": url,
            "error": str(exc),
        }
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
    if n_admissible > 0:
        raise RuntimeError("an admissible radius table appeared; the ratio test is not implemented because none was registered")
    verdict, reason = "inconclusive", "data-unavailable"
    measured = {
        "value": n_admissible,
        "unit": "admissible tables of paired septal radii",
        "n": 0,
        "uncertainty": None,
        "extra": {
            "candidates_checked": len(checked),
            "landing_pages_reached": reached,
            "septa_measured": 0,
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
        "No radius table was parsed. Admissibility follows the test contract: paired median "
        "and transverse radii of real straight-coned septa with a planar perpendicular attachment. "
        "Every candidate fails that constraint, so the septum count is zero and the verdict is "
        "inconclusive with reason data-unavailable."
    )
    result["results_summary"] = [
        f"{reached} of {len(checked)} landing pages responded; {n_admissible} admissible radius tables.",
        "No straight-cone septal radii were retrieved, so the spherical-cap ratio was not computed.",
    ]
    for key, value in frozen.items():
        if result.get(key) != value:
            raise RuntimeError(f"refusing to alter pre-registered field {key}")
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "n_admissible": n_admissible, "reached": reached}, indent=2))


if __name__ == "__main__":
    main()
