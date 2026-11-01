"""Fetch the mirrorwing flyingfish annotation (figshare 14600634, CC BY 4.0) and select the genes of interest.

The annotation files use two ID schemes: pep/cds/gff use `GHS#####`, every BLAST/InterPro table uses `HsScaf####G####`.
The files do not give the mapping. Here we test one hypothesis (the Nth gene of scaffold HS#### by position is
HsScaf####G<N>) against protein lengths, and write the result, whether it holds or not; nothing is mapped unless it passes.

  PYTHONPATH=. python3 -m connectors.genomics.fetch_flyingfish
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from . import sources as S

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "genomics"
ART = OUT / "artifacts"
ARTICLE = "https://api.figshare.com/v2/articles/14600634"
# mammalian/teleost symbols that SwissProt hits would carry for the zebrafish gene set (zebrafish-only genes have no entry here)
SYMBOLS = {"KCNH2": "kcnh2a", "KCNK5": "kcnk5b", "KCNJ13": "kcnj13", "PPP3CA": "ppp3ca", "SLC43A2": "slc43a2a/b", "FGF10": "fgf10a", "FGF20": "fgf20a", "SHH": "shha",
           "TBX5": "tbx5a", "LEF1": "lef1", "WNT5B": "wnt5b", "MSX1": "msx1b", "HOXD13": "hoxd13a", "RUNX2": "runx2b", "SP7": "sp7", "PIEZO1": "piezo1", "PIEZO2": "piezo2a",
           "TMC2": "tmc2b", "PKD2": "pkd2", "FGF24": "fgf24", "FGF8": "fgf8 (control)"}


def canon(gn: str | None) -> str | None:
    """Map a SwissProt GN name to a SYMBOLS key. Zebrafish entries carry a paralog suffix (kcnh2a, fgf8a); other species do not.

    Exact upper-case match only missed the suffixed names, which made 'KCNH2' look absent when the hit was kcnh2a."""
    if not gn:
        return None
    u = gn.upper()
    if u in SYMBOLS:
        return u
    if len(u) > 1 and u[-1] in "AB" and u[:-1] in SYMBOLS:
        return u[:-1]
    return None


def write(name: str, data: str | bytes) -> dict:
    b = data.encode() if isinstance(data, str) else data
    (ART / name).write_bytes(b)
    return {"path": f"data/genomics/artifacts/{name}", "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}


def fasta(lines):
    out, name, seq = {}, None, []
    for l in lines:
        if l.startswith(">"):
            if name:
                out[name] = "".join(seq)
            name, seq = l[1:].split()[0], []
        elif name:
            seq.append(l.strip())
    if name:
        out[name] = "".join(seq)
    return out


def main() -> int:
    body, meta_r = S.fetch(ARTICLE, 2_000_000)
    art = json.loads(body)
    files = {f["name"]: f for f in art["files"]}
    rec = {"article": {"receipt": meta_r.to_dict(), "license": art["license"], "doi": art["doi"], "published": art["published_date"], "artifact": write("figshare_14600634_article.json", body)}}

    def grab(name):
        f = files[name]
        kept, _, r = S.stream_lines(f["download_url"], lambda l: True, 60_000_000)
        ok = r.md5 == f["computed_md5"] and r.bytes == f["size"]
        rec.setdefault("files", {})[name] = {"receipt": r.to_dict(), "figshare_md5": f["computed_md5"], "figshare_size": f["size"], "md5_and_size_match": ok}
        if not ok:
            raise SystemExit(f"{name}: md5/size differ from figshare's declaration")
        return kept

    gff, pep, sp = grab("Hirundichthys_speculiger.gene.gff"), grab("Hirundichthys_speculiger.pep.fa"), grab("Hirundichthys_speculiger.pep.fa.blast.swissprot.xls")
    prot = fasta(pep)
    mrna = {}
    for l in gff:
        c = l.split("\t")
        if len(c) > 8 and c[2] == "mRNA":
            mrna[c[8].split("ID=")[1].rstrip(";")] = (c[0], int(c[3]), int(c[4]), c[6])
    # best SwissProt hit per query (max bit score), and the longest aligned query extent
    best, qend, allhits = {}, defaultdict(int), defaultdict(list)
    for l in sp[1:]:
        c = l.split("\t")
        if len(c) < 13:
            continue
        q, score = c[0], float(c[11])
        gn0 = re.search(r"GN=(\S+)", c[12])
        allhits[q].append((score, canon(gn0.group(1)) if gn0 else None, c[10]))
        qend[q] = max(qend[q], int(c[7]))
        if q not in best or score > best[q][0]:
            gn = re.search(r"GN=(\S+)", c[12])
            best[q] = (score, c[1], float(c[2]), c[10], gn.group(1) if gn else None, c[12].strip(), int(c[6]), int(c[7]))
    # hypothesis: HsScaf<s>G<n> == n-th mRNA (by start) on scaffold HS<s>
    by_scaf = defaultdict(list)
    for gid, (sc, st, en, strand) in mrna.items():
        by_scaf[sc].append((st, en, gid))
    for sc in by_scaf:
        by_scaf[sc].sort()
    tested = agree = 0
    for q in list(best)[:4000]:
        m = re.fullmatch(r"HsScaf(\d+)G(\d+)", q)
        if not m:
            continue
        sc, n = f"HS{m.group(1)}", int(m.group(2))
        if sc not in by_scaf or n > len(by_scaf[sc]):
            continue
        gid = by_scaf[sc][n - 1][2]
        tested += 1
        if qend[q] <= len(prot.get(gid, "")) + 0:
            agree += 1
    rate = agree / tested if tested else 0
    def strict(offset):
        t = ok = 0
        for q, bh in list(best.items())[:6000]:
            m = re.fullmatch(r"HsScaf(\d+)G(\d+)", q)
            if not m or bh[3] not in ("0.0", "0"):
                continue
            sc, n = f"HS{m.group(1)}", int(m.group(2)) + offset
            if sc in by_scaf and 1 <= n <= len(by_scaf[sc]):
                L = len(prot.get(by_scaf[sc][n - 1][2], ""))
                if L:
                    t += 1
                    ok += abs(L - bh[7]) <= max(5, 0.05 * L)
        return t, ok
    s0, s1, s2 = strict(0), strict(1), strict(-1)
    selected = {q: bh for q, bh in best.items() if canon(bh[4])}
    def paralog(raw, sym):
        """Is this best hit usable as evidence about the set's gene? A zebrafish suffix (a/b) must match the set's paralog."""
        setgene = SYMBOLS[sym]
        if sym == "FGF8":
            return False, "fgf8 is a control, not a member of the gene set"
        if raw.upper() == sym:
            return True, "best hit carries a mammalian-style symbol: no paralog information"
        if "/" in setgene:
            return True, f"best hit is {raw}; the set holds both paralogs ({setgene})"
        if setgene.endswith(raw[-1].lower()):
            return True, f"best hit {raw} matches the set's paralog {setgene}"
        return False, f"best hit is the zebrafish paralog {raw}; the set holds {setgene}"

    per_gene = []
    for q, bh in sorted(selected.items()):
        m = re.fullmatch(r"HsScaf(\d+)G(\d+)", q)
        sc, n = f"HS{m.group(1)}", int(m.group(2))
        gid = by_scaf[sc][n - 1][2] if sc in by_scaf and n <= len(by_scaf[sc]) else None
        L = len(prot.get(gid, "")) if gid else 0
        cov = round(bh[7] / L, 3) if L else None
        per_gene.append({"query": q, "symbol_hit": canon(bh[4]), "raw_gn": bh[4], "zebrafish_gene": SYMBOLS[canon(bh[4])], "best_subject": bh[1], "identity_pct": bh[2], "e_value": bh[3], "bit_score": bh[0],
                         "inferred_gene_model": gid, "scaffold": mrna[gid][0] if gid else None, "start": mrna[gid][1] if gid else None, "end": mrna[gid][2] if gid else None,
                         "strand": mrna[gid][3] if gid else None, "protein_length": L or None, "aligned_end": bh[7], "alignment_covers_fraction": cov,
                         "mapping_status": "inferred; length-consistent" if cov and 0.95 <= cov <= 1.05 else "inferred; NOT length-consistent (do not use coordinates)"})
        ok, why = paralog(bh[4], canon(bh[4]))
        per_gene[-1]["paralog_compatible"], per_gene[-1]["paralog_note"] = ok, why
        per_gene[-1]["usable"] = ok and per_gene[-1]["mapping_status"].startswith("inferred; length")
    absent_syms = sorted(set(SYMBOLS) - {canon(bh[4]) for bh in selected.values()})
    anyhit = {}
    for sym in absent_syms:
        qs = [(q, h) for q, hs in allhits.items() for h in hs if h[1] == sym]
        anyhit[sym] = {"hits": len(qs), "distinct_queries": len({q for q, _ in qs}), "examples": [{"query": q, "hit_score": h[0], "its_best_hit_gene": best[q][4], "its_best_score": best[q][0]} for q, h in sorted(qs, key=lambda x: -x[1][0])[:3]]}
    rec["id_mapping_test"] = {"hypothesis": "HsScaf<s>G<n> is the n-th mRNA by start position on scaffold HS<s>", "weak_test_alignment_end_within_protein": f"{agree}/{tested}",
                              "strict_test": "full-length (E=0) best hits whose aligned end is within max(5 aa, 5%) of the mapped protein length",
                              "strict_hypothesis": {"tested": s0[0], "within": s0[1], "rate": round(s0[1] / s0[0], 4) if s0[0] else None},
                              "control_offset_plus1": {"tested": s1[0], "within": s1[1], "rate": round(s1[1] / s1[0], 4) if s1[0] else None},
                              "control_offset_minus1": {"tested": s2[0], "within": s2[1], "rate": round(s2[1] / s2[0], 4) if s2[0] else None},
                              "reading": "the hypothesis fits far better than a one-gene shift, so it is probably right; it is still an inference, so each selected gene carries its own check and none is used unless length-consistent"}
    rec["selected_genes"] = per_gene
    rec["absent_symbols_any_hit"] = anyhit
    rows = ["Query_id\tBest_subject\tIdentity\tE_value\tScore\tGN\tSubject_annotation\tQuery_start\tQuery_end"]
    for q, b in sorted(selected.items()):
        rows.append(f"{q}\t{b[1]}\t{b[2]}\t{b[3]}\t{b[0]}\t{b[4]}\t{b[5]}\t{b[6]}\t{b[7]}")
    good = [g for g in per_gene if g["usable"]]
    rec["length_consistent_selected_genes"] = len(good)
    rec["peptides_selected"] = write("flyingfish_selected_proteins.faa", "".join(f">{g['inferred_gene_model']} {g['query']} best_swissprot_hit={g['best_subject']}({g['symbol_hit']}) source=figshare14600634 pep.fa\n" + "\n".join(prot[g["inferred_gene_model"]][i:i+60] for i in range(0, len(prot[g["inferred_gene_model"]]), 60)) + "\n" for g in good))
    ids = {g["inferred_gene_model"] for g in good}
    rec["gff_selected"] = write("flyingfish_selected_gene_models.gff3", "##gff-version 3\n" + "\n".join(l for l in gff if any(f"ID={i};" in l or f"Parent={i};" in l for i in ids)) + "\n")
    rec["swissprot_best_hits_selected"] = {"rows": len(selected), "of_queries": len(best), "artifact": write("flyingfish_swissprot_best_hits_selected.tsv", "\n".join(rows) + "\n"),
                                           "symbols_present": sorted({canon(b[4]) for b in selected.values()}), "symbols_absent": absent_syms}
    rec["annotation_totals"] = {"mRNA_in_gff": len(mrna), "proteins_in_pep": len(prot), "scaffolds_with_genes": len(by_scaf), "queries_with_swissprot_hit": len(best)}
    (OUT / "flyingfish_receipts.json").write_text(json.dumps(rec, indent=1, sort_keys=True))
    print(json.dumps({k: rec[k] for k in ("id_mapping_test", "annotation_totals", "length_consistent_selected_genes", "absent_symbols_any_hit")}, indent=1)); print([(g["zebrafish_gene"], g["mapping_status"][:18], g["alignment_covers_fraction"]) for g in per_gene])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
