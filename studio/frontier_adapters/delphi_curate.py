"""Mechanical curation report over the bulk snapshots. It REPORTS; it never drops, rejects or accepts a record.

Each finding is a count plus claim ids (public Delphi ids; no quote text). Heuristics are named as heuristics. Delphi's own
labels (verification, dataTest, status, truth) are upstream assertions: this report cross-checks them against what the Delphi
record itself carries, and does not adopt them.
"""
from __future__ import annotations

import collections
import json


def _load(path):
    with open(path) as fh:
        return [json.loads(l) for l in fh if l.strip()]


def curate(snapshots: list[dict], earlier_catalog: list[dict] | None = None) -> dict:
    S = snapshots
    g = lambda s, k: s["delphi_graph"].get(k)
    ids = lambda xs: sorted(s["claim_id"] for s in xs)
    out = {"records": len(S), "by_kind": dict(collections.Counter(s["kind"] for s in S)),
           "by_registry": dict(collections.Counter(str(s["registry"]) for s in S)),
           "by_thinker": dict(collections.Counter(g(s, "thinker") for s in S))}

    # 1. source problems, from the mechanical integrity checks
    prob = collections.defaultdict(list)
    for s in S:
        for p in s.get("integrity_problems", []):
            prob[p].append(s["claim_id"])
    out["source_problems"] = {k: {"count": len(v), "ids": sorted(v)[:12], "ids_truncated": len(v) > 12} for k, v in sorted(prob.items())}
    out["hash_scope_not_reproducible"] = sum(1 for s in S if s["source"].get("hash_scope") == "pipeline_extracted_page_text_not_reproducible")

    # 2. upstream-label consistency (heuristics, named)
    lean_no_trace = [s for s in S if g(s, "verification") in ("lean", "literature") and s["kind"] == "math" and not s["source"].get("locator")]
    th = lambda s: g(s, "thinker") or ""
    labelled_math_no_notation = [s for s in S if g(s, "math") and not s["fields"].get("skos:notation") and s["kind"] != "catalog"]
    nonformal = [s for s in S if s["fields"].get("delphi:hypothesisType") in ("empirical-law", "principle-or-framework")]
    out["scope_checks"] = {
        "upstream_math_true_but_no_notation_in_record": {"count": len(labelled_math_no_notation), "ids": ids(labelled_math_no_notation)[:12]},
        "math_claim_labelled_lean_or_literature_but_record_has_no_locator_quote_or_hash": {"count": len(lean_no_trace), "ids": ids(lean_no_trace)[:12],
            "meaning": "the upstream label cannot be traced to a span of the source from the Delphi record alone"},
        "record_self_declares_non_formal_yet_upstream_verification_is_not_untested": {
            "count": len([s for s in nonformal if g(s, "verification") not in (None, "untested")]),
            "ids": ids([s for s in nonformal if g(s, "verification") not in (None, "untested")])[:12]},
        "refuted_or_partial_upstream": {"refuted": ids([s for s in S if g(s, "verification") == "refuted"]),
                                        "partial": ids([s for s in S if g(s, "verification") == "partial"])},
    }
    out["upstream_verification_labels"] = dict(collections.Counter(str(g(s, "verification")) for s in S))
    out["upstream_data_test_labels"] = {
        "captured": False,
        "why": "Delphi's overview counts data-tested claims (131 at build 2026-10-31 18:16), but neither the delphi_graph list view nor "
               "delphi_search_claims returns a per-claim data-test verdict, so none could be retrieved in bulk. An empty column here means "
               "NOT CAPTURED, not 'no test'."}

    # 3. disagreement
    dis = sorted((s for s in S if (g(s, "disagreement") or 0) >= 0.3), key=lambda s: -(g(s, "disagreement") or 0))
    contra = [s for s in S if g(s, "verification") == "refuted" and (g(s, "truth") or 0) >= 0.5]
    out["disagreement"] = {
        "llm_assessor_disagreement_ge_0.3": {"count": len(dis), "top": [(s["claim_id"], g(s, "disagreement")) for s in dis[:12]]},
        "upstream_refuted_but_llm_truth_ge_0.5": {"count": len(contra), "ids": ids(contra)},
        "note": "LLM-elicited scores are not evidence; disagreement is reported, not resolved",
    }

    # 4. duplicated experimental / source provenance
    byq = collections.defaultdict(list); byloc = collections.defaultdict(list); bywork = collections.defaultdict(list)
    for s in S:
        if s["quote"].get("sha256"):
            byq[s["quote"]["sha256"]].append(s["claim_id"])
        if s["kind"] == "literature" and s["source"].get("url") and s["source"].get("locator"):
            byloc[(s["source"]["url"], s["source"]["locator"])].append(s["claim_id"])
        if s["kind"] == "catalog":
            bywork[s["source"].get("work") or "(none)"].append(s["claim_id"])
    dq = {k[:12]: v for k, v in byq.items() if len(v) > 1}
    dl = {f"{k[0].rsplit('/', 1)[-1]}#{k[1]}": v for k, v in byloc.items() if len(v) > 1}
    shared_ev = collections.defaultdict(list)
    for s in S:
        ev = s["fields"].get("delphi:hasEvidence")
        for e in (ev if isinstance(ev, list) else [ev] if ev else []):
            shared_ev[e].append(s["claim_id"])
    out["duplicated_provenance"] = {
        "identical_quote_digest_across_claims": {"groups": len(dq), "claims": sum(len(v) for v in dq.values()), "examples": dict(list(dq.items())[:5])},
        "identical_source_span_across_claims": {"groups": len(dl), "claims": sum(len(v) for v in dl.values()), "examples": dict(list(dl.items())[:5])},
        "catalog_claims_per_cited_work": {"works": len(bywork), "claims": sum(len(v) for v in bywork.values()),
                                          "largest": sorted(((len(v), k[:90]) for k, v in bywork.items()), reverse=True)[:8],
                                          "meaning": "claims sharing one paper are not independent experiments"},
        "shared_delphi_evidence_nanopub": {k: v for k, v in shared_ev.items() if len(v) > 1},
        "claims_citing_delphi_evidence_nanopubs": sum(len(set(v)) for v in shared_ev.values()),
    }

    # 5. registry status and drift against an earlier retrieval
    out["registry"] = {"now": out["by_registry"]}
    if earlier_catalog is not None:
        old = {e["id"]: e for e in earlier_catalog}
        now = {s["claim_id"]: s for s in S}
        common = sorted(set(old) & set(now))
        reg_changed = [i for i in common if old[i].get("registry") != now[i]["registry"]]
        np_changed = [i for i in common if old[i].get("nanopub") != now[i]["nanopub_uri"]]
        out["drift_since_earlier_retrieval"] = {
            "earlier_records": len(old), "compared": len(common), "added_since": len(set(now) - set(old)), "removed_since": len(set(old) - set(now)),
            "registry_changed": len(reg_changed), "registry_transitions": dict(collections.Counter(f"{old[i].get('registry')}->{now[i]['registry']}" for i in reg_changed)),
            "nanopub_uri_changed": len(np_changed), "ids_nanopub_changed_examples": np_changed[:8],
            "statement_changed": [i for i in common if old[i].get("statement") != now[i]["fields"].get("dct:description")][:12],
            "title_changed": [i for i in common if old[i].get("title") != now[i]["fields"].get("rdfs:label")][:12],
        }
    return out


if __name__ == "__main__":
    import sys
    out_dir = sys.argv[1]
    earlier = None
    if len(sys.argv) > 2:
        with open(sys.argv[2]) as fh:
            earlier = json.load(fh)
    rep = curate(_load(f"{out_dir}/snapshots.jsonl"), earlier)
    with open(f"{out_dir}/curation-report.json", "w") as fh:
        json.dump(rep, fh, indent=1, sort_keys=True)
    print(json.dumps(rep, indent=1, sort_keys=True)[:6000])
