import json,copy,sys
from pathlib import Path
from engineering.claim_reuse.compute import ART, compute
p=json.loads((ART/'protocol.json').read_text()); case=p['cases'][0]
rec=json.loads((ART/case['id']/'claim-read-before-run.json').read_text())['record']
def attempt(name,r,proto=p):
    try: res=compute(r,proto,case,Path(sys.argv[1])/name); print(name,'-> NOT refused; checks_passed=',res.get('numerical_checks_passed'))
    except Exception as e: print(name,'-> refused:',type(e).__name__,str(e)[:90])
attempt('control-unmutated',rec)
m=copy.deepcopy(rec); m['version']=m['version'][:-1]+('0' if m['version'][-1]!='0' else '1'); attempt('altered-version',m)
m=copy.deepcopy(rec); m['id']='eng-finmech-claim-other'; attempt('altered-id',m)
m=copy.deepcopy(rec); m['payload']['statement']=m['payload']['statement'].replace('1323/2048000','1323/2048001'); attempt('altered-statement-EI',m)
m=copy.deepcopy(rec); m['payload']['source']['locator']=m['payload']['source']['locator'].replace('a48399f','b48399f'); attempt('altered-source-locator',m)
m=copy.deepcopy(rec); m['payload']['statement']=m['payload']['statement'].replace('tip_over_L','slope'); attempt('altered-binding-limit',m)
