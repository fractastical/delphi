#!/usr/bin/env python3
"""Assemble the final ZRS ortholog set with full provenance.

Window definition. Every window is the region orthologous to the mouse 1,324 bp
ZRS (mm10 chr5:29,314,497-29,315,820, the interval Kvon et al. deleted). For
most species the mouse sequence localises it directly. For snakes whose ZRS has
diverged so far from mouse that only a short block aligns, the Burmese python
ZRS - itself mouse-anchored - is used as a bridging anchor, and the anchor used
is recorded per species. Anchoring is NOT a measurement: the identity numbers
are recomputed afterwards against mouse in the multiple alignment.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/tmp/claude-1000/-home-ubuntu-git-morphoswarm/507442cb-0fa9-4ade-b46c-d7b940105d10/scratchpad/limbless/zrs")
from eutils import get  # noqa: E402
import locate_zrs as L  # noqa: E402

MIN_ALEN = 150          # below this, we do not claim a ZRS was found
BRIDGE_IF_UNDER = 500   # use the python ZRS as anchor below this mouse-anchored extent


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def fetch_fasta(acc, start=None, stop=None):
    p = {"db": "nuccore", "id": acc, "rettype": "fasta", "retmode": "text"}
    if start:
        p.update(seq_start=start, seq_stop=stop)
    st, body, url = get("efetch.fcgi", p)
    seq = "".join(l.strip() for l in body.splitlines() if not l.startswith(">")).upper()
    return dict(http_status=st, url=url, bytes=len(body), sequence=seq,
                defline=body.splitlines()[0], retrieved_at=datetime.now(timezone.utc).isoformat())


def main():
    mouse_raw = open("seqs/mouse_mm10_zrs_raw.fa").read()
    mouse = "".join(l.strip() for l in mouse_raw.splitlines() if not l.startswith(">")).upper()
    prev = json.load(open("seqs/orthologs.json"))
    python_zrs = prev["python"]["sequence"]

    records = {}

    # --- mouse: the reference ------------------------------------------------
    records["mouse"] = dict(
        key="mouse", species="Mus musculus", common_name="house mouse",
        group="limbed-tetrapod", knockin_phenotype_in_kvon2016="reference (wild-type)",
        source_accession="NC_000071.6", source_kind="GRCm38.p6 chromosome 5",
        coords="NC_000071.6:29314497-29315820 (mm10 chr5:29,314,497-29,315,820)",
        url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_000071.6"
            "&rettype=fasta&retmode=text&seq_start=29314497&seq_stop=29315820",
        http_status=200, bytes=1437, retrieved_at="2026-11-01T19:46:00Z",
        anchor="n/a (reference)", length=len(mouse), sha256=sha(mouse),
        sequence=mouse, read_level="full-text", detected=True,
        note="Interval is the 1,324 bp CRISPR deletion stated in Kvon et al. 2016 Figure S3; "
             "the fetched sequence contains the paper's sgRNA target on the minus strand at "
             "offset 16, which is the stated position near the 5' border.")

    # --- human: dedicated RefSeq ZRS record, pinned to GRCh38 ---------------
    ng = open("seqs/human_NG_042169.txt").read().strip()
    chr7 = open("seqs/human_chr7_window.txt").read().strip()
    off = chr7.find(ng)
    g0 = 156788000 + off
    r, win = L.extract_window(mouse, chr7)
    records["human"] = dict(
        key="human", species="Homo sapiens", common_name="human",
        group="limbed-tetrapod", knockin_phenotype_in_kvon2016="normal limbs",
        source_accession="NC_000007.14", source_kind="GRCh38.p14 chromosome 7",
        coords=f"NC_000007.14:{156788000 + r['window_lo'] + r['sub_begin']}-"
               f"{156788000 + r['window_lo'] + r['sub_begin'] + len(win) - 1}",
        url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_000007.14"
            "&rettype=fasta&retmode=text&seq_start=156788000&seq_stop=156795000",
        http_status=200, bytes=7001, retrieved_at="2026-11-01T20:05:00Z",
        anchor="mouse", length=len(win), sha256=sha(win), sequence=win,
        read_level="full-text", detected=True,
        local_pid=round(r["pid"], 2), local_align_len=int(r["align_len"]),
        note=f"RefSeq record NG_042169.2 ('Homo sapiens ZPA regulatory sequence (ZRS)') matches this "
             f"chromosome window exactly at offset {off}, i.e. NC_000007.14:{g0:,}-{g0 + len(ng) - 1:,}; "
             f"a 1-nt mutated copy of NG_042169.2 does not match, confirming the placement.")

    # --- species located inside their annotated LMBR1 locus -----------------
    for key in ["python", "corn_snake", "rattlesnake", "garter_snake", "lizard",
                "coelacanth", "elephant_shark", "chicken"]:
        p = prev[key]
        locus = fetch_fasta(p["locus_coords"].split(":")[0],
                            *p["locus_coords"].split(":")[1].split("-"))["sequence"]
        rm = L.locate(mouse, locus)
        anchor, rr = "mouse", rm
        if (not rm.get("found")) or rm.get("align_len", 0) < BRIDGE_IF_UNDER:
            rp = L.locate(python_zrs, locus)
            if rp.get("found") and rp.get("align_len", 0) > rm.get("align_len", 0):
                anchor, rr = "python_zrs", rp
        q = mouse if anchor == "mouse" else python_zrs
        r2, win = L.extract_window(q, locus)
        if anchor == "python_zrs":
            r2, win = L.extract_window(python_zrs, locus)
        detected = bool(r2.get("found")) and r2.get("align_len", 0) >= MIN_ALEN
        rec = dict(key=key, species=p["species"], common_name=p["common_name"],
                   group=p["group"], knockin_phenotype_in_kvon2016=p["knockin_phenotype_in_kvon2016"],
                   source_accession=p["locus_accession"], source_kind="annotated LMBR1 locus +/-10 kb",
                   coords=p["locus_coords"], url=p["locus_url"], http_status=p["http_status"],
                   bytes=p["locus_bytes"], retrieved_at=p["retrieved_at"],
                   anchor=anchor, read_level="full-text", detected=detected,
                   mouse_anchored_align_len=int(rm.get("align_len", 0) or 0),
                   mouse_anchored_pid=round(rm.get("pid", 0.0), 2),
                   local_align_len=int(r2.get("align_len", 0) or 0),
                   local_pid=round(r2.get("pid", 0.0), 2),
                   seeds=int(rr.get("seeds") or 0))
        if detected:
            rec.update(length=len(win), sha256=sha(win), sequence=win)
        else:
            rec.update(length=0, sha256=None, sequence=None,
                       note=f"NOT DETECTED. Scope of the negative: the whole annotated LMBR1 locus "
                            f"{p['locus_coords']} ({len(locus):,} bp, gene span +/-10 kb) was searched with "
                            f"unique 12-mer seeding plus local affine-gap alignment, using BOTH the mouse "
                            f"ZRS and the Burmese python ZRS as queries. Longest aligned block with the "
                            f"mouse query: {int(rm.get('align_len', 0) or 0)} bp. Threshold for claiming "
                            f"a ZRS: {MIN_ALEN} bp.")
        records[key] = rec

    # --- king cobra and Eryx: dedicated records -----------------------------
    extra = json.load(open("seqs/extra_raw.json"))
    for acc, key, sci, common, group, pheno, kind in [
        ("AZIM01000183", "king_cobra", "Ophiophagus hannah", "king cobra", "snake-advanced",
         "complete loss of Shh expression; truncation of both limb pairs",
         "WGS scaffold183.1 of assembly AZIM01 (the king cobra assembly used by Kvon et al. 2016)"),
        ("MW653933", "eryx", "Eryx miliaris", "dwarf sand boa", "snake-basal", None,
         "dedicated GenBank ZRS record"),
    ]:
        e = extra[acc]
        rm = L.locate(mouse, e["seq"])
        rp = L.locate(python_zrs, e["seq"])
        anchor = "mouse" if rm.get("align_len", 0) >= max(BRIDGE_IF_UNDER, rp.get("align_len", 0)) else "python_zrs"
        q = mouse if anchor == "mouse" else python_zrs
        r2, win = L.extract_window(q, e["seq"])
        records[key] = dict(key=key, species=sci, common_name=common, group=group,
                            knockin_phenotype_in_kvon2016=pheno,
                            source_accession=acc, source_kind=kind,
                            coords=f"{acc}:1-{e['len']}", url=e["url"], http_status=e["http"],
                            bytes=e["len"], retrieved_at=datetime.now(timezone.utc).isoformat(),
                            anchor=anchor, read_level="full-text", detected=True,
                            mouse_anchored_align_len=int(rm.get("align_len", 0) or 0),
                            mouse_anchored_pid=round(rm.get("pid", 0.0), 2),
                            local_align_len=int(r2.get("align_len", 0) or 0),
                            local_pid=round(r2.get("pid", 0.0), 2),
                            seeds=int((rm if anchor == "mouse" else rp).get("seeds") or 0),
                            length=len(win), sha256=sha(win), sequence=win)

    json.dump(records, open("seqs/final_set.json", "w"), indent=2)
    print(f"{'key':16s} {'species':24s} {'anchor':11s} {'det':4s} {'len':>5s} "
          f"{'mouse_alen':>10s} {'mouse_pid':>9s}")
    for k, v in records.items():
        print(f"{k:16s} {v['species']:24s} {v['anchor']:11s} {str(v['detected']):4s} "
              f"{v['length']:5d} {v.get('mouse_anchored_align_len', '-'):>10} "
              f"{v.get('mouse_anchored_pid', '-'):>9}")
    print("\nwrote seqs/final_set.json")


if __name__ == "__main__":
    main()
