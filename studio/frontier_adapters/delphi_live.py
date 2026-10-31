"""Live Delphi ingestion: an inventory of the server, an incremental claim diff against what Frontier already holds, and
Delphi's claim-test nanopubs as PROPOSED Evidence drafts. Read-only; keyless; nothing is published or written upstream.

Three questions this module answers with measurements, not with a record count:
  1. What does the live server hold right now?           `inventory`  (tools, build, per-source counts, repo commit)
  2. What is new since the records Frontier imported?    `classify`   (new / unchanged / labels_changed / content_changed /
                                                                       removed_upstream / withheld), per claim id, with the fields
                                                                       that changed. `reproduce_imported` first proves the baseline
                                                                       drafts rebuild the exact imported versions.
  3. What did Delphi test, on what data?                 `test_snapshot` + `to_evidence_draft`: one claim-test nanopub ->
                                                                       one Evidence draft pinned to the exact imported Claim version.

What is deliberately NOT done:
  * An upstream verdict is never local acceptance. Evidence is `source_assessment`; the verdict, confidence, data kind and
    preregistration flag travel raw in `provider_assessment`. `relation` is set only where the upstream verdict is literally
    `supports` or `refutes`; `mixed` and `inconclusive` stay `unspecified` (mapping them would be our inference).
  * A dataset checksum Delphi recorded is a declaration. No byte was fetched, so no `ArtifactRef` is made (its `byte_size`
    would have to be invented); the declarations travel in `provenance.datasets` with `bytes_checked: false`.
  * A changed claim is a successor draft whose `predecessor` is the imported version. `Store.import_bundle` records it as a
    FORK and leaves the head unchanged (SPEC-004); the update bundle is therefore separate, and resolution is the importer's act.
  * LLM truth scores and dataset-resolvability ratings stay labelled upstream opinions inside `prior_review`; they are not
    Assessments (an Assessment is local review under POLICY).
"""
from __future__ import annotations

import collections
import json
import re
import urllib.request

from .common import iso_utc, sha_bytes, sha_obj
from .delphi_claim import _rx
from .delphi_mcp import Delphi, json_from_text, rows_of

LIVE_ID = "frontier_adapters.delphi_live"
LIVE_VERSION = "0.1.0"
REPO_API = "https://api.github.com/repos/fractastical/delphi"
HEALTH = "https://delphisci-mcp.fly.dev/healthz"
D = "https://w3id.org/delphi/ontology/"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
PROV = "http://www.w3.org/ns/prov#"
DCT = "http://purl.org/dc/terms/"
SCHEMA = "https://schema.org/"


# ---------------------------------------------------------------- 1. inventory
def _get(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "frontier-adapters/delphi-live (read-only)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read()


def graph_dirs_query() -> str:
    return ('SELECT ?d (COUNT(DISTINCT ?g) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } '
            'BIND(REPLACE(STR(?g),"^(.*/nanopubs/[^/]+)/.*$","$1") AS ?d) } GROUP BY ?d ORDER BY DESC(?n) LIMIT 200')


def local_claim_nanopubs_query() -> str:
    """Head graphs of every claim-source nanopub in the repository (not tests, not assessments)."""
    return ('SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } '
            'FILTER(REGEX(STR(?g),"/claim-sources/[^/]+/nanopubs/unsigned/[^/]+[.]trig.Head$")) } ORDER BY ?g LIMIT 3000')


def ids_from_heads(rows, segment: str = "/nanopubs/unsigned/") -> list[str]:
    out = set()
    for r in rows_of(rows):
        m = re.search(re.escape(segment) + r"([^/#]+)\.trig", r["g"])
        if m:
            out.add(m.group(1))
    return sorted(out)


def inventory(mcp: Delphi, get=_get) -> dict:
    """What the live server holds now. Every MCP request is in `mcp.receipts`; the two plain GETs carry their own digest."""
    inv = {"collector": f"{LIVE_ID} {LIVE_VERSION}", "retrieved_at": iso_utc(), "endpoint": mcp.url}
    st, body = get(HEALTH)
    inv["healthz"] = {"http": st, "sha256": sha_bytes(body), "body": json.loads(body)}
    tl = mcp._rpc("tools/list", {}, label="tools/list", args_sha=sha_obj({}))
    inv["tools"] = [{"name": t["name"], "read_only": bool((t.get("annotations") or {}).get("readOnlyHint")),
                     "params": sorted((t.get("inputSchema") or {}).get("properties", {}))} for t in tl["result"]["tools"]]
    inv["tools_used_here"] = sorted(t["name"] for t in inv["tools"] if t["read_only"])
    inv["tools_never_called"] = {"names": sorted(t["name"] for t in inv["tools"] if not t["read_only"]),
                                 "why": "they post to the Science Claw forum or propose/log upstream; this adapter is read-only"}
    for src in ("local", "network"):
        o = json_from_text(mcp.text("delphi_overview", {"source": src})[0])
        inv[f"overview_{src}"] = {"files": o.get("files"), "endpoint": o.get("endpoint"),
                                  "domains": {d["domain"].rsplit("/", 1)[-1]: {"claims": d["claims"], "with_math": d["claimsWithMath"]}
                                              for d in o["domains"]},
                                  "claims_total": sum(d["claims"] for d in o["domains"]),
                                  "assessment_types": {a["type"]: {k: a[k] for k in ("assessments", "claims", "assessors")}
                                                       for a in o["assessmentTypes"]}}
    g = json_from_text(mcp.text("delphi_graph", {"view": "status"})[0])
    inv["claim_graph"] = {"built": g.get("built"), "total": g.get("total"),
                          "label": "Delphi's own verification/data-test tallies: upstream assertions, not Frontier review"}
    inv["organisms"] = json_from_text(mcp.text("delphi_organisms", {"overview": True})[0])
    inv["local_graph_dirs"] = {r["d"].split("/delphi/local/", 1)[-1]: int(r["n"]) for r in mcp.sparql(graph_dirs_query())}
    st, body = get(REPO_API + "/commits/main")
    c = json.loads(body)
    inv["upstream_repo"] = {"repo": "fractastical/delphi", "branch": "main", "http": st, "commit": c.get("sha"),
                            "committed_at": ((c.get("commit") or {}).get("committer") or {}).get("date"),
                            "note": "the commit main pointed at when read; the server serves its last deploy, whose `built` stamp is in healthz"}
    return inv


# ---------------------------------------------------------------- 2. incremental claim diff
LABEL_KEYS = ("delphi_graph", "assessments")
# Where the TriG file sits in Delphi's repository (and `domain_dir`, derived from that path), not what the claim says. Build
# 2026-10-31 20:10 moved every claim from `books/<domain>/nanopubs/...` or `<domain>/nanopubs/...` to `claim-sources/<domain>/...`.
LOCATION_KEYS = ("nanopub_path", "domain_dir")


def content_view(draft: dict) -> dict:
    """The part of a Claim draft that is the claim itself (what Delphi's record says), without upstream labels/opinions and
    without its repository location."""
    p = draft["payload"]
    o = p["prior_review"]["delphi_original"]
    return {"title": p["title"], "statement": p["statement"], "context": p["context"], "source": p["source"],
            "source_record_version": p["source_record_version"], "source_uri": draft["source_uri"],
            **{k: v for k, v in o.items() if k not in LABEL_KEYS + LOCATION_KEYS}}


def location_view(draft: dict) -> dict:
    o = draft["payload"]["prior_review"]["delphi_original"]
    return {k: o.get(k) for k in LOCATION_KEYS}


def label_view(draft: dict) -> dict:
    o = draft["payload"]["prior_review"]["delphi_original"]
    return {k: o.get(k) for k in LABEL_KEYS}


def _diff_keys(a: dict, b: dict, prefix: str = "") -> list[str]:
    out = []
    for k in sorted(set(a) | set(b)):
        x, y = a.get(k), b.get(k)
        if x == y:
            continue
        if isinstance(x, dict) and isinstance(y, dict):
            out += _diff_keys(x, y, f"{prefix}{k}.")
        else:
            out.append(prefix + k)
    return out


def created_at_of(draft: dict) -> str:
    """The import CLI's pin: a Claim draft's own retrieval time (`import_cli._created_at`)."""
    return draft["payload"]["prior_review"]["adapter"]["retrieved_at"]


def reproduce_imported(prev: dict[str, dict], imported: dict[str, dict], created_at: dict[str, str] | None = None) -> dict:
    """Rebuild each baseline draft into a Record and compare its version with the version Frontier imported. `created_at`
    overrides the pin for drafts recovered from already-made Records (the NCA chain's claims). A baseline that does not
    reproduce is not a baseline; the mismatches are listed."""
    from frontier.models import Draft, make_record
    created_at = created_at or {}
    ok, bad, missing = 0, [], []
    for cid, ref in sorted(imported.items()):
        d = prev.get(cid)
        if d is None:
            missing.append(cid)
            continue
        v = make_record(Draft.model_validate(d), created_at=created_at.get(cid) or created_at_of(d))["version"]
        if v == ref["version"]:
            ok += 1
        else:
            bad.append({"id": cid, "imported": ref["version"], "rebuilt": v})
    return {"imported": len(imported), "reproduced_exactly": ok, "mismatched": bad, "no_baseline_draft": missing}


def classify(prev: dict[str, dict], now: dict[str, dict], imported: dict[str, dict], withheld_now: dict[str, str] | None = None) -> dict:
    """Per claim id: what changed between the baseline drafts (`prev`, the ones Frontier imported from) and `now`.

    new                 in `now`, never imported and absent from the baseline
    new_to_store        in the baseline but never imported (e.g. catalog-only then), importable now
    unchanged           imported; content, upstream labels and repository location identical
    relocated           imported; content and labels identical, only the TriG file's path in Delphi's repository moved
    labels_changed      imported; the claim content is identical, Delphi's labels/opinions moved (location may also have)
    content_changed     imported; the claim's own record changed (statement, source, nanopub, registry ...)
    Each row lists `changed_content`, `changed_labels` and `changed_location` separately.
    removed_upstream    imported or in the baseline, absent now
    withheld            present now but its draft failed validation (reason kept)
    """
    withheld_now = withheld_now or {}
    rows = {}
    for cid in sorted(set(prev) | set(now) | set(imported) | set(withheld_now)):
        r = {"id": cid, "imported_ref": imported.get(cid)}
        if cid in withheld_now:
            r.update(status="withheld", reason=withheld_now[cid])
        elif cid not in now:
            r["status"] = "removed_upstream"
        elif cid not in imported:
            r["status"] = "new_to_store" if cid in prev else "new"
            if cid in prev:
                r["changed"] = _diff_keys(content_view(prev[cid]), content_view(now[cid]))
        elif cid not in prev:
            r["status"] = "content_changed"
            r["changed"] = ["(no baseline draft: compared by version only)"]
        else:
            c = _diff_keys(content_view(prev[cid]), content_view(now[cid]))
            lab = _diff_keys(label_view(prev[cid]), label_view(now[cid]))
            loc = _diff_keys(location_view(prev[cid]), location_view(now[cid]))
            r["status"] = ("content_changed" if c else "labels_changed" if lab else "relocated" if loc else "unchanged")
            r.update(changed_content=c, changed_labels=lab, changed_location=loc)
        rows[cid] = r
    counts = collections.Counter(r["status"] for r in rows.values())
    fields = {k: dict(collections.Counter(f for r in rows.values() for f in r.get(k, [])).most_common())
              for k in ("changed_content", "changed_labels", "changed_location")}
    fields["new_to_store_vs_baseline"] = dict(collections.Counter(f for r in rows.values() for f in r.get("changed", [])).most_common())
    return {"counts": dict(sorted(counts.items())), "changed_field_counts": fields, "rows": rows}


def increment(classified: dict, now: dict[str, dict]) -> dict:
    """Drafts to import: `new` (no head exists, imports cleanly) and `updates` (predecessor = imported version; FORKS on import).
    Label-only changes are NOT turned into successor versions: a fork per truth-score refresh would bury the real updates."""
    new, updates = [], []
    for cid, r in sorted(classified["rows"].items()):
        if r["status"] in ("new", "new_to_store"):
            new.append(now[cid])
        elif r["status"] == "content_changed" and r["imported_ref"]:
            updates.append({**now[cid], "predecessor": r["imported_ref"]["version"]})
    return {"new": new, "updates": updates}


# ---------------------------------------------------------------- 3. claim tests -> Evidence
TEST_SEG = "/claim-tests/nanopubs/unsigned/"


def claim_tests_heads_query() -> str:
    return ('SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } '
            'FILTER(REGEX(STR(?g),"/claim-tests/nanopubs/unsigned/[^/]+[.]trig.Head$")) } ORDER BY ?g LIMIT 3000')


def claim_test_rows_query(claim_ids: list[str]) -> str:
    alt = "|".join(_rx(c) for c in claim_ids)
    return ('SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } '
            f'FILTER(REGEX(STR(?g),"/claim-tests/nanopubs/unsigned/({alt})[.]trig")) }} ORDER BY ?g ?s ?p ?o LIMIT 3000')


def _local(p: str) -> str:
    return re.split(r"[#/]", p)[-1]


def _commit_of(url: str | None) -> str | None:
    m = re.search(r"/blob/([0-9a-f]{40})/", url or "")
    return m.group(1) if m else None


def test_snapshot(claim_id: str, rows: list[dict]) -> dict:
    """Pure: the rows of one claim-test nanopub -> a JSON-safe snapshot. Raises LookupError on a partial read."""
    mine = [r for r in rows if re.search(re.escape(TEST_SEG) + re.escape(claim_id) + r"\.trig", r["g"])]
    graphs = {r["g"].rsplit("#", 1)[-1] for r in mine}
    missing = {"Head", "assertion", "provenance", "pubinfo"} - graphs
    if missing:
        raise LookupError(f"claim test {claim_id!r}: nanopub graphs incomplete, missing {sorted(missing)}")
    by_s = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in mine:
        by_s[(r["g"].rsplit("#", 1)[-1], r["s"])][_local(r["p"])].append(r["o"])
    asserted = {s: f for (g, s), f in by_s.items() if g == "assertion"}
    claim_iri = "https://w3id.org/delphi/resource/claim/" + claim_id
    a_iri = next((o for o in asserted.get(claim_iri, {}).get("hasAssessment", [])), None)
    if a_iri is None:
        a_iri = next((s for s, f in asserted.items() if D + "Assessment" in f.get("type", [])), None)
    if a_iri is None or a_iri not in asserted:
        raise LookupError(f"claim test {claim_id!r}: no Assessment node in the assertion graph")
    a = asserted[a_iri]
    def one(f, k):
        return (sorted(f.get(k, [])) or [None])[0]

    conf = one(a, "hasConfidence")
    datasets = []
    for e in sorted(a.get("hasEvidence", [])):
        f = asserted.get(e, {})
        ck = one(f, "hasChecksum")
        datasets.append({"iri": e, "label": one(f, "label"), "description": one(f, "description"), "license": one(f, "license"),
                         "location": one(f, "atLocation"), "derived_from": one(f, "wasDerivedFrom"),
                         "declared_sha256": ck.split(":", 1)[1] if ck and ck.startswith("sha256:") else None,
                         "declared_checksum_raw": ck, "bytes_checked": False})
    revisions = []
    for rv in sorted(a.get("qualifiedRevision", [])):
        f = asserted.get(rv, {})
        revisions.append({"iri": rv, "label": one(f, "label"), "started": one(f, "startedAtTime"), "description": one(f, "description"),
                          "used": sorted(f.get("used", [])), "informed_by": sorted(f.get("wasInformedBy", [])),
                          "caveats_added": sorted(f.get("evidenceAgainst", []))})
    agents = {s: {"name": one(f, "name"), "comment": one(f, "comment"), "see_also": one(f, "seeAlso")}
              for s, f in asserted.items() if PROV + "Agent" in f.get("type", [])}
    prov = {s: f for (g, s), f in by_s.items() if g == "provenance"}
    pub = {s: f for (g, s), f in by_s.items() if g == "pubinfo"}
    np_path = next((r["g"].split("#")[0] for r in mine if r["g"].endswith("#Head")), "")
    pubf = next((f for s, f in pub.items() if s.endswith(".trig") or s == np_path), {})
    derived = sorted({o for f in prov.values() for o in f.get("wasDerivedFrom", [])})
    see_also = sorted(a.get("seeAlso", []))
    result_json = next((u for u in see_also + derived if re.search(r"/result\.json$", u or "")), None)
    snap = {
        "claim_id": claim_id, "claim_iri": claim_iri, "assessment_iri": a_iri,
        "nanopub_path": np_path.split("/delphi/local/", 1)[-1] if "/delphi/local/" in np_path else np_path,
        "title": one(a, "label"), "assessment_type": one(a, "assessmentType"),
        "verdict": one(a, "hasVerdict"), "confidence": float(conf) if conf is not None else None,
        "data_kind": one(a, "dataKind"), "preregistered": one(a, "preregistered"),
        "hypothesis": one(a, "hypothesis"), "expected_observation": one(a, "expectedObservation"),
        "disconfirming_observation": one(a, "disconfirmingObservation"), "admissible_datasets": one(a, "admissibleDatasets"),
        "pass_criterion": one(a, "passCriterion"), "fail_criterion": one(a, "failCriterion"),
        "inference_method": one(a, "inferenceMethod"), "description": one(a, "description"), "measured": one(a, "comment"),
        "caveats": sorted(a.get("evidenceAgainst", [])), "attributed_to": sorted(a.get("wasAttributedTo", [])),
        "contributors": sorted(a.get("contributor", [])), "contributor_agents": agents,
        "datasets": datasets, "revisions": revisions,
        "result_json": result_json, "result_commit": _commit_of(result_json), "derived_from": derived, "see_also": see_also,
        "tester": {s: {"label": one(f, "label"), "model": one(f, "usesModel"), "on_behalf_of": one(f, "actedOnBehalfOf")}
                   for s, f in prov.items() if PROV + "SoftwareAgent" in f.get("type", [])},
        "plan": sorted({o for f in prov.values() for o in f.get("hadPlan", [])}),
        "record": {"created": one(pubf, "created"), "creator": one(pubf, "creator"), "license": one(pubf, "license"),
                   "domain": one(pubf, "domain")},
    }
    snap["snapshot_sha256"] = sha_obj(snap)
    return snap


def _clip(s: str | None, n: int) -> str | None:
    return s if s is None or len(s) <= n else s[: n - 15] + " [... clipped]"


def to_evidence_draft(ts: dict, target: dict, retrieved_at: str, *, namespace: str = "node-a", issuer: str = "importer") -> dict:
    """One Delphi claim test -> an Evidence draft pinned to `target` (the exact Claim version Frontier holds)."""
    if target["kind"] != "Claim" or target["id"] != ts["claim_id"]:
        raise ValueError(f"target {target['id']!r} is not the tested claim {ts['claim_id']!r}")
    for k in ("verdict", "result_json", "record"):
        if not ts.get(k):
            raise ValueError(f"claim test {ts['claim_id']!r} has no {k}; not importable as Evidence")
    verdict = ts["verdict"]
    ctx = "\n".join(f"{lbl}: {ts[k]}" for lbl, k in (
        ("Hypothesis", "hypothesis"), ("Expected observation", "expected_observation"),
        ("Disconfirming observation", "disconfirming_observation"), ("Admissible datasets", "admissible_datasets"),
        ("Pass criterion", "pass_criterion"), ("Fail criterion", "fail_criterion"), ("Measured (as Delphi states it)", "measured"))
        if ts.get(k))
    limitations = [_clip(c, 3000) for c in ts["caveats"]][:38] + [
        "Imported upstream claim test: Frontier did not re-run it, did not fetch its datasets and did not review it.",
        "Delphi produced both the claim extraction and this test; it is not independent of the claim's source pipeline."]
    if not ts["datasets"]:
        limitations.append("The test nanopub declares no dataset node.")
    payload = {
        "target": target, "evidence_kind": "source_assessment",
        "source": {"uri": ts["result_json"], "locator": ts["nanopub_path"], "source_version": ts["result_commit"],
                   "content_sha256": None, "content_available": False, "license": None,
                   "access": ("Delphi claim-test nanopub (unsigned, in the Delphi repository; on no registry) and its result file "
                              "pinned to a commit on public GitHub. Read through the keyless delphisci MCP; result bytes not fetched here.")},
        "created_time": {"value": ts["record"]["created"], "basis": "declared"} if ts["record"].get("created") else {"value": None, "basis": "unknown"},
        "retrieved_time": {"value": retrieved_at, "basis": "witnessed"},
        "method": _clip("As recorded upstream (not re-executed): " + (ts.get("inference_method") or ts.get("description") or "not stated"), 12000),
        "context": _clip(ctx or "No hypothesis or criteria recorded in the test nanopub.", 12000),
        "assumptions": [],
        "provenance": {"delphi_claim_test": {k: ts[k] for k in ("assessment_iri", "nanopub_path", "assessment_type", "attributed_to",
                                                                "contributors", "contributor_agents", "tester", "plan", "derived_from",
                                                                "see_also", "revisions", "record", "description", "snapshot_sha256")},
                       "datasets": ts["datasets"],
                       "datasets_note": "checksums are Delphi's declarations; no byte was fetched or hashed here",
                       "adapter": {"id": LIVE_ID, "version": LIVE_VERSION, "retrieved_at": retrieved_at}},
        "source_dependence": {"same_pipeline_as_claim": True, "tested_by": ts["attributed_to"],
                              "note": "Delphi extracted the claim and ran the test; not assessed for independence here"},
        "uncertainty": (f"Upstream confidence {ts['confidence']} (Delphi's own number, not re-derived)" if ts.get("confidence") is not None
                        else "No confidence recorded upstream") + f"; preregistered: {ts.get('preregistered') or 'not stated'}; "
                       f"data kind: {ts.get('data_kind') or 'not stated'}.",
        "limitations": limitations,
        "local_id": ts["assessment_iri"],
        "provider_assessment": {"verdict": verdict, "confidence": ts.get("confidence"), "data_kind": ts.get("data_kind"),
                                "preregistered": ts.get("preregistered"), "assessment_type": ts.get("assessment_type"),
                                "label": "Delphi's upstream claim-test verdict, carried raw: NOT local acceptance, NOT a Frontier review"},
        "relation": verdict if verdict in ("supports", "refutes") else "unspecified",
    }
    return {"namespace": namespace, "kind": "Evidence", "id": f"delphi-claim-test--{ts['claim_id']}", "issuer": issuer,
            "source_uri": ts["assessment_iri"], "visibility": "public", "predecessor": None, "payload": payload}


# ---------------------------------------------------------------- readable claim context (site / graph field contract)
def readable_context(draft: dict, ref: dict, tests: list[dict] | None = None) -> dict:
    """User-readable view of one Claim record, built only from fields the draft already carries (no new inference)."""
    p = draft["payload"]
    o = p["prior_review"]["delphi_original"]
    u = o.get("unmapped_fields", {})
    s = p["source"]
    g = o.get("delphi_graph", {})
    deep = None
    if s.get("uri") and s.get("locator"):
        deep = s["uri"] + ("#" + s["locator"] if s["locator"].startswith("line=") else "")
    return {
        "schema": "frontier-delphi-claim-context-0.1", "ref": ref,
        "title": p["title"], "statement": p["statement"],
        "conditions": p["context"],
        "math_latex": u.get("skos:notation"), "claim_kind": u.get("dct:type"), "hypothesis_type": u.get("delphi:hypothesisType"),
        "proposed_test": u.get("delphi:proposedTest"),
        "source": {"citation": u.get("dct:source") or o.get("source_detail", {}).get("citation"), "uri": s.get("uri"),
                   "locator": s.get("locator"), "deep_link": deep, "work": o.get("source_detail", {}).get("work"),
                   "access": s.get("access"), "quote": {"stored": False, "sha256": o.get("quote", {}).get("sha256")}},
        "publication": {"claim_iri": o.get("claim_iri"), "nanopub_uri": o.get("nanopub_uri"), "registry": o.get("registry"),
                        "state": o.get("publication_state"), "nanopub_path": o.get("nanopub_path"),
                        "record_license": (o.get("record") or {}).get("license")},
        "upstream_labels": {"verification": g.get("verification"), "status": g.get("status"), "truth": g.get("truth"),
                            "disagreement": g.get("disagreement"), "assessments": (o.get("assessments") or {}).get("count"),
                            "label": "Delphi's labels and LLM-elicited scores: upstream opinions, never Frontier acceptance"},
        "tests": tests or [],
        "local_status": "imported_unreviewed",
    }


# ---------------------------------------------------------------- baseline and the end-to-end run
RECORD_ONLY = ("schema_version", "created_at", "version")


def draft_of_record(record: dict) -> dict:
    return {k: v for k, v in record.items() if k not in RECORD_ONLY}


def load_baseline(draft_files: list[str], plan_paths: list[str], records_files: list[str]) -> tuple[dict, dict, dict]:
    """(baseline drafts by id, imported Claim refs by id, created_at overrides). Drafts come from the frozen bulk files; Claims
    imported from already-made Records (the chain) are recovered from those Records, which are what Frontier holds."""
    prev, imported, created = {}, {}, {}
    for f in draft_files:
        with open(f) as fh:
            for line in fh:
                if line.strip():
                    d = json.loads(line)
                    prev[d["id"]] = d
    for p in plan_paths:
        with open(p) as fh:
            for b in json.load(fh)["bundles"]:
                for r in b["refs"]:
                    if r["kind"] == "Claim":
                        imported[r["id"]] = r
    for f in records_files:
        with open(f) as fh:
            for r in json.load(fh):
                if r["kind"] == "Claim":
                    imported[r["id"]] = {k: r[k] for k in ("namespace", "kind", "id", "version")}
                    prev[r["id"]] = draft_of_record(r)
                    created[r["id"]] = r["created_at"]
    return prev, imported, created


def _jsonl(path):
    try:
        with open(path) as fh:
            return [json.loads(line) for line in fh if line.strip()]
    except FileNotFoundError:
        return []


def _write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
    import os
    os.replace(tmp, path)


def run(mcp: Delphi, out_dir: str, *, baseline: tuple[dict, dict, dict], batch_tests: int = 15) -> dict:
    """Inventory -> fresh claim snapshot -> diff against the imported baseline -> claim-test Evidence -> readable index.
    Writes records (exact versions) for import_cli `build --records`; imports nothing."""
    import glob
    import os
    from frontier.models import Draft, make_record

    from . import delphi_bulk
    from .common import validate_draft
    os.makedirs(out_dir, exist_ok=True)
    prev, imported, created = baseline
    summary = {"collector": f"{LIVE_ID} {LIVE_VERSION}", "started": iso_utc()}
    inv = inventory(mcp)
    _write_json(os.path.join(out_dir, "inventory.json"), inv)
    summary["build"] = inv["healthz"]["body"].get("built")

    # claims: every claim-source nanopub id, so claims with a local unsigned nanopub and no registry are read from their rows
    local_ids = set(ids_from_heads(mcp.sparql(local_claim_nanopubs_query())))
    bulk_dir = os.path.join(out_dir, "bulk")
    cp = delphi_bulk.run(mcp, bulk_dir, local_backed=frozenset(local_ids))
    now = {d["id"]: d for f in sorted(glob.glob(os.path.join(bulk_dir, "claims-*.jsonl"))) for d in _jsonl(f)}
    withheld = {e["id"]: e["error"] for e in _jsonl(os.path.join(bulk_dir, "errors.jsonl"))}
    summary["claims"] = {"catalog_control": cp.get("catalog_control"), "bulk_counts": cp.get("counts"), "stopped": cp.get("stopped"),
                         "local_claim_nanopub_ids": len(local_ids)}
    summary["baseline"] = reproduce_imported(prev, imported, created)
    cls = classify(prev, now, imported, withheld)
    _write_json(os.path.join(out_dir, "claim-diff.json"), cls)
    summary["diff"] = {"counts": cls["counts"], "changed_field_counts": cls["changed_field_counts"]}
    inc = increment(cls, now)

    def record(d):
        return make_record(Draft.model_validate(d), created_at=created_at_of(d))

    new_records = [record(d) for d in inc["new"]]
    upd_records = [record(d) for d in inc["updates"]]
    refs = {cid: r for cid, r in imported.items()}
    refs.update({r["id"]: {k: r[k] for k in ("namespace", "kind", "id", "version")} for r in new_records})

    # claim tests
    test_ids = ids_from_heads(mcp.sparql(claim_tests_heads_query()), TEST_SEG)
    snaps, test_errors = [], []
    for i in range(0, len(test_ids), batch_tests):
        chunk = test_ids[i:i + batch_tests]
        rows = mcp.sparql(claim_test_rows_query(chunk))
        if len(rows) >= 3000:
            raise RuntimeError("claim-test SPARQL page hit its 3000-row limit; lower batch_tests rather than truncate")
        for cid in chunk:
            try:
                snaps.append(test_snapshot(cid, rows))
            except LookupError as exc:
                test_errors.append({"id": cid, "error": str(exc)})
    retrieved = iso_utc()
    ev_records, untargeted = [], []
    for ts in snaps:
        target = refs.get(ts["claim_id"])
        if target is None:
            untargeted.append(ts["claim_id"])
            continue
        try:
            d = to_evidence_draft(ts, target, retrieved)
            validate_draft(d)
            ev_records.append(make_record(Draft.model_validate(d), created_at=retrieved))
        except (ValueError, KeyError) as exc:
            test_errors.append({"id": ts["claim_id"], "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
    with open(os.path.join(out_dir, "claim-test-snapshots.jsonl"), "w") as fh:
        for ts in snaps:
            fh.write(json.dumps(ts, sort_keys=True) + "\n")
    summary["claim_tests"] = {"nanopubs": len(test_ids), "snapshotted": len(snaps), "evidence_records": len(ev_records),
                              "errors": test_errors, "no_claim_in_frontier": untargeted,
                              "verdicts": dict(collections.Counter(s["verdict"] for s in snaps)),
                              "data_kinds": dict(collections.Counter(str(s["data_kind"]) for s in snaps)),
                              "preregistered": dict(collections.Counter(str(s["preregistered"]) for s in snaps)),
                              "with_revisions": sum(1 for s in snaps if s["revisions"]),
                              "dataset_declarations": sum(len(s["datasets"]) for s in snaps),
                              "dataset_declarations_with_sha256": sum(1 for s in snaps for x in s["datasets"] if x["declared_sha256"])}
    _write_json(os.path.join(out_dir, "records-new-claims-and-tests.json"), new_records + ev_records)
    _write_json(os.path.join(out_dir, "records-updates-FORK.json"), upd_records)

    # readable index: one row per Claim ref Frontier will hold as head after the clean import
    tests_by = collections.defaultdict(list)
    for r in ev_records:
        pa = r["payload"]["provider_assessment"]
        tests_by[r["payload"]["target"]["id"]].append({"evidence_ref": {k: r[k] for k in ("namespace", "kind", "id", "version")},
                                                       "upstream_verdict": pa["verdict"], "upstream_confidence": pa["confidence"],
                                                       "data_kind": pa["data_kind"], "preregistered": pa["preregistered"]})
    with open(os.path.join(out_dir, "claim-context.jsonl"), "w") as fh:
        for cid in sorted(refs):
            d = now.get(cid) if cid not in imported else prev.get(cid)
            if d is not None:
                row = readable_context(d, refs[cid], tests_by.get(cid))
                if cid in now:
                    row["publication"]["nanopub_path_now"] = now[cid]["payload"]["prior_review"]["delphi_original"]["nanopub_path"]
                fh.write(json.dumps(row, sort_keys=True) + "\n")
    with open(os.path.join(out_dir, "receipts.jsonl"), "w") as fh:
        for rc in mcp.receipts:
            fh.write(json.dumps(rc, sort_keys=True) + "\n")
    summary.update(ended=iso_utc(), requests=mcp.requests, receipts=len(mcp.receipts),
                   records={"new_claims": len(new_records), "claim_test_evidence": len(ev_records), "updates_that_fork": len(upd_records)})
    _write_json(os.path.join(out_dir, "summary.json"), summary)
    return summary


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Read-only live Delphi ingestion run (inventory, diff, claim tests); imports nothing")
    ap.add_argument("--out", required=True)
    ap.add_argument("--baseline-drafts", action="append", default=[], help="frozen Claim draft JSONL the imported versions were built from")
    ap.add_argument("--imported-plan", action="append", default=[], help="import plan.json whose refs Frontier holds")
    ap.add_argument("--imported-records", action="append", default=[], help="Records JSON imported as-is (e.g. the NCA chain)")
    ap.add_argument("--max-requests", type=int, default=260)
    ap.add_argument("--min-interval", type=float, default=1.0)
    ap.add_argument("--max-wall-s", type=float, default=540)
    a = ap.parse_args(argv)
    mcp = Delphi(max_requests=a.max_requests, min_interval=a.min_interval, max_wall_s=a.max_wall_s)
    s = run(mcp, a.out, baseline=load_baseline(a.baseline_drafts, a.imported_plan, a.imported_records))
    print(json.dumps({k: s[k] for k in ("build", "diff", "records", "requests")}, indent=1))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
