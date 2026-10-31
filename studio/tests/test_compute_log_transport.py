import base64
import hashlib
import json

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
