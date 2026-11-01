"""Build the exact job bundle with the controller, extract it into an empty directory and run the entry script there with PREFLIGHT=1 (imports + input files only).
Catches missing-file packaging errors locally. Usage: PYTHONPATH=frontier_compute/vendor python3 -m frontier_compute.preflight ITEMS.json [--base .]"""
import io, json, os, subprocess, sys, tarfile, tempfile
from pathlib import Path
from compute_ops.batch import build_bundle


def main(items_path, base="."):
    spec = json.load(open(items_path))
    ok = True
    for it in spec["items"]:
        blob = build_bundle(it, Path(base))
        d = tempfile.mkdtemp(prefix="preflight_")
        tarfile.open(fileobj=io.BytesIO(blob)).extractall(d)
        env = dict(os.environ, PREFLIGHT="1", COPS_OUT=d, PYTHONPATH="")
        env.pop("PYTHONPATH")
        env.update({k: str(v) for k, v in (it.get("env") or {}).items()})
        p = subprocess.run([it.get("python", "python3"), "-I", it["script"], *map(str, it.get("args", []))], cwd=d, env=env, capture_output=True, text=True, timeout=120)
        print(it["id"], "rc", p.returncode, (p.stdout + p.stderr).strip()[-300:])
        ok &= p.returncode == 0
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "."))
