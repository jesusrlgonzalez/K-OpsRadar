"""Deterministic *synthetic* log data, with an external contamination ledger."""
import argparse,csv,json,random
from datetime import datetime,timedelta,timezone
from pathlib import Path
FIELDS=['ingest_id','event_id','timestamp','observed_timestamp','service','host','severity','http_status','duration_ms','trace_id','span_id','schema_version','message']
SERVICES=['api-gateway','auth-svc','billing-svc','worker-svc']
def create(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    rng=random.Random(23015)
    start=datetime(2026,2,1,tzinfo=timezone.utc)
    rows=[];truth=[]
    for i in range(2400):
        service=SERVICES[i%4]; seq=i//4
        ts=start+timedelta(minutes=5*seq)
        obs=ts+timedelta(seconds=rng.randint(1,20))
        status=500 if seq%137 in (101,102,103,104) else (503 if rng.random()<.025 else 200)
        dur=8000 if status>=500 and seq%137 in (101,102,103,104) else rng.randint(25,480)
        row=dict(ingest_id=f'ING-{i:05d}',event_id=f'EV-{i:05d}',timestamp=ts.isoformat(),observed_timestamp=obs.isoformat(),service=service,host=f'node-{(i%7)+1}',severity='ERROR' if status>=500 else 'INFO',http_status=str(status),duration_ms=str(dur),trace_id=f'{i+1:032x}',span_id=f'{i+1:016x}',schema_version='v1',message=f'synthetic request finished path=/api/v1/check status={status}')
        rows.append(row)
    # Each injected defect is mapped to a single row; not available to the auditor.
    injections=[('INVALID_TIME', [12,127,244,399]),('MISSING_SERVICE',[59,184,279,443]),('NEGATIVE_DURATION',[22,197,376,545]),('UNKNOWN_SEVERITY',[71,153,352]),('TRACE_CORRUPT',[51,258,422]),('LATE_DELIVERY',[9,401,803]),('FUTURE_CLOCK',[28,215,416]),('UNSUPPORTED_SCHEMA',[144,284,633]),('DUPLICATE_EVENT_ID',[105,205,605,905]),('SENSITIVE_MESSAGE',[41,191,381,701]),('BAD_STATUS',[124,524]),('INVALID_OBSERVED_TIME',[74,474]),('OUT_OF_ORDER_DELIVERY',[849,1001])]
    for typ,idxs in injections:
        for idx in idxs:
            r=rows[idx]
            if typ=='INVALID_TIME':r['timestamp']='2026-88-99T23:99:99'
            elif typ=='MISSING_SERVICE':r['service']=''
            elif typ=='NEGATIVE_DURATION':r['duration_ms']='-13'
            elif typ=='UNKNOWN_SEVERITY':r['severity']='BOOM'
            elif typ=='TRACE_CORRUPT':r['trace_id']='ZZ_not_a_trace'
            elif typ=='LATE_DELIVERY':r['observed_timestamp']=(datetime.fromisoformat(r['timestamp'])+timedelta(hours=5)).isoformat()
            elif typ=='FUTURE_CLOCK':r['observed_timestamp']=(datetime.fromisoformat(r['timestamp'])-timedelta(hours=2)).isoformat()
            elif typ=='UNSUPPORTED_SCHEMA':r['schema_version']='v9'
            elif typ=='DUPLICATE_EVENT_ID':r['event_id']=rows[idx-1]['event_id']
            elif typ=='SENSITIVE_MESSAGE':r['message']='synthetic customer fake.analyst@corp.test IP 192.0.2.20 token=FAKE-SECRET-DO-NOT-USE'
            elif typ=='BAD_STATUS':r['http_status']='999'
            elif typ=='INVALID_OBSERVED_TIME':r['observed_timestamp']='not-a-time'
            elif typ=='OUT_OF_ORDER_DELIVERY':
                # Records arrive after a 60 min event-time jump backward within the same service.
                r['timestamp']=(datetime.fromisoformat(r['timestamp'])-timedelta(hours=1)).isoformat()
            truth.append({'ingest_id':r['ingest_id'],'injected_issue':typ,'synthetic':True})
    with (out/'logs_dirty.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows(rows)
    with (out/'INJECTION_TRUTH_NOT_FOR_TRAINING.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['ingest_id','injected_issue','synthetic'],lineterminator='\n');w.writeheader();w.writerows(truth)
    (out/'SOURCE_PROVENANCE.json').write_text(json.dumps({'origin':'GENERATED_SYNTHETIC_I23','not_real_incidents':True,'seed':23015,'records':len(rows),'injections':len(truth),'warning':'All events, hosts, domains and customer references are fictional. Truth labels must not enter feature engineering.'},indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return len(rows),len(truth)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='DATOS_FUENTES/04_SINTETICOS');a=p.parse_args();print(create(a.out))
