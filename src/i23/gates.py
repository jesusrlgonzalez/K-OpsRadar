"""Conservative gate inspection: no unreviewed demo artifacts can count as approvals."""
import argparse,json,re
from pathlib import Path
GATES=('G0','G1','G2','G3','G4','G5_TECH','G5_BUSINESS')
def evaluate(root,gate):
    if gate not in GATES:raise ValueError('invalid gate')
    root=Path(root)
    path=root/'EVIDENCIAS'/gate/'approval.json'
    missing=[]
    if not path.exists():missing.append(str(path.relative_to(root)))
    else:
        try:
            d=json.loads(path.read_text(encoding='utf-8'))
            if d.get('gate')!=gate or d.get('status')!='APPROVED':missing.append('wrong gate/status')
            if not d.get('owner') or not d.get('independent_reviewer') or d['owner']==d['independent_reviewer']:missing.append('insufficient separation of duties')
            if not re.fullmatch(r'[0-9a-f]{64}',d.get('evidence_sha256','')):missing.append('missing evidence hash')
            if not d.get('approved_at'):missing.append('missing approval timestamp')
        except (ValueError,KeyError,TypeError):missing.append('invalid approval evidence')
    # Only evidence of approval at this gate can be checked locally. Real signatory authenticity remains external.
    return {'gate':gate,'status':'BLOCK' if missing else 'EVIDENCE_DOCUMENT_PRESENT_REQUIRES_EXTERNAL_VALIDATION','issues':missing,'automatic_authority':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--gate',default='G1',choices=GATES);a=p.parse_args();print(json.dumps(evaluate(a.root,a.gate),indent=2))
