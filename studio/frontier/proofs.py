"""Fixed recorded-proof catalogue. Reads pinned bytes; never executes Lean."""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import re
import stat

from scripts import lean_gallery

FAMILY_IDS = ("geometric-similarity", "unit-algebra", "cantilever-guard")
MAX_FILE_BYTES = 128_000
MAX_SOURCE_CHARS = 6_000
RECEIPTS = {
    "geometric-similarity": "b384c5ace8569027b226e4c5d24de8a54686877cfaf8266b8c7f7295953a6b17",
    "unit-algebra": "f7d02122cf5fa6e6aad588161997820e5e633ecfbf9badda65be0c32c45751d6",
    "cantilever-guard": "2f5ebcb086f2dbe70a84a9f8863365736b1a59724744eb3a7101737a808c4be4",
}
SCOPE = "Recorded mathematical compile/control results only; not a new Lean run, scientific review, empirical finding, or proof of biological validity."


class _FixedReader:
    def __init__(self, root, allowed):
        self.root = Path(root).resolve()
        self.allowed = frozenset(allowed)

    def read(self, relative):
        if relative not in self.allowed or PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts:
            raise ValueError("Unlisted proof input")
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            parts = PurePosixPath(relative).parts
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            try:
                before = os.fstat(fd)
                if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
                    raise ValueError("Proof input outside file bound")
                raw = os.read(fd, MAX_FILE_BYTES + 1)
                after = os.fstat(fd)
                def identity(s):
                    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
                if len(raw) > MAX_FILE_BYTES or len(raw) != before.st_size or identity(before) != identity(after):
                    raise ValueError("Proof input changed during read")
                return raw
            finally:
                os.close(fd)
        finally:
            os.close(directory)


class ProofCatalog:
    def __init__(self, root=None):
        self.root = Path(root).resolve() if root else Path(__file__).resolve().parents[1]
        # This catalogue is deliberately fixed, rather than following paths found in receipts.
        source = {
            "engineering/formal/GeometricSimilarity.lean", "engineering/formal/MutantRefutations.lean",
            "engineering/formal/NegativeControls.lean", "engineering/formal/lean_checks.py", "engineering/constraints.py",
            "engineering/formal/unit_algebra_checks.py",
            "engineering/formal/UnitAlgebra.lean", "engineering/formal/UnitAlgebraControls.lean", "engineering/formal/UnitAlgebraNegative.lean",
            "engineering/formalize/lean/CantileverGuard.lean", "engineering/formalize/lean/CantileverGuard_negative_corrupt_law.lean",
        }
        published = set()
        for spec in lean_gallery.FAMILIES:
            source.add(f"{spec['dir']}/{spec['receipt']}")
            for name in [spec["theory"], Path(spec["receipt"]).name] + [spec[k] for k in ("positive_extra", "negative", "negative_file") if spec.get(k)]:
                published.add(f"artifacts/lean-gallery/{spec['id']}/{name}")
        self.source = _FixedReader(self.root, source)
        self.published = _FixedReader(self.root / "site", published)

    def read(self, family=None, include_source=False, public_host=None):
        if family is not None and family not in FAMILY_IDS:
            raise ValueError("Unknown fixed proof family")
        if not isinstance(include_source, bool):
            raise ValueError("include_source must be boolean")
        families, withheld = [], []
        for spec in lean_gallery.FAMILIES:
            if family and spec["id"] != family:
                continue
            try:
                receipt = self.source.read(f"{spec['dir']}/{spec['receipt']}")
                if sha256(receipt).hexdigest() != RECEIPTS[spec["id"]]:
                    raise ValueError("Recorded receipt changed")
                checked = lean_gallery._family(spec, self.source, {}, self.root)
                if checked["status"] != "current" or not checked["receipt"]["all_ok"]:
                    raise ValueError("Recorded sources are stale")
                files = []
                for item in checked["files"]:
                    raw = self.published.read(item["path"])
                    if sha256(raw).hexdigest() != item["sha256"] or len(raw) != item["bytes"]:
                        raise ValueError("Published proof bytes changed")
                    entry = {k: item[k] for k in ("name", "role", "sha256", "bytes")}
                    entry["href"] = item["path"]
                    if public_host and re.fullmatch(r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}", public_host):
                        entry["public_url"] = f"https://{public_host}/{item['path']}"
                    files.append(entry)
                theory = next(x for x in files if x["role"] == "theory")
                result = {k: checked[k] for k in ("id", "title", "summary", "assumptions", "equations")}
                result.update(status="recorded_compile_source_matched", recorded_compile=True,
                              versions=checked["versions"], files=files, source_href=theory["href"],
                              receipt_href=checked["receipt"]["href"],
                              theorem_names=[x["name"] for x in checked["theorems"] if x["kind"] == "theorem"],
                              positive_exit=checked["run"]["positive"]["exit"], negative_exit=checked["run"]["negative"]["exit"],
                              only_standard_axioms=checked["run"]["positive"]["only_standard_axioms"],
                              negative_control_ids=[x["id"] for x in checked["negative_blocks"]])
                if include_source:
                    text = checked["source"]
                    result["source"] = {"text": text[:MAX_SOURCE_CHARS], "truncated": len(text) > MAX_SOURCE_CHARS,
                                        "max_chars": MAX_SOURCE_CHARS, "full_file_sha256": theory["sha256"]}
                families.append(result)
            except (OSError, ValueError, KeyError, TypeError, UnicodeError):
                # Do not return receipt diagnostics: they can contain old local compiler paths.
                withheld.append({"id": spec["id"], "status": "withheld", "reason": "Missing, changed, stale or invalid recorded/published proof inputs"})
        return {"schema": "frontier.proofs/1", "scope": SCOPE, "compile_executed": False,
                "biological_validation": False, "source_character_limit_per_family": MAX_SOURCE_CHARS,
                "families": families, "withheld": withheld, "requested_family": family,
                "include_source": include_source}
