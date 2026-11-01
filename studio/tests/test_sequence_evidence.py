"""Scope/identity checks, not functional validation or independent replication."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from connectors.sequence_evidence.build import BASE, build, safe_read
from connectors.sequence_evidence.identity import (
    compare_transcript, digest, genomic_reference, parse_record, validate_ledger,
)

ROOT = Path(__file__).resolve().parents[1]


def ledger():
    return json.loads((ROOT / BASE / 'ledger.json').read_text())


def test_actual_available_sequences_and_contexts():
    data = ledger()
    result = validate_ledger(data, lambda p: safe_read(ROOT, p))
    assert result['sequences_checked'] == 36
    generated = [s for s in data['sequences'] if s['sequence_kind'] == 'existing_model_output']
    assert len(generated) == len({s['sequence_sha256'] for s in generated}) == 32
    assert {s['length_nt'] for s in generated} == {1000}
    assert {'lepb', 'kcnh2a', 'fgf20a'}.isdisjoint(data['existing_evo2_target_labels'])
    assert data['unresolved_LEN_GRCz11_coordinates'] is True
    assert not result['new_inference']


def test_reject_actual_artifact_mutation():
    data = ledger()
    with pytest.raises(ValueError, match='Artifact digest'):
        validate_ledger(data, lambda p: safe_read(ROOT, p) + b'A')


def test_missing_source_identity_refused():
    data = ledger()
    data['entries'][0]['source_refs'] = ['nonexistent']
    with pytest.raises(ValueError, match='source context'):
        validate_ledger(data, lambda p: safe_read(ROOT, p))


@pytest.mark.parametrize('accession,gene,gid', [
    ('NM_001037103.1', 'fgf20a', 559630),
    ('NM_001037103.2', 'kcnh2a', 559630),
    ('NM_001037103.2', 'fgf20a', 0),
])
def test_wrong_reference_or_gene_refused(accession, gene, gid):
    raw = (ROOT / BASE / 'raw/fgf20a-NM_001037103.2.gb').read_bytes()
    with pytest.raises(ValueError, match='mismatch'):
        parse_record(raw, accession, gene, gid)


def test_explicit_minus_strand_and_assembly_are_not_silent_liftover():
    raw = (ROOT / BASE / 'raw/fgf20a-gene.xml').read_bytes()
    ref = genomic_reference(raw, 559630, 'NC_141021.1')
    assert (ref['start_1based'], ref['end_inclusive'], ref['strand']) == (17857305, 17859368, '-')
    assert ref['assembly'] == 'Reference GRCz13ab Primary Assembly'
    with pytest.raises(ValueError, match='versioned'):
        genomic_reference(raw, 559630, 'NC_007132.7')


def test_genome_transcript_disagreement_stays_explicit():
    raw = ROOT / BASE / 'raw'
    genome = parse_record((raw / 'fgf20a-genomic.gb').read_bytes(), 'NC_141021.1', 'fgf20a', 559630)
    rna = parse_record((raw / 'fgf20a-NM_001037103.2.gb').read_bytes(), 'NM_001037103.2', 'fgf20a', 559630)
    compared = compare_transcript(genome, rna)
    assert compared['substitution_count'] == 3
    assert [s['transcript_position_1based'] for s in compared['substitutions']] == [627, 772, 803]
    assert compared['interchangeable'] is False
    data = ledger()['reference_comparisons']['kcnh2a']
    assert data['substitutions'] is None
    assert data['status'] == 'annotation_reports_indels_alignment_not_performed'


@pytest.mark.parametrize('change', ['function', 'direction', 'mechanics'])
def test_no_function_or_mechanics_promotion(change):
    data = deepcopy(ledger())
    proposed = next(e for e in data['entries'] if e['evidence_class'] == 'model_output')
    if change == 'function':
        proposed['functional_validation'] = 'measured'
    elif change == 'direction':
        proposed['demonstrated_effect'] = 'Promoter function established'
    else:
        data['bridges'][0]['to_layer'] = 'mechanics'
    with pytest.raises(ValueError):
        validate_ledger(data, lambda p: safe_read(ROOT, p))


def test_inverse_unresolved_candidate_is_explicit_not_empty_success():
    item = next(e for e in ledger()['entries'] if e['id'] == 'fin-inverse-open-question')
    assert item['candidate_refs'] == [] and not item['model_ready']
    assert item['functional_validation'] == 'unknown'
    assert item['desired_readout'] and item['missing_causal_bridge']


def test_unsafe_artifact_path_and_ambiguous_bases_refused(tmp_path):
    with pytest.raises(ValueError):
        safe_read(ROOT, '../outside')
    with pytest.raises(ValueError):
        safe_read(ROOT, str(ROOT / 'GOAL.md'))
    (tmp_path / 'link').symlink_to(ROOT / 'GOAL.md')
    with pytest.raises(ValueError):
        safe_read(tmp_path, 'link')
    with pytest.raises(ValueError):
        digest('ACNT')


def test_full_article_mirror_refused_without_grant(tmp_path):
    raw = tmp_path / BASE / 'raw'
    raw.mkdir(parents=True)
    (raw / 'tree2016.html').write_text('Explicit invalid publication fixture')
    with pytest.raises(ValueError, match='redistribution grant'):
        build(tmp_path)
    receipts = json.loads((ROOT / BASE / 'article-source-receipts.json').read_text())
    assert len(receipts['sources']) == 3
    assert not list((ROOT / BASE / 'raw').glob('*.html'))
    assert all(s['response_sha256'] and s['source_locators'] and
               s['redistribution_license'] is None for s in receipts['sources'])
