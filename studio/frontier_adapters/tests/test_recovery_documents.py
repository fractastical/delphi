"""Documentary registration cannot masquerade as execution or trim Project members."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from frontier.models import Record
from frontier.store import Missing
from frontier_adapters.recovery_documents import build, live_project

ROOT = Path(__file__).resolve().parents[2]


def documents():
    return build(ROOT, namespace="delphi-frontier", issuer="corpus-importer", created_at="2026-10-31T21:20:00Z", source_commit="test-only-source-identity")


def test_twenty_valid_records_register_ten_missing_members_without_actions():
    records, report = documents()
    assert len(records) == 20 and report["document_members"] == 10
    assert {r["kind"] for r in records} == {"Claim", "Evidence"}
    for record in records:
        Record.model_validate(record)
        source = record["payload"]["source"]
        row = next(item for item in report["rows"] if item["document_claim"]["version"] == record["version"] or item["document_evidence"]["version"] == record["version"])
        assert source["content_sha256"] == sha256((ROOT / row["source_file"]["path"]).read_bytes()).hexdigest()
        if record["kind"] == "Evidence":
            assert record["payload"]["evidence_kind"] == "source_assessment"
            assert record["payload"]["relation"] == "context_only"
            assert record["payload"]["produced_by"] is None
            assert record["payload"]["provenance"]["execution_performed"] is False
    observed_register = next(r for r in records if r["id"] == "src-fish1990")
    assert observed_register["payload"]["provenance"]["upstream_source_register"]["kind"] == "observed"
    assert observed_register["payload"]["evidence_kind"] == "source_assessment"


def test_repin_keeps_all_thirteen_members_and_exact_documentary_ids():
    records, _ = documents()
    draft = json.loads((ROOT / "projects/flying-fish.draft.json").read_text())["draft"]
    original = deepcopy(draft)
    versions = {(r["kind"], r["id"]): {k: r[k] for k in ("namespace", "kind", "id", "version")} for r in records}
    for member in draft["payload"]["members"]:
        versions.setdefault((member["ref"]["kind"], member["ref"]["id"]), member["ref"] | {"namespace": "delphi-frontier"})
    class FakePublicStore:
        namespace = "delphi-frontier"
        def head_ref(self, kind, identifier):
            return {"ref": versions[kind, identifier]}
    actual = live_project(draft, FakePublicStore(), issuer="corpus-importer")
    assert draft == original
    assert len(actual["payload"]["members"]) == 13
    assert [m["ref"]["id"] for m in actual["payload"]["members"]] == [m["ref"]["id"] for m in draft["payload"]["members"]]
    assert all(m["ref"]["namespace"] == "delphi-frontier" for m in actual["payload"]["members"])
    park = next(m for m in actual["payload"]["members"] if m["ref"]["id"] == "src-parkchoi2010")
    assert "Disagreement retained" in park["applicability"]


def test_missing_live_member_refuses_instead_of_shrinking_or_retaining_snapshot():
    draft = json.loads((ROOT / "projects/flying-fish.draft.json").read_text())["draft"]
    original = deepcopy(draft)
    class MissingStore:
        namespace = "delphi-frontier"
        def head_ref(self, kind, identifier):
            raise Missing("test-only absent source")
    with pytest.raises(Missing):
        live_project(draft, MissingStore(), issuer="corpus-importer")
    assert draft == original
