"""The 15-item attestation check is a bounded curation demonstration; these tests keep its record consistent and honest. No network."""
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

F = Path(__file__).resolve().parent.parent / "findings"
REGISTER = Path("/home/ubuntu/git/morphoswarm/data/problems/register.yaml")
sample = json.loads((F / "attestation-sample-15.json").read_text())
check = json.loads((F / "attestation-check-15.json").read_text())
facet = json.loads((F / "attestation-facet-review-15.json").read_text())
readme = (F / "README-attestation-check-15.md").read_text()
ids = lambda rows: [(r["slug"], r["index"]) for r in rows]


def test_sample_shape_and_that_it_was_fixed_by_rule():
    assert sample["n"] == 15 == len(sample["items"])
    assert sample["by_stratum"] == {"settled": 3, "url_wolfram": 1, "open_pmcid": 11}
    assert len({i["slug"] for i in sample["items"]}) == 15 and len({i["source"] for i in sample["items"]}) == 15
    assert any("wolfram" in (i["url"] or "") for i in sample["items"])
    assert all(i["stance"] == "settled" for i in sample["items"] if i["stratum"] == "settled")
    assert "not a random sample" in sample["rule"] and "not a verification" in sample["rule"]


@pytest.mark.skipif(not REGISTER.exists(), reason="morphoswarm register not present on this host")
def test_sample_is_reproducible_and_quotes_are_the_registers(tmp_path):
    import yaml
    reg = {p["slug"]: p for p in yaml.safe_load(REGISTER.read_text())["problems"]}
    assert sample["register_sha256"] == sha256(REGISTER.read_bytes()).hexdigest()
    for i in sample["items"]:
        a = reg[i["slug"]]["attestations"][i["index"]]
        assert (a["quote"], a["locator"], a["stance"]) == (i["quote"], i["locator"], i["stance"]), "quote copied exactly, never edited"
    # Re-running the selection mechanically gives the same 15 (the script writes next to itself, so run a copy).
    copy = tmp_path / "select.py"
    copy.write_text((F / "select_attestation_sample.py").read_text())
    done = subprocess.run([sys.executable, "-I", str(copy), str(REGISTER)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    again = json.loads((tmp_path / "attestation-sample-15.json").read_text())
    assert ids(again["items"]) == ids(sample["items"])


def test_mechanical_check_matches_the_sample_and_uses_only_defined_statuses():
    assert check["sample_sha256"] == sha256((F / "attestation-sample-15.json").read_bytes()).hexdigest()
    assert ids(check["results"]) == ids(sample["items"])
    assert {r["status"] for r in check["results"]} <= {"verified", "quote_not_found", "source_only", "access_failure"}
    assert check["status_counts"] == {k: sum(1 for r in check["results"] if r["status"] == k) for k in {r["status"] for r in check["results"]}}
    for r in check["results"]:
        assert r["status"] != "verified" or r["access"] in ("full_text", "full_text_via_jina"), "verified needs retrieved full text"
        assert r["status"] != "verified" or r["match"] in ("normalised_exact", "letters_and_digits_only")
        assert r["tries"] and all("route" in t and "http" in t for t in r["tries"])
        if r["status"] == "quote_not_found":
            assert r["closest_excerpt"] and r["best_window_ratio"] < 1
    assert all("whole document" not in json.dumps(r) for r in check["results"])


def test_facet_review_is_separate_complete_and_its_tally_is_recomputable():
    assert ids(facet["items"]) == ids(sample["items"])
    assert "full papers were not read" in facet["reviewer"] and "Not independently reviewed" in facet["reviewer"]
    items = facet["items"]
    t = facet["tally"]
    assert t["quote_supports_stance"] == {k: sum(1 for x in items if x["quote_supports_stance"] == k) for k in ("yes", "partly", "no")}
    assert t["fit_to_question"] == {k: sum(1 for x in items if x["fit_to_question"] == k) for k in ("direct", "partial")}
    assert t["flags"] == {f: sum(1 for x in items if f in x["flags"]) for f in facet["scale"]["flags"]}
    assert t["clean_yes_and_direct_no_flags"] == sum(1 for x in items if x["quote_supports_stance"] == "yes" and x["fit_to_question"] == "direct" and not x["flags"])
    assert all(x["note"] and x["quote_supports_stance"] in ("yes", "partly", "no") for x in items)
    # the one stance the quote does not support is recorded as a mismatch, not smoothed over
    no = [x for x in items if x["quote_supports_stance"] == "no"]
    assert [x["slug"] for x in no] == ["teleost-genome-duplication-diversification-causality"] and "stance_overstated" in no[0]["flags"]


def test_readme_numbers_match_the_files_and_it_does_not_overclaim():
    assert f"{check['status_counts'].get('verified', 0)} of 15" in readme
    t = facet["tally"]
    assert f"**{t['clean_yes_and_direct_no_flags']} of 15**" in readme
    assert "Nothing here verifies the other 450 attestations" in readme and "not an error\n  rate for the register" in readme
    assert "completeness" in readme and "nothing was imported live" in readme
    low = readme.lower()
    for phrase in ("all 250 verified", "register is verified", "register verified", "verified the register"):
        assert phrase not in low
