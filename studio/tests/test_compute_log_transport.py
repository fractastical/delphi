import base64
import hashlib
import json
import io
import tarfile
import os
from pathlib import Path
import subprocess
import sys

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


def test_real_worker_keeps_large_file_manifest_out_of_provider_log_header(tmp_path):
    script = Path(__file__).parents[1] / "frontier_compute/vendor/compute_ops/warm_worker.py"
    writer = "import os,pathlib; p=pathlib.Path(os.environ['COPS_OUT']); [(p/('evidence-'+'x'*150+str(i))).write_text('actual fixture') for i in range(120)]"
    queue = {"queue_id": "header-check", "max_wall_s": 30, "margin_s": 0,
             "workloads": [{"id": "many-files", "argv": [sys.executable, "-c", writer], "timeout_s": 10}]}
    config = tmp_path / "queue.json"
    config.write_text(json.dumps(queue))
    result = subprocess.run([sys.executable, str(script), str(config)], capture_output=True, text=True,
                            env={"PATH": os.environ["PATH"], "COPS_OUT": str(tmp_path / "out"),
                                 "WARM_PARTS_DIR": str(tmp_path / "parts"), "WARM_CWD": str(tmp_path)},
                            timeout=20, check=True)
    header_line = next(line for line in result.stdout.splitlines() if line.startswith("COPS_PART_BEGIN "))
    assert len(header_line.encode()) < 8000
    meta, blob = extract_parts(result.stdout.splitlines())[0]
    assert blob is not None and meta["rc"] == 0
    stored = (tmp_path / "out" / meta["files_manifest"]["path"]).read_bytes()
    assert hashlib.sha256(stored).hexdigest() == meta["files_manifest"]["sha256"]
    assert len(stored) > 16384 and len(json.loads(stored)["files"]) == 120
