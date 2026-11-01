#!/usr/bin/env python3
"""Fetch each species' LMBR1 locus, locate the ZRS inside it, record provenance."""
import hashlib
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/tmp/claude-1000/-home-ubuntu-git-morphoswarm/507442cb-0fa9-4ade-b46c-d7b940105d10/scratchpad/limbless/zrs")
from eutils import get  # noqa: E402
import locate_zrs as L  # noqa: E402

FLANK = 10000

# species -> (common name, genomic accession, gene chrstart, chrstop from NCBI Gene (0-based),
#             kvon2016 knock-in phenotype or None, group)
LOCI = {
    "python":      ("Burmese python",   "Python bivittatus",     "NW_028277088.1", 8376641, 8437086,
                    "severe limb truncation (rudimentary digits)", "snake-basal"),
    "corn_snake":  ("corn snake",       "Pantherophis guttatus", "NC_142066.1",  148631530, 148700530,
                    None, "snake-advanced"),
    "rattlesnake": ("tiger rattlesnake", "Crotalus tigris",      "NW_024096751.1", 1011878, 1081764,
                    None, "snake-advanced"),
    "garter_snake": ("garter snake",    "Thamnophis elegans",    "NC_045558.1",  11776098, 11844479,
                    None, "snake-advanced"),
    "lizard":      ("green anole",      "Anolis carolinensis",   "NC_085846.1", 108646138, 108695158,
                    None, "limbed-tetrapod"),
    "coelacanth":  ("coelacanth",       "Latimeria chalumnae",   "NC_088140.1",  43807645, 44021762,
                    "normal limbs", "lobe-finned fish"),
    "elephant_shark": ("elephant shark", "Callorhinchus milii",  "NW_024704743.1", 2419633, 2498108,
                    None, "cartilaginous fish"),
    "chicken":     ("chicken",          "Gallus gallus",         "NC_052533.1",   8435835, 8501552,
                    None, "limbed-tetrapod"),
}


def fetch_locus(acc, lo, hi):
    start = max(1, lo + 1 - FLANK)   # NCBI Gene coords are 0-based
    stop = hi + 1 + FLANK
    st, body, url = get("efetch.fcgi", {"db": "nuccore", "id": acc, "rettype": "fasta",
                                        "retmode": "text", "seq_start": start, "seq_stop": stop})
    seq = "".join(l.strip() for l in body.splitlines() if not l.startswith(">")).upper()
    return st, url, len(body), seq, start, stop


def main():
    mouse = "".join(l.strip() for l in open("seqs/mouse_mm10_zrs_raw.fa") if not l.startswith(">")).upper()
    out = {}
    for key, (common, sci, acc, lo, hi, pheno, group) in LOCI.items():
        st, url, nbytes, locus, start, stop = fetch_locus(acc, lo, hi)
        ts = datetime.now(timezone.utc).isoformat()
        nonacgt = sum(1 for c in locus if c not in "ACGT")
        r, win = L.extract_window(mouse, locus)
        rec = dict(key=key, species=sci, common_name=common, group=group,
                   knockin_phenotype_in_kvon2016=pheno,
                   locus_accession=acc, locus_coords=f"{acc}:{start}-{stop}",
                   locus_url=url, http_status=st, locus_bytes=nbytes,
                   locus_length=len(locus), locus_ambiguous_bases=nonacgt,
                   retrieved_at=ts, read_level="full-text",
                   seeds=int(r.get("seeds") or 0), seed_strand=r.get("strand"),
                   found=r.get("found"))
        if r.get("found"):
            zlo = r["window_lo"] + r["sub_begin"]
            rec.update(local_pid=round(r["pid"], 2), local_align_len=int(r["align_len"]),
                       local_identities=int(r["identity"]),
                       query_span=[int(r["query_begin"]), int(r["query_end"])],
                       zrs_length=len(win), sequence=win,
                       sha256=hashlib.sha256(win.encode()).hexdigest(),
                       zrs_offset_in_locus_window=int(zlo))
            print(f"{key:15s} {sci:24s} seeds={r['seeds']:4d} {r['strand']} "
                  f"pid={r['pid']:5.1f}% alen={r['align_len']:5d} q={r['query_begin']}-{r['query_end']} len={len(win):5d} sha={rec['sha256'][:10]}")
        else:
            rec.update(sequence=None, sha256=None, zrs_length=0)
            print(f"{key:15s} {sci:24s} NOT LOCALISED (seeds={r.get('seeds')})")
        out[key] = rec
    json.dump(out, open("seqs/orthologs.json", "w"), indent=2)
    print("\nwrote seqs/orthologs.json")


if __name__ == "__main__":
    main()
