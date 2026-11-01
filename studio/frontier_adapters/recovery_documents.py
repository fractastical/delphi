"""Register missing Project documents as documentary source assessments.

This hashes actual local files and preserves upstream bibliographic/read-level
assertions. It does not fetch papers, manufacture a measured result, execute an
Action, or convert an upstream review into local acceptance.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from frontier.models import Draft, make_record

from .import_cli import ref_of

DOCUMENTS = {
    "doc-SPEC-005": ("specs/SPEC-005-agentic-engineering-demo.md", "Mission engineering specification"),
    "doc-model-coupling": ("docs/model-coupling.md", "Typed model coupling specification"),
    "doc-2026-10-31-kcne1-binding-ddg-STOPPED": ("results/2026-10-31-kcne1-binding-ddg-STOPPED.md", "Documented stopped KCNE1 coverage test"),
}
SOURCE_IDS = {"src-fish1990", "src-parkchoi2010", "src-davenport1992", "src-davenport2003", "src-daane2021", "src-darwin1859", "src-lovejoy2004"}


def build(root, *, namespace, issuer, created_at, source_commit, documents=None, source_ids=None):
    """Register explicit documents, optionally alongside the original fish source register.

    Secondary projects pass their own documents and an empty source_ids set;
    they must not inherit Flying Fish bibliography or biological context.
    """
    root = Path(root)
    documents = DOCUMENTS if documents is None else documents
    source_ids = SOURCE_IDS if source_ids is None else source_ids
    mission_path = "site/content/mission.json"
    mission = json.loads((root / mission_path).read_text()) if source_ids else {"sources": []}
    source_rows = {"src-" + row["id"]: (index, row) for index, row in enumerate(mission["sources"])}
    records, rows = [], []
    for identifier in [*documents, *sorted(source_ids)]:
        if identifier in documents:
            path, title = documents[identifier]
            selector, upstream = "whole document", None
            read_level = "exact local document bytes read and hashed; reported past results are not rerun"
        else:
            index, upstream = source_rows[identifier]
            path, title, selector = mission_path, upstream["cite"], f"/sources/{index}"
            read_level = "upstream register reports: " + upstream["read_level"] + "; not independently repeated by recovery"
        data = (root / path).read_bytes()
        digest = sha256(data).hexdigest()
        source = {"uri": f"https://github.com/kganjam/delphi-frontier/blob/{source_commit}/{path}",
                  "locator": selector, "source_version": source_commit, "content_sha256": digest,
                  "content_available": False, "access": "Local repository document/metadata read; references only, no upstream paper bytes fetched by recovery", "license": None}
        provenance = {"documentary_registration": True, "execution_performed": False,
                      "source_file": {"path": path, "sha256": digest, "byte_size": len(data), "selector": selector},
                      "upstream_source_register": deepcopy(upstream), "read_level": read_level,
                      "producer_exception": "Documentary/source curation has no executed simulator Action; none is invented"}
        claim = make_record(Draft(namespace=namespace, issuer=issuer, kind="Claim", id="documentary:" + identifier,
                                  source_uri="urn:frontier:documentary:" + identifier, visibility="public",
                                  payload={"title": "Documentary registration: " + title,
                                           "statement": "The pinned repository file registers this document/source context. Its scientific assertions remain attributed and unreviewed; this is not a new observation or execution.",
                                           "context": "Missing Project member recovery from actual local bytes; bibliographic metadata and upstream read-level assertions are distinct from primary-source validation.",
                                           "assumptions": ["The existing source register's bibliographic identity is preserved without inventing a DOI or locator"],
                                           "limitations": ["No independent source-content verification, empirical measurement, simulation execution or receiving-node acceptance is established"],
                                           "source": source, "source_record_version": digest, "origin": "derived", "prior_review": {"adapter": provenance}}), created_at=created_at)
        evidence = make_record(Draft(namespace=namespace, issuer=issuer, kind="Evidence", id=identifier,
                                     source_uri="urn:frontier:documentary-evidence:" + identifier, visibility="public",
                                     payload={"target": ref_of(claim), "evidence_kind": "source_assessment", "source": source,
                                              "created_time": {"value": created_at, "basis": "witnessed"},
                                              "retrieved_time": {"value": created_at, "basis": "witnessed"},
                                              "method": "Read and SHA256-hash the exact local repository file; register its documentary role and preserve reported source context. No paper retrieval, simulation or experiment performed.",
                                              "context": title + ". " + read_level,
                                              "assumptions": ["Upstream metadata/read levels remain assertions by their original curator"],
                                              "provenance": provenance, "source_dependence": {"group": "local-document-sha256:" + digest, "note": "Rows sharing one source register are one documentary input, not independent experiments"},
                                              "uncertainty": "Primary source coverage and biological validity not independently measured here; unavailable full text remains unavailable",
                                              "limitations": ["Documentary source_assessment, not observed/simulated/formal Evidence", "No executed producer Action is asserted or manufactured", "Reference-only artifact; no new redistribution licence or hosted URL asserted"],
                                              "relation": "context_only", "produced_by": None,
                                              "artifacts": [{"title": Path(path).name, "uri": "urn:sha256:" + digest, "sha256": digest,
                                                             "byte_size": len(data), "media_type": "application/json" if path.endswith(".json") else "text/markdown",
                                                             "role": "input", "availability": "referenced", "license": None}]}), created_at=created_at)
        records.extend([claim, evidence])
        rows.append({"member_id": identifier, "document_claim": ref_of(claim), "document_evidence": ref_of(evidence), **provenance})
    return records, {"schema": "frontier.project-document-registration/1", "records": len(records), "document_members": len(rows), "rows": rows,
                     "scope": "Documentary source assessments only; no external fetch, executed Action, local review or biological acceptance"}


def live_project(draft, store, *, issuer):
    """Keep every member/index; exact live refs only. Fail rather than dropping one."""
    out = deepcopy(draft)
    original_refs = [deepcopy(member["ref"]) for member in out["payload"]["members"]]
    out["namespace"], out["issuer"] = store.namespace, issuer
    out["predecessor"] = None
    for member in out["payload"]["members"]:
        member["ref"] = store.head_ref(member["ref"]["kind"], member["ref"]["id"])["ref"]
        if member.get("calibration"):
            member["calibration"] = store.head_ref(member["calibration"]["kind"], member["calibration"]["id"])["ref"]
        if member["ref"]["id"] in DOCUMENTS or member["ref"]["id"] in SOURCE_IDS:
            member["applicability"] += " Live member is a documentary source_assessment registration, not a newly executed observation or simulation."
        if member["ref"]["id"] == "src-parkchoi2010":
            member["applicability"] += " Disagreement retained: the source register attributes summarized full-text access, while the earlier Project draft calls the paper unread; no audited coefficient is inferred from this difference."
    for question in out["payload"]["open_questions"]:
        if question.get("problem"):
            ref = question["problem"]
            question["problem"] = store.head_ref(ref["kind"], ref["id"])["ref"]
    limitations = [text for text in out["payload"]["limitations"] if "snapshot-catalog ref" not in text]
    limitations += ["Exact members were repinned from the original thirteen-member snapshot draft without removing or reordering any member; documentary source registrations do not add biological validation.",
                    "Scale coverage and descriptive requirements retain the original draft's bounded scope; subsequently registered assets may require a later Project version."]
    out["payload"]["limitations"] = limitations
    out["payload"]["source"]["access"] = "Original repository snapshot draft retained as source; every linked member now pins an exact public live record"
    Draft.model_validate(out)
    assert [(r["kind"], r["id"]) for r in original_refs] == [(m["ref"]["kind"], m["ref"]["id"]) for m in out["payload"]["members"]]
    return out
