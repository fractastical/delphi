"""Map a curated open-problems register onto Frontier Problem drafts.

Every field is copied or derived from the register. Nothing is invented: the four
actionability fields (acceptance criteria, falsifiers, next action, stop bounds) have no
source in the register, so every problem imports as `completeness="recorded"` and the
importer reports that count rather than filling them in.

The register's questions are a CURATOR'S questions. A cited source that calls a facet open
(an `attestation` with stance "open") is evidence about that facet, not proof that the question
as the curator phrased it is a primary-literature open problem, so no problem is labelled
`sourced_field_open_problem`; they import as `curated_question` (CURATOR_KIND). The register's
three provenance fields are kept separate end to end: `why_source`, `references` and
`attestations`. Every item of each is copied verbatim into `original.register_provenance`
(which survives even when the whole-record copy is dropped for size), and the report counts
them separately. Quotes are never edited, shortened or composed: they are the curator's
transcription and are not checked against the papers by this script, which fetches nothing.

Usage: python3 scripts/import_register.py <register.yaml> [--out drafts.jsonl]
"""
from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from frontier.models import ACTIONABILITY, MAX_RECORD_BYTES, Draft, Problem, canonical  # noqa: E402

NAMESPACE = "node-a"
CURATOR_KIND = "curated_question"  # see the module docstring; SPEC-001 open question 3
MAX_ITEMS = 40
MAX_SHORT = 3000
MAX_TEXT = 12000


def text(value, limit=MAX_TEXT):
    """Flatten a scalar, list or mapping to one bounded string without dropping content silently."""
    if value is None:
        return None
    if isinstance(value, str):
        out = value.strip()
    elif isinstance(value, (int, float, bool)):
        out = str(value)
    elif isinstance(value, list):
        out = "; ".join(x for x in (text(v, limit) for v in value) if x)
    elif isinstance(value, dict):
        out = "; ".join(f"{k}: {t}" for k, v in value.items() if (t := text(v, limit)))
    else:
        out = str(value)
    if not out:
        return None
    return out[: limit - 1] + "…" if len(out) > limit else out


def strings(value):
    items = value if isinstance(value, list) else ([value] if value else [])
    out = [t for v in items if (t := text(v, MAX_SHORT))]
    return out[:MAX_ITEMS]


def uri_for(entry):
    """A resolvable URI from whatever identifier the entry carries, or None."""
    if not isinstance(entry, dict):
        return None
    if entry.get("url"):
        return text(entry["url"], MAX_SHORT)
    pmcid = entry.get("pmcid")
    if pmcid and str(pmcid).upper().startswith("PMC"):
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
    if entry.get("pmid"):
        return f"https://pubmed.ncbi.nlm.nih.gov/{entry['pmid']}/"
    if entry.get("doi"):
        return f"https://doi.org/{entry['doi']}"
    return None


def attestation_items(problem):
    """Every attestation, verbatim and in register order. The quote is copied unmodified (no strip, no truncation).

    `uri` is derived from the entry's own identifier and is marked as derived; nothing else is added. An entry
    that is not a mapping is kept as `raw` so that no item disappears.
    """
    items = []
    for i, a in enumerate(problem.get("attestations") or []):
        if not isinstance(a, dict):
            items.append({"index": i, "raw": a, "uri": None, "stance": None})
            continue
        items.append({"index": i, "pmcid": a.get("pmcid"), "url": a.get("url"), "uri": uri_for(a), "locator": a.get("locator"),
                      "quote": a.get("quote"), "kind": a.get("kind"), "stance": a.get("stance"),
                      "quote_checked_against_source": False,
                      **{k: v for k, v in a.items() if k not in ("pmcid", "url", "locator", "quote", "kind", "stance")}})
    return items


def usable_attestation(item):
    """An attestation that can stand as the problem's source: stance open, a resolvable id, a locator and a quote."""
    return (item.get("stance") == "open" and item.get("uri") and isinstance(item.get("locator"), str) and item["locator"].strip()
            and isinstance(item.get("quote"), str) and item["quote"].strip())


def source_of(problem):
    """The register has THREE provenance fields, kept separate here and in the report.

    1. `why_source`: one pmcid, a locator and a verbatim quote (34 of 250). Used first, as before.
    2. `attestations`: a list of cited sources, each with pmcid or url, locator, quote, kind and a stance of
       "open" or "settled" (465 entries, on all 250 problems). The importer used to ignore this field, which
       is why it reported 148 problems with no source at all. The first attestation with stance "open" (a
       resolvable id, a locator and a quote) is used when `why_source` is absent. A "settled" attestation never
       stands as the source for a question's openness (it is preserved, and counted).
    3. `references`: a list of cited papers with a role and a curator's note, no locator and no quote.
       WEAKER than the other two: supports the topic, not any specific statement.

    In every case `source` points at a citation. The importer fetched no bytes: a quote is the curator's
    transcription and is not independently verified here, and an attestation supports that the cited source
    calls a facet of the topic open, not that the curator's question is a primary-literature open problem.
    """
    ws = problem.get("why_source") or {}
    if ws:
        return {"uri": uri_for(ws), "locator": text(ws.get("locator"), MAX_SHORT),
                "source_version": None, "content_sha256": None, "content_available": False,
                "access": "Public reference, from the register's why_source. This importer did not "
                          "retrieve the bytes, so the quote is the curator's transcription and is "
                          "not independently verified here.",
                "license": None, "provenance_path": "why_source"}
    items = attestation_items(problem)
    usable = [x for x in items if usable_attestation(x)]
    if usable:
        first = usable[0]
        settled = sum(1 for x in items if x.get("stance") == "settled")
        return {"uri": first["uri"], "locator": text(first["locator"], MAX_SHORT),
                "source_version": None, "content_sha256": None, "content_available": False,
                "access": f"Public reference, from the register's attestations (entry {first['index']} of {len(items)}; "
                          f"stance {first['stance']}, kind {first.get('kind')}). The quote is the curator's transcription and was "
                          "not checked against the source; this importer retrieved no bytes. The citation supports that the "
                          "source calls a facet of the topic open, not that the question as phrased is a primary-literature "
                          f"open problem. {settled} of {len(items)} attestations have stance settled for some facet; all items "
                          "are in original.register_provenance.",
                "license": None, "provenance_path": "attestation"}
    refs = [r for r in (problem.get("references") or []) if uri_for(r)]
    if refs:
        return {"uri": uri_for(refs[0]), "locator": None,
                "source_version": None, "content_sha256": None, "content_available": False,
                "access": f"Public reference, from the register's references list ({len(refs)} entries, "
                          "first used here). WEAKER than why_source: no locator and no quote, so this "
                          "source supports the problem's topic and not any specific statement in it.",
                "license": None, "provenance_path": "references"}
    return {"uri": None, "locator": None, "source_version": None, "content_sha256": None,
            "content_available": False,
            "access": "The register records NO resolvable source for this problem in why_source, attestations "
                      "or references. It is a curator's statement, not a sourced field-level open problem, "
                      "and must not be presented as one.",
            "license": None, "provenance_path": "none"}


def legacy_provenance_path(problem):
    """What the previous importer chose (why_source, then references, never attestations). Kept ONLY to reproduce the 34/68/148 split."""
    if problem.get("why_source"):
        return "why_source"
    return "references" if [r for r in (problem.get("references") or []) if uri_for(r)] else "none"


def register_provenance(problem):
    """Item-level, verbatim copy of the three provenance fields. Nothing here is summarised or shortened."""
    return {"why_source": problem.get("why_source") or None,
            "references": list(problem.get("references") or []),
            "attestations": attestation_items(problem),
            "note": "Curator transcription. Quotes were not checked against the cited sources; no bytes were retrieved."}


def attestation_summary(problem):
    items = attestation_items(problem)
    return {"total": len(items), "open": sum(1 for x in items if x.get("stance") == "open"),
            "settled": sum(1 for x in items if x.get("stance") == "settled"),
            "distinct_sources": len({x["uri"] for x in items if x.get("uri")})}


def to_draft(problem):
    slug = problem["slug"]
    title = text(slug.replace("-", " ").replace("_", " ").capitalize(), MAX_SHORT)
    payload = {
        "title": title,
        "known_state": text(problem.get("why_it_matters")) or "The register states no background beyond the question itself.",
        "question": text(problem["statement"]),
        "problem_kind": CURATOR_KIND,
        "novelty_status": text(
            "A curator's question from the source register; field-level novelty was not re-checked by this importer. "
            f"Register importance: {text(problem.get('importance'), 400) or 'unstated'}. "
            f"Register tractability: {text(problem.get('tractability'), 400) or 'unstated'}. "
            f"Cited attestations: {(a := attestation_summary(problem))['total']} ({a['open']} open, {a['settled']} settled; "
            f"{a['distinct_sources']} distinct sources), transcribed by the curator and not checked against the sources.", MAX_SHORT),
        "data_access": text(problem.get("data_needed")) or "The register names no data requirement.",
        "completeness": "recorded",
        "required_capabilities": strings(problem.get("model_handles")),
        "downstream_uses": strings(problem.get("modules")),
        "source": {k: v for k, v in source_of(problem).items() if k != "provenance_path"},
        "original": {"register_record": problem,
                     "register_schema": "morphoswarm/data/problems/register.yaml",
                     "provenance_path": source_of(problem)["provenance_path"],
                     "register_provenance": register_provenance(problem)},
    }
    draft = {"namespace": NAMESPACE, "kind": "Problem", "id": slug, "issuer": "importer",
             "source_uri": "urn:frontier:import:morphoswarm-open-problems-register", "payload": payload}
    # `original` is the first thing to drop if a record exceeds the envelope limit: it is a
    # convenience copy, while every other field is load-bearing. Record that we dropped it.
    if len(canonical(draft).encode()) > MAX_RECORD_BYTES:
        payload["original"] = {"register_schema": payload["original"]["register_schema"],
                               "provenance_path": payload["original"]["provenance_path"],
                               "register_record_omitted": "Record exceeded the envelope byte limit.",
                               "register_record_sha256": sha256(canonical(problem).encode()).hexdigest(),
                               "register_provenance": payload["original"]["register_provenance"]}
    if len(canonical(draft).encode()) > MAX_RECORD_BYTES:
        # Still too large: keep every item and its identifier, locator and stance, and replace each quote by its digest and an
        # explicit omission flag. A quote is never truncated, because a shortened quote is a different, fabricated passage.
        prov = payload["original"]["register_provenance"]
        prov["attestations"] = [({**x, "quote": None, "quote_omitted_for_size": True,
                                  "quote_sha256": sha256(str(x.get("quote")).encode()).hexdigest()} if "quote" in x else x)
                                for x in prov["attestations"]]
    return draft


def register_field_counts(problems):
    """Counts of each provenance field as the REGISTER carries it, separately and independent of what the mapping uses."""
    atts = [(p, x) for p in problems for x in attestation_items(p)]
    refs = [(p, r) for p in problems for r in (p.get("references") or [])]
    by_source = {}
    for p, x in atts:
        if x.get("uri"):
            by_source.setdefault(x["uri"], set()).add(p["slug"])
    per_problem = [{x["uri"] for x in attestation_items(p) if x.get("uri")} for p in problems]
    ref_sources = {uri_for(r) for _, r in refs if uri_for(r)}
    return {
        "why_source": {"problems": sum(1 for p in problems if p.get("why_source")),
                       "with_pmcid_locator_quote": sum(1 for p in problems if (w := p.get("why_source") or {}) and uri_for(w) and w.get("locator") and w.get("quote"))},
        "references": {"problems": sum(1 for p in problems if p.get("references")),
                       "entries": len(refs), "resolvable_entries": sum(1 for _, r in refs if uri_for(r)),
                       "problems_with_a_resolvable_entry": sum(1 for p in problems if any(uri_for(r) for r in (p.get("references") or []))),
                       "distinct_resolvable_sources": len(ref_sources), "carry_locator_or_quote": sum(1 for _, r in refs if isinstance(r, dict) and (r.get("locator") or r.get("quote")))},
        "attestations": {"problems": sum(1 for p in problems if p.get("attestations")), "entries": len(atts),
                         "by_stance": {k: sum(1 for _, x in atts if x.get("stance") == k) for k in sorted({str(x.get("stance")) for _, x in atts})},
                         "by_kind": {k: sum(1 for _, x in atts if x.get("kind") == k) for k in sorted({str(x.get("kind")) for _, x in atts})},
                         "entries_with_pmcid": sum(1 for _, x in atts if x.get("pmcid")),
                         "entries_with_url_only": sum(1 for _, x in atts if not x.get("pmcid") and x.get("url")),
                         "entries_with_no_resolvable_id": sum(1 for _, x in atts if not x.get("uri")),
                         "entries_with_locator_and_quote": sum(1 for _, x in atts if x.get("locator") and x.get("quote")),
                         "problems_with_a_usable_open_attestation": sum(1 for p in problems if any(usable_attestation(x) for x in attestation_items(p))),
                         "problems_with_a_settled_facet": sum(1 for p in problems if any(x.get("stance") == "settled" for x in attestation_items(p))),
                         "problems_with_every_attestation_settled": sum(1 for p in problems if attestation_items(p) and all(x.get("stance") == "settled" for x in attestation_items(p))),
                         "distinct_sources": len(by_source),
                         "problems_resting_on_exactly_one_distinct_source": sum(1 for u in per_problem if len(u) == 1),
                         "max_problems_sharing_one_source": max((len(v) for v in by_source.values()), default=0)},
        "problems_with_none_of_the_three": sum(1 for p in problems if not (p.get("why_source") or p.get("references") or p.get("attestations"))),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("register")
    ap.add_argument("--out")
    args = ap.parse_args()

    raw = yaml.safe_load(Path(args.register).read_text())
    problems = raw["problems"] if isinstance(raw, dict) else raw
    register_sha = sha256(Path(args.register).read_bytes()).hexdigest()

    drafts, rejected, truncated = [], [], 0
    for problem in problems:
        try:
            draft = to_draft(problem)
            Draft.model_validate(draft)
            if "register_record_omitted" in draft["payload"]["original"]:
                truncated += 1
            drafts.append(draft)
        except Exception as exc:  # a rejection is a finding, not a crash
            rejected.append({"slug": problem.get("slug"), "error": str(exc)[:400]})

    actionable = sum(1 for d in drafts if d["payload"]["completeness"] == "actionable")
    chosen = {"why_source": 0, "attestation": 0, "references": 0, "none": 0}
    for d in drafts:
        chosen[d["payload"]["original"]["provenance_path"]] += 1
    legacy = {"why_source": 0, "references": 0, "none": 0}
    for p in problems:
        legacy[legacy_provenance_path(p)] += 1
    report = {
        "register": args.register,
        "register_sha256": register_sha,
        "problems_in_register": len(problems),
        "importable": len(drafts),
        "rejected": len(rejected),
        "rejections": rejected[:10],
        "actionable": actionable,
        "problem_kind_used": sorted({d["payload"]["problem_kind"] for d in drafts}),
        "source_fields_in_register": register_field_counts(problems),
        "source_chosen_for_the_draft": {
            "why_source": chosen["why_source"], "attestation_open_with_locator_and_quote": chosen["attestation"],
            "references_topic_only": chosen["references"], "no_resolvable_source": chosen["none"],
            "any_source": len(drafts) - chosen["none"],
            "scope": "Which field fed the single Problem.source of each draft. NOT the number of problems the register cites: "
                     "see source_fields_in_register, which counts each field separately, and original.register_provenance on "
                     "every draft, which keeps every item."},
        "previous_mapping": {**legacy, "scope": "What the previous importer reported (why_source, then references, attestations "
                             "never read). The 'none' count was a property of the field the importer read, not of the register."},
        "recorded_not_actionable": len(drafts) - actionable,
        "original_record_omitted_for_size": truncated,
        "missing_actionability_fields": list(ACTIONABILITY),
        "not_checked": "No quote, locator or identifier was checked against its source: this script fetches nothing. A count of "
                       "sources is not a count of independent evidence (one source can underlie several problems).",
        "why": "The register states what is unknown and why it matters. It does not state what would "
               "settle the question, what would refute an answer, what to do next, or when to stop. "
               "Those four fields are not invented here.",
    }
    if args.out:
        Path(args.out).write_text("".join(json.dumps(d, sort_keys=True) + "\n" for d in drafts))
        report["out"] = args.out
        report["out_sha256"] = sha256(Path(args.out).read_bytes()).hexdigest()
    print(json.dumps(report, indent=1))
    return 0 if drafts and not rejected else 1


if __name__ == "__main__":
    raise SystemExit(main())
