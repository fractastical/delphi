"""Real local bytes and real serving guards, including cache and traversal failures."""
from hashlib import sha256
import os

import pytest

from frontier import media
from frontier.store import FrontierError
from frontier.web import mime_for, resolve_static


def put(site, name, contents=b"actual published bytes"):
    target = site / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(contents)
    return target


def test_actual_bytes_deduplicated_and_href_percent_encoded(tmp_path):
    contents = b"same actual image bytes"
    first = put(tmp_path, "artifacts/a space # %.png", contents)
    put(tmp_path, "artifacts/another.png", contents)
    projection = media.LocalMedia(tmp_path, validator=resolve_static, mime_resolver=mime_for)
    result = projection.lookup(sha256(contents).hexdigest().upper())
    assert result["sha256"] == sha256(contents).hexdigest()
    assert len(result["matches"]) == 2
    assert result["matches"][0]["href"] == "/artifacts/a%20space%20%23%20%25.png"
    for match in result["matches"]:
        assert match["bytes_verified"] is True and match["byte_size"] == first.stat().st_size
        assert match["media_type"] == "image/png" and match["sha256"] == result["sha256"]
        assert resolve_static(tmp_path, match["href"]) is not None
    assert "unchanged" in result["scope"] and result["index"]["complete"] is True


def test_text_preview_verifies_full_bytes_and_truncates_by_character(tmp_path):
    contents = '{"label":"fin αβγ", "units":"Pa"}'.encode()
    put(tmp_path, "artifacts/a space.json", contents)
    digest = sha256(contents).hexdigest()
    result = media.LocalMedia(tmp_path).text_preview(digest, max_chars=15)
    assert result["status"] == "available" and result["full_file_hash_verified"] is True
    assert result["text"] == contents.decode()[:15] and result["truncated"] is True
    assert result["byte_size"] == len(contents) and result["characters_returned"] == 15
    assert result["href"] == "/artifacts/a%20space.json" and str(tmp_path) not in str(result)
    complete = media.LocalMedia(tmp_path).text_preview(digest)
    assert complete["text"] == contents.decode() and complete["truncated"] is False


@pytest.mark.parametrize("value", [0, -1, 16001, True, 1.5, "100"])
def test_text_preview_rejects_invalid_limit_before_scan(tmp_path, monkeypatch, value):
    projection = media.LocalMedia(tmp_path)
    monkeypatch.setattr(projection, "_scan", lambda: pytest.fail("invalid limit scanned files"))
    with pytest.raises(FrontierError):
        projection.text_preview("a" * 64, max_chars=value)


@pytest.mark.parametrize("name,contents,status", [
    ("frame.png", b"image", "unsupported_type"),
    ("invalid.json", b"\xff", "unsupported_encoding"),
    ("binary.txt", b"zero\x00byte", "unsupported_encoding"),
    ("private/result.json", b"private content", "unavailable"),
])
def test_text_preview_never_returns_binary_or_private_content(tmp_path, name, contents, status):
    put(tmp_path, "artifacts/" + name, contents)
    result = media.LocalMedia(tmp_path).text_preview(sha256(contents).hexdigest())
    assert result["status"] == status and result["text"] is None


def test_text_preview_size_limit_and_cached_replacement_fail_closed(tmp_path, monkeypatch):
    path = put(tmp_path, "artifacts/trace.json", b"12345")
    digest = sha256(path.read_bytes()).hexdigest()
    projection = media.LocalMedia(tmp_path, scan_ttl=60)
    assert projection.lookup(digest)["matches"]
    monkeypatch.setattr(media, "MAX_TEXT_BYTES", 4)
    assert projection.text_preview(digest)["status"] == "too_large"
    monkeypatch.setattr(media, "MAX_TEXT_BYTES", 100)
    path.write_bytes(b"54321")
    result = projection.text_preview(digest)
    assert result["status"] == "changed" and result["text"] is None


def test_text_preview_cached_path_cannot_be_replaced_by_symlink(tmp_path):
    site = tmp_path / "site"
    path = put(site, "artifacts/trace.json", b"published")
    outside = put(tmp_path, "outside.json", b"not published")
    projection = media.LocalMedia(site, scan_ttl=60)
    digest = sha256(b"published").hexdigest()
    assert projection.lookup(digest)["matches"]
    path.unlink()
    path.symlink_to(outside)
    result = projection.text_preview(digest)
    assert result["text"] is None and "not published" not in str(result)


def test_real_changes_removal_and_same_mtime_drop_old_digest(tmp_path):
    target = put(tmp_path, "artifacts/frame.png", b"old")
    projection = media.LocalMedia(tmp_path)
    old = sha256(b"old").hexdigest()
    assert projection.lookup(old)["matches"]
    initial = target.stat()
    target.write_bytes(b"new")  # same byte length; mtime restored deliberately.
    os.utime(target, ns=(initial.st_atime_ns, initial.st_mtime_ns))
    assert not projection.lookup(old)["matches"]
    assert projection.lookup(sha256(b"new").hexdigest())["matches"]
    target.unlink()
    assert not projection.lookup(sha256(b"new").hexdigest())["matches"]
    assert not projection._cache


def test_unchanged_bytes_use_cached_hash_and_changed_bytes_rehash(tmp_path, monkeypatch):
    target = put(tmp_path, "artifacts/frame.png", b"one")
    calls = []
    real_hash = media.sha256
    def counted():
        calls.append(1)
        return real_hash()
    monkeypatch.setattr(media, "sha256", counted)
    projection = media.LocalMedia(tmp_path)
    for _ in range(2):
        assert projection.lookup(sha256(b"one").hexdigest())["matches"]
    assert len(calls) == 1
    target.write_bytes(b"two")
    assert not projection.lookup(sha256(b"one").hexdigest())["matches"]
    assert len(calls) == 2


def test_symlink_escape_and_in_tree_symlinks_are_not_indexed(tmp_path):
    site = tmp_path / "site"
    outside = put(tmp_path, "elsewhere/outside.png", b"outside")
    inside = put(site, "artifacts/inside.png", b"inside")
    (site / "artifacts/escape.png").symlink_to(outside)
    (site / "artifacts/alias.png").symlink_to(inside)
    (site / "artifacts/linked-dir").symlink_to(outside.parent, target_is_directory=True)
    projection = media.LocalMedia(site)
    assert not projection.lookup(sha256(b"outside").hexdigest())["matches"]
    assert len(projection.lookup(sha256(b"inside").hexdigest())["matches"]) == 1
    other = tmp_path / "other-site"
    other.mkdir()
    (other / "artifacts").symlink_to(outside.parent, target_is_directory=True)
    assert not media.LocalMedia(other).lookup(sha256(b"outside").hexdigest())["matches"]


def test_private_components_hidden_names_unsupported_types_and_nonartifact_files_refused(tmp_path):
    payload = b"must never appear"
    for name in ["artifacts/.hidden.png", "artifacts/secret.png", "artifacts/credentials.json",
                 "artifacts/private-source/normal.png", "artifacts/sub/token-vault/plain.png",
                 "artifacts/run.exe", "artifacts/unknown.bin", "artifacts/.env", "public.png"]:
        put(tmp_path, name, payload)
    result = media.LocalMedia(tmp_path).lookup(sha256(payload).hexdigest())
    assert not result["matches"]
    assert result["index"]["files"] == 0


@pytest.mark.parametrize("value", [None, [], "", "a" * 63, "g" * 64, "a" * 65, "../" + "a" * 64, "https://x/" + "a" * 64])
def test_malformed_sha_is_400_before_scan(tmp_path, value, monkeypatch):
    projection = media.LocalMedia(tmp_path)
    monkeypatch.setattr(projection, "_scan", lambda: pytest.fail("invalid sha caused filesystem scan"))
    with pytest.raises(FrontierError) as error:
        projection.lookup(value)
    assert error.value.http_status == 400


def test_per_file_and_whole_index_byte_limits_without_large_allocations(tmp_path, monkeypatch):
    put(tmp_path, "artifacts/large.png", b"12345")
    monkeypatch.setattr(media, "MAX_FILE_BYTES", 4)
    result = media.LocalMedia(tmp_path).lookup(sha256(b"12345").hexdigest())
    assert not result["matches"] and result["index"]["complete"] is False
    put(tmp_path, "artifacts/a.png", b"1234")
    put(tmp_path, "artifacts/b.png", b"1234")
    monkeypatch.setattr(media, "MAX_INDEX_BYTES", 6)
    result = media.LocalMedia(tmp_path).lookup(sha256(b"1234").hexdigest())
    assert len(result["matches"]) == 1 and result["index"]["byte_size"] <= 6
    assert result["index"]["complete"] is False


def test_file_and_directory_entry_limits_bound_scan(tmp_path, monkeypatch):
    for name in ("a.png", "b.png", "c.png"):
        put(tmp_path, "artifacts/" + name, b"x")
    monkeypatch.setattr(media, "MAX_FILES", 2)
    result = media.LocalMedia(tmp_path).lookup(sha256(b"x").hexdigest())
    assert len(result["matches"]) == 2 and result["index"]["complete"] is False
    monkeypatch.setattr(media, "MAX_ENTRIES", 1)
    result = media.LocalMedia(tmp_path).lookup(sha256(b"x").hexdigest())
    assert len(result["matches"]) <= 1 and result["index"]["complete"] is False


def test_streaming_hash_does_not_read_whole_file_and_rejects_midread_mutation(tmp_path, monkeypatch):
    target = put(tmp_path, "artifacts/frame.png", b"0123456789")
    chunks = []
    real_hash = media.sha256
    class Recorder:
        def __init__(self):
            self.inner = real_hash()
        def update(self, chunk):
            chunks.append(len(chunk))
            self.inner.update(chunk)
        def hexdigest(self):
            return self.inner.hexdigest()
    monkeypatch.setattr(media, "CHUNK_BYTES", 3)
    monkeypatch.setattr(media, "sha256", Recorder)
    assert media.LocalMedia(tmp_path).lookup(sha256(target.read_bytes()).hexdigest())["matches"]
    assert chunks == [3, 3, 3, 1]
    class Mutating(Recorder):
        def update(self, chunk):
            target.write_bytes(b"changed!!!")
            super().update(chunk)
    monkeypatch.setattr(media, "sha256", Mutating)
    result = media.LocalMedia(tmp_path).lookup(sha256(b"0123456789").hexdigest())
    assert not result["matches"] and result["index"]["complete"] is False


def test_cached_hash_loses_match_if_current_serving_guard_refuses(tmp_path):
    put(tmp_path, "artifacts/frame.png", b"x")
    allowed = [True]
    def guard(root, href):
        return resolve_static(root, href) if allowed[0] else None
    projection = media.LocalMedia(tmp_path, validator=guard)
    assert projection.lookup(sha256(b"x").hexdigest())["matches"]
    allowed[0] = False
    assert not projection.lookup(sha256(b"x").hexdigest())["matches"]


def test_directory_swapped_to_escape_after_validation_cannot_be_opened(tmp_path):
    site = tmp_path / "site"
    put(site, "artifacts/sub/frame.png", b"published")
    outside = put(tmp_path, "outside/frame.png", b"must stay outside")
    swapped = []
    def racing_guard(root, href):
        target = resolve_static(root, href)
        if target is not None and not swapped:
            folder = root / "artifacts/sub"
            folder.rename(tmp_path / "moved-original")
            folder.symlink_to(outside.parent, target_is_directory=True)
            swapped.append(True)
        return target
    result = media.LocalMedia(site, validator=racing_guard).lookup(sha256(b"must stay outside").hexdigest())
    assert swapped and not result["matches"] and result["index"]["files"] == 0


def test_release_symlink_is_pinned_to_one_resolved_root(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    put(one, "artifacts/frame.png", b"one")
    put(two, "artifacts/frame.png", b"two")
    current = tmp_path / "current"
    current.symlink_to(one, target_is_directory=True)
    projection = media.LocalMedia(current)
    current.unlink()
    current.symlink_to(two, target_is_directory=True)
    assert projection.lookup(sha256(b"one").hexdigest())["matches"]
    assert not projection.lookup(sha256(b"two").hexdigest())["matches"]
    assert media.LocalMedia(current).lookup(sha256(b"two").hexdigest())["matches"]


def test_scan_ttl_bounds_rescans_from_anonymous_lookups(tmp_path):
    """The public adapter sets scan_ttl so repeated /api/media requests share one walk of the artifact tree."""
    put(tmp_path, "artifacts/a.png", b"first")
    projection = media.LocalMedia(tmp_path, scan_ttl=3600)
    scans = []
    real = projection._scan
    projection._scan = lambda: (scans.append(1), real())[1]
    for _ in range(25):
        projection.lookup("0" * 64)
    assert len(scans) == 1                      # control below: ttl 0 (the default) still rescans every call
    fresh = media.LocalMedia(tmp_path)
    fresh_scans, real = [], fresh._scan
    fresh._scan = lambda: (fresh_scans.append(1), real())[1]
    for _ in range(3):
        fresh.lookup("0" * 64)
    assert len(fresh_scans) == 3
