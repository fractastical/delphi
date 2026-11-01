"""Deterministic sequence identity/context gates; no functional model or design."""
from __future__ import annotations

from hashlib import sha256
from io import StringIO
import json
import re
import xml.etree.ElementTree as ET


def digest(sequence):
    if not isinstance(sequence, str) or not sequence or not re.fullmatch('[ACGT]+', sequence):
        raise ValueError('Expected explicit unambiguous DNA alphabet; no guessed bases')
    return sha256(sequence.encode()).hexdigest()


def parse_record(raw, accession, gene, gene_id):
    from Bio import SeqIO

    record = SeqIO.read(StringIO(raw.decode()), 'genbank')
    if record.id != accession or record.annotations.get('organism') != 'Danio rerio':
        raise ValueError('Accession/species mismatch')
    gene_features = [f for f in record.features if f.type == 'gene' and f.qualifiers.get('gene') == [gene]]
    if len(gene_features) != 1 or f'GeneID:{gene_id}' not in gene_features[0].qualifiers.get('db_xref', []):
        raise ValueError('Gene identity mismatch')
    sequence = str(record.seq).upper()
    digest(sequence)
    return record


def genomic_reference(raw_xml, gene_id, accession):
    root = ET.fromstring(raw_xml)
    gene = root.find('Entrezgene')
    if gene is None:
        raise ValueError('Missing gene identity')
    if gene.findtext('./Entrezgene_track-info/Gene-track/Gene-track_geneid') != str(gene_id):
        raise ValueError('Gene XML identity mismatch')
    candidates = [x for x in gene.findall('./Entrezgene_locus/Gene-commentary')
                  if f"{x.findtext('Gene-commentary_accession')}.{x.findtext('Gene-commentary_version')}" == accession]
    if len(candidates) != 1:
        raise ValueError('Expected one exact versioned genomic reference')
    item = candidates[0]
    interval = item.find('./Gene-commentary_seqs/Seq-loc/Seq-loc_int/Seq-interval')
    strand = interval.find('./Seq-interval_strand/Na-strand').get('value')
    if strand not in ('plus', 'minus'):
        raise ValueError('Unknown strand')
    return {'accession': accession, 'assembly': item.findtext('Gene-commentary_heading'),
            'chromosome_label': item.findtext('Gene-commentary_label'),
            'start_1based': int(interval.findtext('Seq-interval_from')) + 1,
            'end_inclusive': int(interval.findtext('Seq-interval_to')) + 1,
            'strand': '+' if strand == 'plus' else '-', 'coordinate_basis': 'Converted from NCBI Gene XML zero-based inclusive interval; no liftover'}


def compare_transcript(genomic, transcript):
    candidates = [f for f in genomic.features if f.type == 'mRNA' and f.qualifiers.get('transcript_id') == [transcript.id]]
    if len(candidates) != 1:
        raise ValueError('Exact transcript mapping absent or ambiguous')
    feature = candidates[0]
    projected = str(feature.extract(genomic.seq)).upper()
    actual = str(transcript.seq).upper()
    notes = feature.qualifiers.get('note', [])
    if len(projected) != len(actual):
        return {'status': 'length_mismatch', 'genome_spliced_nt': len(projected), 'transcript_nt': len(actual),
                'substitutions': None, 'note': feature.qualifiers.get('note', []), 'interchangeable': False}
    mismatches = [{'transcript_position_1based': i + 1, 'genomic_base': a, 'transcript_base': b}
                  for i, (a, b) in enumerate(zip(projected, actual)) if a != b]
    if any('indel' in note.lower() for note in notes):
        return {'status': 'annotation_reports_indels_alignment_not_performed',
                'genome_spliced_nt': len(projected), 'transcript_nt': len(actual),
                'substitutions': None, 'note': notes, 'interchangeable': not mismatches,
                'unaligned_positional_mismatch_count': len(mismatches),
                'first_16_unaligned_positional_differences': mismatches[:16],
                'scope': 'Equal total length does not remove indels. Position-wise differences are not a substitution count; no alignment or allele equivalence inferred'}
    return {'status': 'exact_match' if not mismatches else 'substitution_mismatch', 'genome_spliced_nt': len(projected),
            'transcript_nt': len(actual), 'substitutions': mismatches, 'substitution_count': len(mismatches),
            'note': feature.qualifiers.get('note', []), 'interchangeable': not mismatches,
            'scope': 'Exact reference-annotation comparison; not proof that either sequence equals an experimental allele or construct'}


def validate_ledger(ledger, read_artifact):
    if ledger['schema'] != 'frontier.sequence-function-ledger/1':
        raise ValueError('Unknown ledger schema')
    seqs = ledger['sequences']
    source_ids = {s['id'] for s in ledger['sources']}
    if len(source_ids) != len(ledger['sources']):
        raise ValueError('Duplicate source identity')
    by_id = {s['id']: s for s in seqs}
    if len(by_id) != len(seqs):
        raise ValueError('Duplicate sequence identity')
    for seq in seqs:
        if not seq['source_refs'] or not set(seq['source_refs']).issubset(source_ids):
            raise ValueError('Missing sequence provenance')
        artifact = seq['artifact_ref']
        if artifact is None:
            if seq['sequence_sha256'] is not None:
                raise ValueError('Sequence hash without bytes/reference')
            continue
        raw = read_artifact(artifact['path'])
        if sha256(raw).hexdigest() != artifact['sha256'] or len(raw) != artifact['bytes']:
            raise ValueError('Artifact digest/size mismatch')
        if seq['sequence_kind'] == 'existing_model_output':
            rows = json.loads(raw)
            matches = [r for r in rows if r['sha256'] == seq['sequence_sha256']]
            if len(matches) != 1:
                raise ValueError('Ambiguous generated sequence reference')
            text = matches[0]['sequence']
        else:
            lines = raw.decode().splitlines()
            if not lines or not lines[0].startswith('>'):
                raise ValueError('Expected FASTA sequence artifact')
            text = ''.join(lines[1:])
        if digest(text) != seq['sequence_sha256'] or len(text) != seq['length_nt']:
            raise ValueError('Sequence identity mismatch')
    entries = {e['id']: e for e in ledger['entries']}
    if len(entries) != len(ledger['entries']):
        raise ValueError('Duplicate evidence identity')
    for entry in entries.values():
        if entry['direction'] not in {'reference_only', 'forward_evidence', 'inverse_proposal'}:
            raise ValueError('Unknown causal direction')
        if any(ref not in by_id for ref in entry['sequence_refs']):
            raise ValueError('Missing sequence reference')
        if entry['evidence_class'] == 'model_output' and entry['functional_validation'] != 'unknown':
            raise ValueError('Model output cannot manufacture measured functional validation')
        if entry['direction'] == 'inverse_proposal' and entry.get('demonstrated_effect'):
            raise ValueError('Inverse proposal cannot be declared demonstrated')
        if not entry['missing_causal_bridge'] or not entry['falsifiable_validation_readout']:
            raise ValueError('Missing cross-layer boundary/readout')
        if not entry['species'] or not entry['source_refs'] or not set(entry['source_refs']).issubset(source_ids):
            raise ValueError('Missing species/source context')
    for bridge in ledger['bridges']:
        if bridge['from_entry'] not in entries or bridge['status'] not in {'context_supported', 'proposed', 'unresolved', 'contradicted'}:
            raise ValueError('Unknown bridge/source')
        if bridge['status'] == 'context_supported' and bridge['to_layer'] in {'mechanics', 'performance', 'behavior', 'organism'}:
            raise ValueError('This ledger has no measured causal calibration to mechanics/performance')
    return {'sequences_checked': len(seqs), 'entries_checked': len(entries), 'bridges_checked': len(ledger['bridges']),
            'new_inference': False, 'biological_implementation': False}
