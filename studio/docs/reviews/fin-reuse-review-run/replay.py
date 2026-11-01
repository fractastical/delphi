import json,sys
from pathlib import Path
from engineering.claim_reuse.compute import ART, compute
p=json.loads((ART/'protocol.json').read_text()); OUT=Path(sys.argv[1])
for case in p['cases']:
    rec=json.loads((ART/case['id']/'claim-read-before-run.json').read_text())['record']
    r=compute(rec,p,case,OUT/case['id'])
    print(case['id'], 'type',type(r).__name__)
