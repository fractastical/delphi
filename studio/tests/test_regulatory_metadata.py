import pytest

from engineering.regulatory_metadata.audit import children, describe_sample, parse_soft


def test_requires_both_exact_identity_fields_and_rejects_challenge():
    good = b"^SAMPLE = GSM1\n!Sample_geo_accession = GSM1\n"
    assert parse_soft(good, "GSM1")["Sample_geo_accession"] == ["GSM1"]
    for bad in [good.replace(b"= GSM1", b"= GSM2", 1), good.replace(b"!Sample_geo_accession = GSM1", b"!Sample_geo_accession = GSM2"), b"<html>challenge</html>"]:
        with pytest.raises(ValueError):
            parse_soft(bad, "GSM1")


def test_preserves_repeated_fields_and_only_explicit_children():
    raw = b"^SERIES = GSE1\n!Series_geo_accession = GSE1\n!Series_relation = SuperSeries of: GSE2\n!Series_relation = SubSeries of: GSE3\n!Series_sample_id = GSM1\n!Series_sample_id = GSM2\n"
    fields = parse_soft(raw, "GSE1")
    assert children(fields) == ["GSE2"]
    assert fields["Series_sample_id"] == ["GSM1", "GSM2"]


def test_library_titles_do_not_create_biological_replicates_or_cell_labels():
    fields = {"Sample_title": ["4dpa_rep1_ATAC"], "Sample_characteristics_ch1": ["tissue: caudal fin", "age: 1 year"], "Sample_data_processing": ["Aligned to GRCz11"], "Sample_supplementary_file_1": ["https://example.org/matrix.mtx.gz"]}
    row = describe_sample("GSM1", fields)
    assert row["replicate_labels"] == []
    assert row["time_or_age"][0]["value"] == "1 year"
    assert not row["biological_replicate_identity_resolved"]
    assert not row["cell_level_labels_checked"]
    assert row["processed_file_links"][0]["sha256"] is None
    assert not row["processed_file_links"][0]["fetched"]


def test_second_pass_exposes_literal_passages_without_relabelling_or_pairing():
    from engineering.regulatory_metadata.review import literal_candidates

    result = literal_candidates({"Sample_characteristics_ch1": ["passages: 0 dpa"], "Sample_title": ["ATAC_sp7ne0dpa_rep1"], "Sample_data_processing": ["Genome_build: GRCz10; Ensembl release 85"]})
    assert result["time"][0] == {"selector": "Sample_characteristics_ch1", "literal": "passages: 0 dpa"}
    assert result["assembly"][0]["literal"] == "GRCz10"
    assert result["annotation"][0]["literal"] == "Ensembl release 85"

    assert result["replicate"][0]["literal"] == "ATAC_sp7ne0dpa_rep1"
