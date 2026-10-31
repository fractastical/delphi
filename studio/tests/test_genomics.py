"""Genomics connector: fetch bounds, hash integrity, record validity, and regressions for flaws found while reading the output.

Offline: it reads the committed data under data/genomics/ and re-derives what it can. Live fetching is exercised by running the fetch modules,
not by this file.
"""

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from connectors.genomics import sources as S  # noqa: E402
from connectors.genomics import fetch_flyingfish as FF  # noqa: E402
from connectors.genomics import build_index as BI  # noqa: E402

D = ROOT / "data" / "genomics"
SIGNED_QUERY = "X-Am" "z-Signa" "ture=SECRET&X-Am" "z-Creden" "tial=KEYID"      # assembled so this file holds no credential-shaped string


def J(name):
    return json.loads((D / name).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---- fetch bounds ---------------------------------------------------------------------------


def test_urls_outside_the_allow_list_or_over_http_are_refused():
    for bad in ("http://zfin.org/downloads/gene.txt", "https://evil.example/x", "https://zfin.org.evil.example/x", "https://s3-eu-west-1.amazonaws.com/pfigshare-u-files/1/x"):
        with pytest.raises(S.FetchRefused):
            S._check(bad)
    S._check("https://zfin.org/downloads/gene.txt")


def test_the_s3_hop_is_allowed_only_from_the_figshare_downloader():
    url = "https://s3-eu-west-1.amazonaws.com/pfigshare-u-files/28029993/x.gff?" + SIGNED_QUERY
    S._check(url, "ndownloader.figshare.com")
    for via in (None, "zfin.org", "api.figshare.com"):
        with pytest.raises(S.FetchRefused):
            S._check(url, via)
    with pytest.raises(S.FetchRefused):
        S._check("https://s3-eu-west-1.amazonaws.com/other-bucket/x", "ndownloader.figshare.com")


def test_refusal_messages_do_not_leak_signed_query_strings():
    with pytest.raises(S.FetchRefused) as e:
        S._check("https://evil.example/x?" + SIGNED_QUERY)
    assert "SECRET" not in str(e.value) and SIGNED_QUERY not in str(e.value)


# ---- manifest -------------------------------------------------------------------------------


def test_every_manifest_file_exists_with_the_pinned_hash_and_size():
    man = J("manifest.json")
    assert len(man["files"]) == man["counts"]["files"] >= 10
    for f in man["files"]:
        p = ROOT / f["path"]
        assert p.is_file() and sha(p) == f["sha256"] and p.stat().st_size == f["bytes"], f["path"]
    assert len({f["path"] for f in man["files"]}) == len(man["files"])


def test_manifest_obeys_its_schema_and_the_schema_rejects_violations():
    jsonschema = pytest.importorskip("jsonschema")
    schema, man = J("manifest.schema.json"), J("manifest.json")
    v = jsonschema.Draft202012Validator(schema)
    assert not list(v.iter_errors(man))

    def broken(edit):
        m = json.loads(json.dumps(man)); edit(m); return list(v.iter_errors(m))
    assert broken(lambda m: m["files"][0].update(sha256="xyz"))
    assert broken(lambda m: m["unresolved"].clear())
    assert broken(lambda m: m["display_rules"].update(show_species_on_every_row=False))
    assert broken(lambda m: m["files"][0].update(evidence_class="made_up"))
    assert broken(lambda m: m.update(extra=1))
    assert broken(lambda m: m["files"][0].update(path="/etc/passwd"))


def test_a_tampered_file_is_detected_by_the_manifest_check(tmp_path):
    man = J("manifest.json")
    f = next(x for x in man["files"] if x["path"].endswith("genes.csv"))
    copy = tmp_path / "genes.csv"
    copy.write_bytes((ROOT / f["path"]).read_bytes() + b"x")
    assert sha(copy) != f["sha256"]


# ---- records --------------------------------------------------------------------------------


def test_records_are_valid_frontier_records_with_exact_target_versions_and_a_clean_licence_gate():
    from frontier import models, store
    recs = J("records/records.json")["records"]
    assert 10 <= len(recs) <= 25
    by = {r["id"]: r for r in recs}
    for r in recs:
        models.Record.model_validate(r)
        if r["kind"] == "Evidence":
            t = r["payload"]["target"]
            assert by[t["id"]]["version"] == t["version"] and by[t["id"]]["kind"] == t["kind"]
            assert r["payload"]["evidence_kind"] != "observed" and r["payload"]["limitations"]
    assert not store._unlicensed_available_content(recs)
    assert {r["kind"] for r in recs} == {"Claim", "Evidence", "Problem"}
    assert all(r["payload"]["completeness"] == "recorded" for r in recs if r["kind"] == "Problem")


def test_negative_control_the_licence_gate_does_flag_unlicensed_available_content():
    from frontier import store
    rec = json.loads(json.dumps(next(r for r in J("records/records.json")["records"] if r["kind"] == "Claim")))
    rec["payload"]["source"]["content_available"] = True
    rec["payload"]["source"]["license"] = None
    assert store._unlicensed_available_content([rec])


def test_species_and_evidence_class_are_explicit_and_the_transfer_claim_is_a_hypothesis():
    by = {r["id"]: r for r in J("records/records.json")["records"]}
    for r in by.values():
        text = json.dumps(r["payload"])
        if r["kind"] == "Claim":
            assert "[species:" in text and "evidence_class:" in text, r["id"]
    assert by["gx-transfer-hypothesis-zebrafish-to-flyingfish"]["payload"]["origin"] == "hypothesis"
    assert "proposed_transfer" in by["gx-transfer-hypothesis-zebrafish-to-flyingfish"]["payload"]["context"]
    assert by["gx-problem-lat4a-identity"]["payload"]["original"]["status"] == "unresolved"
    assert not [r["id"] for r in by.values() if r["kind"] == "Claim" and "lat4a" in r["id"] and r["id"] != "gx-daane-lat4a-kcnh2a-source"]


def test_authors_in_statements_match_the_stored_europe_pmc_record():
    by = {r["id"]: r for r in J("records/records.json")["records"]}
    meta = json.loads((D / "artifacts" / "europepmc_PMC8294118.json").read_text())["resultList"]["result"][0]["authorString"]
    assert meta.startswith("Xu P") and "Xu et al." in by["gx-mirrorwing-assembly-annotation"]["payload"]["statement"]
    assert "Ding" not in json.dumps(by)


# ---- data invariants ------------------------------------------------------------------------


def test_genes_ids_come_from_the_stored_zfin_files_and_lat4a_is_not_a_row():
    rows = list(csv.DictReader(open(D / "genes.csv")))
    assert len(rows) == 22 and "lat4a" not in {r["symbol"] for r in rows}
    gene_txt = (D / "artifacts" / "zfin_gene_selected.tsv").read_text()
    for r in rows:
        assert r["zfin_id"] in gene_txt and re.fullmatch(r"ZDB-GENE-\d{6}-\d+", r["zfin_id"]) and re.fullmatch(r"ENSDARG\d{11}", r["ensembl_gene"])


def test_missing_values_stay_missing_in_the_expression_table():
    rows = list(csv.DictReader(open(D / "zfin_expression_selected.csv")))
    assert len(rows) == 2266
    assert sum(1 for r in rows if r["sub_structure"] == "") > 1000, "empty source fields must stay empty, not become 0 or 'None'"
    assert not [r for r in rows if r["sub_structure"] in ("0", "None", "nan")]


def test_kcnh2a_facts_match_the_stored_rows():
    exp = [r for r in csv.DictReader(open(D / "zfin_expression_selected.csv")) if r["symbol"] == "kcnh2a"]
    ph = [r for r in csv.DictReader(open(D / "zfin_phenotype_selected.csv")) if r["symbol"] == "kcnh2a"]
    assert len(exp) == 19 and {r["assay"] for r in exp} == {"Reverse transcription PCR"} and not ph
    assert {"fin", "regenerating fin"} <= {r["structure"] for r in exp}


def test_plot_manifest_hashes_match_files_and_inputs():
    pm = J("plots/plot_manifest.json")
    assert len(pm["plots"]) == 4
    for p in pm["plots"]:
        assert sha(ROOT / p["file"]) == p["sha256"]
        for i in p["inputs"]:
            assert sha(ROOT / i["path"]) == i["sha256"], i["path"]
    assert pm["plots_code_sha256"] == sha(ROOT / "connectors/genomics/plots.py")


def test_flyingfish_files_matched_figshare_and_the_id_mapping_beats_its_controls():
    f = J("flyingfish_receipts.json")
    assert all(v["md5_and_size_match"] for v in f["files"].values()) and f["annotation_totals"]["mRNA_in_gff"] == 23611
    t = f["id_mapping_test"]
    assert t["strict_hypothesis"]["rate"] > 0.85 and t["control_offset_plus1"]["rate"] < 0.1 and t["control_offset_minus1"]["rate"] < 0.1
    assert t["strict_hypothesis"]["rate"] > 8 * max(t["control_offset_plus1"]["rate"], t["control_offset_minus1"]["rate"])


def test_usable_gene_models_are_length_consistent_and_paralog_compatible():
    f = J("flyingfish_receipts.json")
    usable = [g for g in f["selected_genes"] if g["usable"]]
    assert usable and all(0.95 <= g["alignment_covers_fraction"] <= 1.05 and g["paralog_compatible"] for g in usable)
    not_used = {g["query"]: g for g in f["selected_genes"] if not g["usable"]}
    assert any("zebrafish paralog" in g["paralog_note"] for g in not_used.values()), "a shhb best hit must not count for shha"
    assert not [g for g in usable if g["raw_gn"].lower() in ("shhb", "fgf8a", "fgf8b")]
    seqs = (D / "artifacts" / "flyingfish_selected_proteins.faa").read_text().count(">")
    assert seqs == len(usable)


# ---- regressions for flaws found by reading the output --------------------------------------


def test_canon_accepts_zebrafish_paralog_suffixes_and_rejects_others():
    assert FF.canon("kcnh2a") == "KCNH2" and FF.canon("KCNH2") == "KCNH2" and FF.canon("Piezo1") == "PIEZO1" and FF.canon("fgf8a") == "FGF8"
    assert FF.canon("kcnh7") is None and FF.canon(None) is None and FF.canon("notagene") is None


def test_fin_pattern_is_word_bounded_so_definitive_is_not_a_fin():
    assert BI.FIN.search("pectoral fin") and BI.FIN.search("median fin fold") and BI.FIN.search("fin") and BI.FIN.search("fin bud")
    assert not BI.FIN.search("definitive hemopoiesis") and not BI.FIN.search("finger") and not BI.FIN.search("final")


def test_assembly_reading_states_offsets_and_that_ncbi_gene_is_a_different_assembly():
    a = J("assembly_check.json")
    for g, v in a["genes_checked_against_ucsc"].items():
        assert any(h["overlap_bp"] > 0 for h in v["ucsc_danrer11_refseq_matches"]), g
        assert v["ncbi_current_overlaps_zfin_span"] is False, g
        assert not v["ncbi_gene_current"]["chraccver"].startswith("NC_0070"), g      # GRCz11 chromosomes are NC_007112-NC_007132
    assert "NOT identical" in a["reading"] and "different assembly" in a["reading"]


# ---- no signed links or credentials in anything committed ----------------------------------


def _credential_hits(text):
    from connectors.genomics.scrub_receipts import CRED
    return CRED.findall(text)


def test_no_file_under_data_or_connectors_or_tests_carries_a_signed_url_or_credential():
    offenders = []
    for base in ("data/genomics", "connectors/genomics", "tests/test_genomics.py"):
        root = ROOT / base
        for p in ([root] if root.is_file() else sorted(q for q in root.rglob("*") if q.is_file())):
            if "__pycache__" in p.parts:
                continue
            try:
                text = p.read_text(errors="ignore")
            except OSError:
                continue
            if _credential_hits(text):
                offenders.append(str(p.relative_to(ROOT)))
    assert not offenders, f"signed URL or credential pattern in: {offenders}"


def test_negative_control_the_scanner_does_flag_a_signed_url():
    assert _credential_hits("https://s3-eu-west-1.amazonaws.com/b/x?" + SIGNED_QUERY)
    assert not _credential_hits("https://ndownloader.figshare.com/files/28029993")


def test_public_url_withholds_signed_links_and_keeps_ordinary_ones():
    assert S.public_url("https://s3-eu-west-1.amazonaws.com/b/x?" + SIGNED_QUERY) is None
    assert S.public_url("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=gene&id=1") == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=gene&id=1"
    assert S.public_url("https://ndownloader.figshare.com/files/28029993") == "https://ndownloader.figshare.com/files/28029993"


def test_figshare_receipts_keep_the_public_url_and_hashes_and_withhold_the_signed_hop():
    f = J("flyingfish_receipts.json")["files"]
    assert len(f) == 3
    for name, v in f.items():
        r = v["receipt"]
        assert r["url"].startswith("https://ndownloader.figshare.com/files/") and "?" not in r["url"], name
        assert r["final_url"] is None and r["redirect_host"] == "s3-eu-west-1.amazonaws.com", name
        assert re.fullmatch(r"[0-9a-f]{64}", r["sha256"]) and re.fullmatch(r"[0-9a-f]{32}", r["md5"]) and v["md5_and_size_match"] and r["md5"] == v["figshare_md5"]


def test_every_receipt_final_url_is_public_or_null():
    for name in ("receipts.json", "flyingfish_receipts.json", "extra_receipts.json"):
        def walk(n):
            if isinstance(n, dict):
                for k, v in n.items():
                    if k == "final_url":
                        assert v is None or S.public_url(v) == v, (name, v[:60] if v else v)
                    walk(v)
            elif isinstance(n, list):
                for v in n:
                    walk(v)
        walk(J(name))


def test_zfin_ensembl_ids_agree_across_two_zfin_files_and_the_check_says_it_is_not_independent():
    c = J("id_crosscheck.json")
    assert c["agree"] == c["of"] == 22 and "not an independent source" in c["limits"]
    rows = {r["symbol"]: r for r in csv.DictReader(open(D / "genes.csv"))}
    for sym, v in c["genes"].items():
        assert rows[sym]["ensembl_gene"] == v["ensembl_1_to_1"] and v["ensembl_1_to_1"] in v["ensembl_in_zfin_gff_alias"], sym
    # negative control: a wrong id must not count as agreeing
    assert "ENSDARG00000000000" not in c["genes"]["kcnh2a"]["ensembl_in_zfin_gff_alias"]
