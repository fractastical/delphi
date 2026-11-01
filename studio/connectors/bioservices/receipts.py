"""Provenance receipts shared by the bioservices connectors.

A receipt answers "what exactly did this read, and could someone else read the
same thing again". It deliberately records the request as well as the response,
because a checksum alone does not say what was asked for.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class RetrievalReceipt:
    """What a connector fetched, from where, and in what state it ended.

    ``state`` is one of the SPEC-005 connector states. ``validated`` is only
    claimed by a caller that actually ran a check, never by the fetch itself.
    """

    source_id: str
    url: str
    state: str
    retrieved_utc: str
    size_bytes: int | None = None
    sha256: str | None = None
    media_type: str | None = None
    license: str | None = None
    version: str | None = None
    notes: list[str] = field(default_factory=list)

    VALID_STATES = ("discovered", "accessible", "retrieved", "replayed", "validated")

    def __post_init__(self) -> None:
        if self.state not in self.VALID_STATES:
            raise ValueError(f"unknown connector state {self.state!r}; expected one of {self.VALID_STATES}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def environment_fingerprint(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Enough of the environment to tell two runs apart.

    Package versions are read from the live interpreter rather than from a
    lockfile, so the record describes what actually executed.
    """

    versions: dict[str, str] = {}
    for mod in ("torch", "transformers", "numpy", "scipy"):
        try:
            versions[mod] = __import__(mod).__version__
        except Exception:  # pragma: no cover - absence is itself the record
            versions[mod] = "absent"
    fp: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "packages": versions,
    }
    if extra:
        fp.update(extra)
    return fp


def git_sha(repo: str) -> str:
    """The commit the code ran at, or an explicit marker when it is unknown."""
    try:
        out = subprocess.run(
            ["git", "-C", repo, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30, check=True,
        )
        dirty = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
        return out.stdout.strip() + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def write_json(path: str, payload: Any) -> str:
    """Write ``payload`` as sorted, newline-terminated JSON; return its sha256."""
    text = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    return sha256_text(text)
