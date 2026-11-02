#!/usr/bin/env python3
"""Test darwin1859-intro-04: congeners descend from a generally extinct species.

Reads the frozen genus list and thresholds from result.json. Downloads cytochrome-b
sequences and PBDB species lists into ./data (gitignored).

    python3 analysis.py --self-test
    python3 analysis.py --fill
"""
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
RESULT_PATH = os.path.join(HERE, "result.json")
RESULT = json.load(open(RESULT_PATH))
RULE = RESULT["sampling"]
GENERA = RESULT["genera"]

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
TITLE_RE = re.compile(r"cytochrome[\s-]*b\b|cyt[\s-]*b\b", re.I)

S = requests.Session()
S.headers["User-Agent"] = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"
FETCH_LOG = []
DEVIATIONS = []


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def remember(url, body, extra=None):
    rec = {"download_url": url, "retrieved_at": now(), "byte_size": len(body), "sha256": sha256(body)}
    if extra:
        rec.update(extra)
    FETCH_LOG.append(rec)
    return rec


def http(method, url, params=None, payload=None, timeout=180):
    last = None
    for attempt in range(5):
        try:
            if method == "GET":
                r = S.get(url, params=params, timeout=timeout)
            else:
                r = S.post(url, json=payload, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                last = r.status_code
                continue
            if r.status_code >= 400:
                raise requests.HTTPError(f"{r.status_code} {url} {r.text[:400]}", response=r)
            return r
        except requests.HTTPError:
            raise
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{method} failed {url}: {last}")


def cached_get(name, url, params, pause=0.34):
    path = os.path.join(DATA, name)
    meta_path = path + ".meta.json"
    if os.path.exists(path) and os.path.exists(meta_path):
        body = open(path, "rb").read()
        meta = json.load(open(meta_path))
        if meta.get("sha256") == sha256(body) and meta.get("byte_size") == len(body):
            FETCH_LOG.append(meta)
            return body
    time.sleep(pause)
    r = http("GET", url, params=params)
    body = r.content
    meta = remember(r.url, body)
    open(path, "wb").write(body)
    json.dump(meta, open(meta_path, "w"))
    return body


def verify_repo_files():
    for g in GENERA:
        for f in g["files"]:
            raw = open(os.path.join("/workspace", f["path"]), "rb").read()
            if len(raw) != f["byte_size"] or sha256(raw) != f["sha256"]:
                raise SystemExit(f"repo file hash mismatch: {f['path']}")


def wilson(k, n, z=1.96):
    if not n:
        return None, None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    margin = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return max(0.0, centre - margin), min(1.0, centre + margin)


def keypair(a, b):
    return (a, b) if a < b else (b, a)


def nj_descendant_clusters(names, dist):
    """Neighbor-joining. Returns the set of frozensets that are descendant clusters,
    including singletons and both sides of the final split."""
    nodes = list(names)
    cluster = {n: frozenset([n]) for n in names}
    D = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            D[keypair(a, b)] = float(dist(a, b))

    def get(a, b):
        return D[keypair(a, b)]

    def put(a, b, v):
        D[keypair(a, b)] = v

    descendant = set(cluster.values())
    n_id = 0
    while len(nodes) > 2:
        m = len(nodes)
        r = {a: sum(get(a, b) for b in nodes if b != a) for a in nodes}
        best_q, pair = None, None
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                q = (m - 2) * get(a, b) - r[a] - r[b]
                key = keypair(a, b)
                if best_q is None or q < best_q - 1e-12 or (abs(q - best_q) <= 1e-12 and (pair is None or key < pair)):
                    best_q, pair = q, key
        a, b = pair
        nu = f"__n{n_id}"
        n_id += 1
        dab = get(a, b)
        cluster[nu] = cluster[a] | cluster[b]
        descendant.add(cluster[nu])
        for c in nodes:
            if c == a or c == b:
                continue
            put(nu, c, 0.5 * (get(a, c) + get(b, c) - dab))
        nodes = [n for n in nodes if n != a and n != b] + [nu]
    if len(nodes) == 2:
        descendant.add(cluster[nodes[0]])
        descendant.add(cluster[nodes[1]])
    return descendant


def is_monophyletic(descendant, all_tips, member_tips):
    s = frozenset(member_tips)
    if len(s) < 2:
        return None
    return s in descendant or (frozenset(all_tips) - s) in descendant


def self_test():
    # Two genera of three, tight within and far between.
    names = ["A1", "A2", "A3", "B1", "B2", "B3"]

    def dist(a, b):
        return 0.1 if a[0] == b[0] else 1.0

    desc = nj_descendant_clusters(names, dist)
    assert is_monophyletic(desc, names, ["A1", "A2", "A3"]), desc
    assert is_monophyletic(desc, names, ["B1", "B2", "B3"])
    # Interleaved pairs are not genus clades.
    names2 = ["A1", "A2", "B1", "B2"]

    def dist2(a, b):
        close = {frozenset(("A1", "B1")), frozenset(("A2", "B2"))}
        return 0.05 if frozenset((a, b)) in close else 0.8

    desc2 = nj_descendant_clusters(names2, dist2)
    assert is_monophyletic(desc2, names2, ["A1", "B1"])
    assert not is_monophyletic(desc2, names2, ["A1", "A2"])
    assert not is_monophyletic(desc2, names2, ["B1", "B2"])
    print("self-test ok", flush=True)


def kmer_counts(seq, k):
    seq = "".join(ch for ch in seq.upper() if ch in "ACGT")
    from collections import Counter
    return Counter(seq[i:i + k] for i in range(max(0, len(seq) - k + 1)))


def cosine_distance(c1, c2):
    if len(c1) > len(c2):
        c1, c2 = c2, c1
    dot = sum(v * c2.get(key, 0) for key, v in c1.items())
    n1 = sum(v * v for v in c1.values()) ** 0.5
    n2 = sum(v * v for v in c2.values()) ** 0.5
    if n1 == 0 or n2 == 0:
        return None
    sim = max(-1.0, min(1.0, dot / (n1 * n2)))
    return 1.0 - sim


def fasta_seq(text):
    return "".join(ln.strip() for ln in text.splitlines() if ln and not ln.startswith(">"))


def is_binomial(name):
    parts = name.split()
    if len(parts) != RULE["binomial_tokens"]:
        return False
    if not parts[0][:1].isupper() or not parts[1][:1].islower():
        return False
    return parts[1].replace("-", "").isalpha()


def esearch_json(name, params):
    body = cached_get(name, ESEARCH, params)
    return json.loads(body)


def esummary_json(name, db, ids):
    body = cached_get(name, ESUMMARY, {"db": db, "id": ",".join(ids), "retmode": "json"})
    return json.loads(body)


def taxonomy_binomials(genus):
    taxid = genus.get("ncbi_taxid")
    name = genus["accepted_name"]
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    if taxid:
        term = f"txid{int(taxid)}[Organism:exp] AND species[Rank]"
    else:
        term = f"\"{name}\"[Genus] AND species[Rank]"
    js = esearch_json(f"tax_{safe}.json", {"db": "taxonomy", "term": term, "retmode": "json", "retmax": "400"})
    count = int(js["esearchresult"]["count"])
    ids = js["esearchresult"].get("idlist") or []
    if count == 0 and taxid:
        DEVIATIONS.append(f"{name}: inventory taxid {taxid} returned no species; used a genus-name taxonomy search.")
        term = f"\"{name}\"[Genus] AND species[Rank]"
        js = esearch_json(f"taxname_{safe}.json", {"db": "taxonomy", "term": term, "retmode": "json", "retmax": "400"})
        count = int(js["esearchresult"]["count"])
        ids = js["esearchresult"].get("idlist") or []
    if count > RULE["max_taxonomy_species_considered"]:
        return None, count
    names = []
    for i in range(0, len(ids), 80):
        chunk = ids[i:i + 80]
        sm = esummary_json(f"taxsum_{safe}_{i}.json", "taxonomy", chunk)
        res = sm["result"]
        for uid in chunk:
            sci = (res.get(uid) or {}).get("scientificname") or ""
            if is_binomial(sci):
                names.append(sci)
    names = sorted(set(names))
    return names, count


def choose_cytb(summary, binomial):
    res = summary["result"]
    uids = [str(u) for u in res.get("uids", []) if str(u) in res]
    cands = []
    for uid in uids:
        rec = res[uid]
        try:
            slen = int(rec.get("slen"))
        except (TypeError, ValueError):
            continue
        if not (RULE["slen_min"] <= slen <= RULE["slen_max"]):
            continue
        org = rec.get("organism") or ""
        if not (org == binomial or org.startswith(binomial + " ")):
            continue
        title = rec.get("title") or ""
        acc = rec.get("accessionversion") or rec.get("caption") or ""
        title_ok = 0 if TITLE_RE.search(title) else 1
        cands.append((title_ok, -slen, acc, str(uid), slen, title, org))
    if not cands:
        return None
    # Prefer a title that names cytochrome b; if none do, keep the gene-index hits.
    if any(c[0] == 0 for c in cands):
        cands = [c for c in cands if c[0] == 0]
    cands.sort()
    title_ok, neg, acc, uid, slen, title, org = cands[0]
    return {"uid": uid, "accession": acc, "slen": slen, "title": title, "organism": org}


def fetch_cytb(binomial, cache_stem):
    term = RULE["nuccore_term"].format(binomial=binomial)
    js = esearch_json(f"cytb_{cache_stem}.json", {"db": "nuccore", "term": term, "retmode": "json", "retmax": "8"})
    ids = js["esearchresult"].get("idlist") or []
    if not ids:
        return None
    sm = esummary_json(f"cytbsum_{cache_stem}.json", "nuccore", ids)
    pick = choose_cytb(sm, binomial)
    if pick is None:
        return None
    fasta = cached_get(
        f"fasta_{pick['accession']}.fa",
        EFETCH,
        {"db": "nuccore", "id": pick["uid"], "rettype": "fasta", "retmode": "text"},
    )
    seq = fasta_seq(fasta.decode("utf-8", "replace"))
    letters = "".join(ch for ch in seq.upper() if ch in "ACGT")
    if len(letters) < RULE["slen_min"]:
        return None
    pick = dict(pick)
    pick["sequence_letters"] = letters
    pick["species"] = binomial
    return pick


def clause_A():
    chordata = [g for g in GENERA if g.get("phylum") == RULE["clause_A_phylum"]]
    sequences = []  # dicts with species, genus, counts
    genus_notes = []
    for g in chordata:
        name = g["accepted_name"]
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
        binomials, count = taxonomy_binomials(g)
        if binomials is None:
            genus_notes.append({"genus": name, "status": "skipped", "reason": f"{count} species exceeds the cap"})
            print(f"A skip {name} count={count}", flush=True)
            continue
        examined = binomials[: RULE["max_species_examined_per_genus"]]
        kept = []
        for sp in examined:
            if len(kept) >= RULE["max_sequences_per_genus"]:
                break
            stem = re.sub(r"[^A-Za-z0-9_.-]", "_", sp)
            rec = fetch_cytb(sp, stem)
            if rec is None:
                continue
            rec["genus"] = name
            rec["counts"] = kmer_counts(rec.pop("sequence_letters"), RULE["kmer_k"])
            kept.append(rec)
            sequences.append(rec)
        genus_notes.append({
            "genus": name,
            "taxonomy_binomials": len(binomials),
            "examined": examined,
            "sequenced": [r["species"] for r in kept],
            "accessions": [r["accession"] for r in kept],
        })
        print(f"A {name} sequenced {len(kept)} of {len(examined)} examined", flush=True)
    tested = {}
    for rec in sequences:
        tested.setdefault(rec["genus"], []).append(rec["species"])
    tested = {g: sps for g, sps in tested.items() if len(sps) >= 2}
    if len(sequences) < 2 or len(tested) == 0:
        return {
            "outcome": "inconclusive",
            "reason": "data-unavailable" if len(sequences) == 0 else "underpowered",
            "n_tested": len(tested),
            "n_sequences": len(sequences),
            "genera": genus_notes,
            "monophyly_fraction": None,
            "nonidentical_fraction": None,
        }
    names = [r["species"] + "|" + r["genus"] for r in sequences]
    # species binomials can repeat only across genera; the label is unique
    by_label = {r["species"] + "|" + r["genus"]: r for r in sequences}
    labels = list(by_label)
    counts = {lab: by_label[lab]["counts"] for lab in labels}

    def dist(a, b):
        return cosine_distance(counts[a], counts[b])

    desc = nj_descendant_clusters(labels, dist)
    rows = []
    n_mono = 0
    n_diff = 0
    for genus, sps in sorted(tested.items()):
        members = [sp + "|" + genus for sp in sps]
        mono = bool(is_monophyletic(desc, labels, members))
        dists = []
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                dists.append(dist(a, b))
        differs = any(d > 1e-9 for d in dists)
        n_mono += int(mono)
        n_diff += int(differs)
        rows.append({
            "genus": genus,
            "species": sps,
            "monophyletic": mono,
            "mean_within_distance": round(sum(dists) / len(dists), 6) if dists else None,
            "sequences_differ": differs,
        })
    n = len(rows)
    mono_f = n_mono / n
    diff_f = n_diff / n
    if n < RULE["min_genera_A"]:
        outcome, reason = "inconclusive", "underpowered"
    elif mono_f < RULE["monophyly_fail"] or diff_f < RULE["nonidentical_fail"]:
        outcome, reason = "fail", None
    elif mono_f >= RULE["monophyly_pass"] and diff_f >= RULE["nonidentical_pass"]:
        outcome, reason = "pass", None
    else:
        outcome, reason = "mixed", None
    return {
        "outcome": outcome,
        "reason": reason,
        "n_tested": n,
        "n_monophyletic": n_mono,
        "n_sequences_differ": n_diff,
        "n_sequences": len(labels),
        "monophyly_fraction": round(mono_f, 6),
        "nonidentical_fraction": round(diff_f, 6),
        "monophyly_wilson95": [round(x, 6) for x in wilson(n_mono, n)],
        "genera_tested": rows,
        "genus_notes": genus_notes,
    }


def classify_extant(val):
    if isinstance(val, bool):
        return "extant" if val else "extinct"
    if val is None or val == "":
        return "unknown"
    s = str(val).strip().lower()
    if s in RULE["extant_tokens"]:
        return "extant"
    if s in RULE["extinct_tokens"]:
        return "extinct"
    return "unrecognized"


def fetch_pbdb(genus):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", genus)
    params = dict(RULE["pbdb_params"])
    params["base_name"] = genus
    body = cached_get(f"pbdb_{safe}.json", RULE["pbdb_url"], params, pause=0.2)
    return json.loads(body)


def clause_B():
    rows = []
    token_examples = {}
    phylum_field_seen = False
    for g in GENERA:
        name = g["accepted_name"]
        try:
            js = fetch_pbdb(name)
        except Exception as e:
            rows.append({"genus": name, "error": str(e)[:200]})
            print(f"B error {name} {e}", flush=True)
            continue
        records = js.get("records") or []
        n_extant = n_extinct = n_unknown = n_unrec = n_phy_match = n_phy = 0
        inv_phy = (g.get("phylum") or "").lower()
        for rec in records:
            if "phylum" in rec and rec.get("phylum"):
                phylum_field_seen = True
                n_phy += 1
                if str(rec.get("phylum")).strip().lower() == inv_phy:
                    n_phy_match += 1
            status = classify_extant(rec.get("is_extant"))
            raw = rec.get("is_extant")
            token_examples.setdefault(str(raw), 0)
            token_examples[str(raw)] += 1
            if status == "extant":
                n_extant += 1
            elif status == "extinct":
                n_extinct += 1
            elif status == "unknown":
                n_unknown += 1
            else:
                n_unrec += 1
        recognized = n_extant + n_extinct
        collision = bool(n_phy and inv_phy and (n_phy_match / n_phy) < 0.5)
        informative = (
            (not collision)
            and n_extant >= RULE["min_extant_species"]
            and recognized >= RULE["min_species_with_recognized_status"]
        )
        supports = informative and n_extinct >= RULE["min_extinct_species_to_support"]
        rows.append({
            "genus": name,
            "phylum": g.get("phylum"),
            "n_records": len(records),
            "n_extant": n_extant,
            "n_extinct": n_extinct,
            "n_unknown": n_unknown,
            "n_unrecognized": n_unrec,
            "collision": collision,
            "fossil_informative": informative,
            "has_extinct_species": bool(supports),
        })
        print(f"B {name} extant={n_extant} extinct={n_extinct} informative={informative}", flush=True)
    informative = [r for r in rows if r.get("fossil_informative")]
    n = len(informative)
    k = sum(1 for r in informative if r["has_extinct_species"])
    frac = (k / n) if n else None
    if n < RULE["min_genera_B"]:
        outcome, reason = "inconclusive", "underpowered" if n or any(r.get("n_records") for r in rows) else "data-unavailable"
    elif frac < RULE["extinct_fraction_fail"]:
        outcome, reason = "fail", None
    elif frac >= RULE["extinct_fraction_pass"]:
        outcome, reason = "pass", None
    else:
        outcome, reason = "mixed", None
    lo, hi = wilson(k, n) if n else (None, None)
    return {
        "outcome": outcome,
        "reason": reason,
        "n_informative": n,
        "n_with_extinct": k,
        "extinct_fraction": round(frac, 6) if frac is not None else None,
        "wilson95": [round(lo, 6), round(hi, 6)] if lo is not None else None,
        "phylum_field_seen": phylum_field_seen,
        "is_extant_token_counts": token_examples,
        "genera": rows,
    }


def equus_side(pbdb_rows):
    side = RESULT["equus_side_case_not_used_for_verdict"]
    seqs = []
    for sp in side["species_darwin_names"]:
        stem = re.sub(r"[^A-Za-z0-9_.-]", "_", sp)
        rec = fetch_cytb(sp, stem)
        if rec:
            rec["counts"] = kmer_counts(rec.pop("sequence_letters"), RULE["kmer_k"])
            rec["role"] = "ingroup"
            seqs.append(rec)
    outgroup = None
    for sp in side["outgroup_fallback_order"]:
        stem = re.sub(r"[^A-Za-z0-9_.-]", "_", sp)
        rec = fetch_cytb(sp, stem)
        if rec:
            rec["counts"] = kmer_counts(rec.pop("sequence_letters"), RULE["kmer_k"])
            rec["role"] = "outgroup"
            outgroup = rec
            break
    equus_pbdb = next((r for r in pbdb_rows if r["genus"] == "Equus"), None)
    result = {
        "sequenced_ingroup": [r["species"] for r in seqs],
        "missing_ingroup": [sp for sp in side["species_darwin_names"] if sp not in {r["species"] for r in seqs}],
        "outgroup": None if outgroup is None else outgroup["species"],
        "outgroup_accession": None if outgroup is None else outgroup["accession"],
        "pbdb_equus": equus_pbdb,
    }
    if len(seqs) < 2 or outgroup is None:
        result["monophyletic"] = None
        result["note"] = "fewer than 2 equine sequences or no tapir sequence"
        return result
    allrecs = seqs + [outgroup]
    labels = [r["species"] for r in allrecs]
    counts = {r["species"]: r["counts"] for r in allrecs}
    desc = nj_descendant_clusters(labels, lambda a, b: cosine_distance(counts[a], counts[b]))
    members = [r["species"] for r in seqs]
    result["monophyletic"] = bool(is_monophyletic(desc, labels, members))
    result["accessions"] = {r["species"]: r["accession"] for r in allrecs}
    return result


def overall(a, b):
    if a["outcome"] == "fail" or b["outcome"] == "fail":
        return "refutes", None
    if a["outcome"] == "pass" and b["outcome"] == "pass":
        return "supports", None
    nonpass = [x for x in (a, b) if x["outcome"] != "pass"]
    if nonpass and all(x["outcome"] == "inconclusive" for x in nonpass):
        reasons = [x["reason"] for x in nonpass if x.get("reason")]
        if reasons and all(r == "data-unavailable" for r in reasons):
            return "inconclusive", "data-unavailable"
        return "inconclusive", "underpowered"
    return "mixed", None


def confidence_for(verdict):
    # Capped because genus limits are partly molecular and plants are untested.
    # Numbers fixed with the preregistration's circularity caveat, not from the counts.
    return {"supports": 0.55, "refutes": 0.60, "mixed": 0.45, "inconclusive": 0.30}[verdict]


def strip_counts(clause_a):
    """Drop k-mer count objects; they are not JSON-serializable Counters in notes."""
    return clause_a


def public_A(a):
    keep = {k: a[k] for k in a if k != "genus_notes"}
    # genus notes can be large but are names only
    keep["n_genera_considered"] = len(a.get("genus_notes") or [])
    return keep


def run():
    verify_repo_files()
    print("repo files match the preregistered hashes", flush=True)
    a = clause_A()
    b = clause_B()
    side = equus_side(b.get("genera") or [])
    verdict, reason = overall(a, b)
    return a, b, side, verdict, reason


def build_measured(a, b, side):
    return {
        "value": b.get("extinct_fraction"),
        "unit": "fraction of fossil-informative living genera with at least one extinct accepted PBDB species",
        "n": b.get("n_informative"),
        "uncertainty": f"Wilson 95% {b.get('wilson95')}; clause A monophyly {a.get('monophyly_fraction')} of {a.get('n_tested')}",
        "extra": {
            "clause_A_outcome": a.get("outcome"),
            "clause_A_reason": a.get("reason"),
            "monophyly_fraction": a.get("monophyly_fraction"),
            "monophyly_wilson95": a.get("monophyly_wilson95"),
            "n_genera_sequenced": a.get("n_tested"),
            "n_monophyletic": a.get("n_monophyletic"),
            "nonidentical_fraction": a.get("nonidentical_fraction"),
            "n_sequences": a.get("n_sequences"),
            "clause_B_outcome": b.get("outcome"),
            "clause_B_reason": b.get("reason"),
            "n_with_extinct": b.get("n_with_extinct"),
            "extinct_fraction": b.get("extinct_fraction"),
            "extinct_wilson95": b.get("wilson95"),
            "is_extant_token_counts": b.get("is_extant_token_counts"),
            "phylum_field_seen": b.get("phylum_field_seen"),
            "equus_side": {k: side[k] for k in side if k != "pbdb_equus"} | (
                {"pbdb_equus_extinct": (side.get("pbdb_equus") or {}).get("n_extinct"),
                 "pbdb_equus_extant": (side.get("pbdb_equus") or {}).get("n_extant")}
            ),
        },
    }


def method_text(a, b, verdict):
    return (
        f"Clause A: for each frozen Chordata genus, took up to {RULE['max_species_examined_per_genus']} "
        f"alphabetical binomial species from NCBI taxonomy and kept up to {RULE['max_sequences_per_genus']} "
        f"with a cytochrome-b nucleotide record of length {RULE['slen_min']}-{RULE['slen_max']}. "
        f"Built one neighbor-joining tree on cosine distances of nucleotide {RULE['kmer_k']}-mers and scored "
        f"monophyly of each genus with at least two sequences ({a.get('n_tested')} genera, "
        f"monophyly fraction {a.get('monophyly_fraction')}). "
        f"Clause B: for every frozen genus, counted PBDB accepted species (vocab=pbdb, show=attr,app,class) "
        f"as extant or extinct from is_extant. A living genus with at least two recognized species and at least "
        f"one extant species is fossil-informative ({b.get('n_informative')}); the extinct fraction is "
        f"{b.get('extinct_fraction')}. "
        f"The verdict {verdict} follows the pre-registered combination of clause outcomes "
        f"A={a.get('outcome')} and B={b.get('outcome')}. "
        f"The Equus side case is reported and is not part of the verdict."
    )


def dataset_block():
    files = []
    for rec in FETCH_LOG:
        item = {
            "download_url": rec.get("download_url"),
            "retrieved_at": rec.get("retrieved_at"),
            "byte_size": rec.get("byte_size"),
            "sha256": rec.get("sha256"),
        }
        files.append(item)
    ncbi = [f for f in files if "ncbi.nlm.nih.gov" in (f.get("download_url") or "")]
    pbdb = [f for f in files if "paleobiodb.org" in (f.get("download_url") or "")]
    return [
        {
            "id": "ncbi-nuccore-cytb",
            "name": "NCBI taxonomy species lists and cytochrome-b nucleotide records",
            "landing_url": "https://www.ncbi.nlm.nih.gov/nuccore/",
            "doi": None,
            "version": "live NCBI, accessions and retrieval hashes recorded per file",
            "license": "NCBI sequence records are freely accessible. Information created by or for the US government on the NCBI site is in the public domain (https://www.ncbi.nlm.nih.gov/home/about/policies/). Individual GenBank records may be submissions from outside the US government.",
            "files": ncbi,
            "role": "species lists and cytochrome-b sequences for the monophyly test",
        },
        {
            "id": "paleobiology-database-taxa-list-1.2",
            "name": "Paleobiology Database data service 1.2 taxa/list",
            "landing_url": "https://paleobiodb.org/",
            "doi": None,
            "version": "data service 1.2, live database, identified by retrieval time and SHA-256",
            "license": "Creative Commons CC0 (https://creativecommons.org/publicdomain/zero/1.0/), read from the service datainfo block on 2026-11-02",
            "files": pbdb,
            "role": "accepted species and is_extant flags for the extinct-ancestor clause",
        },
        {
            "id": "darwin-origin-genus-inventory",
            "name": "Vendored genus records under test-data/organisms/darwin-origin",
            "landing_url": "https://github.com/fractastical/delphi",
            "doi": None,
            "version": "hashes recorded in genera[].files at preregistration",
            "license": "same as the repository",
            "files": [f for g in GENERA for f in g["files"]],
            "role": "frozen genus membership, phylum and NCBI taxid",
        },
    ]


def fill_result(a, b, side, verdict, reason):
    # Drop bulky per-genus exam lists from the committed measured block; keep them in derived/.
    measured = build_measured(a, b, side)
    RESULT["status"] = "complete"
    RESULT["measured"] = measured
    RESULT["verdict"] = verdict
    RESULT["confidence"] = confidence_for(verdict)
    RESULT["data_kind"] = "biological"
    RESULT["method"] = method_text(a, b, verdict)
    RESULT["datasets"] = dataset_block()
    RESULT["deviations"] = DEVIATIONS
    if reason:
        RESULT["reason"] = reason
    elif "reason" in RESULT:
        del RESULT["reason"]
    RESULT["results_summary"] = [
        f"Clause A {a.get('outcome')}: monophyly {a.get('n_monophyletic')}/{a.get('n_tested')} "
        f"= {a.get('monophyly_fraction')}; sequences differ in {a.get('nonidentical_fraction')} of tested genera; "
        f"sequences used {a.get('n_sequences')}.",
        f"Clause B {b.get('outcome')}: extinct species in {b.get('n_with_extinct')}/{b.get('n_informative')} "
        f"fossil-informative living genera = {b.get('extinct_fraction')} (Wilson 95% {b.get('wilson95')}).",
        f"Equus side (not used for the verdict): monophyletic={side.get('monophyletic')}, "
        f"sequenced={side.get('sequenced_ingroup')}, outgroup={side.get('outgroup')}, "
        f"PBDB extinct species={((side.get('pbdb_equus') or {}).get('n_extinct'))}.",
        f"Verdict {verdict} with confidence {confidence_for(verdict)}.",
    ]
    json.dump(a.get("genera_tested"), open(os.path.join(DERIVED, "clause_a_genera.json"), "w"), indent=2)
    json.dump(b.get("genera"), open(os.path.join(DERIVED, "clause_b_genera.json"), "w"), indent=2)
    json.dump(side, open(os.path.join(DERIVED, "equus_side.json"), "w"), indent=2)
    with open(RESULT_PATH, "w") as fh:
        json.dump(RESULT, fh, indent=2)
        fh.write("\n")


def check_result(a, b, side, verdict):
    if RESULT.get("status") != "complete":
        print("result.json is not complete; pass --fill", flush=True)
        return
    got = build_measured(a, b, side)
    exp = RESULT["measured"]
    if exp.get("value") != got.get("value") or exp.get("n") != got.get("n"):
        raise SystemExit(f"measured mismatch expected {exp.get('value')} n={exp.get('n')} got {got.get('value')} n={got.get('n')}")
    if RESULT.get("verdict") != verdict:
        raise SystemExit(f"verdict mismatch {RESULT.get('verdict')} vs {verdict}")
    print("recomputed measured matches result.json", flush=True)


def main():
    self_test()
    if "--self-test" in sys.argv:
        return
    a, b, side, verdict, reason = run()
    summary = {
        "verdict": verdict,
        "reason": reason,
        "clause_A": {k: a[k] for k in a if k not in ("genus_notes", "genera_tested")},
        "clause_B": {k: b[k] for k in b if k != "genera"},
        "equus_side": side,
        "deviations": DEVIATIONS,
    }
    json.dump(a.get("genus_notes"), open(os.path.join(DERIVED, "clause_a_sampling.json"), "w"), indent=2)
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=2)
    # The same hashes are copied onto the dataset file records in result.json.
    # A full log of this run is over the 200 KB derived-table limit, so it is not written.
    blob = json.dumps(FETCH_LOG, indent=1).encode()
    log_path = os.path.join(DERIVED, "fetch_log.json")
    if len(blob) <= 200_000:
        open(log_path, "wb").write(blob)
    else:
        if os.path.exists(log_path):
            os.remove(log_path)
        print(
            f"fetch log is {len(blob)} bytes, above the 200 KB derived-table limit; "
            "per-file URL, size and SHA-256 stay on the dataset records in result.json",
            flush=True,
        )
    print("verdict", verdict, reason, flush=True)
    if "--fill" in sys.argv:
        fill_result(a, b, side, verdict, reason)
        print("filled result.json", flush=True)
    else:
        check_result(a, b, side, verdict)


if __name__ == "__main__":
    main()
