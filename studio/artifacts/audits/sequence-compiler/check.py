"""Bounded independent integration/rejection probes; never changes compiler inputs."""
from pathlib import Path
from hashlib import sha256
import argparse
import json
import tempfile
import types
import platform
import shutil


def main(compiler, ledger_root, output):
    raw = compiler.read_bytes()
    snapshot = output.with_suffix('.compiler.py.txt')
    snapshot.write_bytes(raw)
    module = types.ModuleType('reviewed_genotype_snapshot')
    module.__file__ = str(compiler)
    exec(compile(raw, str(compiler), 'exec'), module.__dict__)
    ledger_path = Path('artifacts/sequence-evidence/ledger.json')
    ledger_raw = (ledger_root / ledger_path).read_bytes()
    ledger = json.loads(ledger_raw)
    use = {'ref': {'path': str(ledger_path), 'sha256': sha256(ledger_raw).hexdigest()},
           'sequence_ids': [s['id'] for s in ledger['sequences']],
           'entry_ids': [e['id'] for e in ledger['entries']]}
    consumed = module.consume_ledger(ledger_root, {'ledger': use})
    entries = {e['id']: e for e in consumed['entries']}
    context = entries['LEN-P2-positive'].get('context')
    results = {'compiler_file_sha256': sha256(raw).hexdigest(),
               'compiler_snapshot': snapshot.name, 'python': platform.python_version(),
               'ledger_sha256': sha256(ledger_raw).hexdigest(),
               'scope': 'Source identity/context/rejection checks; not sequence function or independent biology',
               'actual_ledger': {'sequences': len(consumed['sequences']),
                  'valid_sequences': sum(s['valid'] for s in consumed['sequences']),
                  'invalid_sequences': [{'id': s['id'], 'problems': s['problems']} for s in consumed['sequences'] if not s['valid']],
                  'LEN_context_consumed': context, 'LEN_context_original': next(e['context'] for e in ledger['entries'] if e['id'] == 'LEN-P2-positive'),
                  'LEN_source_context_preserved': entries['LEN-P2-positive'].get('source_context'),
                  'directions_preserved': all(entries[e['id']].get('direction') == e['direction'] for e in ledger['entries']),
                  'model_outputs_still_unknown': all(entries[e['id']].get('functional_validation') == 'unknown'
                      for e in ledger['entries'] if e['evidence_class'] == 'model_output'),
                  'entries': len(consumed['entries']), 'problems': consumed['problems']}}
    if hasattr(module, 'baseline_graph'):
        graph = module.baseline_graph(ledger_root)
        design = {'schema': module.DESIGN_SCHEMA, 'id': 'actual-ledger-missing-context-negative',
                  'claim': 'proposal', 'context': context, 'ledger': use}
        forward = module.compile_design(ledger_root, graph, design)
        old = [s for s in ledger['sequences'] if s['sequence_kind'] == 'existing_model_output'][:2]
        candidates = [{'id': s['id'], 'source_ref': s['artifact_ref'], 'length_nt': s['length_nt'],
                       'sequence_sha256': s['sequence_sha256'], 'evidence_kind': 'model_output',
                       'provenance': {'proposer': 'original-recorded-generator',
                         'method': 'Existing artifact retained in a missing-context refusal probe; no new design',
                         'source_refs': s['source_refs']}} for s in old]
        inverse = module.compile_inverse(ledger_root, graph,
            {'schema': module.INVERSE_SCHEMA, 'id': 'actual-existing-output-refusal',
             'target_node': 'expression', 'candidates': candidates}, design)
        results['actual_forward_inverse'] = {'forward_verdict': forward['verdict'],
            'forward_reasons': forward['reasons'], 'interface_state': forward['interface_state'],
            'inverse': inverse, 'scope': 'Deliberately incomplete source-context test; prior outputs remain hypotheses, not fin candidates or function evidence'}
        natural = next(s for s in ledger['sequences'] if s['id'] == 'fgf20a-transcript')
        candidate = {'id': natural['id'], 'source_ref': natural['artifact_ref'],
                     'length_nt': natural['length_nt'], 'sequence_sha256': natural['sequence_sha256']}
        results['actual_sequence_positive'] = module.check_sequence(ledger_root, candidate)
        results['actual_sequence_bad_declared_digest'] = module.check_sequence(ledger_root,
            {**candidate, 'sequence_sha256': '0'*64})
        other = next(s for s in ledger['sequences'] if s['id'] == 'kcnh2a-transcript')
        results['actual_I1_matching_candidate'] = module._check_inputs(ledger_root, 'I1', {},
            {'sequence_sha256': natural['sequence_sha256']}, {natural['sequence_sha256']})
        results['actual_I1_wrong_candidate'] = module._check_inputs(ledger_root, 'I1', {},
            {'sequence_sha256': natural['sequence_sha256']}, {other['sequence_sha256']})
        results['downstream_non_digest_string_diagnostic'] = module._check_inputs(ledger_root, 'I3',
            {'transfer_version': 'explicit-checker-fixture'}, {'upstream': 'not-a-digest'}, set())
    with tempfile.TemporaryDirectory() as dirname:
        root = Path(dirname)
        # Deliberately unrelated, explicitly non-execution bytes with a valid hash.
        raw_control = b'Not an execution record, measurement, or validation plan.\n'
        (root/'unrelated.txt').write_bytes(raw_control)
        ref = {'path': 'unrelated.txt', 'sha256': sha256(raw_control).hexdigest()}
        plan = {'id': 'p', 'version': '1', 'candidate_id': 'not_the_reference_file',
                'endpoint': 'functional expression', 'ref': ref,
                'required_checks': [{'id': 'c', 'endpoint': True, 'executable': True}]}
        result = {'plan_id': 'p', 'check_id': 'c', 'plan_version': '1', 'status': 'pass',
                  'cases': {'positive': True, 'negative': True, 'negative_rejected': True}, 'ref': ref}
        results['unrelated_result_bytes_and_bool_counts'] = module.evaluate_validation(root, {'validation_plans': [plan], 'validation_results': [result]})
        na_plan = {**plan, 'required_checks': [{'id': 'c', 'endpoint': False}]}
        na_result = {**result, 'status': 'not_applicable', 'reason': 'Declared out of scope'}
        results['all_nonendpoint_not_applicable'] = module.evaluate_validation(root, {'validation_plans': [na_plan], 'validation_results': [na_result]})
        # Properly pinned typed records isolate the count and missing-endpoint
        # guards from the earlier unrelated-file gate. These are invalid checker
        # fixtures, explicitly not empirical measurements or biological results.
        if hasattr(module, 'PLAN_SCHEMA') and hasattr(module, 'RESULT_SCHEMA'):
            dna_hash = next(s['sequence_sha256'] for s in ledger['sequences'] if s['id'] == 'fgf20a-transcript')

            def bound_records(endpoint, status, cases):
                frozen_plan = {'schema': module.PLAN_SCHEMA, 'id': 'typed-p', 'version': '1',
                    'candidate_id': 'checker-fixture', 'candidate_sequence_sha256': dna_hash,
                    'endpoint': 'Deliberately invalid validation bookkeeping fixture',
                    'required_checks': [{'id': 'c', 'endpoint': endpoint, 'executable': True}]}
                frozen_result = {'schema': module.RESULT_SCHEMA, 'plan_id': 'typed-p', 'plan_version': '1',
                    'check_id': 'c', 'candidate_sequence_sha256': dna_hash, 'status': status, 'cases': cases,
                    'reason': 'Deliberate validator fixture, no biology',
                    'validator': {'role': 'synthetic_checker_fixture', 'identity': 'independent-review',
                                  'dependence_identity': 'one-test-fixture'}}
                (root/'plan.json').write_text(json.dumps(frozen_plan))
                (root/'result.json').write_text(json.dumps(frozen_result))
                def refs(name):
                    return {'path': name, 'sha256': sha256((root/name).read_bytes()).hexdigest()}
                return module.evaluate_validation(root, {'validation_plans': [{**frozen_plan, 'ref': refs('plan.json')}],
                    'validation_results': [{**frozen_result, 'ref': refs('result.json')}]})

            results['bound_records_bool_counts'] = bound_records(True, 'pass',
                {'positive': True, 'negative': True, 'negative_rejected': True})
            results['bound_records_all_NA'] = bound_records(False, 'not_applicable', {})
            results['bound_records_structural_positive'] = bound_records(True, 'pass',
                {'positive': 2, 'negative': 1, 'negative_rejected': True})
            results['bound_records_string_endpoint_diagnostic'] = bound_records('false', 'pass',
                {'positive': 2, 'negative': 1, 'negative_rejected': True})
    if getattr(module, 'INSTRUMENT_FILE', '').endswith('instrument-contracts.json'):
        compiler_root = compiler.parents[2]
        paths = [Path(module.INSTRUMENT_FILE), Path(module.INSTRUMENT_MANIFEST), Path(module.PROTOCOL_FILE)]
        returned = module.instrument_contracts(compiler_root)
        results['current_DOE_binding'] = {'returned': returned,
            'input_files': [{'path': str(p), 'sha256': sha256((compiler_root/p).read_bytes()).hexdigest()}
                            for p in paths]}
        generated = module.build_files(compiler_root)
        results['regenerated_compiler_artifacts_match'] = {
            name: (compiler_root/'artifacts/biodesign-compiler'/name).read_text() == text
            for name, text in generated.items()}
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            for p in paths:
                (root/p).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(compiler_root/p, root/p)
            results['DOE_exact_copy'] = module.instrument_contracts(root)
            protocol = root / module.PROTOCOL_FILE
            protocol.write_bytes(protocol.read_bytes()+b'\n')
            results['DOE_changed_protocol_without_new_pin'] = module.instrument_contracts(root)
            manifest = root / module.INSTRUMENT_MANIFEST
            data = json.loads(manifest.read_text())
            data['files']['protocol.json']['sha256'] = sha256(protocol.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(data))
            results['DOE_whitespace_new_raw_pin_same_canonical'] = module.instrument_contracts(root)
            contract = root / module.INSTRUMENT_FILE
            doc = json.loads(contract.read_text())
            doc['protocol_sha256'] = '0'*64
            contract.write_text(json.dumps(doc))
            data['files']['instrument-contracts.json']['sha256'] = sha256(contract.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(data))
            results['DOE_wrong_canonical_protocol'] = module.instrument_contracts(root)
    output.write_text(json.dumps(results, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'compiler_sha256': results['compiler_file_sha256'],
                     'valid_sequences': results['actual_ledger']['valid_sequences'],
                     'unrelated_pass': results['unrelated_result_bytes_and_bool_counts']['all_required_pass'],
                     'all_NA_pass': results['all_nonendpoint_not_applicable']['all_required_pass']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--ledger-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    main(args.compiler.resolve(), args.ledger_root.resolve(), args.output)
