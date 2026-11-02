"""Test aristotle-pa02-30 against Animal Diversity Web accounts.

Run: python3 analysis.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _fetch

HERE = Path(__file__).resolve().parent
ACCOUNTS = {
    "Monachus monachus": "https://animaldiversity.org/accounts/Monachus_monachus/",
    "Phoca vitulina": "https://animaldiversity.org/accounts/Phoca_vitulina/",
    "Zalophus californianus": "https://animaldiversity.org/accounts/Zalophus_californianus/",
    "Odobenus rosmarus": "https://animaldiversity.org/accounts/Odobenus_rosmarus/",
    "Condylura cristata": "https://animaldiversity.org/accounts/Condylura_cristata/",
    "Heterocephalus glaber": "https://animaldiversity.org/accounts/Heterocephalus_glaber/",
    "Phocidae": "https://animaldiversity.org/accounts/Phocidae/",
}
PHOCIDS = ("Monachus monachus", "Phoca vitulina")
OTHERS = ("Zalophus californianus", "Odobenus rosmarus", "Condylura cristata", "Heterocephalus glaber")
ABSENT = re.compile(
    r"no external ears?|without external ears?|lack(?:s|ing)? (?:any )?external ears?|"
    r"lack(?:s|ing)? pinnae?|no pinnae?|ears are absent|external ears absent|"
    r"no external pinna|do not have external ears|lack any external ear",
    re.I,
)
PRESENT = re.compile(r"external ears|small ears|pinnae|ear flaps", re.I)


def html_text(data):
    html = data.decode("utf-8", "replace")
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = html.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", html)


def score(text):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    hits = []
    state = "not_stated"
    for sentence in sentences:
        if not re.search(r"\b(pinnae?|external ears?|ear flaps?|auditory)\b", sentence, re.I):
            continue
        if re.search(r"\byears?\b", sentence, re.I) and not re.search(r"\bears?\b", sentence, re.I):
            # 'years' contains 'ears'; require an ear word that is not inside 'years'
            if not re.search(r"\b(pinnae?|external ears?|ear flaps?|auditory|ears|ear)\b", sentence, re.I):
                continue
        if not re.search(r"\b(pinnae?|external ear|ears|ear flap|auditory meatus|auditory)\b", sentence, re.I):
            continue
        # drop sentences whose only 'ear' hit is the substring of 'years'
        if re.search(r"\byears\b", sentence, re.I) and not re.search(
            r"\b(pinnae?|external ears?|ear flap|auditory|ears|ear)\b", sentence, re.I
        ):
            continue
        hits.append(sentence.strip())
        if ABSENT.search(sentence):
            state = "absent"
        elif state != "absent" and PRESENT.search(sentence):
            state = "present"
    # A sentence about 'years' can still match \bears\b inside years if the engine is wrong.
    # Keep only sentences that match the absent or present patterns, or auditory/pinna/external ear.
    kept = [sentence for sentence in hits if ABSENT.search(sentence) or PRESENT.search(sentence) or re.search(
        r"external ear|pinna|auditory|ear flap", sentence, re.I)]
    if not kept:
        return "not_stated", []
    if any(ABSENT.search(sentence) for sentence in kept):
        return "absent", kept
    if any(PRESENT.search(sentence) for sentence in kept):
        return "present", kept
    return "mentioned_unscored", kept


def main():
    fetched = {name: _fetch.fetch(url) for name, url in ACCOUNTS.items()}
    scored = {name: score(html_text(item["data"])) for name, item in fetched.items()}
    phocid_states = {name: scored[name][0] for name in PHOCIDS}
    other_states = {name: scored[name][0] for name in OTHERS}
    if any(phocid_states[name] == "not_stated" for name in PHOCIDS):
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.62
    elif any(phocid_states[name] == "present" for name in PHOCIDS) or any(other_states[name] == "absent" for name in OTHERS):
        verdict, reason, confidence = "refutes", None, 0.74
    elif all(phocid_states[name] == "absent" for name in PHOCIDS) and all(other_states[name] != "absent" for name in OTHERS):
        if any(other_states[name] == "not_stated" for name in OTHERS) and not any(other_states[name] in ("present", "mentioned_unscored") for name in OTHERS):
            verdict, reason, confidence = "mixed", None, 0.5
        else:
            # Support requires that none of the others is stated to lack a pinna. Silence is not a lack.
            # The pre-registered support text says none "is stated to lack". Silence satisfies that.
            # Mixed is only when every non-phocid account is silent. If any speaks and none is absent, support.
            if all(other_states[name] == "not_stated" for name in OTHERS):
                verdict, reason, confidence = "mixed", None, 0.5
            else:
                verdict, reason, confidence = "supports", None, 0.72
    else:
        verdict, reason, confidence = "mixed", None, 0.5
    measured = {
        "value": sum(1 for name in PHOCIDS if phocid_states[name] == "absent"),
        "unit": "phocid species accounts stating that the external ear is absent",
        "n": len(PHOCIDS),
        "uncertainty": None,
        "extra": {
            "phocid_states": phocid_states,
            "other_states": other_states,
            "phocidae_family_state": scored["Phocidae"][0],
            "sentences": {name: sentences[:3] for name, (state, sentences) in scored.items()},
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
        "method": (
            "Animal Diversity Web accounts for the Mediterranean monk seal, the harbour seal, the California "
            "sea lion, the walrus, the star-nosed mole, the naked mole-rat and the family Phocidae were downloaded. "
            "Sentences mentioning an external ear, pinna or auditory opening were kept. Absence patterns were "
            "applied before presence patterns. The family account was not allowed to stand in for either species. "
            "A phocid account that never mentions the ear makes the pre-registered test inconclusive."
        ),
        "datasets": [{
            "id": "adw-pinniped-and-earless-quadruped-accounts",
            "name": "Animal Diversity Web accounts of phocids and other viviparous quadrupeds",
            "landing_url": "https://animaldiversity.org/",
            "doi": None,
            "version": "live accounts",
            "license": None,
            "files": [{k: item[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")} for item in fetched.values()],
            "role": "statements of external-ear presence or absence",
        }],
        "measured": measured,
        "caveats": [
            "The family page is context only. It cannot fill in a species account that does not mention the ear.",
            "Sentence matching can miss a paraphrase. The kept sentences are stored in derived/measured.json.",
            "Cetaceans were excluded, as pre-registered, because the claim is about quadrupeds.",
            "No licence line was extracted from the account pages.",
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
    print(verdict, phocid_states, other_states, "family", scored["Phocidae"][0])


if __name__ == "__main__":
    main()
