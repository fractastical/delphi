"""Independent reviewer check. Own closed form (Fractions) and own Hermite-cubic FEM; does not import the author's code."""
import json, re, sys, hashlib, csv
from fractions import Fraction as F
from pathlib import Path
import numpy as np
A=Path('/data/worktrees/delphi-frontier/fin-reuse-author-ro/artifacts/claim-reuse')
live=json.load(open('/tmp/claude-1000/claim.json'))
out={}
sha=lambda b:hashlib.sha256(b).hexdigest()
# 1. pins and hashes
proto=json.loads((A/'protocol.json').read_text())
out['protocol_file_sha256']=sha((A/'protocol.json').read_bytes())
for k,f in (('source_request_sha256','source-request.json'),('source_result_sha256','source-result.json'),('claim_read_file_sha256',None)):
    pass
out['source_request_sha_ok']=sha((A/'source-request.json').read_bytes())==proto['source_request_sha256']
out['source_result_sha_ok']=sha((A/'source-result.json').read_bytes())==proto['source_result_sha256']
req=json.loads((A/'source-request.json').read_text())
canon=hashlib.sha256(json.dumps(req,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
out['request_canonical_sha_matches_claim_prefix_f276a86069b8577d']=canon.startswith('f276a86069b8577d')
# 2. each Evidence artifact hash against the committed file
for n in ('below','above'):
    ev=json.load(open(f'/tmp/claude-1000/ev-{n}.json'))['record']['payload']; case=n+'-threshold'; bad=[]
    for a in ev['artifacts']:
        cands=[A/a['title'],A/case/a['title']]
        f=next((c for c in cands if c.exists()),None)
        if f is None or sha(f.read_bytes())!=a['sha256'] or f.stat().st_size!=a['byte_size']: bad.append(a['title'])
    out[f'{case}_artifact_hash_mismatches']=bad
# 3. Claim read before run equals the live record; parse the statement myself
for case in ('below-threshold','above-threshold'):
    rd=json.loads((A/case/'claim-read-before-run.json').read_text())
    out[f'{case}_claim_read_equals_live_record']=rd['record']==live['record']
m=re.search(r'EI_crit = (\d+)/(\d+) N m\^2',live['record']['payload']['statement']); EIc=F(int(m.group(1)),int(m.group(2)))
out['parsed_EI_crit']=str(EIc)
# 4. my own closed form, from the request's declared inputs
ca=req['candidate']; rho=F(ca['flight_assumptions']['rho']['value']); CL=F(ca['flight_assumptions']['CL_max']['value'])
V=F(ca['solver_result']['witness']['V']); b=F(ca['solver_result']['witness']['b'])
L=F(req['fin']['ray_length_fraction_of_semispan'])*b/2; w=F(req['fin']['tributary_width_m'])
q=rho*V*V*CL/2*w; tl=F(req['validity']['tip_over_L_max']); sl=F(req['validity']['slope_max_rad'])
out['mine']={'q':str(q),'L':str(L),'EI_tip':str(F(1,8)*q*L**3/tl),'EI_slope':str(q*L**3/(6*sl))}
out['claim_equals_my_EI_tip']=F(1,8)*q*L**3/tl==EIc
def fem(EI,q,L,n):
    h=L/n; k=EI/h**3*np.array([[12,6*h,-12,6*h],[6*h,4*h*h,-6*h,2*h*h],[-12,-6*h,12,-6*h],[6*h,2*h*h,-6*h,4*h*h]])
    f=q*h/2*np.array([1,h/6,1,-h/6]); N=2*(n+1); K=np.zeros((N,N)); R=np.zeros(N)
    for e in range(n):
        s=slice(2*e,2*e+4); K[s,s]+=k; R[s]+=f
    free=np.arange(2,N); u=np.zeros(N); u[free]=np.linalg.solve(K[np.ix_(free,free)],R[free])
    return u[0::2],u[1::2]
res={}
for case,mar in (('below-threshold',F(9,10)),('above-threshold',F(11,10))):
    EI=EIc*mar; tipx=q*L**4/(8*EI); slx=q*L**3/(6*EI)
    mine={'EI':str(EI),'tip_over_L_exact':str(tipx/L),'slope_exact':str(slx),'valid_exact':bool(tipx/L<=tl and slx<=sl)}
    r=json.loads((A/case/'result.json').read_text()); ei=json.loads((A/case/'effective-inputs.json').read_text())
    mine['author_solver_EI_equals_mine']=ei['solver_EI_Nm2_exact']==str(EI)
    mine['author_margin']=ei['margin_exact']
    mine['fem']={}
    for g in r['grids']:
        W,T=fem(float(EI),float(q),float(L),g['elements']); mine['fem'][g['elements']]={'my_tip_rel_err_vs_exact':abs(W[-1]-float(tipx))/float(tipx),'my_vs_author_tip_rel':abs(W[-1]-g['tip_m'])/g['tip_m'],'my_vs_author_slope_rel':abs(np.max(np.abs(T))-g['max_slope_rad'])/g['max_slope_rad']}
    v=r['validity']; mine['author_valid']=v['valid']; mine['author_tip_over_L']=v['tip_over_L']; mine['author_slope']=v['max_slope_rad']
    mine['author_matches_exact']=(v['valid']==mine['valid_exact'] and abs(v['tip_over_L']-float(tipx/L))<1e-8 and abs(v['max_slope_rad']-float(slx))<1e-8)
    res[case]=mine
    # profile.csv vs w(x)
    rows=list(csv.reader((A/case/'profile.csv').open())); hdr=rows[0]
    out[f'{case}_profile_header']=hdr; out[f'{case}_profile_rows']=len(rows)-1
out['cases']=res
print(json.dumps(out,indent=1,default=str))
