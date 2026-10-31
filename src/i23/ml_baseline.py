"""Experimental IsolationForest comparator with strictly chronological split; never assert incident detection."""
import argparse,csv,json
from pathlib import Path
def split_windows(rows,frac=.6):
    # Split by CLOCK boundary, never by randomly shuffled service windows.
    times=sorted({r['hour_utc'] for r in rows})
    if len(times)<10:raise ValueError('insufficient time intervals')
    boundary=times[max(1,int(len(times)*frac))-1]
    train=[r for r in rows if r['hour_utc']<=boundary]
    test=[r for r in rows if r['hour_utc']>boundary]
    if not train or not test:raise ValueError('empty split')
    return train,test,boundary
def run(metrics,out):
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    with Path(metrics).open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    train,test,boundary=split_windows(rows)
    def X(rows):return [[float(r['count']),float(r['error_rate']),float(r['p95_duration_ms'])] for r in rows]
    scale=StandardScaler().fit(X(train));model=IsolationForest(random_state=23015,n_estimators=60,contamination=.08).fit(scale.transform(X(train)))
    scores=model.decision_function(scale.transform(X(test)))
    flagged=[]
    for r,s in zip(test,scores):
        if s<0:flagged.append({'service':r['service'],'hour_utc':r['hour_utc'],'outlier_score':round(float(s),8),'label':'STATISTICAL_OUTLIER_NOT_CONFIRMED_INCIDENT'})
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    report={'experiment':'EXPLORATORY_SYNTHETIC_ONLY','split':'chronological_by_hour_across_services','last_training_hour':boundary,'training_windows':len(train),'test_windows':len(test),'flagged_test_windows':len(flagged),'flagged':sorted(flagged,key=lambda x:(x['hour_utc'],x['service'])),'limitations':['Not a validated incident classifier','Unlabeled anomaly scores; no precision/recall claimed','Synthetic patterns are insufficient for production threshold selection']}
    out.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--metrics',required=True);p.add_argument('--out',required=True);a=p.parse_args();r=run(a.metrics,a.out);print({k:v for k,v in r.items() if k!='flagged'})
