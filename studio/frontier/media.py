"""Verified local projection of publicly served artifact bytes, never evidence edits.

One LocalMedia instance belongs to one resolved immutable site release. Lookups
scan only its artifacts subtree, stream bounded hashes, and cache by full stat
identity. Every lookup rechecks serving guards and current file identity; removed
or changed files cannot retain their former digest mapping. No URI is fetched.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import re
import stat
from threading import Lock
from urllib.parse import quote

MAX_FILE_BYTES = 64_000_000
MAX_INDEX_BYTES = 256_000_000
MAX_FILES = 2000
MAX_ENTRIES = 4000  # Also bound unsupported files/directories, not just accepted media.
MAX_DEPTH = 20
CHUNK_BYTES = 1024 * 1024
HEX = re.compile(r"^[0-9a-fA-F]{64}$")
# Stricter than the static guard's basename rule: refuse sensitive directory
# components too. This projection must not discover private-directory assets.
SENSITIVE = re.compile(r"secret|token|credential|password|passwd|private|apikey|api_key|\.pem|\.key|\.env|id_rsa", re.I)
SCOPE = "Published local site/artifacts bytes only; Evidence declarations, availability and review status are unchanged"


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _default_validator(root, href):
    from .web import resolve_static  # Late import prevents web -> media -> web initialization cycles.
    return resolve_static(root, href)


def _default_mime(root, target):
    from .web import mime_for
    return mime_for(root, target)


class LocalMedia:
    """Lazy release-scoped public-byte index. Optional callbacks reuse web guards.

    ``LocalMedia(site_dir, validator=resolve_static, mime_resolver=mime_for)``
    accepts the same callback signatures as frontier.web. Default callbacks load
    lazily. site_dir is resolved once so a deployment symlink changing releases
    does not silently mix two releases in one index; create a new instance then.
    """

    def __init__(self, site_dir, *, validator=None, mime_resolver=None):
        self.root = Path(site_dir).resolve()
        self.artifacts = self.root / "artifacts"
        self.validator = validator or _default_validator
        self.mime_resolver = mime_resolver or _default_mime
        self._cache = {}
        self._lock = Lock()

    def _directory(self, parts):
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            return directory
        except BaseException:
            os.close(directory)
            raise

    def _open(self, relative):
        """Walk every component using no-follow openat, then check regularity.

        The descriptor chain prevents a directory swapped to an escaping symlink
        between path validation and opening from exposing outside bytes.
        """
        directory = self._directory(relative.parts[:-1])
        try:
            file_descriptor = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        finally:
            os.close(directory)
        stream = os.fdopen(file_descriptor, "rb")
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            stream.close()
            raise OSError("not a bounded regular file")
        return stream, info

    def _candidates(self):
        """Yield bounded lexical paths; never follow a directory or file symlink."""
        stack = [(self.artifacts, 0)]
        entries = files = 0
        while stack:
            directory, depth = stack.pop()
            try:
                descriptor = self._directory(directory.relative_to(self.root).parts)
                try:
                    with os.scandir(descriptor) as children:
                        for child in children:
                            entries += 1
                            if entries > MAX_ENTRIES:
                                yield None
                                return
                            if child.name.startswith(".") or SENSITIVE.search(child.name) or child.is_symlink():
                                continue
                            if child.is_dir(follow_symlinks=False):
                                if depth >= MAX_DEPTH:
                                    yield None
                                else:
                                    stack.append((directory / child.name, depth + 1))
                            elif child.is_file(follow_symlinks=False):
                                files += 1
                                if files > MAX_FILES:
                                    yield None
                                    return
                                yield directory / child.name
                finally:
                    os.close(descriptor)
            except OSError:
                # A publication may be replaced/removed during a lookup. No
                # stale entries survive: this lookup rebuilds all digest links.
                continue

    def _scan(self):
        cache, by_digest = {}, {}
        total_bytes = hash_budget_used = 0
        complete = True
        for path in self._candidates():
            if path is None:
                complete = False
                continue
            try:
                relative = path.relative_to(self.root)
                href = "/" + quote(relative.as_posix(), safe="/")
                guarded = self.validator(self.root, href)
                if guarded is None or Path(guarded) != path or not path.is_relative_to(self.artifacts):
                    continue
                media_type = self.mime_resolver(self.root, path)
                if media_type is None:
                    continue
                stream, _ = self._open(relative)
                with stream:
                    before = os.fstat(stream.fileno())
                    if before.st_size > MAX_FILE_BYTES or total_bytes + before.st_size > MAX_INDEX_BYTES:
                        complete = False
                        continue
                    identity = _identity(before)
                    previous = self._cache.get(relative.as_posix())
                    if previous and previous[0] == identity:
                        digest = previous[1]
                    else:
                        if hash_budget_used + before.st_size > MAX_INDEX_BYTES:
                            complete = False
                            continue
                        # Reserve the entire observed size even if a concurrent
                        # deletion/truncation makes a read fail, bounding all I/O.
                        hash_budget_used += before.st_size
                        hasher, consumed = sha256(), 0
                        while consumed < before.st_size:
                            chunk = stream.read(min(CHUNK_BYTES, before.st_size - consumed))
                            if not chunk:
                                break
                            consumed += len(chunk)
                            hasher.update(chunk)
                        if consumed != before.st_size:
                            complete = False
                            continue
                        digest = hasher.hexdigest()
                    after = os.fstat(stream.fileno())
                    # fstat catches mutation during reads; path stat catches
                    # replacement of the filename while the old descriptor lived.
                    if _identity(after) != identity or _identity(path.stat(follow_symlinks=False)) != identity:
                        complete = False
                        continue
                if self.validator(self.root, href) != path:
                    continue
                total_bytes += before.st_size
                cache[relative.as_posix()] = (identity, digest)
                by_digest.setdefault(digest, []).append({"href": href, "sha256": digest, "byte_size": before.st_size,
                                                        "media_type": media_type, "bytes_verified": True})
            except (OSError, ValueError, UnicodeError):
                continue
        self._cache = cache
        return by_digest, {"complete": complete, "files": len(cache), "byte_size": total_bytes,
                           "limits": {"per_file_bytes": MAX_FILE_BYTES, "total_bytes": MAX_INDEX_BYTES,
                                      "files": MAX_FILES, "directory_entries": MAX_ENTRIES, "depth": MAX_DEPTH}}

    def lookup(self, digest):
        if not isinstance(digest, str) or not HEX.fullmatch(digest):
            from .store import FrontierError
            raise FrontierError("sha256 must contain exactly 64 hexadecimal characters")
        digest = digest.lower()
        with self._lock:
            by_digest, coverage = self._scan()
            matches = sorted(by_digest.get(digest, []), key=lambda row: row["href"])
        return {"sha256": digest, "matches": matches, "scope": SCOPE, "index": coverage,
                "note": "Matching bytes were checked in this local published release; this is availability projection, not scientific acceptance. "
                        "An absent match makes no claim about remote or unindexed artifacts."}
