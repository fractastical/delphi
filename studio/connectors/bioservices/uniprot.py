"""UniProtKB reference sequences, used as an independent reference check.

A DMS assay's reference sequence is reconstructed from the assay's own rows
(see :mod:`connectors.bioservices.proteingym`). That reconstruction is
self-consistent by construction, so on its own it cannot tell us the assay is
about the protein it claims to be about. Comparing it to UniProt can.
"""

from __future__ import annotations

import urllib.request

from connectors.bioservices.receipts import RetrievalReceipt, sha256_text, utc_now

FASTA_URL = "https://rest.uniprot.org/uniprotkb/{accession}.fasta"
USER_AGENT = "delphi-frontier-bioservices/0.1 (public-data replication)"
# UniProtKB is distributed under CC BY 4.0.
UNIPROT_LICENSE = "CC BY 4.0 (UniProt Consortium)"


def fetch_sequence(accession: str, timeout: int = 90) -> tuple[str, str, RetrievalReceipt]:
    """Return ``(header, sequence, receipt)`` for a UniProtKB accession."""
    url = FASTA_URL.format(accession=accession)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8")
    lines = text.splitlines()
    if not lines or not lines[0].startswith(">"):
        raise ValueError(f"{accession}: response is not FASTA")
    header = lines[0]
    sequence = "".join(line.strip() for line in lines[1:])
    receipt = RetrievalReceipt(
        source_id=f"uniprotkb.{accession}",
        url=url,
        state="retrieved",
        retrieved_utc=utc_now(),
        size_bytes=len(text.encode("utf-8")),
        sha256=sha256_text(sequence),
        media_type="text/x-fasta",
        license=UNIPROT_LICENSE,
        version=_version_from_header(header),
        notes=[header],
    )
    return header, sequence, receipt


def _version_from_header(header: str) -> str:
    """UniProt encodes the sequence version as ``SV=n`` in the FASTA header."""
    for token in header.split():
        if token.startswith("SV="):
            return token
    return "SV=unknown"


def compare(reference: str, uniprot_sequence: str) -> dict:
    """Describe the agreement between two sequences without judging it.

    Returns the comparison; the caller decides whether a mismatch is fatal.
    """
    identical = reference == uniprot_sequence
    result: dict = {
        "identical": identical,
        "reference_length": len(reference),
        "uniprot_length": len(uniprot_sequence),
        "reference_sha256": sha256_text(reference),
        "uniprot_sha256": sha256_text(uniprot_sequence),
    }
    if not identical and len(reference) == len(uniprot_sequence):
        diffs = [
            {"position": i + 1, "uniprot": a, "reference": b}
            for i, (a, b) in enumerate(zip(uniprot_sequence, reference))
            if a != b
        ]
        result["n_substitutions"] = len(diffs)
        result["first_differences"] = diffs[:10]
    return result
