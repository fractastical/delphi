"""Map a curated open-problems register onto Frontier Problem drafts.

Every field is copied or derived from the register. Nothing is invented: the four
actionability fields (acceptance criteria, falsifiers, next action, stop bounds) have no
source in the register, so every problem imports as `completeness="recorded"` and the
importer reports that count rather than filling them in.

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


def source_of(problem):
    """The register has TWO provenance paths and most entries have neither.

    `why_source` is the strong one: a pmcid, a locator and a verbatim quote, carried by 34 of
    250. `references` is weaker: a list of pmcids with a role and a curator's note, no locator
    and no quote, carried by 74 more. 148 of 250 have neither, and that absence is recorded
    here rather than papered over, because an evidence layer that cannot see its own unsourced
    fraction is worse than no evidence layer.
    """
    ws = problem.get("why_source") or {}
    if ws:
        return {"uri": uri_for(ws), "locator": text(ws.get("locator"), MAX_SHORT),
                "source_version": None, "content_sha256": None, "content_available": False,
                "access": "Public reference, from the register's why_source. This importer did not "
                          "retrieve the bytes, so the quote is the curator's transcription and is "
                          "not independently verified here.",
                "license": None, "provenance_path": "why_source"}
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
            "access": "The register records NO source for this problem. It is a curator's statement, "
                      "not a sourced field-level open problem, and must not be presented as one.",
            "license": None, "provenance_path": "none"}


def to_draft(problem):
    slug = problem["slug"]
    title = text(slug.replace("-", " ").replace("_", " ").capitalize(), MAX_SHORT)
    payload = {
        "title": title,
        "known_state": text(problem.get("why_it_matters")) or "The register states no background beyond the question itself.",
        "question": text(problem["statement"]),
        "problem_kind": "sourced_field_open_problem",
        "novelty_status": text(
            "Curated in the source register; field-level novelty was not re-checked by this importer. "
            f"Register importance: {text(problem.get('importance'), 400) or 'unstated'}. "
            f"Register tractability: {text(problem.get('tractability'), 400) or 'unstated'}.", MAX_SHORT),
        "data_access": text(problem.get("data_needed")) or "The register names no data requirement.",
        "completeness": "recorded",
        "required_capabilities": strings(problem.get("model_handles")),
        "downstream_uses": strings(problem.get("modules")),
        "source": {k: v for k, v in source_of(problem).items() if k != "provenance_path"},
        "original": {"register_record": problem,
                     "register_schema": "morphoswarm/data/problems/register.yaml",
                     "provenance_path": source_of(problem)["provenance_path"]},
    }
    draft = {"namespace": NAMESPACE, "kind": "Problem", "id": slug, "issuer": "importer",
             "source_uri": "urn:frontier:import:morphoswarm-open-problems-register", "payload": payload}
    # `original` is the first thing to drop if a record exceeds the envelope limit: it is a
    # convenience copy, while every other field is load-bearing. Record that we dropped it.
    if len(canonical(draft).encode()) > MAX_RECORD_BYTES:
        payload["original"] = {"register_schema": payload["original"]["register_schema"],
                               "register_record_omitted": "Record exceeded the envelope byte limit.",
                               "register_record_sha256": sha256(canonical(problem).encode()).hexdigest()}
    return draft


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
    paths = {"why_source": 0, "references": 0, "none": 0}
    for d in drafts:
        paths[d["payload"]["original"]["provenance_path"]] += 1
    report = {
        "register": args.register,
        "register_sha256": register_sha,
        "problems_in_register": len(problems),
        "importable": len(drafts),
        "rejected": len(rejected),
        "rejections": rejected[:10],
        "actionable": actionable,
        "provenance": {"with_locator_and_quote": paths["why_source"],
                       "topic_reference_only": paths["references"],
                       "no_source_at_all": paths["none"],
                       "any_source": paths["why_source"] + paths["references"]},
        "recorded_not_actionable": len(drafts) - actionable,
        "original_record_omitted_for_size": truncated,
        "missing_actionability_fields": list(ACTIONABILITY),
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
