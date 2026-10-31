"""Read-only analytics store built from redacted audit outputs (stdlib SQLite)."""
import argparse,csv,sqlite3
from contextlib import closing
from pathlib import Path
SCHEMA="""CREATE TABLE events (ingest_id TEXT PRIMARY KEY, event_time_utc TEXT, service TEXT, quality_status TEXT, reasons TEXT, message_redacted TEXT);
CREATE TABLE windows (service TEXT, hour_utc TEXT, count INTEGER, http_5xx INTEGER, error_rate REAL, p95_duration_ms REAL, PRIMARY KEY(service,hour_utc));
CREATE TABLE alerts (service TEXT, hour_utc TEXT, signal TEXT, error_rate REAL, evidence_events INTEGER, status TEXT, is_confirmed_incident INTEGER);
CREATE INDEX events_svc_ts ON events(service,event_time_utc);
CREATE VIEW quality_by_service AS SELECT service,quality_status,COUNT(*) AS count FROM events GROUP BY service,quality_status;
"""
def build(inputs, db):
    inputs=Path(inputs);db=Path(db);db.parent.mkdir(parents=True,exist_ok=True)
    if db.exists():db.unlink()
    with closing(sqlite3.connect(db)) as c, c:
        c.executescript(SCHEMA)
        with (inputs/'decisions.csv').open(newline='',encoding='utf-8') as f:
            rd=csv.DictReader(f)
            c.executemany('INSERT INTO events VALUES (?,?,?,?,?,?)',[(r['ingest_id'],r['event_time_utc'],r['service'],r['quality_status'],r['reasons'],r['message_redacted']) for r in rd])
        with (inputs/'window_metrics.csv').open(newline='',encoding='utf-8') as f:
            rd=csv.DictReader(f);c.executemany('INSERT INTO windows VALUES (?,?,?,?,?,?)',[(r['service'],r['hour_utc'],int(r['count']),int(r['http_5xx']),float(r['error_rate']),float(r['p95_duration_ms'])) for r in rd])
        with (inputs/'triage_alerts.csv').open(newline='',encoding='utf-8') as f:
            rd=csv.DictReader(f);c.executemany('INSERT INTO alerts VALUES (?,?,?,?,?,?,?)',[(r['service'],r['hour_utc'],r['signal'],float(r['error_rate']),int(r['evidence_events']),r['status'],0) for r in rd])
        n=c.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    return n
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--in-dir',required=True);p.add_argument('--db',required=True);a=p.parse_args();print(build(a.in_dir,a.db))
