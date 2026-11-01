"""Secondary-project registration must preserve actual bytes without fish context."""
from hashlib import sha256

from frontier.models import Record
from frontier_adapters.recovery_documents import build


def test_explicit_documents_need_no_fish_register_and_keep_exact_identity(tmp_path):
    raw = b"# Validation contract\nA model implication is not a measured premise.\n"
    (tmp_path / "contract.md").write_bytes(raw)
    records, receipt = build(tmp_path, namespace="test-node", issuer="curator",
                             created_at="2026-11-01T06:00:00+00:00", source_commit="a" * 40,
                             documents={"doc-contract": ("contract.md", "Validation contract")}, source_ids=set())
    assert len(records) == 2
    claim, evidence = [Record.model_validate(r).model_dump() for r in records]
    assert evidence["payload"]["target"]["version"] == claim["version"]
    assert evidence["payload"]["source"]["content_sha256"] == sha256(raw).hexdigest()
    assert evidence["payload"]["evidence_kind"] == "source_assessment"
    assert evidence["payload"]["produced_by"] is None
    assert evidence["payload"]["provenance"]["upstream_source_register"] is None
    assert evidence["payload"]["artifacts"][0]["availability"] == "referenced"
    assert receipt["document_members"] == 1
    assert receipt["rows"][0]["member_id"] == "doc-contract"
