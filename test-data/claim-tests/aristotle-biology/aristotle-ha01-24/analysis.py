#!/usr/bin/env python3
"""Compare right and left kidney centers of mass in the TotalSegmentator subset.

Superior is NIfTI +Z. The unit check (kidney length in m or mm) was committed
before any coordinate was computed. The zip is cached at
/tmp/totalsegmentator_dataset_small_v2.zip so the 3.3 GB file is not committed.
"""
import datetime as dt
import hashlib
import json
import struct
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DERIVED = HERE / "derived"
ZIP_PATH = Path("/tmp/totalsegmentator_dataset_small_v2.zip")
URL = "https://zenodo.org/api/records/8367170/files/Totalsegmentator_dataset_small_v2.zip/content"
EXPECT_MD5 = "53c02c76a2ada07fd7c5c55aac5c91fc"
EXPECT_SIZE = 3263252066
MIN_VOXELS = 500
MIN_N = 40


def md5(path):
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_nifti(raw):
    if raw[:2] == b"\x1f\x8b":
        import gzip
        raw = gzip.decompress(raw)
    hdr = raw[:348]
    endian = "<" if struct.unpack_from("<i", hdr, 0)[0] == 348 else ">"
    dim = struct.unpack_from(endian + "8h", hdr, 40)
    datatype = struct.unpack_from(endian + "h", hdr, 70)[0]
    vox_offset = int(struct.unpack_from(endian + "f", hdr, 108)[0])
    qform_code = struct.unpack_from(endian + "h", hdr, 252)[0]
    sform_code = struct.unpack_from(endian + "h", hdr, 254)[0]
    srow = np.array([
        struct.unpack_from(endian + "4f", hdr, 280),
        struct.unpack_from(endian + "4f", hdr, 296),
        struct.unpack_from(endian + "4f", hdr, 312),
    ], dtype=np.float64)
    pixdim = struct.unpack_from(endian + "8f", hdr, 76)
    qb, qc, qd = struct.unpack_from(endian + "3f", hdr, 256)
    qoff = struct.unpack_from(endian + "3f", hdr, 268)
    nx, ny, nz = int(dim[1]), int(dim[2]), int(dim[3])
    dt = {
        2: "u1", 4: "i2", 8: "i4", 16: "f4", 64: "f8", 256: "i1", 512: "u2",
    }[datatype]
    if endian == ">":
        dt = ">" + dt
    n = nx * ny * nz
    item = np.dtype(dt).itemsize
    data = np.frombuffer(raw[vox_offset:vox_offset + n * item], dtype=dt)
    data = data.reshape((nz, ny, nx))
    affine = srow
    code = sform_code
    if sform_code == 0:
        affine = quat_affine(qb, qc, qd, qoff, pixdim)
        code = qform_code
    return data, affine, code


def quat_affine(b, c, d, offset, pixdim):
    b2, c2, d2 = b * b, c * c, d * d
    a2 = 1.0 - (b2 + c2 + d2)
    a = a2 ** 0.5 if a2 > 0 else 0.0
    qfac = pixdim[0] if pixdim[0] != 0 else 1.0
    if qfac < 0:
        qfac = -1.0
    else:
        qfac = 1.0
    r = np.array([
        [a * a + b2 - c2 - d2, 2 * b * c - 2 * a * d, 2 * b * d + 2 * a * c],
        [2 * b * c + 2 * a * d, a * a + c2 - b2 - d2, 2 * c * d - 2 * a * b],
        [2 * b * d - 2 * a * c, 2 * c * d + 2 * a * b, a * a + d2 - c2 - b2],
    ], dtype=np.float64)
    r[2, :] *= qfac
    scale = np.diag([pixdim[1], pixdim[2], pixdim[3]])
    aff = np.zeros((3, 4))
    aff[:, :3] = r @ scale
    aff[:, 3] = offset
    return aff


def kidney_stats(raw):
    data, aff, code = read_nifti(raw)
    zz, yy, xx = np.nonzero(data)
    n = int(xx.size)
    if n < MIN_VOXELS or code == 0:
        return None
    # subsample if huge, but kidney masks are small
    ijk = np.stack([xx, yy, zz, np.ones(n)], axis=0)
    world = aff @ ijk
    z = world[2]
    centroid = world[:3].mean(axis=1)
    return {"n": n, "z_mean": float(centroid[2]), "z_min": float(z.min()), "z_max": float(z.max())}


def write_result(verdict, reason, confidence, measured, method, datasets, summary, data_kind):
    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": data_kind,
        "method": method,
        "measured": measured,
        "datasets": datasets,
        "results_summary": summary,
    })
    if reason:
        result["reason"] = reason
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not ZIP_PATH.exists():
        write_result(
            "inconclusive", "data-unavailable", 0.3,
            {"value": None, "unit": "fraction of subjects with right kidney superior", "n": 0, "uncertainty": None, "extra": {}},
            "The TotalSegmentator zip was not on disk at /tmp/totalsegmentator_dataset_small_v2.zip, so no kidney coordinate was computed.",
            [], ["zip missing"], "none",
        )
        print("missing zip")
        return
    size = ZIP_PATH.stat().st_size
    digest = md5(ZIP_PATH)
    file_sha = sha256(ZIP_PATH)
    dataset = {
        "id": "totalsegmentator-small-v2-zenodo-8367170",
        "name": "Small subset of the TotalSegmentator CT dataset (102 subjects)",
        "landing_url": "https://doi.org/10.5281/zenodo.8367170",
        "doi": "10.5281/zenodo.8367170",
        "version": "Totalsegmentator_dataset_small_v2.zip",
        "license": "CC BY 4.0",
        "files": [{
            "download_url": URL,
            "retrieved_at": now,
            "byte_size": size,
            "sha256": file_sha,
            "md5": digest,
        }],
        "role": "left and right kidney segmentation masks",
    }
    if size != EXPECT_SIZE or digest != EXPECT_MD5:
        write_result(
            "inconclusive", "data-unavailable", 0.4,
            {"value": None, "unit": "fraction", "n": 0, "uncertainty": None,
             "extra": {"byte_size": size, "md5": digest}},
            "The downloaded zip did not match the publisher size or md5 recorded at registration, so it was not analyzed.",
            [dataset], [f"size {size} md5 {digest}"], "none",
        )
        print("checksum mismatch", size, digest)
        return

    rows = []
    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = zf.namelist()
        left = {n.split("/")[0]: n for n in names if n.endswith("kidney_left.nii.gz")}
        right = {n.split("/")[0]: n for n in names if n.endswith("kidney_right.nii.gz")}
        subjects = sorted(set(left) & set(right))
        for subj in subjects:
            try:
                L = kidney_stats(zf.read(left[subj]))
                R = kidney_stats(zf.read(right[subj]))
            except Exception as exc:
                rows.append({"subject": subj, "error": str(exc)[:160]})
                continue
            if L is None or R is None:
                rows.append({"subject": subj, "skipped": True})
                continue
            rows.append({
                "subject": subj,
                "z_left": L["z_mean"],
                "z_right": R["z_mean"],
                "extent_left": L["z_max"] - L["z_min"],
                "extent_right": R["z_max"] - R["z_min"],
                "n_left": L["n"],
                "n_right": R["n"],
            })
    usable = [r for r in rows if "z_left" in r]
    extents = [r["extent_left"] for r in usable] + [r["extent_right"] for r in usable]
    median_extent = float(np.median(extents)) if extents else None
    scale = None
    if median_extent is not None and 0.04 <= median_extent <= 0.20:
        scale = 1000.0
    elif median_extent is not None and 40 <= median_extent <= 200:
        scale = 1.0
    compared = []
    if scale is not None:
        for r in usable:
            dz = (r["z_right"] - r["z_left"]) * scale
            compared.append({**r, "dz_mm": dz, "right_higher": dz > 5})
    (DERIVED / "kidneys.json").write_text(json.dumps({
        "n_subjects_with_both_files": len(subjects),
        "n_usable": len(usable),
        "median_extent_native": median_extent,
        "scale_to_mm": scale,
        "rows": compared or usable,
    }, indent=2) + "\n")

    if scale is None:
        verdict, reason, confidence = "inconclusive", "other", 0.45
        fraction = None
        n = len(usable)
    else:
        n = len(compared)
        n_right = sum(1 for r in compared if r["right_higher"])
        fraction = (n_right / n) if n else None
        if n < MIN_N:
            verdict, reason, confidence = "inconclusive", "underpowered", 0.5
        elif fraction < 0.50:
            verdict, reason, confidence = "refutes", None, 0.8 if fraction < 0.25 else 0.7
        elif fraction < 0.95:
            verdict, reason, confidence = "mixed", None, 0.6
        else:
            verdict, reason, confidence = "inconclusive", "underpowered", 0.55
    write_result(
        verdict, reason, confidence,
        {
            "value": fraction,
            "unit": "fraction of qualifying human CT subjects in whom the right kidney center of mass is more than 5 mm superior to the left",
            "n": n,
            "uncertainty": "binary masks; 5 mm tie band; anomalies not removed",
            "extra": {
                "median_kidney_extent_native_units": median_extent,
                "scale_to_mm": scale,
                "n_right_higher": None if fraction is None else int(round(fraction * n)),
            },
        },
        "Checked the zip against the publisher md5 and size, read only kidney_left and kidney_right masks, and compared center-of-mass Z in the NIfTI world frame. The median kidney length selected meters or millimeters before the 5 mm test. The side comparison was not used to choose the axis.",
        [dataset],
        [
            f"Qualifying subjects: {n}. Median native extent: {median_extent}. Scale to mm: {scale}.",
            f"Fraction with right kidney higher: {fraction}.",
        ],
        "biological" if usable else "none",
    )
    print(verdict, "n", n, "fraction", fraction, "extent", median_extent)


if __name__ == "__main__":
    main()
