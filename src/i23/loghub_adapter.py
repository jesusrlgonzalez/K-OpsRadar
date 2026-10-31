"""Domain-safe admission profiler for authentic BGL text logs. Does NOT convert BGL to HTTP events."""
import argparse,hashlib,json
from pathlib import Path
def profile_bgl(source,output):
    source=Path(source);output=Path(output)
    if not source.is_file():raise FileNotFoundError(source)
    total=0;nonalert=0;alert=0;blank=0
    with source.open(encoding='utf-8',errors='replace') as f:
        for line in f:
            total+=1
            if not line.strip():blank+=1;continue
            if line.split(maxsplit=1)[0]=='-':nonalert+=1
            else:alert+=1
    result={'source_kind':'REAL_LOGHUB_BGL_IF_OWNER_VERIFIED','admission':'PENDING_LICENSE_AND_INDEPENDENT_REVIEW',
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'lines':total,'marked_nonalert':nonalert,'marked_alert':alert,'blank':blank,
            'interpretation':'BGL first token alert-category versus dash; NOT an HTTP status or confirmed application incident',
            'http_mapping_supported':False,'raw_copied':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);args=p.parse_args();print(profile_bgl(args.source,args.out))
