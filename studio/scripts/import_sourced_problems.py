"""Map newly sourced problem proposals onto Frontier Problem drafts.

Separate from `import_register.py` because the two inputs have genuinely different shapes: the
register is a curated YAML file whose provenance is mostly absent, while a proposal carries a
retrieved identifier, a locator and a quote tested as an exact substring of the retrieved text.
The bounded-string helpers are shared rather than copied.

Nothing here upgrades a proposal. A problem arrives `proposed`; `completeness` is the author's
own declaration, and an independent reviewer decides whether it holds.
"""
from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from frontier.models import ACTIONABILITY, Draft, Problem  # noqa: E402
from import_register import MAX_SHORT, NAMESPACE, strings, text  # noqa: E402


def uri_for(source):
    if source.get("doi"):
        return f"https://doi.org/{str(source['doi']).removeprefix('https://doi.org/')}"
    ident = str(source.get("identifier", ""))
    digits = "".join(ch for ch in ident if ch.isdigit())
    if "PMID" in ident.upper() and digits:
        return f"https://pubmed.ncbi.nlm.nih.gov/{digits}/"
    if ident.upper().startswith("PMC"):
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{ident}/"
    return None


def to_draft(item):
    src = item.get("source") or {}
    read_level = src.get("read_level", "unstated")
    payload = {
        "title": text(item["title"], MAX_SHORT),
        "known_state": text(item["known_state"]),
        "question": text(item["question"]),
        "problem_kind": "sourced_field_open_problem",
        "novelty_status": text(f"{item.get('novelty_status', 'unchecked')}. "
                               f"{item.get('novelty_note', '')}", MAX_SHORT),
        "data_access": text(item.get("data_access")) or "No data requirement stated.",
        "completeness": item.get("completeness", "recorded"),
        "acceptance_criteria": strings(item.get("acceptance_criteria")),
        "falsifiers": strings(item.get("falsifiers")),
        "next_action": text(item.get("next_action")),
        "cost_stop_bounds": text(item.get("cost_stop_bounds")),
        "required_capabilities": [],
        "downstream_uses": strings(item.get("field")),
        "source": {
            "uri": uri_for(src),
            "locator": text(src.get("locator"), MAX_SHORT),
            "source_version": None,
            "content_sha256": None,
            # The abstract was read; the bytes are not held here, so nothing may be exported as
            # content. This is what keeps the record clear of the export licence gate.
            "content_available": False,
            "access": text(f"Public bibliographic record. read_level={read_level}. "
                           "The quote was tested as an exact substring of the retrieved text; "
                           "full text was NOT read unless read_level says otherwise.", MAX_SHORT),
            "license": None,
        },
        "original": {"proposal": item, "proposal_schema": "frontier-sourced-problems-0.1"},
    }
    return {"namespace": NAMESPACE, "kind": "Problem", "id": item["id"], "issuer": "importer",
            "source_uri": "urn:frontier:import:sourced-problem-proposal", "payload": payload}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proposals")
    ap.add_argument("--out")
    args = ap.parse_args()

    raw = json.loads(Path(args.proposals).read_text())
    items = raw if isinstance(raw, list) else raw.get("problems", raw)

    drafts, rejected = [], []
    for item in items:
        try:
            draft = to_draft(item)
            Draft.model_validate(draft)
            drafts.append(draft)
        except Exception as exc:
            rejected.append({"id": item.get("id"), "error": str(exc)[:400]})

    actionable = [d for d in drafts if d["payload"]["completeness"] == "actionable"]
    # An actionable problem that is missing one of the four would have been refused by the model,
    # so this is a belt-and-braces readback rather than the gate itself.
    assert all(all(d["payload"][f] for f in ACTIONABILITY) for d in actionable)
    with_uri = sum(1 for d in drafts if d["payload"]["source"]["uri"])
    report = {
        "proposals": args.proposals,
        "proposals_sha256": sha256(Path(args.proposals).read_bytes()).hexdigest(),
        "proposed": len(items), "importable": len(drafts), "rejected": len(rejected),
        "rejections": rejected,
        "actionable": len(actionable),
        "recorded_not_actionable": len(drafts) - len(actionable),
        "with_resolvable_source_uri": with_uri,
        "read_levels": sorted({d["payload"]["original"]["proposal"].get("source", {})
                               .get("read_level", "unstated") for d in drafts}),
        "note": "Imported as PROPOSED. completeness is the author's declaration; an independent "
                "reviewer decides whether it holds. No full text was read for any of these.",
    }
    if args.out:
        Path(args.out).write_text("".join(json.dumps(d, sort_keys=True) + "\n" for d in drafts))
        report["out"] = args.out
    print(json.dumps(report, indent=1))
    return 0 if drafts and not rejected else 1


if __name__ == "__main__":
    raise SystemExit(main())
