import hashlib
import json

import pytest

from frontier_compute.checkpoint_entry import export_checkpoints, sync_small


def fixture(tmp_path):
    science = tmp_path / "science"
    out = tmp_path / "out"
    out.mkdir()
    (science / "checkpoints").mkdir(parents=True)
    data = b"atomic complete state"
    path = science / "checkpoints/R2-1.ckpt"
    path.write_bytes(data)
    row = {
        "file": path.name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    (science / "checkpoints/manifest.json").write_text(
        json.dumps({"coherent_only_if_listed": True, "snapshots": [row]})
    )
    return science, out, row


def test_only_native_coherent_hashes_exported_once(tmp_path):
    science, out, row = fixture(tmp_path)
    calls = []

    def uploader(cap, path):
        calls.append(path)
        return {
            "sha256": row["sha256"],
            "bytes": row["bytes"],
            "object": "exact-object",
        }

    ledger = {}
    export_checkpoints(science, out, [{"capability": {}}], ledger, uploader=uploader)
    export_checkpoints(science, out, [{"capability": {}}], ledger, uploader=uploader)
    assert len(calls) == 1 and len(ledger) == 1
    assert (
        json.loads((out / "external-checkpoints.json").read_text())["checkpoints"][
            "R2-1.ckpt"
        ]["source_snapshot"]
        == row
    )


@pytest.mark.parametrize(
    "change", ["bytes", "hash", "traversal", "unlisted", "symlink"]
)
def test_corrupt_or_unlisted_checkpoint_never_uploads(tmp_path, change):
    science, out, row = fixture(tmp_path)
    if change == "bytes":
        row["bytes"] += 1
    elif change == "hash":
        row["sha256"] = "0" * 64
    elif change == "traversal":
        row["file"] = "../foreign.ckpt"
    elif change == "symlink":
        path = science / "checkpoints/R2-1.ckpt"
        path.rename(science / "other")
        path.symlink_to(science / "other")
    (science / "checkpoints/manifest.json").write_text(
        json.dumps(
            {"coherent_only_if_listed": change != "unlisted", "snapshots": [row]}
        )
    )
    with pytest.raises(ValueError):
        export_checkpoints(
            science,
            out,
            [{"capability": {}}],
            {},
            uploader=lambda *a: pytest.fail("must not upload"),
        )


def test_large_state_is_external_not_silently_dropped(tmp_path):
    science, out, _ = fixture(tmp_path)
    (science / "status.json").write_text('{"native_rc":10}')
    sync_small(science, out)
    assert (out / "science/status.json").read_text() == '{"native_rc":10}'
    assert (out / "science/checkpoints/manifest.json").exists()
    assert not (out / "science/checkpoints/R2-1.ckpt").exists()
    assert (science / "checkpoints/R2-1.ckpt").exists()
