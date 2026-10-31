"""Run the frozen Morpheus continuation on CPU, returning bounded real outputs."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request


PACKET_SHA = "994eb8314f1d912e7dc16a9a9ca0e9d5591f86cf805bfa16e6e2070f2c34f4f7"
BIN_SHA = "3d9a6e5a4cb86824b745500df1474596d39cce5deed24f767c0841df0f94d5ad"
URL = "https://gitlab.com/morpheus.lab/morpheus/-/package_files/178666119/download"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    archive = Path("artifacts/multicell/morpheus-packet.tgz")
    if sha(archive) != PACKET_SHA:
        raise ValueError("Morpheus packet hash mismatch")
    out = Path(os.environ["COPS_OUT"]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="morpheus-runtime-") as temporary:
        work = Path(temporary)
        with tarfile.open(archive) as packet:
            packet.extractall(work, filter="data")
        subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=work, check=True)
        subprocess.run(["bash", "-n", "run_packet.sh"], cwd=work, check=True)
        if os.environ.get("PREFLIGHT"):
            print("Morpheus packet hashes and shell syntax passed; no simulation executed")
            return
        data = work / "output"
        data.mkdir()
        binary = data / "morpheus-2.3.9"
        # Keep the public dependency outside COPS_OUT; it is not a result artifact.
        with urllib.request.urlopen(URL, timeout=300) as source, binary.open("wb") as target:
            shutil.copyfileobj(source, target)
        if sha(binary) != BIN_SHA:
            raise ValueError("Morpheus public binary hash mismatch")
        binary.chmod(0o755)
        env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "ARM_TIMEOUT_S": "3000"}
        completed = subprocess.run(["bash", "run_packet.sh", str(data)], cwd=work, env=env, timeout=3100, check=False)
        arms = []
        for name in ("baseline", "nofeedback", "seed2"):
            source = data / name
            destination = out / name
            destination.mkdir()
            for filename in ("logger.csv", "model.xml", "stdout.log", "exit.txt"):
                if (source / filename).exists():
                    shutil.copyfile(source / filename, destination / filename)
            exit_code = int((source / "exit.txt").read_text().strip().split("=")[1])
            log = source / "logger.csv"
            last_time = float(log.read_text().splitlines()[-1].split()[0]) if log.exists() else None
            arms.append({"arm": name, "exit_code": exit_code, "last_time": last_time,
                         "full_horizon": exit_code == 0 and last_time is not None and last_time >= 2.0})
        receipt = {"schema": "frontier.morpheus.continuation/1", "packet_sha256": PACKET_SHA,
                   "binary_sha256": BIN_SHA, "source_commit": "29a26b00838736c4180f22fea075688f1d51e619",
                   "cpu_threads_per_arm": 1, "parallel_arms": 3, "arm_timeout_s": 3000,
                   "script_exit": completed.returncode, "arms": arms,
                   "scope": "Generic edited upstream ODE/CPM/PDE example, not fish-calibrated biology; original capped partial runs preserved.",
                   "files": {str(p.relative_to(out)): sha(p) for p in out.rglob("*") if p.is_file()}}
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt), flush=True)
        if not all(arm["full_horizon"] for arm in arms):
            raise RuntimeError("Morpheus returned partial/failed arms; preserve last-time receipts")


if __name__ == "__main__":
    main()
