"""ProteinGym deep-mutational-scanning substitution assays.

ProteinGym (Notin et al.) publishes curated DMS datasets with a uniform schema:
``mutant`` (e.g. ``A107C``), ``mutated_sequence``, ``DMS_score`` and
``DMS_score_bin``. This module retrieves the substitutions archive, extracts
named assays, and reconstructs each assay's reference sequence *from the data
itself* so the reference can be checked against an independent source rather
than assumed.

Only public, anonymous HTTPS access is used. The archive is written to a
caller-supplied directory and nothing in it is executed.
"""

from __future__ import annotations

import csv
import io
import os
import re
import urllib.request
import zipfile
from dataclasses import dataclass

from connectors.bioservices.receipts import RetrievalReceipt, sha256_bytes, sha256_file, utc_now

ARCHIVE_URL = "https://marks.hms.harvard.edu/proteingym/ProteinGym_v1.3/DMS_ProteinGym_substitutions.zip"
ARCHIVE_VERSION = "ProteinGym_v1.3 / DMS_ProteinGym_substitutions"
# ProteinGym's code and curated data are distributed under the MIT licence; the
# underlying measurements belong to the original publications, which the assay
# id names. Both are recorded because they are different grants.
ARCHIVE_LICENSE = "MIT (ProteinGym curation); underlying measurements from the cited source publication"

AA = "ACDEFGHIKLMNPQRSTVWY"
MUTANT_RE = re.compile(rf"^([{AA}])(\d+)([{AA}])$")
USER_AGENT = "delphi-frontier-bioservices/0.1 (public-data replication)"


class ReferenceMismatch(ValueError):
    """A variant disagrees with the reference sequence it claims to be built on."""


@dataclass(frozen=True)
class Variant:
    mutant: str
    wt_aa: str
    position: int  # 1-based into the assay reference sequence
    mut_aa: str
    dms_score: float

    @property
    def key(self) -> str:
        return self.mutant


@dataclass
class Assay:
    """One DMS assay: its variants and the reference they were measured against."""

    assay_id: str
    reference_sequence: str
    variants: dict[str, Variant]
    source_sha256: str
    n_rows: int

    def __len__(self) -> int:
        return len(self.variants)


def fetch_archive(dest_dir: str, timeout: int = 540) -> tuple[str, RetrievalReceipt]:
    """Download the substitutions archive into ``dest_dir``.

    Returns the local path and a retrieval receipt. A pre-existing file with
    content is reused, so re-running an experiment does not re-download.
    """
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, "DMS_ProteinGym_substitutions.zip")
    reused = os.path.exists(path) and os.path.getsize(path) > 0
    if not reused:
        req = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(path, "wb") as out:
            while chunk := resp.read(1 << 20):
                out.write(chunk)
    receipt = RetrievalReceipt(
        source_id="proteingym.dms_substitutions",
        url=ARCHIVE_URL,
        state="retrieved",
        retrieved_utc=utc_now(),
        size_bytes=os.path.getsize(path),
        sha256=sha256_file(path),
        media_type="application/zip",
        license=ARCHIVE_LICENSE,
        version=ARCHIVE_VERSION,
        notes=["reused cached archive" if reused else "downloaded over anonymous HTTPS"],
    )
    return path, receipt


def _member_name(archive: str, assay_id: str) -> str:
    with zipfile.ZipFile(archive) as zf:
        wanted = f"{assay_id}.csv"
        for name in zf.namelist():
            if os.path.basename(name) == wanted:
                return name
    raise KeyError(f"assay {assay_id!r} not present in {archive}")


def load_assay(archive: str, assay_id: str) -> Assay:
    """Read one assay and derive its reference sequence from its own rows.

    Every single-substitution row states a wild-type residue, a position and a
    full mutated sequence. Each row therefore constrains the reference at every
    position: the mutated position must hold the mutant residue, and all other
    positions must hold the reference residue. Reading all rows together
    over-determines the reference, so any internal inconsistency raises rather
    than being silently resolved.
    """
    member = _member_name(archive, assay_id)
    with zipfile.ZipFile(archive) as zf:
        raw = zf.read(member)
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    if not rows:
        raise ValueError(f"assay {assay_id!r} has no rows")

    lengths = {len(r["mutated_sequence"]) for r in rows}
    if len(lengths) != 1:
        raise ReferenceMismatch(f"{assay_id}: mutated_sequence lengths are ragged: {sorted(lengths)[:5]}")
    n = lengths.pop()

    reference: list[str | None] = [None] * n
    variants: dict[str, Variant] = {}
    for r in rows:
        m = MUTANT_RE.match(r["mutant"])
        if not m:  # multi-substitution or non-standard residue: out of scope here
            continue
        wt, pos, mut = m.group(1), int(m.group(2)), m.group(3)
        seq = r["mutated_sequence"]
        if not 1 <= pos <= n:
            raise ReferenceMismatch(f"{assay_id}: {r['mutant']} position {pos} outside 1..{n}")
        if seq[pos - 1] != mut:
            raise ReferenceMismatch(
                f"{assay_id}: {r['mutant']} declares {mut} at {pos} but the sequence holds {seq[pos - 1]}"
            )
        for i, ch in enumerate(seq):
            if i == pos - 1:
                continue
            if reference[i] is None:
                reference[i] = ch
            elif reference[i] != ch:
                raise ReferenceMismatch(
                    f"{assay_id}: position {i + 1} is {reference[i]} in one row and {ch} in {r['mutant']}"
                )
        if reference[pos - 1] is None:
            reference[pos - 1] = wt
        elif reference[pos - 1] != wt:
            raise ReferenceMismatch(
                f"{assay_id}: position {pos} is {reference[pos - 1]} elsewhere but {wt} in {r['mutant']}"
            )
        variants[r["mutant"]] = Variant(r["mutant"], wt, pos, mut, float(r["DMS_score"]))

    unresolved = [i + 1 for i, c in enumerate(reference) if c is None]
    if unresolved:
        raise ReferenceMismatch(f"{assay_id}: {len(unresolved)} positions never observed, first={unresolved[:5]}")

    return Assay(
        assay_id=assay_id,
        reference_sequence="".join(reference),  # type: ignore[arg-type]
        variants=variants,
        source_sha256=sha256_bytes(raw),
        n_rows=len(rows),
    )


def check_variant_against_reference(mutant: str, reference: str) -> Variant:
    """Parse ``mutant`` and refuse it unless it matches ``reference``.

    This is the gate the pilot exercises with a deliberately wrong residue: a
    variant whose stated wild-type residue is not the one in the reference is an
    error, not a variant to score anyway.
    """
    m = MUTANT_RE.match(mutant)
    if not m:
        raise ReferenceMismatch(f"{mutant!r} is not a single substitution over the 20 standard residues")
    wt, pos, mut = m.group(1), int(m.group(2)), m.group(3)
    if not 1 <= pos <= len(reference):
        raise ReferenceMismatch(f"{mutant}: position {pos} outside 1..{len(reference)}")
    if reference[pos - 1] != wt:
        raise ReferenceMismatch(
            f"{mutant}: reference holds {reference[pos - 1]} at position {pos}, not the declared {wt}"
        )
    return Variant(mutant, wt, pos, mut, float("nan"))


def matched_variants(a: Assay, b: Assay) -> list[str]:
    """Variant keys measured in both assays, in deterministic order.

    Refuses to match assays that were not measured against the same reference,
    because a shared ``mutant`` string over different references is a different
    substitution.
    """
    if a.reference_sequence != b.reference_sequence:
        raise ReferenceMismatch(
            f"{a.assay_id} and {b.assay_id} have different reference sequences; variants are not comparable"
        )
    return sorted(set(a.variants) & set(b.variants))
