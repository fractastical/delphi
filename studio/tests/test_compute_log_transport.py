import base64
import hashlib
import json
import io
import tarfile

import pytest

from frontier_compute.vendor.compute_ops.batch import extract_parts, extract_result


@pytest.mark.parametrize("kind", ["PART", "RESULT"])
def test_legitimate_identical_payload_chunks_are_retained(kind):
    blob = b"abcabcxyz"
    metadata = {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "truncated": False}
    lines = [f"COPS_{kind}_BEGIN " + json.dumps(metadata)]
    lines += ["COPS_B64 " + base64.b64encode(blob[i:i+3]).decode() for i in range(0, len(blob), 3)]
    lines += [f"COPS_{kind}_END"]
    result = extract_parts(lines)[0] if kind == "PART" else extract_result(lines)
    assert result[1] == blob


def test_timestamped_query_overlap_preserves_repeated_real_data():
    blob = b"abcabcxyz"
    metadata = {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "truncated": False}
    lines = ["COPS_PART_BEGIN " + json.dumps(metadata),
             "t1 COPS_B64 YWJj", "t2 COPS_B64 YWJj", "t2 COPS_B64 YWJj", "t3 COPS_B64 eHl6", "COPS_PART_END"]
    assert extract_parts(lines)[0][1] == blob


def test_corruption_still_fails_closed():
    metadata = {"bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest(), "truncated": False}
    with pytest.raises(ValueError, match="digest mismatch"):
        extract_result(["COPS_RESULT_BEGIN " + json.dumps(metadata), "COPS_B64 eHl6", "COPS_RESULT_END"])


@pytest.mark.parametrize("corrupt", [False, True])
def test_clipped_header_requires_exact_payload_hash_in_verified_outer_receipt(corrupt):
    blob = b"actual complete scientific archive"
    receipt = {"seq": 0, "id": "fixed-case", "bytes": len(blob),
               "sha256": hashlib.sha256(blob).hexdigest(), "truncated": False}
    buf = io.BytesIO()
    payload = json.dumps({"workloads": [receipt]}).encode()
    with tarfile.open(fileobj=buf, mode="w:gz") as archive:
        member = tarfile.TarInfo("./queue_receipts.json")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    outer = buf.getvalue()
    meta = {"bytes": len(outer), "sha256": hashlib.sha256(outer).hexdigest(), "truncated": False}
    lines = ['COPS_PART_BEGIN {"files":{"clipped',
             "COPS_B64 " + base64.b64encode(b"corrupted" if corrupt else blob).decode(),
             "COPS_PART_END", "COPS_RESULT_BEGIN " + json.dumps(meta),
             "COPS_B64 " + base64.b64encode(outer).decode(), "COPS_RESULT_END"]
    if corrupt:
        with pytest.raises(ValueError, match="uniquely match"):
            extract_parts(lines)
    else:
        recovered, actual = extract_parts(lines)[0]
        assert actual == blob and recovered["id"] == "fixed-case"
        assert recovered["metadata_recovery"].startswith("Exact digest/size")


def test_clipped_header_without_verified_receipt_is_not_accepted():
    with pytest.raises(ValueError, match="no verified outer receipt"):
        extract_parts(['COPS_PART_BEGIN {"files":{"clipped', 'COPS_B64 YWJj', 'COPS_PART_END'])
