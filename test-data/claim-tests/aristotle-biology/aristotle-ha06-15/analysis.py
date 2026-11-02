"""Test aristotle-ha06-15 against the FishBase reproduction page for Mustelus mustelus.

Run from the repo root or this directory: python3 analysis.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _fetch

HERE = Path(__file__).resolve().parent
SUMMARY = "https://fishbase.se/summary/Mustelus-mustelus"
REPRO = "https://fishbase.se/Reproduction/Mustelus_mustelus"


def cell_after(html, label):
    """Text of the table cell that follows a row label."""
    match = re.search(
        rf"{re.escape(label)}.*?</td>\s*<td[^>]*>(.*?)</td>",
        html,
        flags=re.I | re.S,
    )
    if not match:
        return ""
    text = re.sub(r"<[^>]+>", " ", match.group(1))
    text = re.sub(r"&nbsp;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def main():
    summary = _fetch.fetch(SUMMARY)
    repro = _fetch.fetch(REPRO)
    summary_html = summary["data"].decode("utf-8", "replace")
    repro_html = repro["data"].decode("utf-8", "replace")
    if "Mustelus mustelus" not in summary_html or "Mustelus mustelus" not in repro_html:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.5
        description, guild = "", ""
    else:
        reason = None
        guild = cell_after(repro_html, "Reproductive guild")
        description = cell_after(repro_html, "Description of life cycle and mating behavior")
        low = f"{guild} {description}".lower()
        viviparous = ("viviparous" in low) or ("internal live bearer" in low) or ("live bearers" in low)
        placenta = any(phrase in low for phrase in ("yolk-sac placenta", "yolk sac placenta", "placenta", "umbilical", "navel-string", "navel string"))
        aplacental = ("aplacental" in low) or ("no placenta" in low) or ("without a placenta" in low)
        oviparous = ("oviparous" in low) and not viviparous
        chorion = "chorion" in low
        membranes = "membrane" in low
        if not description:
            verdict, reason, confidence = "inconclusive", "data-unavailable", 0.5
        elif oviparous or (aplacental and not placenta):
            verdict, confidence = "refutes", 0.80
        elif viviparous and placenta and not (aplacental and "yolk-sac placenta" not in low and "yolk sac placenta" not in low):
            verdict, confidence = "supports", 0.86
        elif viviparous and not placenta:
            verdict, confidence = "mixed", 0.7
        else:
            verdict, reason, confidence = "inconclusive", "other", 0.4
    litter = re.search(r"(\d+)\s+to\s+(\d+)", description or "")
    birth = re.search(r"(\d+)\s*cm", description or "")
    smooth = "Smooth-hound" in summary_html or "smooth-hound" in summary_html.lower()
    measured = {
        "value": 1 if verdict == "supports" else 0,
        "unit": "placental-attachment-stated",
        "n": 1,
        "uncertainty": None,
        "extra": {
            "reproductive_guild": guild,
            "life_cycle": description,
            "common_name_smooth_hound": smooth,
            "chorion_mentioned": "chorion" in (description or "").lower(),
            "membrane_mentioned": "membrane" in (description or "").lower(),
            "litter_min": int(litter.group(1)) if litter else None,
            "litter_max": int(litter.group(2)) if litter else None,
            "size_at_birth_cm": int(birth.group(1)) if birth else None,
        },
    }
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    assert result["pass_criterion"].startswith("Pre-registered.")
    result.update({
        "status": "complete",
        "data_kind": "biological",
        "verdict": verdict,
        "confidence": confidence,
        "interpretation": result["interpretation"],
        "method": (
            "The FishBase species summary was downloaded to confirm the page is Mustelus mustelus, "
            "the smooth-hound. The reproduction page was downloaded in the same run and the reproductive-guild "
            "cell and the life-cycle cell were read. Viviparity plus a stated yolk-sac placenta, placenta, "
            "or navel-string was scored as support; oviparity or an explicit aplacental statement was scored "
            "as a refutation. Chorion and membrane words were recorded and did not change the verdict."
        ),
        "datasets": [{
            "id": "fishbase-mustelus-mustelus-reproduction",
            "name": "FishBase reproduction account for Mustelus mustelus",
            "landing_url": SUMMARY,
            "doi": None,
            "version": "live FishBase page",
            "license": None,
            "files": [
                {k: summary[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")},
                {k: repro[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")},
            ],
            "role": "reproductive guild and life-cycle description of the smooth-hound",
        }],
        "measured": measured,
        "caveats": [
            "FishBase is a compiled catalogue. The life-cycle sentence cites other references; this test did not re-dissect a shark.",
            "The words chorion and membrane are not in the life-cycle sentence, so that clause of the claim is untested.",
            "The test is for Mustelus mustelus only, the species named in the claim's scope.",
            "No licence statement was present in the two retrieved HTML pages.",
        ],
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    derived = HERE / "derived"
    derived.mkdir(exist_ok=True)
    (derived / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    print(verdict, confidence, measured["extra"]["life_cycle"])


if __name__ == "__main__":
    main()
