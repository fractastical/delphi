"""Bounded read-only audit of committed numerical outputs, not biology validation."""
from pathlib import Path
from hashlib import sha256
import argparse
import csv
from io import StringIO
import json
import math
import subprocess


def audit(owner, commit, output):
    def raw(path):
        return subprocess.check_output(['git', '-C', str(owner), 'show', commit+':'+str(path)])

    def js(path):
        return json.loads(raw(path), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))

    base = Path('artifacts/voxel-actuation')
    names = subprocess.check_output(['git', '-C', str(owner), 'ls-tree', '-r', '--name-only', commit, '--', str(base), 'scripts/voxel_actuation']).decode().splitlines()
    summary = js(base/'summary.json')
    protocol = js(base/'protocol.json')
    assert protocol['body']['body_len_m'] == 0.04
    frozen = subprocess.check_output(['git', '-C', str(owner), 'show', '7b9bd5d:'+str(base/'protocol.json')])
    assert frozen == raw(base/'protocol.json')
    sims, controls = [], []
    maximum_path_roundoff = 0.0
    for path in [Path(n) for n in names if n.endswith('.json')]:
        doc = js(path)
        if doc.get('schema') == 'frontier.voxelyze-soft-actuation/1':
            p, r, n = doc['params'], doc['result'], doc['numerics']
            assert not n['diverged']
            assert math.isclose(r['body_len_m'], (p['nx']-1)*p['voxel_m'], abs_tol=1e-12)
            vector = [r['com_end_m'][k]-r['com_start_m'][k] for k in (0, 1)]
            disp = math.hypot(*vector)
            # Coordinates and scalar outputs were printed to nine decimals.
            assert abs(vector[0]-r['net_dx_m']) <= 2.1e-9
            assert abs(vector[1]-r['net_dy_m']) <= 2.1e-9
            assert abs(disp-r['net_disp_m']) <= 2.1e-9
            assert abs(r['net_disp_m']/r['body_len_m']-r['disp_in_body_lengths']) <= 5.2e-7
            rows = list(csv.DictReader(StringIO(raw(path.with_name(path.stem+'-com.csv')).decode())))
            assert len(rows) == (n['steps_settle']+n['steps_measure']-1)//n['record_every']+1
            old = ((p['nx']-1)*p['voxel_m']/2, (p['ny']-1)*p['voxel_m']/2)
            length = 0.0
            for i, row in enumerate(rows):
                values = [float(row[k]) for k in row if k != 'phase']
                assert all(math.isfinite(v) for v in values)
                step = int(row['step'])
                assert step == i*n['record_every']
                assert abs(float(row['t_s'])-(step+1)*n['dt_s']) <= 5.3e-7
                assert row['phase'] == ('measure' if step >= n['steps_settle'] else 'settle')
                here = (float(row['com_x_m']), float(row['com_y_m']))
                length += math.hypot(here[0]-old[0], here[1]-old[1])
                old = here
            path_error = abs(length-r['path_len_m'])
            # Sum of segment errors from quantized CSV endpoints; not a new physical tolerance.
            bound = len(rows)*math.sqrt(2)*2e-9+5e-10
            assert path_error <= bound
            maximum_path_roundoff = max(maximum_path_roundoff, path_error)
            measure = [row for row in rows if row['phase'] == 'measure']
            sampled_disp = math.hypot(float(measure[-1]['com_x_m'])-float(measure[0]['com_x_m']),
                                      float(measure[-1]['com_y_m'])-float(measure[0]['com_y_m']))
            sims.append({'path': str(path), 'params': p, 'result': r, 'frames': len(rows),
                         'CSV_path_error_m': path_error,
                         'CSV_measure_first_last_displacement_m': sampled_disp,
                         'full_endpoint_vs_sampled_difference_m': r['net_disp_m']-sampled_disp,
                         'JSON_measurement_start_time_s': n['steps_settle']*n['dt_s'],
                         'JSON_end_time_s': (n['steps_settle']+n['steps_measure'])*n['dt_s'],
                         'CSV_measurement_first_time_s': float(measure[0]['t_s']),
                         'CSV_last_time_s': float(rows[-1]['t_s']),
                         'scope': 'Full endpoint metric is checked from JSON endpoints; decimated CSV omits exact endpoints, so its interval metric is separately retained'})
        elif doc.get('schema') == 'frontier.voxelyze-analytic-control/1':
            p, m = doc['params'], doc['measured']
            length = (p['n_voxels']-1)*p['voxel_m']
            if doc['mode'] == 'expansion':
                factor = 1-p['cte_per_C']*p['temp_C'] if doc['mutate'] == 'sign' else 1 if doc['mutate']=='none_law' else 1+p['cte_per_C']*p['temp_C']
                expected = length*factor
            else:
                used_E = p['E_Pa']*(10 if doc['mutate']=='stiffness' else 1)
                expected = p['tip_force_N']*length**3/(3*used_E*p['voxel_m']**4/12)
            assert math.isclose(expected, doc['analytic']['expected_m'], rel_tol=2e-7)
            settled = m['settle_drift_frac'] <= p['tol_settle'] and not m['diverged']
            passed = abs(m['value_m']/expected-1) <= p['tol'] and settled
            verdict = not passed and settled if doc['must_fail'] else passed
            assert (settled, passed, verdict) == (doc['gate']['settled'],doc['gate']['passed'],doc['gate']['control_verdict_ok'])
            controls.append({'path': str(path), 'mode': doc['mode'], 'mutate': doc['mutate'], 'expected_recomputed_m': expected,
                             'ratio_recomputed': m['value_m']/expected, 'settled': settled, 'passed': passed,
                             'control_verdict_ok': verdict, 'scope': 'Mutants change analytic reference expectations, not upstream engine code'})
    bypath = {r['path']: r for r in sims}
    coarse = bypath[str(base/'candidates/travelling.json')]
    fine = bypath[str(base/'posthoc/travelling-fine.json')]
    a, b = coarse['result'], fine['result']
    native_candidates = {Path(r['path']).stem:r for r in sims if '/candidates/' in r['path']}
    for name, r in native_candidates.items():
        for k in ('net_dx_m','net_dy_m','disp_per_cycle_m','path_len_m'):
            assert abs(summary['arm_A_candidates'][name][k]-r['result'][k]) <= 1.1e-9
        assert abs(summary['arm_A_candidates'][name]['body_lengths']-r['result']['disp_in_body_lengths']) <= 5.1e-6
    fric = bypath[str(base/'controls/D-frictionless.json')]
    fric_rows = list(csv.DictReader(StringIO(raw(base/'controls/D-frictionless-com.csv').decode())))
    def spread(k):
        return max(float(row[k]) for row in fric_rows)-min(float(row[k]) for row in fric_rows)
    assert spread('com_x_m') == spread('com_y_m') == 0.0
    vox = list(csv.DictReader(StringIO(raw(base/'trajectory/travelling-voxels.csv').decode())))
    com = list(csv.DictReader(StringIO(raw(base/'trajectory/travelling-com.csv').decode())))
    groups = {}
    for row in vox:
        assert all(math.isfinite(float(v)) for v in row.values())
        groups.setdefault(int(row['step']), []).append(row)
    assert len(groups)==241 and len(vox)==10845
    max_com = 0.0
    for row in com:
        frame = groups[int(row['step'])]
        assert len(frame)==45 and len({v['vox'] for v in frame})==45
        for k, col in [('x_m','com_x_m'),('y_m','com_y_m'),('z_m','com_z_m')]:
            error = abs(sum(float(v[k]) for v in frame)/45-float(row[col]))
            assert error <= 1.01e-9
            max_com=max(max_com,error)
    E = bypath[str(base/'controls/E-zero-gravity.json')]['result']
    assert E['disp_in_body_lengths']>0.01 and summary['controls']['E_zero_gravity']['met'] is False
    G = {tag:bypath[str(base/f'refinement/G-{tag}.json')]['result'] for tag in ('coarse','fine')}
    output.mkdir(parents=True,exist_ok=True)
    result={'source_commit':commit,'protocol_byte_identical_to_frozen_commit':'7b9bd5d','simulation_JSONs':len(sims),
            'simulation_run_count_excluding_animation_repeat':len(sims)-1,'analytic_JSONs':len(controls),
            'simulations':sims,'analytic_controls':controls,'maximum_csv_path_quantization_error_m':maximum_path_roundoff,
            'animation':{'frames':len(groups),'voxel_rows':len(vox),'voxels':45,'maximum_arithmetic_mean_vs_saved_COM_error_m':max_com,
                         'saved_fields':'voxel centers and imposed temperature; no orientations, forces, energy or physical cell boundaries'},
            'frictionless':{'reported_dx_m':fric['result']['net_dx_m'],'reported_dy_m':fric['result']['net_dy_m'],
                            'sampled_x_range_m':spread('com_x_m'),'sampled_y_range_m':spread('com_y_m'),
                            'sampled_z_range_m':spread('com_z_m'),'drive_range_C':spread('T_drive_C'),
                            'scope':'Horizontal COM stationary at printed precision while drive/vertical motion persist; not a dead-run or biological validation'},
            'E_preserved_failed_bound':E,'G_preserved':G,
            'posthoc_travelling':{'coarse_displacement_m':a['net_disp_m'],'fine_displacement_m':b['net_disp_m'],
                 'coarse_center_span_m':a['body_len_m'],'fine_center_span_m':b['body_len_m'],
                 'common_outer_length_m':0.05,'nominal_envelope_m':[0.05,0.03,0.03],'nominal_mass_kg':0.045,
                 'raw_SI_relative_difference_coarse_denominator':b['net_disp_m']/a['net_disp_m']-1,
                 'center_span_normalized_relative_difference':b['disp_in_body_lengths']/a['disp_in_body_lengths']-1,
                 'scope':'Posthoc two-grid observation; varying normalization, not spatial convergence or a biological microcarrier'},
            'candidate_spread_orders_of_magnitude':math.log10(max(r['result']['net_disp_m'] for r in native_candidates.values())/min(r['result']['net_disp_m'] for r in native_candidates.values())),
            'no_new_full_assay':True,'biological_validation':False,
            'input_files':[{'path':n,'sha256':sha256(raw(n)).hexdigest(),'bytes':len(raw(n))} for n in names]}
    (output/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'simulation_JSONs':len(sims),'analytic_JSONs':len(controls),'animation_max_COM_error_m':max_com,
                      'raw_refinement_difference':result['posthoc_travelling']['raw_SI_relative_difference_coarse_denominator'],
                      'candidate_spread_orders':result['candidate_spread_orders_of_magnitude']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--owner-root',type=Path,required=True)
    parser.add_argument('--commit',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    audit(args.owner_root.resolve(),args.commit,args.output)
