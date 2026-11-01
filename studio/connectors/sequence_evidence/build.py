"""Build an offline, identity-pinned sequence/context ledger, without inference."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
from collections import Counter
import resource
import time

from .identity import compare_transcript, digest, genomic_reference, parse_record, validate_ledger

BASE = Path('artifacts/sequence-evidence')
GENES = [('fgf20a', 559630, 'NM_001037103.2', 'NC_141021.1'),
         ('kcnh2a', 563802, 'NM_001042722.2', 'NC_141022.1')]


def pin(root, path):
    raw = (root / path).read_bytes()
    return {'path': str(path), 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw)}


def write(root, path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def build(root):
    started = time.perf_counter()
    root = Path(root).resolve()
    if any((root/BASE/'raw').glob('*.html')):
        raise ValueError('Full article HTML publication is blocked: no verified redistribution grant for these sources')
    original = json.loads((root / BASE / 'retrieved-inputs.json').read_text())
    for expected in original['files']:
        actual = pin(root, expected['path'])
        if any(actual[k] != expected[k] for k in ('sha256', 'bytes')):
            raise ValueError('Frozen retrieved input changed')
    sequences, entries, comparisons, sources = [], [], {}, []

    def entry(key, direction, source_refs, **fields):
        item = {'id': key, 'direction': direction, 'evidence_class': 'paper_reported_experiment',
                'species': 'Danio rerio', 'sequence_refs': [], 'source_refs': source_refs,
                'context': {}, 'demonstrated_effect': None, 'functional_validation': 'paper_reported_in_context',
                'downstream_layer': 'expression', 'model_ready': False,
                'model_ready_reason': 'Context-specific observation is not an executable cross-scale model',
                'missing_causal_bridge': 'No measured expression-to-material, geometry, control or flight transfer function',
                'falsifiable_validation_readout': 'Context-matched reporter or endogenous expression, independently measured',
                **fields}
        entries.append(item)

    paper_specs = [
        ('kang2016', 'tree2016.html', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC4844022/',
         '10.1038/nature17644', ['Figure 2', 'Figure 4', 'Figure 5', 'Extended Data 7–9', 'Methods']),
        ('dev2020', 'tree2020.html', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7406312/',
         '10.1242/dev.191262', ['Figure 6: LEN deletion; Results']),
        ('promoter-context', 'compat2023.html', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC10211259/',
         '10.1016/j.ydbio.2022.09.007', ['Results: promoter compatibility'])]
    for key, name, url, doi, selectors in paper_specs:
        receipt = next(r for r in json.loads((root/BASE/'article-source-receipts.json').read_text())['sources'] if r['cache_name'] == name)
        sources.append({'id': key, 'url': url, 'doi': doi, 'response_sha256': receipt['response_sha256'],
                        'response_bytes': receipt['response_bytes'], 'redistribution_license': None,
                        'full_text_in_public_tree': False, 'source_receipt': pin(root, BASE/'article-source-receipts.json'),
                        'read_method': 'Ordinary public HTTPS GET; source passages/figure legends inspected',
                        'selectors': selectors, 'evidence_status': 'paper_reported; not independently replicated here'})
    sources.append({'id': 'daane2021', 'url': 'https://www.daanelab.org/pdfs/papers/Daane-CurrBio-2021.pdf',
                    'doi': '10.1016/j.cub.2021.08.054', 'artifact_ref': pin(root, 'data/genomics/daane2021_pins.json'),
                    'selectors': ['Figure 3', 'Figure 4'], 'read_method': 'Existing source-matched full-text extraction and figure legends',
                    'source_receipt': pin(root, 'data/genomics/daane2021_source.json')})
    for gene, gene_id, rna, chrom in GENES:
        raw = BASE/'raw'
        transcript = parse_record((root/raw/f'{gene}-{rna}.gb').read_bytes(), rna, gene, gene_id)
        genome_raw = (root/raw/f'{gene}-genomic.gb').read_bytes()
        # GenBank partial chromosome records retain chromosome accession.version.
        genomic = parse_record(genome_raw, chrom, gene, gene_id)
        ref = genomic_reference((root/raw/f'{gene}-gene.xml').read_bytes(), gene_id, chrom)
        comparisons[gene] = compare_transcript(genomic, transcript)
        sources.append({'id': f'ncbi-{gene}', 'url': f'https://www.ncbi.nlm.nih.gov/gene/{gene_id}',
                        'evidence_status': 'Reference annotation, not experimentally tested construct',
                        'artifact_refs': [pin(root, raw/f'{gene}-{rna}.gb'), pin(root, raw/f'{gene}-genomic.gb'),
                                          pin(root, raw/f'{gene}-gene.xml')],
                        'retrieval': 'NCBI EUtils efetch; exact queries in retrieval-queries.json'})
        for kind, record, reference in [('genomic', genomic, ref), ('transcript', transcript,
                {'accession': rna, 'assembly': None, 'start_1based': 1, 'end_inclusive': len(transcript.seq),
                 'strand': '+', 'coordinate_basis': 'Transcript orientation, not chromosome coordinates'})]:
            text = str(record.seq).upper()
            seq_id = f'{gene}-{kind}'
            fasta = BASE/'sequences'/f'{seq_id}.fasta'
            (root/fasta).parent.mkdir(parents=True, exist_ok=True)
            (root/fasta).write_text(f'>{seq_id}|{reference["accession"]}|reference_only\n' +
                                   '\n'.join(text[i:i+80] for i in range(0, len(text), 80)) + '\n')
            sequences.append({'id': seq_id, 'sequence_kind': 'natural_reference', 'sequence_sha256': digest(text),
                              'length_nt': len(text), 'artifact_ref': pin(root, fasta), 'reference': reference,
                              'source_refs': [f'ncbi-{gene}'], 'experimental_construct_identity': 'unknown',
                              'strain': next(f.qualifiers.get('strain', ['unknown'])[0]
                                             for f in record.features if f.type == 'source')})
            entry(seq_id, 'reference_only', [f'ncbi-{gene}'], evidence_class='sequence_annotation',
                  sequence_refs=[seq_id], functional_validation='unknown',
                  context={'reference': reference, 'allele': 'Reference, not longfin/dob experimental allele'},
                  missing_causal_bridge='Reference sequence is not the causal experimental allele or tested construct',
                  falsifiable_validation_readout='Exact source-allele/construct sequence identity and matched expression/function')

    entry('LEN-P2-positive', 'forward_evidence', ['kang2016'],
          context={'tissue': 'adult caudal fin blastema', 'state': 'amputation/regeneration',
                   'strain': 'EK; see paper Methods', 'element': 'LEN, reported 1350 bp', 'promoter': 'lepb P2',
                   'assembly_in_source': 'Zv9; no coordinate conversion performed', 'interval': None, 'strand': None},
          demonstrated_effect='LEN plus P2 drove injury-dependent reporter expression in tested lines (Figures 2,4).',
          missing_causal_bridge='Exact source fragment/interval not recovered; no calibrated expression-to-fin-shape link')
    entry('P2-adult-negative', 'forward_evidence', ['kang2016'],
          context={'tissue': 'adult caudal fin', 'state': 'regeneration', 'promoter': 'P2 only; exact sequence unresolved'},
          demonstrated_effect='P2-only reporter lacked adult caudal injury induction; larval fin-fold induction was reported (Methods).',
          falsifiable_validation_readout='Stage-matched reporter contrast, retaining larval versus adult distinction')
    entry('LEN-fragment-context', 'forward_evidence', ['kang2016', 'promoter-context'],
          context={'tissue': 'regenerating adult caudal fin', 'promoter': 'P2 versus cmlc2 versus alpha-cry'},
          demonstrated_effect='Fin-active modules and promoter-dependent differences were reported; 830–1350 had weak signal at long exposure (Extended Data 7–9).',
          missing_causal_bridge='Fragment-relative positions are not genome coordinates; promoter/stage context cannot be discarded')
    entry('LEN-endogenous-necessity', 'forward_evidence', ['dev2020'], downstream_layer='growth',
          context={'tissue': 'adult caudal fin', 'state': 'regeneration', 'allele': 'Source LEN deletion; exact sequence unresolved'},
          demonstrated_effect='LEN deletion abolished injury-associated lepb induction while fin regeneration remained normal (Figure 6).',
          falsifiable_validation_readout='Endogenous lepb RNA and independent fin regrowth endpoint, not reporter alone')
    entry('fgf20a-context-rescue', 'forward_evidence', ['kang2016'], downstream_layer='growth',
          context={'tissue': 'adult caudal fin', 'allele': 'dob/fgf20a mutant', 'construct': 'Source LENP2:fgf20a, sequence not equated to current RefSeq'},
          demonstrated_effect='Source-reported LEN-directed fgf20a rescue of regeneration in mutant context (Figure 5).',
          falsifiable_validation_readout='Context-specific regrowth and expression; no extrapolation to pectoral geometry or flight')
    entry('kcnh2a-lat4a-proportions', 'forward_evidence', ['daane2021'], downstream_layer='shape',
          context={'tissue': 'zebrafish fins', 'alleles': 'nr21 and longfin; not reference coding sequence', 'cell': 'Not resolved by this ledger'},
          demonstrated_effect='Source trans-heterozygote fin proportions resembled flying-fish proportions; this is not demonstrated flight.',
          missing_causal_bridge='Regulatory inversion/allele identity, cell-resolved expression, material and aerodynamic links unresolved',
          falsifiable_validation_readout='Allele-specific expression and source-defined fin length/body-length endpoints')
    sources.append({'id': 'lat4a-identity', 'artifact_ref': pin(root, 'data/genomics/lat4a_resolution_v3.json'),
                    'evidence_status': 'Supplement-to-orthology mapping; authors do not print zebrafish accession'})
    entry('lat4a-identity-gap', 'reference_only', ['lat4a-identity'], evidence_class='sequence_annotation',
          functional_validation='unknown', context={'candidate_symbol': 'slc43a2a', 'exact_mutant_DNA': None},
          missing_causal_bridge='RefSeq protein 153 aa does not resolve T200K/F326L residue numbering; no mutant DNA constructed',
          falsifiable_validation_readout='Independent full-length isoform/allele mapping of published residue numbering')

    targets = set()
    for arm in ('A', 'B'):
        path = BASE/'reused'/f'evo2-arm{arm}.json'
        source_id = f'existing-evo2-{arm}'
        sources.append({'id': source_id, 'artifact_ref': pin(root, path),
                        'evidence_status': 'Existing computational output reused, no new inference',
                        'original_path': ('results/compute/evo2zf/results/fevo2zf1-evo2-zebrafish-h100/out/zebrafish/candidates.json' if arm == 'A'
                                          else 'results/bioservices/evo2_zebrafish_armB/candidates_armB.json'),
                        'original_branch_B': 'work/frontier-bioservices' if arm == 'B' else None})
        for row in json.loads((root/path).read_text()):
            key = f'evo2-{arm}-{row["target"]}-{row["sample"]}'
            targets.add(row['target'])
            sequences.append({'id': key, 'sequence_kind': 'existing_model_output', 'length_nt': row['length'],
                              'sequence_sha256': row['sha256'], 'artifact_ref': pin(root, path),
                              'reference': None, 'source_refs': [source_id]})
            entry(key, 'inverse_proposal', [source_id], evidence_class='model_output', sequence_refs=[key],
                  functional_validation='unknown', context={'original_target_label': row['target'], 'arm': row['arm'],
                  'prompt_sha256': row.get('prompt_sha256'), 'fewshot_examples': row.get('fewshot_examples'),
                  'cell_stage_injury_specificity': 'unknown; original target name is not validation'},
                  desired_readout='Functional regulatory activity associated with the original label; unassayed',
                  missing_causal_bridge='Likelihood/composition does not establish promoter function, cell specificity or fin regeneration',
                  falsifiable_validation_readout='Independent context-matched expression assay against native and negative controls')
    entry('fin-inverse-open-question', 'inverse_proposal', ['kang2016', 'dev2020'], evidence_class='proposed_question',
          functional_validation='unknown', candidate_refs=[],
          desired_readout='Injury-dependent adult zebrafish caudal fin expression with bounded basal activity',
          context={'tissue': 'adult caudal fin', 'promoter_context': 'Must match tested source control', 'new_inference': False},
          model_ready_reason='No evidence-matched inverse model or exact LEN control coordinates; no candidate proposed',
          missing_causal_bridge='Resolve natural control identity, assay noise, expression-to-growth and downstream mechanics first')
    scores_path = BASE/'reused/evo2-scores.json'
    scores = json.loads((root/scores_path).read_text())
    score_hashes = {row['sha256'] for row in scores}
    generated = [s for s in sequences if s['sequence_kind'] == 'existing_model_output']
    if len(generated) != 32 or len({s['sequence_sha256'] for s in generated}) != 32:
        raise ValueError('Expected exact existing 32 unique outputs')
    if any(s['sequence_sha256'] not in score_hashes for s in generated):
        raise ValueError('Existing sequence missing from original score table')
    sources.append({'id': 'existing-evo2-scores', 'artifact_ref': pin(root, scores_path),
                    'evidence_status': 'Sequence likelihood, not functional regulatory assay'})
    bridges = [
        {'id': 'LEN-to-expression', 'from_entry': 'LEN-P2-positive', 'to_layer': 'expression', 'status': 'context_supported',
         'conditions': 'Only source-tested construct, adult fin injury and promoter context; sequence identity unresolved'},
        {'id': 'lepb-to-required-regrowth', 'from_entry': 'LEN-endogenous-necessity', 'to_layer': 'growth',
         'status': 'contradicted', 'conditions': 'Source deletion eliminated induction without blocking regrowth; necessity inference fails'},
        {'id': 'fin-proportions-to-flight', 'from_entry': 'kcnh2a-lat4a-proportions', 'to_layer': 'performance',
         'status': 'unresolved', 'conditions': 'No measured material, aero, stability, behavior or energy transfer'},
        {'id': 'expression-to-EI', 'from_entry': 'fgf20a-context-rescue', 'to_layer': 'mechanics', 'status': 'unresolved',
         'conditions': 'No quantitative expression/cell/growth-to-EI calibration; tissue EI is not hinge stiffness'}]
    ledger = {'schema': 'frontier.sequence-function-ledger/1', 'protocol': pin(root, BASE/'PROTOCOL.json'),
              'sources': sources, 'sequences': sequences, 'entries': entries, 'bridges': bridges,
              'reference_comparisons': comparisons, 'existing_evo2_target_labels': sorted(targets),
              'existing_evo2_score_audit': {'counts_by_kind': dict(Counter(r['kind'] for r in scores)),
                    'real_rows_fully_held_out': sum(r['kind'] == 'real_held_out' and r['fully_held_out'] for r in scores),
                    'all_32_outputs_have_original_score': True,
                    'scope': 'Continuation holdouts are not nine unseen loci; no function scores'},
              'scope': 'Reference identity and paper-context evidence, not functional DNA design, independent biological replication or flight feasibility',
              'unresolved_LEN_GRCz11_coordinates': True, 'new_inference': False}
    checked = validate_ledger(ledger, lambda p: safe_read(root, p))
    write(root, BASE/'ledger.json', ledger)
    import Bio
    write(root, BASE/'checks.json', {**checked, 'reference_comparisons': comparisons,
          'python': platform.python_version(), 'biopython': Bio.__version__,
          'control_scope': 'Exact annotation and hash checks; not functional validation',
          'ledger': pin(root, BASE/'ledger.json'), 'protocol': pin(root, BASE/'PROTOCOL.json'),
          'generated_at_UTC': datetime.now(timezone.utc).isoformat(),
          'resources': {'wall_s_before_receipt': time.perf_counter() - started,
                        'process_max_rss_KiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        'user_cpu_s': resource.getrusage(resource.RUSAGE_SELF).ru_utime,
                        'system_cpu_s': resource.getrusage(resource.RUSAGE_SELF).ru_stime,
                        'scope': 'This local build process only; not prior retrieval or model inference',
                        'dollars': None},
          'code': [pin(root, Path(__file__).relative_to(root)), pin(root, 'connectors/sequence_evidence/identity.py')]})
    write(root, BASE/'validation-contract.json', {
        'schema': 'frontier.sequence-validation-plan/1', 'candidate': 'fin-inverse-open-question',
        'ledger': pin(root, BASE/'ledger.json'), 'protocol': pin(root, BASE/'PROTOCOL.json'),
        'endpoint': 'Adult Danio rerio caudal-injury expression relative to basal expression in a specified promoter context',
        'sequence': None, 'context': {'assembly': 'unresolved for LEN; original Zv9 cannot be substituted by GRCz11/GRCz13ab',
                                    'cell': 'Source blastemal reporter compartment; no cell-resolved calibration'},
        'required_controls': ['Source LEN+P2 positive', 'P2-only adult negative, not larval negative',
                              'Uninjured matched context', 'Promoter-context alternative', 'Independent endogenous RNA'],
        'statuses': {'reference_integrity': 'pass', 'functional_prediction': 'blocked',
                     'independent_empirical_validation': 'not_run', 'inverse_design': 'blocked',
                     'expression_to_material_transfer': 'blocked', 'whole_organism_implementation': 'not_run'},
        'scope_of_pass': 'Four exact natural references and 32 original computational outputs checked; not source construct identity',
        'noise_tolerance_sample_size': None, 'reason_unknown': 'Requires context-matched measured assay; not invented from source figures',
        'readout_operator': 'Measured reporter intensity and endogenous expression under matched sampling and background controls; presently uncalibrated',
        'independence': 'Source papers are reused evidence; this curation is not new independent biology. A model cannot validate its own optimized sequence.',
        'next_action': 'Recover exact source LEN/control interval and allele identity before candidate forward/inverse evaluation',
        'execution_authority': 'Public source/reference retrieval and deterministic checks only; no new inference or wetlab execution'})
    return checked


def safe_read(root, path):
    root = Path(root).resolve()
    target = root / path
    if Path(path).is_absolute() or '..' in Path(path).parts or target.is_symlink():
        raise ValueError('Unsafe artifact path')
    target.resolve().relative_to(root)
    return target.read_bytes()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    print(json.dumps(build(parser.parse_args().root)))
