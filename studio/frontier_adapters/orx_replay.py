"""EXPLICIT replay of an exported OpenResearch run. This EXECUTES the run's command.

Only use on code you wrote or have read. Requires trust_code=True. Wrap the call in
`systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 -p TasksMax=128 -p RuntimeMaxSec=600`.

It answers one question with measurements: given ONLY what the record carries (source tarball identified by
digest, plus the command), does a clean re-execution reproduce the result file byte-for-byte, under each
interpreter you name? A mutation control must change the output, or the comparison is not discriminating.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import tarfile
import tempfile

from .common import iso_utc, sha_bytes


def replay(export_dir: str, *, command: str, result_file: str, recorded_sha256: str,
           interpreters: dict[str, str], mutation: tuple[str, str, str] | None = None,
           trust_code: bool = False, timeout: int = 60) -> dict:
    if not trust_code:
        raise PermissionError("replay executes the run's command; pass trust_code=True only for code you have read")
    tar = os.path.join(export_dir, "source.tar")
    results = {}
    for label, interp in interpreters.items():
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as bindir:
            with tarfile.open(tar) as tf:
                tf.extractall(work, filter="data")                       # no path escapes, no special files
            if mutation:
                path, old, new = mutation
                p = os.path.join(work, path)
                with open(p) as fh:
                    text = fh.read()
                if old not in text:
                    raise ValueError("mutation target not found: the control would be vacuous")
                with open(p, "w") as fh:
                    fh.write(text.replace(old, new, 1))
            os.symlink(interp, os.path.join(bindir, "python3"))
            env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": work}       # clean environment: nothing inherited
            proc = subprocess.run(["bash", "-c", command], cwd=work, env=env, capture_output=True, timeout=timeout)
            out = os.path.join(work, result_file)
            digest = None
            if os.path.isfile(out):
                with open(out, "rb") as fh:
                    digest = sha_bytes(fh.read())
            version = subprocess.run([interp, "--version"], capture_output=True, text=True).stdout.strip()
            results[label] = {"interpreter_version": version, "exit": proc.returncode, "result_sha256": digest,
                              "matches_recorded": digest == recorded_sha256}
    return {"performed": True, "at": iso_utc(), "recorded_sha256": recorded_sha256, "mutation_control": bool(mutation),
            "command_run": shlex.split(command)[:6], "results": results,
            "note": "the interpreter and its version are NOT in the OpenResearch record; the replayer chose them"}


def replay_external(tar_bytes: bytes, *, inputs: dict[str, bytes], command: str, interpreter: str, config_key: str,
                    output_name: str, expected_output_sha256: str | None = None, expected_stdout_sha256: str | None = None,
                    mutate_input: tuple[str, bytes] | None = None, trust_code: bool = False, timeout: int = 180,
                    env_extra: dict | None = None) -> dict:
    """Replay a run whose inputs and output live OUTSIDE the snapshot (so the snapshot alone cannot reproduce it).

    The snapshot is extracted to a temp dir; `inputs` (name -> bytes, obtained from immutable git blobs) are written to
    a second temp dir; the snapshot's config.json key `config_key` is rewritten to point at that dir. THAT REWRITE IS THE
    ONE DECLARED DEVIATION from the recorded run. The interpreter token in `command` is replaced by `interpreter`.
    Runs under `env -i`. `mutate_input` replaces one input's bytes (the control: output must then differ).
    """
    import re
    if not trust_code:
        raise PermissionError("replay executes the run's command; pass trust_code=True only for code you have read")
    with tempfile.TemporaryDirectory() as root:
        code, data = os.path.join(root, "code"), os.path.join(root, "data")
        os.makedirs(code); os.makedirs(data)
        tar = os.path.join(root, "src.tar")
        with open(tar, "wb") as fh:
            fh.write(tar_bytes)
        with tarfile.open(tar) as tf:
            tf.extractall(code, filter="data")
        for name, b in inputs.items():
            if mutate_input and name == mutate_input[0]:
                b = mutate_input[1]
            with open(os.path.join(data, name), "wb") as fh:
                fh.write(b)
        cfg_path = os.path.join(code, "config.json")
        with open(cfg_path) as fh:
            cfg = json.load(fh)
        cfg[config_key] = data
        with open(cfg_path, "w") as fh:
            json.dump(cfg, fh)
        cmd, n = re.subn(r"(?<![\w-])(?:\S*/)?python3?(?=\s)", interpreter, command, count=1)
        if n != 1:
            cmd = command
        env = {"PATH": "/usr/bin:/bin", "HOME": root, **(env_extra or {})}
        proc = subprocess.run(["bash", "-c", cmd], cwd=code, env=env, capture_output=True, timeout=timeout)
        out = os.path.join(data, output_name)
        out_sha = None
        if os.path.isfile(out):
            with open(out, "rb") as fh:
                out_sha = sha_bytes(fh.read())
        return {"performed": True, "at": iso_utc(), "exit": proc.returncode, "output_sha256": out_sha,
                "stdout_sha256": sha_bytes(proc.stdout),
                "output_matches_expected": (out_sha == expected_output_sha256) if expected_output_sha256 else None,
                "stdout_matches_recorded_log": (sha_bytes(proc.stdout) == expected_stdout_sha256) if expected_stdout_sha256 else None,
                "mutated_input": mutate_input[0] if mutate_input else None,
                "declared_deviation": f"config.json key {config_key!r} rewritten to a temp directory holding the input blobs",
                "interpreter_version": subprocess.run([interpreter, "--version"], capture_output=True, text=True).stdout.strip(),
                "note": "interpreter, its version and the third-party package versions are NOT in the OpenResearch record; the replayer chose them"}
