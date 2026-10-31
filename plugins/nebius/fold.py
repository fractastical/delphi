"""Structure jobs on the Nebius Scientific AI Platform: ESMFold2, AlphaFold3, DiffDock.

Submissions use content-derived idempotency keys, so re-running a script after a lost
response or a crash re-attaches to the same operation instead of starting new work.
`collect` waits for an operation and downloads every output file plus a run record.

    from fold import Client, uniprot, submit_esmfold, submit_alphafold3, collect
"""
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nebius_mcp  # noqa: E402
from nebius_mcp import _find  # noqa: E402,F401


class Client(nebius_mcp.Client):
    """Retries transport failures; safe because every submission carries an idempotency key."""

    def _rpc(self, *args, **kwargs):
        for attempt in range(8):
            try:
                return super()._rpc(*args, **kwargs)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt == 7:
                    raise
                print(f"  transport error ({e}); retrying", file=sys.stderr, flush=True)
                time.sleep(min(60, 5 * 2 ** attempt))

RUN_SCHEMA = "fs2-serve.nebius.ai/scientific-run-request/v1"
MANIFEST_SCHEMA = "fs2-serve.nebius.ai/scientific-artifact-manifest/v1"
MANIFEST_TYPE = "application/vnd.fs2.scientific-manifest+json"


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def uniprot(acc, cache_dir):
    """Canonical UniProtKB sequence, cached as FASTA, with a provenance record."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{acc}.fasta"
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    if not path.exists():
        path.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    raw = path.read_bytes()
    lines = raw.decode().splitlines()
    return {
        "accession": acc,
        "header": lines[0][1:],
        "sequence": "".join(l.strip() for l in lines[1:]),
        "download_url": url,
        "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
        "byte_size": len(raw),
        "sha256": _sha(raw),
    }


def _upload_json(client, model_id, obj, tmp_dir):
    data = json.dumps(obj, sort_keys=True).encode()
    p = Path(tmp_dir) / f"{_sha(data)[:16]}.json"
    p.write_bytes(data)
    return client.upload(model_id, p, "application/json")


def _manifest(client, model_id, name, semantic_type, inner, tmp_dir):
    body = {"schema": MANIFEST_SCHEMA, "entries": [{"name": name, "semantic_type": semantic_type, "artifact": inner}]}
    data = json.dumps(body, sort_keys=True).encode()
    p = Path(tmp_dir) / f"manifest-{_sha(data)[:16]}.json"
    p.write_bytes(data)
    return client.upload(model_id, p, MANIFEST_TYPE)


def _op_id(sub):
    op = (sub.get("operation") or {}).get("id") or sub.get("operation_id") or sub.get("id") \
        or (sub.get("error") or {}).get("operation_id")
    if not op:
        raise RuntimeError(f"submit rejected: {json.dumps(sub)[:1500]}")
    return op


def submit_esmfold(client, tag, sequence, tmp_dir, seed=0):
    params = {"sequence": sequence, "mode": "single-sequence", "seed": seed}
    inner = _upload_json(client, "esmfold2", {"sequence": sequence, "mode": "single-sequence"}, tmp_dir)
    ref = _manifest(client, "esmfold2", "esmfold2-input", "esmfold2-input-json/v1", inner, tmp_dir)
    sub = client.call("submit_esmfold2", {
        "schema": RUN_SCHEMA, "operation": "predict-structure", "service_class": "customer-batch",
        "input_manifest": ref, "parameters": params,
        "idempotency_key": f"esmfold2-{tag}-{_sha(sequence.encode())[:24]}-s{seed}",
        "output_prefix": f"delphisci/esmfold2/{tag}",
    })
    return _op_id(sub)


def submit_alphafold3(client, tag, fold_input, tmp_dir):
    """fold_input is native AlphaFold3 JSON (dialect alphafold3)."""
    inner = _upload_json(client, "alphafold3", fold_input, tmp_dir)
    ref = _manifest(client, "alphafold3", "fold-input", "alphafold3-fold-input/v1", inner, tmp_dir)
    sub = client.call("submit_alphafold3", {
        "schema": RUN_SCHEMA, "operation": "predict-complex-structure", "service_class": "customer-batch",
        "input_manifest": ref, "parameters": {"input_mode": "raw", "fold_job": fold_input["name"]},
        "idempotency_key": f"alphafold3-{tag}-{inner['sha256'][:32]}",
        "output_prefix": f"delphisci/alphafold3/{tag}",
    })
    return _op_id(sub)


def _get(client, artifact_id):
    h = client.call("download_scientific_artifact", {"artifact_id": artifact_id})
    url = h.get("url") or (h.get("handle") or {}).get("url") or h.get("download_url")
    return urllib.request.urlopen(url, timeout=600).read()


def status(client, op_id):
    op = client.call("get_operation", {"operation_id": op_id})
    return str((op.get("operation") or {}).get("status") or op.get("status") or "").lower()


def collect(client, op_id, out_dir, every=20, limit=6 * 3600):
    """Wait for op_id, download its outputs into out_dir, write out_dir/run.json."""
    out_dir = Path(out_dir)
    if (out_dir / "run.json").exists():
        return json.loads((out_dir / "run.json").read_text())
    res = client.wait(op_id, every=every, limit=limit)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(_get(client, res["output_manifest"]["artifact_id"]))
    files = []
    for e in manifest["entries"]:
        a = e["artifact"]
        data = _get(client, a["artifact_id"])
        if _sha(data) != a["sha256"]:
            raise RuntimeError(f"{op_id}: checksum mismatch for {e['name']}")
        ext = {"chemical/x-mmcif": ".cif", "application/json": ".json"}.get(a["media_type"], "")
        fname = e["name"].replace("/", "_") + ("" if e["name"].endswith(ext) else ext)
        (out_dir / fname).write_bytes(data)
        files.append({"name": e["name"], "file": fname, "semantic_type": e["semantic_type"],
                      "sha256": a["sha256"], "size_bytes": a["size_bytes"]})
    native = res.get("native_result") or {}
    record = {
        "operation_id": op_id,
        "platform": "Nebius Scientific AI Platform",
        "model_id": res.get("model_id"),
        "model_revision": (native.get("validation") or res.get("semantic_validation") or {}).get("model_revision"),
        "input_manifest_sha256": (res.get("input_manifest") or {}).get("sha256"),
        "command_seconds": native.get("command_seconds"),
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": files,
    }
    (out_dir / "run.json").write_text(json.dumps(record, indent=1))
    return record


def wait_all(client, ops, out_root, every=30):
    """ops: {tag: op_id}. Collects each as it finishes; returns {tag: run record or error}."""
    pending, done = dict(ops), {}
    while pending:
        for tag, op in list(pending.items()):
            if (Path(out_root) / tag / "run.json").exists():
                done[tag] = collect(client, op, Path(out_root) / tag)
                del pending[tag]
                continue
            st = status(client, op)
            if any(s in st for s in ("succeed", "complete", "done")):
                done[tag] = collect(client, op, Path(out_root) / tag)
                print(f"{tag}: done ({done[tag].get('command_seconds') or 0:.0f} s)", flush=True)
                del pending[tag]
            elif any(s in st for s in ("fail", "cancel", "error")):
                done[tag] = {"operation_id": op, "error": st}
                print(f"{tag}: {st}", flush=True)
                del pending[tag]
        if pending:
            print(f"{time.strftime('%H:%M:%S')} waiting on {len(pending)}: {', '.join(sorted(pending))}", flush=True)
            time.sleep(every)
    return done
