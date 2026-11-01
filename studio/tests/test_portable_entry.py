import hashlib
import io
import tarfile

import pytest

from frontier_compute.portable_entry import unpack


def test_packet_and_member_hashes_required(tmp_path):
    path = tmp_path / "packet.tar"
    with tarfile.open(path, "w") as tar:
        info = tarfile.TarInfo("source.py")
        info.size = 4
        tar.addfile(info, io.BytesIO(b"pass"))
    manifest = {"archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "files": {"source.py": hashlib.sha256(b"pass").hexdigest()}}
    out = tmp_path / "output"
    out.mkdir()
    unpack(path, manifest, out)
    assert (out / "source.py").read_bytes() == b"pass"
    manifest["files"]["source.py"] = "wrong"
    with pytest.raises(ValueError, match="file hash mismatch"):
        unpack(path, manifest, out)
    manifest["archive_sha256"] = "wrong"
    with pytest.raises(ValueError, match="packet hash mismatch"):
        unpack(path, manifest, out)
