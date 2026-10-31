"""Deterministic log admission: preserve evidence, separate data quality from incident claims.

No labels are accepted by this module; synthetic ground truth is never a feature.
"""
import argparse,csv,hashlib,json,re,math
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
from statistics import median
from .fixture import FIELDS
EMAIL=re.compile(r'(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b')
IP=re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
TOKEN=re.compile(r'(?i)\b(token|api[_-]?key|password)\s*[:=]\s*\S+')
TRACE=re.compile(r'^[0-9a-fA-F]{32}$')
SPAN=re.compile(r'^[0-9a-fA-F]{16}$')
ISSUE_SEVERITY={'INVALID_EVENT_TIME':'QUARANTINE','INVALID_OBSERVED_TIME':'QUARANTINE','MISSING_SERVICE':'QUARANTINE','INVALID_HTTP_STATUS':'QUARANTINE','INVALID_DURATION':'QUARANTINE','MISSING_EVENT_ID':'QUARANTINE','MISSING_INGEST_ID':'QUARANTINE','NEGATIVE_DURATION':'QUARANTINE','DUPLICATE_ID_CONFLICT':'QUARANTINE',
 'DUPLICATE_ID_REPLAY':'REVIEW','UNKNOWN_SEVERITY':'REVIEW','INVALID_TRACE_CONTEXT':'REVIEW','OBSERVED_LATE':'REVIEW','SOURCE_CLOCK_SKEW':'REVIEW','UNSUPPORTED_SCHEMA':'REVIEW','EVENT_BEFORE_WATERMARK':'REVIEW','SENSITIVE_MESSAGE_REDACTED':'REVIEW'}
RANK={'CANDIDATE':0,'REVIEW':1,'QUARANTINE':2}
def dt(s):
    try:
        v=datetime.fromisoformat((s or '').replace('Z','+00:00'))
        if v.tzinfo is None:return None
        return v.astimezone(timezone.utc)
    except (ValueError,TypeError,OverflowError):return None
def redacted(s):
    s=EMAIL.sub('[REDACTED_EMAIL]',s)
    s=IP.sub('[REDACTED_IP]',s)
    return TOKEN.sub(lambda m:m.group(1)+'=[REDACTED_SECRET]',s)
def write_csv(path, rows, fields):
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fields,lineterminator='\n',extrasaction='ignore');w.writeheader();w.writerows(rows)
def audit(source,out):
    source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    raw_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    seen={};max_event_by_service={};decisions=[];issues_rows=[];profile=Counter();hours=defaultdict(list)
    with source.open(newline='',encoding='utf-8') as f:
        rd=csv.DictReader(f)
        if not set(FIELDS).issubset(rd.fieldnames or []):raise ValueError('missing required columns')
        for number,r in enumerate(rd,1):
            if None in r:raise ValueError('corrupt CSV extra columns')
            defects=[];ev=dt(r['timestamp']);obs=dt(r['observed_timestamp']);svc=r['service'].strip();event_id=r['event_id'].strip()
            if ev is None:defects.append('INVALID_EVENT_TIME')
            if obs is None:defects.append('INVALID_OBSERVED_TIME')
            if not svc:defects.append('MISSING_SERVICE')
            if not event_id:defects.append('MISSING_EVENT_ID')
            if not r['ingest_id'].strip():defects.append('MISSING_INGEST_ID')
            if r['severity'] not in {'DEBUG','INFO','WARN','ERROR','FATAL'}:defects.append('UNKNOWN_SEVERITY')
            if r['schema_version'] not in {'v1','v2'}:defects.append('UNSUPPORTED_SCHEMA')
            if not TRACE.fullmatch(r['trace_id']) or not SPAN.fullmatch(r['span_id']):defects.append('INVALID_TRACE_CONTEXT')
            try:
                dur=float(r['duration_ms'])
                if not math.isfinite(dur):defects.append('INVALID_DURATION');dur=None
                elif dur<0:defects.append('NEGATIVE_DURATION')
            except (ValueError,TypeError):
                dur=None;defects.append('INVALID_DURATION')
            try:
                status=int(r['http_status'])
                if status<100 or status>599:defects.append('INVALID_HTTP_STATUS')
            except (ValueError,TypeError):
                status=None;defects.append('INVALID_HTTP_STATUS')
            if ev and obs:
                if obs-ev>timedelta(minutes=10):defects.append('OBSERVED_LATE')
                if ev-obs>timedelta(minutes=5):defects.append('SOURCE_CLOCK_SKEW')
            if ev and svc:
                hi=max_event_by_service.get(svc)
                if hi and ev<hi-timedelta(minutes=5):defects.append('EVENT_BEFORE_WATERMARK')
                if hi is None or ev>hi:max_event_by_service[svc]=ev
            # Hash stable exact input content, not guessed identity. Keep private raw externally in production.
            fingerprint=hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if event_id in seen:
                if seen[event_id]==fingerprint:defects.append('DUPLICATE_ID_REPLAY')
                else:defects.append('DUPLICATE_ID_CONFLICT')
            else:seen[event_id]=fingerprint
            safe_message=redacted(r['message'])
            if safe_message!=r['message']:defects.append('SENSITIVE_MESSAGE_REDACTED')
            status_quality='CANDIDATE'
            for reason in defects:
                if RANK[ISSUE_SEVERITY[reason]]>RANK[status_quality]:status_quality=ISSUE_SEVERITY[reason]
                profile[reason]+=1
                issues_rows.append({'ingest_id':r['ingest_id'],'reason':reason,'level':ISSUE_SEVERITY[reason]})
            canonical={'ingest_id':r['ingest_id'],'event_id':event_id,'source_line':number,'quality_status':status_quality,'reasons':';'.join(sorted(set(defects))),
                       'event_time_utc':ev.isoformat() if ev else '', 'observed_time_utc':obs.isoformat() if obs else '',
                       'service':svc, 'host':r['host'],'severity':r['severity'],'http_status':status if status is not None else '',
                       'duration_ms':dur if dur is not None else '', 'trace_id':r['trace_id'] if TRACE.fullmatch(r['trace_id']) else '',
                       'schema_version':r['schema_version'],'message_redacted':safe_message,'source_payload_sha256':fingerprint}
            decisions.append(canonical)
            if status_quality=='CANDIDATE' and ev and isinstance(status,int) and isinstance(dur,float):
                key=(svc,ev.strftime('%Y-%m-%dT%H:00:00+00:00'))
                hours[key].append((status,dur))
    metrics=[];alerts=[]
    for (svc,hour), vals in sorted(hours.items()):
        errs=sum(1 for s,d in vals if s>=500);n=len(vals);rate=errs/n
        delays=sorted(d for s,d in vals);p95=delays[min(n-1,int(.95*n))]
        metrics.append({'service':svc,'hour_utc':hour,'count':n,'http_5xx':errs,'error_rate':round(rate,6),'p95_duration_ms':p95})
        if n>=8 and errs>=4 and rate>=.25:
            alerts.append({'service':svc,'hour_utc':hour,'signal':'HIGH_5XX_RATE','error_rate':round(rate,6),'evidence_events':n,'status':'TRIAGE_ONLY','is_confirmed_incident':False})
    dispositions=Counter(x['quality_status'] for x in decisions)
    count=len(decisions)
    report={'project':'I23','dataset_kind':'SYNTHETIC_DIRTY_FIXTURE','source_sha256':raw_hash,'input_rows':count,'dispositions':{k:dispositions[k] for k in ['CANDIDATE','REVIEW','QUARANTINE']},'conservation_pass':sum(dispositions.values())==count,'issues_count_by_reason':dict(sorted(profile.items())),'windows':len(metrics),'triage_signals':len(alerts),'limits':['Labels are synthetic injections; they are not operational incidents','No automatic remediation, security attribution or confirmed outage classification','PII samples are synthetic; redaction is heuristic, not proven complete']}
    write_csv(out/'decisions.csv',decisions,list(decisions[0]) if decisions else [])
    write_csv(out/'issues.csv',issues_rows,['ingest_id','reason','level'])
    write_csv(out/'window_metrics.csv',metrics,['service','hour_utc','count','http_5xx','error_rate','p95_duration_ms'])
    write_csv(out/'triage_alerts.csv',alerts,['service','hour_utc','signal','error_rate','evidence_events','status','is_confirmed_incident'])
    write_csv(out/'quarantine.csv',[r for r in decisions if r['quality_status']=='QUARANTINE'],list(decisions[0]) if decisions else [])
    write_csv(out/'review.csv',[r for r in decisions if r['quality_status']=='REVIEW'],list(decisions[0]) if decisions else [])
    (out/'quality_report.json').write_text(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args();print(json.dumps(audit(a.source,a.out),indent=2))
