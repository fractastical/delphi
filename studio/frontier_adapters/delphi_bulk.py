"""Bounded, checkpointed, read-only bulk retrieval of the Delphi catalog -> PROPOSED Claim drafts.

Efficient by design: `delphi_graph` returns the whole catalog metadata in ~9 filtered calls; the nanopub-backed claims then need
one SPARQL call per batch of claims (rows are filtered server-side), not several calls per claim. 1,190 claims cost ~50 requests.

Limits are explicit: min interval, max requests, wall budget (see delphi_mcp.Delphi). `Retry-After` is honoured; persistent 429 or any
401/403 stops the run and the checkpoint records why. Nothing is retried around a refusal.

Safety, as elsewhere: no quote text is written (digest only), no private data, nothing submitted. Every retrieved record keeps its
original id / IRI / registry / nanopub URI and a retrieval receipt. Records are NOT silently dropped: a draft that fails validation is
written to `errors.jsonl` with the reason.

Output layout (under `out_dir`), registry kinds kept in SEPARATE files:
  claims-production-NNN.jsonl   Draft dicts, nanopub in Delphi's production registry
  claims-test-NNN.jsonl         Delphi TEST registry: test/unreviewed, never mixed with production
  claims-unpublished-NNN.jsonl  catalog-only (no nanopub, registry null)
  snapshots.jsonl               the snapshots the drafts were built from (no quote text)
  errors.jsonl, checkpoint.json, receipts.jsonl
"""
from __future__ import annotations

import json
import os
import re

from . import delphi_claim as dc
from .common import iso_utc, sha_obj, validate_draft
from .delphi_mcp import Delphi, RetrievalStopped, json_from_text

BULK_VERSION = "0.1.0"
MATH_THINKERS = ("Ronald A. Fisher", "Alan Turing", "Motoo Kimura", "W. D. Hamilton", "John Maynard Smith")


def tier(e: dict) -> int:
    """Mission priority: math-biology first, then biomechanics/development, then the rest. A processing ORDER, not a judgement."""
    t = e.get("thinker") or ""
    if t in MATH_THINKERS:
        return 1
    if t.startswith("D'Arcy"):
        return 2 if e.get("math") else 3
    if t == "Michael Levin":
        return 4
    if t == "Charles Darwin":
        return 5
    return 6


def thinkers_from_overview(text: str) -> list[str]:
    return re.findall(r"^\| \[([^\]]+)\]\(", text, re.M)


def catalog(mcp: Delphi) -> tuple[list[dict], dict]:
    """Whole catalog metadata via filtered `delphi_graph` calls, with controls. Returns (entries, control results)."""
    text, _ = mcp.text("delphi_overview", {"source": "local"})
    total = json_from_text(text)["claimGraph"]["total"]["claims"]
    entries, per = {}, {}
    for name in thinkers_from_overview(text):
        got = dc.graph_entries(mcp, thinker=name)
        per[name] = len(got)
        for x in got:
            entries[x["id"]] = x
    must_fail = mcp.tool("delphi_graph", {"thinker": "Nobody Zzyzx-Not-A-Thinker", "limit": 5})
    ctl = {"overview_total": total, "retrieved": len(entries), "per_thinker": per,
           "count_matches_overview": len(entries) == total,
           "must_fail_nonexistent_thinker_matched": must_fail.get("matched")}
    return sorted(entries.values(), key=lambda e: (tier(e), e["id"])), ctl


def integrity(snap: dict) -> list[str]:
    """Mechanical checks on one snapshot; returns problem codes (empty = none found). Reported, never used to drop a record."""
    p = []
    f = snap["fields"]
    if not (f.get("rdfs:label") and f.get("dct:description") and f.get("delphi:context")):
        p.append("missing_title_statement_or_context")
    if bool(snap["registry"]) != bool(snap["nanopub_uri"]):
        p.append("registry_nanopub_disagree")
    if snap["nanopub_uri"] and not snap["nanopub_uri"].startswith("https://w3id.org/np/RA"):
        p.append("nanopub_uri_not_trusty_shaped")
    s = snap["source"]
    if snap["kind"] == "literature":
        if not s.get("url"): p.append("literature_without_source_url")
        if not s.get("locator"): p.append("literature_without_locator")
        if not s.get("recorded_sha256"): p.append("literature_without_source_hash")
        if not snap["quote"].get("sha256"): p.append("literature_without_quote_digest")
    elif snap["kind"] == "math":
        if s.get("unresolved_internal_iri"): p.append("source_is_delphi_internal_iri_not_resolvable")
        if not s.get("url") and not s.get("unresolved_internal_iri"): p.append("math_claim_without_any_source")
        p.append("no_locator_quote_or_hash_in_record")
    else:
        p.append("catalog_only_unpublished")
        if not s.get("citation"): p.append("catalog_without_citation")
    if not snap["record"].get("license") and snap["kind"] != "catalog":
        p.append("record_without_licence")
    return p


def _append(path, obj):
    with open(path, "a") as fh:
        fh.write(json.dumps(obj, sort_keys=True) + "\n")


def run(mcp: Delphi, out_dir: str, *, limit: int | None = None, batch: int = 25, shard: int = 100, entries: list | None = None) -> dict:
    """Retrieve and map up to `limit` NEW claims (in priority order), resuming from out_dir/checkpoint.json."""
    os.makedirs(out_dir, exist_ok=True)
    cp_path = os.path.join(out_dir, "checkpoint.json")
    cp = json.load(open(cp_path)) if os.path.exists(cp_path) else {"done": [], "counts": {}, "stopped": None, "waves": []}
    if entries is None:
        entries, ctl = catalog(mcp)
        cp["catalog_control"] = ctl
        if not ctl["count_matches_overview"] or ctl["must_fail_nonexistent_thinker_matched"] != 0:
            cp["stopped"] = "catalog control failed; not importing"
            json.dump(cp, open(cp_path, "w"), indent=1, sort_keys=True)
            return cp
    cp["catalog_sha256"] = sha_obj([e["id"] for e in entries])
    done = set(cp["done"])
    todo = [e for e in entries if e["id"] not in done]
    if limit is not None:
        todo = todo[:limit]
    start_receipt, started = len(mcp.receipts), iso_utc()
    try:
        for i in range(0, len(todo), batch):
            chunk = todo[i:i + batch]
            backed = [e for e in chunk if e.get("nanopub") or e.get("registry")]
            rows_by, assessors, rn = {}, {}, None
            if backed:
                ids = [e["id"] for e in backed]
                rows = mcp.sparql(dc.claim_rows_query(ids))
                rn = len(mcp.receipts)
                if len(rows) >= 3000:
                    raise RetrievalStopped("SPARQL page hit its 3000-row limit; batch too large, stopping rather than truncating")
                for r in rows:
                    cid = dc._claim_of_graph(r["g"])
                    rows_by.setdefault(cid, []).append(r)
                assessors = dc.assessors_from(mcp.sparql(dc.assessor_query(ids)))
            for e in chunk:
                try:
                    receipt = {"collector": f"frontier_adapters.delphi_bulk {BULK_VERSION}", "retrieved_at": iso_utc(),
                               "graph_catalog": True, "sparql_receipt_n": rn}
                    if e in backed:
                        snap, _tr = dc.snapshot_from_rows(e["id"], rows_by.get(e["id"], []), e, assessors.get(e["id"], []), receipt)
                    else:
                        snap = dc.snapshot_from_catalog(e, receipt)
                    snap["integrity_problems"] = integrity(snap)
                    draft = dc.to_claim_draft(snap, verification={"performed": False, "reason": "not performed in bulk import"})
                    validate_draft(draft)                                   # real models + licence gate; failure is recorded, not hidden
                    kind = "unpublished" if snap["kind"] == "catalog" else (snap["registry"] or "production")
                    n = cp["counts"].get(kind, 0)
                    _append(os.path.join(out_dir, f"claims-{kind}-{n // shard + 1:03d}.jsonl"), draft)
                    _append(os.path.join(out_dir, "snapshots.jsonl"), snap)
                    cp["counts"][kind] = n + 1
                except (LookupError, ValueError, KeyError) as exc:
                    _append(os.path.join(out_dir, "errors.jsonl"), {"id": e["id"], "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                                                                    "registry": e.get("registry"), "thinker": e.get("thinker")})
                    cp["counts"]["errors"] = cp["counts"].get("errors", 0) + 1
                cp["done"].append(e["id"])
            json.dump(cp, open(cp_path, "w"), indent=1, sort_keys=True)
    except RetrievalStopped as exc:
        cp["stopped"] = str(exc)
    for r in mcp.receipts[start_receipt:]:
        _append(os.path.join(out_dir, "receipts.jsonl"), r)
    cp["waves"].append({"started": started, "ended": iso_utc(), "requests": mcp.requests, "claims_this_wave": len(cp["done"]) - len(done),
                        "min_interval_s": mcp.min_interval, "max_requests": mcp.max_requests, "max_wall_s": mcp.max_wall_s})
    json.dump(cp, open(cp_path, "w"), indent=1, sort_keys=True)
    return cp
