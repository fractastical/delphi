"""Bounded independent integration/rejection probes; never changes compiler inputs."""
from pathlib import Path
from hashlib import sha256
import argparse
import json
import tempfile
import types
import platform


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
                  'entries': len(consumed['entries']), 'problems': consumed['problems']}}
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
