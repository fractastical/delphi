#!/usr/bin/env python3
"""Build result.json (claim-test schema) from derived/*.json. Every number in `measured` comes from those files."""
import csv, gzip, hashlib, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "derived")
p1 = json.load(open(os.path.join(D, "part1_summary.json")))
pr = json.load(open(os.path.join(D, "part1_preston.json")))
p2 = json.load(open(os.path.join(D, "part2_summary.json")))
gf = json.load(open(os.path.join(D, "part2_grok_fine.json")))
man = list(csv.DictReader(gzip.open(os.path.join(D, "gift_manifest.csv.gz"), "rt")))
mh = hashlib.sha256(open(os.path.join(D, "gift_manifest.csv.gz"), "rb").read()).hexdigest()
top = {r["path"]: r for r in man if not r["path"].startswith("lists/")}
files = [dict(download_url=r["url"], retrieved_at=r["retrieved_at"], byte_size=int(r["byte_size"]), sha256=r["sha256"]) for r in top.values()]
nlist = sum(1 for r in man if r["path"].startswith("lists/"))
bytes_lists = sum(int(r["byte_size"]) for r in man if r["path"].startswith("lists/"))
prereg_sha = open(os.path.join(HERE, "PREREG.sha256")).read().split()[0]
c = p2["ch12_04"]

result = {
    "claim_id": "darwin1859-ch12-04",
    "claim_iri": "https://w3id.org/delphi/resource/claim/darwin1859-ch12-04",
    "project": "darwin-origin",
    "problem": "species-area-exponent",
    "approaches_run": ["claude-opus-5-5--2 (sampling-only null)", "grok-4-7--2 (logseries null, adapted)", "grok-4-7--1 (power law vs METE-type on GIFT, adapted)"],
    "status": "complete",
    "hypothesis": "Native vascular plant richness of oceanic islands (GIFT islands >= 500 km from the mainland) lies far below the mainland species-area prediction at equal area; "
                  "and, for the problem it belongs to, the island species-area relationship is a power law with a near-universal exponent around 0.25.",
    "pass_criterion": "Pre-registered (PREREG.md, sha256 " + prereg_sha + "): claim supported if the median observed/predicted richness ratio of oceanic-proxy islands against a negative-binomial mainland power law "
                      "is <= 0.5, at least 70% lie below the prediction and a one-sided Wilcoxon test of log ratios gives p < 0.01. Problem-level: universal power law if pooled z in [0.15, 0.35], bootstrap CI width < 0.1, "
                      "all qualifying 60x30 degree groups' z intervals overlap the pooled one, DerSimonian-Laird tau < 0.05, and no alternative form beats the power law by AIC > 10 and held-out ELPD > 10.",
    "fail_criterion": "Claim refuted if the median ratio >= 1. Universality refuted if any two qualifying groups have disjoint 95% z intervals or any group interval misses the pooled one.",
    "planned_datasets": ["gift-island-checklists-weigelt2020"],
    "test_contract": {
        "expected_observation": "GIFT native vascular richness of far-offshore islands is a small fraction of what mainland units of equal area hold, and island z clusters near one value.",
        "disconfirming_observation": "Island richness at or above the mainland prediction (median ratio >= 1); or island exponents whose group-level intervals are disjoint.",
        "admissible_datasets": "Public GIFT checklists of Tracheophyta (type Flora or Checklist, native status indicated, suitable for geographic analysis), one list per geographic entity (largest native richness); island areas from GIFT. Independent of the WCVP data used by the existing test of this claim.",
        "inference_method": "Negative-binomial (NB2) maximum likelihood for every model; mainland power law predicts islands; group z by Wald; pooled z by bootstrap over islands; model selection by AIC and leave-one-group-out ELPD; thresholds fixed in PREREG.md.",
    },
    "interpretation": "Darwin's 'oceanic islands' are proxied by GIFT entity_class Island with distance_to_mainland >= 500 km (fixed before inspecting data); 'equal continental areas' are GIFT mainland political units, botanical countries and regions "
                      "(random subset of at most 400, seed 20261101). No physical-condition covariate (latitude, climate) is used in this test, unlike the WCVP test, so the 'not explained by physical conditions' clause is not tested. "
                      "'Island groups' are mechanical 60x30 degree cells, not archipelagos, because GIFT returns no group field.",
    "datasets": [{
        "id": "gift-island-checklists-weigelt2020",
        "name": "GIFT, Global Inventory of Floras and Traits (public API)",
        "landing_url": "https://gift.uni-goettingen.de/",
        "doi": "10.1111/jbi.13623",
        "version": "live API, retrieved 2026-11-01",
        "license": "not verified here; see the GIFT terms of use",
        "files": files + [dict(download_url="https://gift.uni-goettingen.de/api/extended/index.php?query=checklists&listid=<id>", retrieved_at="see derived/gift_manifest.csv.gz",
                               byte_size=bytes_lists, sha256=mh,
                               note=f"{nlist} per-list files; per-file URL, time, bytes and SHA-256 in derived/gift_manifest.csv.gz (the sha256 here is that manifest file's)")],
        "role": "island and mainland native vascular plant richness and area",
    }],
    "method": "Part 2: 1,124 GIFT islands and 232 mainland entities, native richness per entity from the largest eligible checklist; NB2 fits of power, power+curvature, Gleason, Lomolino-type and logseries-placement (METE-type surrogate) forms; "
              "group, pooled, CV and island-versus-mainland analyses as pre-registered. Part 1: Coleman random-placement null on 5,130 grid cells (lognormal and logseries pools) with stochastic replicates, Preston canonical lognormal. See RESULTS.md.",
    "measured": {
        "value": c["median_ratio"],
        "unit": "median observed / mainland-predicted native vascular richness, GIFT islands >= 500 km from the mainland",
        "n": c["oceanic_proxy_n"],
        "uncertainty": f"share below prediction {c['share_below_prediction']:.3f}; one-sided Wilcoxon p = {c['wilcoxon_p_one_sided']:.2e}",
        "extra": {
            "ch12_04": c,
            "island_sar_pooled_power": p2["pooled_power"],
            "pooled_z_bootstrap_ci95": p2["pooled_z_bootstrap_ci95"],
            "pooled_quad": p2["pooled_quad"],
            "n_groups_qualifying": p2["n_groups_qualifying"], "groups_overlapping_pooled": p2["groups_overlapping_pooled"],
            "n_disjoint_group_pairs": p2["n_disjoint_group_pairs"], "n_group_pairs": p2["n_group_pairs"],
            "tau_DL": p2["tau_DL"], "group_z_range": p2["group_z_range"],
            "aic_advantage_over_pow": p2["aic_advantage_over_pow"], "cv_dELPD_vs_pow": p2["cv_dELPD_vs_pow"],
            "universal_rule": p2["universal_rule"], "universality_refuted": p2["universality_refuted"],
            "scale_dependent_supported": p2["scale_dependent_supported"], "mete_type_rule": p2["mete_type_rule"],
            "island_sar_classification": p2["classification"],
            "robustness": p2["robustness"],
            "grok_n2": p2["grok_n2"], "grok_n2_fine_exploratory": gf,
            "part1_null": {k: p1[k] for k in ["n_plausible", "plausible_z_quantiles", "plausible_z_sd", "H1A_share_in_0.15_0.35", "H1A", "H1B", "H1C", "H1C_share_q_below_-0.01",
                                              "plausible_median_z_by_amax", "plausible_median_z_by_D", "plausible_median_z_by_J", "H1C_stochastic", "claude_n2_outcome"]},
            "preston_isolate_z": pr["isolate_z_global_S100_1e5"], "preston_isolate_z_local_range": pr["isolate_z_range_local"],
            "preston_stochastic_isolate_z": pr["stochastic_isolate_z_S100_1e4"], "preston_sample_z_a0.2": pr["canonical_a0.2"]["sample_z_over_fractions"],
        },
    },
    "verdict": c["verdict"],
    "confidence": 0.7,
    "data_kind": "biological",
    "caveats": [
        "Verdict is for the claim's island-versus-mainland comparison on GIFT; the problem-level results (power law, universality, METE-type, sampling null) are in measured.extra and RESULTS.md.",
        "GIFT 'Island' entities are heterogeneous (continental shelf islands, oceanic islands, differing checklist effort); distance_to_mainland >= 500 km is only a proxy for 'oceanic'.",
        "No latitude or climate control in this test; the existing WCVP test of this claim has one.",
        "The METE-type form is a logseries-placement surrogate (alpha ln(1 + A/A*)), not meteR/METE, which needs abundance totals and nested cells that island checklists do not give.",
        "The 'group' unit is a mechanical longitude-latitude cell, not an archipelago; heterogeneity between cells mixes archipelago effects with sampling and taxonomy effects.",
        "The grok-4-7 n=2 null was adapted (richness only, density as nuisance parameter) and its coarse pre-registered grid missed the density window; the fine sweep is post hoc.",
        "Not run: claude-opus-5-5 n=1 and n=3, gpt-5-6-sol n=1 and n=2 (no GBIF/nested-survey/meta-analytic data pulled), grok-4-7 n=3 (Lean), and the Triantis et al. observed-z comparison of claude-opus-5-5 n=2.",
    ],
    "agent": {"kind": "local-agent", "model": "claude-sonnet-5-5", "run": "problems/runs/species-area-exponent", "date": "2026-11-01"},
    "code": {"fetch": "fetch_gift.py", "part1": "part1_null.py", "part2": "part2_analysis.py", "fine": "part2_grok_fine.py", "build": "build_result.py", "run_all": "run_all.sh"},
    "preregistration": {"file": "PREREG.md", "sha256": prereg_sha, "timestamp_file": "PREREG.sha256"},
}
# The result lives with the other tests of the claim so the claim graph and the evidence nanopubs
# (test-data/claim-tests/build-test-nanopubs.mjs) pick it up; the code and derived tables stay here.
OUT = os.path.join(HERE, "..", "..", "..", "test-data", "claim-tests", "darwin-origin", "darwin1859-ch12-04", "problem-sar-gift")
os.makedirs(OUT, exist_ok=True)
result["code"]["dir"] = "problems/runs/species-area-exponent"
json.dump(result, open(os.path.join(OUT, "result.json"), "w"), indent=2, default=float)
print("verdict", result["verdict"], "median ratio", c["median_ratio"])
